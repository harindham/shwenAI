import re
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import URL, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.inspection import inspect
from sqlalchemy.pool import NullPool
from gemini_service import GeminiConfigurationError, GeminiServiceError, generate_response
from metadata_store import store_schema_metadata

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class DatabaseConnection(BaseModel):
    provider: Literal["postgresql", "supabase", "mysql", "mariadb", "other"]
    connection_name: str = Field(min_length=1, max_length=80)
    schema: str = Field(min_length=1, max_length=255)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1, max_length=255)
    username: str = Field(min_length=1, max_length=255)
    password: str = Field(max_length=2048)
    ssl_mode: Literal["require", "prefer", "disable"] = "require"
    dialect: str | None = Field(default=None, max_length=80)

    @field_validator("connection_name", "host", "database", "username")
    @classmethod
    def strip_required_connection_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required.")
        return value

    @field_validator("schema")
    @classmethod
    def strip_schema(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Schema is required.")
        return value


class ChatMessage(BaseModel):
    connection_name: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("connection_name", "message")
    @classmethod
    def strip_chat_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field is required.")
        return value

@app.exception_handler(RequestValidationError)
async def safe_validation_error(request: Request, exc: RequestValidationError):
    # Validation responses should never echo submitted credentials.
    errors = [{"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "pg_toast",
    "mysql",
    "performance_schema",
    "sys",
}


def _metadata_for_table(inspector, name: str, schema: str | None, kind: str):
    columns = inspector.get_columns(name, schema=schema)
    primary_key = inspector.get_pk_constraint(name, schema=schema) if kind == "table" else {}
    foreign_keys = inspector.get_foreign_keys(name, schema=schema) if kind == "table" else []
    indexes = inspector.get_indexes(name, schema=schema) if kind == "table" else []
    unique_constraints = inspector.get_unique_constraints(name, schema=schema) if kind == "table" else []
    check_constraints = inspector.get_check_constraints(name, schema=schema) if kind == "table" else []

    result = {
        "name": name,
        "kind": kind,
        "columns": [
            {
                "name": column["name"],
                "type": str(column["type"]),
                "nullable": column.get("nullable"),
                "default": str(column["default"]) if column.get("default") is not None else None,
                "comment": column.get("comment"),
            }
            for column in columns
        ],
        "primary_key": primary_key.get("constrained_columns") or [],
        "foreign_keys": [
            {
                "name": key.get("name"),
                "columns": key.get("constrained_columns") or [],
                "referenced_schema": key.get("referred_schema"),
                "referenced_table": key.get("referred_table"),
                "referenced_columns": key.get("referred_columns") or [],
            }
            for key in foreign_keys
        ],
        "indexes": [
            {
                "name": index.get("name"),
                "columns": index.get("column_names") or [],
                "unique": index.get("unique", False),
            }
            for index in indexes
        ],
        "unique_constraints": [
            {"name": item.get("name"), "columns": item.get("column_names") or []}
            for item in unique_constraints
        ],
        "check_constraints": [
            {"name": item.get("name"), "sql": item.get("sqltext")}
            for item in check_constraints
        ],
    }
    if kind == "view":
        result["definition"] = inspector.get_view_definition(name, schema=schema)
    return result


@app.post("/api/database/connect")
def connect_database(details: DatabaseConnection):
    """Connect once, introspect schema metadata, and close the connection."""
    provider_to_driver = {
        "postgresql": "postgresql+psycopg",
        "supabase": "postgresql+psycopg",
        "mysql": "mysql+pymysql",
        "mariadb": "mysql+pymysql",
    }
    driver = provider_to_driver.get(details.provider)
    if details.provider == "other":
        if not details.dialect or not re.fullmatch(r"[A-Za-z0-9_]+(?:\+[A-Za-z0-9_]+)?", details.dialect):
            raise HTTPException(status_code=422, detail="Enter a valid SQLAlchemy dialect, such as mssql+pyodbc.")
        driver = details.dialect

    url = URL.create(
        driver,
        username=details.username,
        password=details.password,
        host=details.host.strip(),
        port=details.port,
        database=details.database,
    )
    # MySQL and MariaDB use “schema” and “database” synonymously.
    selected_schema = details.database if details.provider in ("mysql", "mariadb") else details.schema
    if selected_schema.lower() in SYSTEM_SCHEMAS:
        raise HTTPException(status_code=400, detail="Choose an application schema.")
    connect_args = {}
    if details.provider in ("postgresql", "supabase"):
        connect_args = {"connect_timeout": 8, "sslmode": details.ssl_mode}
    elif details.provider in ("mysql", "mariadb"):
        connect_args = {"connect_timeout": 8}
        if details.ssl_mode == "disable":
            connect_args["ssl_disabled"] = True
        elif details.ssl_mode == "require":
            connect_args["ssl_verify_cert"] = False

    engine = None
    try:
        engine = create_engine(url, poolclass=NullPool, connect_args=connect_args)
        with engine.connect() as connection:
            database_inspector = inspect(connection)
            table_names = database_inspector.get_table_names(schema=selected_schema)
            view_names = database_inspector.get_view_names(schema=selected_schema)
            try:
                sequence_names = database_inspector.get_sequence_names(schema=selected_schema)
            except NotImplementedError:
                sequence_names = []
            if engine.dialect.name == "sqlite":
                table_names = [name for name in table_names if not name.startswith("sqlite_")]
                view_names = [name for name in view_names if not name.startswith("sqlite_")]
            objects = [
                _metadata_for_table(database_inspector, name, selected_schema, "table")
                for name in table_names
            ]
            objects.extend(
                _metadata_for_table(database_inspector, name, selected_schema, "view")
                for name in view_names
            )
            schemas = [{"name": selected_schema, "sequences": sequence_names, "objects": objects}]

            object_count = len(objects)
            column_count = sum(
                len(database_object["columns"])
                for database_object in objects
            )
            metadata_result = {
                "connected": True,
                "provider": details.provider,
                "database": details.database,
                "schema": selected_schema,
                "connection_name": details.connection_name,
                "summary": {
                    "schemas": len(schemas),
                    "tables_and_views": object_count,
                    "columns": column_count,
                },
                "schemas": schemas,
            }
            try:
                metadata_result["stored_metadata_items"] = store_schema_metadata(
                    metadata_result,
                    details.host,
                    details.port,
                )
            except Exception:
                raise HTTPException(
                    status_code=503,
                    detail="Metadata was fetched but could not be saved to Qdrant. Check that Qdrant is running and configured.",
                ) from None
            return metadata_result
    except (SQLAlchemyError, ImportError):
        # Driver errors may include host, username, or other connection details.
        raise HTTPException(
            status_code=400,
            detail="Could not connect or read database metadata. Check the connection details, driver, and permissions.",
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


@app.post("/api/chat/message")
def receive_chat_message(chat_message: ChatMessage):
    """Send a message to Gemini and return its response."""
    try:
        return {"response": generate_response(chat_message.message)}
    except GeminiConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from None
    except GeminiServiceError:
        raise HTTPException(status_code=502, detail="Could not get a response from Gemini.") from None


@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}


@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}
