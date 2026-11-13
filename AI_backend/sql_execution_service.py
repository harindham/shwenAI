"""Execute generated queries using connection settings saved locally on disk."""

import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from uuid import UUID

import sqlparse
from sqlparse import tokens
from sqlalchemy import URL, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool
from sqlalchemy import text

import logging

logger = logging.getLogger(__name__)

MAX_RESULT_ROWS = 1000
SQL_CONNECTIONS_PATH = Path(__file__).resolve().parent / ".sql_connections"
_connections: dict[str, tuple[URL, dict, str]] = {}
_connections_lock = RLock()


class SQLConnectionNotFoundError(Exception):
    pass


class SQLExecutionError(Exception):
    pass


class SQLConnectionStorageError(Exception):
    pass


def _connection_file(connection_name: str) -> Path:
    digest = hashlib.sha256(connection_name.encode("utf-8")).hexdigest()
    return SQL_CONNECTIONS_PATH / f"{digest}.json"


def list_saved_connections() -> list[str]:
    """Return connection names from saved settings without exposing credentials."""
    names = []
    try:
        files = SQL_CONNECTIONS_PATH.glob("*.json")
        for file_path in files:
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            name = data.get("connection_name") if isinstance(data, dict) else None
            if isinstance(name, str) and name.strip() and _connection_file(name) == file_path:
                names.append(name)
    except OSError as error:
        raise SQLConnectionStorageError("Could not read saved database connections.") from error
    return sorted(set(names), key=str.casefold)


def register_connection(connection_name: str, url: URL, connect_args: dict, schema: str) -> None:
    """Atomically save credentials in an owner-only file, then update the cache."""
    with _connections_lock:
        temporary_path = None
        try:
            SQL_CONNECTIONS_PATH.mkdir(mode=0o700, parents=True, exist_ok=True)
            SQL_CONNECTIONS_PATH.chmod(0o700)
            data = {
                "connection_name": connection_name,
                "url": url.render_as_string(hide_password=False),
                "connect_args": connect_args,
                "schema": schema,
            }
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=SQL_CONNECTIONS_PATH, delete=False) as file:
                temporary_path = Path(file.name)
                os.fchmod(file.fileno(), 0o600)
                json.dump(data, file)
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(_connection_file(connection_name))
        except (OSError, TypeError, ValueError):
            raise SQLConnectionStorageError("Could not save database connection settings. Check local storage permissions and connect again.") from None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
        _connections[connection_name] = (url, dict(connect_args), schema)


def _get_connection(connection_name: str) -> tuple[URL, dict, str]:
    """Restore saved settings on the first query after a backend restart."""
    with _connections_lock:
        settings = _connections.get(connection_name)
        if settings is not None:
            return settings
        try:
            data = json.loads(_connection_file(connection_name).read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or data.get("connection_name") != connection_name
                or not isinstance(data.get("url"), str)
                or not isinstance(data.get("connect_args"), dict)
                or not isinstance(data.get("schema"), str)
            ):
                raise ValueError("Invalid connection settings")
            settings = (make_url(data["url"]), data["connect_args"], data["schema"])
        except FileNotFoundError:
            raise SQLConnectionNotFoundError("Database connection is unavailable. Connect the database again to save its settings.") from None
        except (OSError, ValueError, TypeError, SQLAlchemyError):
            raise SQLConnectionStorageError("Could not read saved database connection settings. Connect the database again.") from None
        _connections[connection_name] = settings
        return settings


def validate_query(query: str) -> str:
    """Accept a single SELECT, including CTEs; the database also enforces read-only mode."""
    statements = sqlparse.parse(query.strip())
    if len(statements) != 1 or statements[0].get_type() != "SELECT":
        raise SQLExecutionError("Only a single read-only SELECT query can be executed.")
    for token in statements[0].flatten():
        if (
            token.ttype in tokens.Comment
            or token.ttype in tokens.Keyword.DDL
            or (token.ttype in tokens.Keyword.DML and token.normalized != "SELECT")
            or (token.ttype in tokens.Keyword and token.normalized in {"INTO", "OUTFILE", "DUMPFILE"})
        ):
            raise SQLExecutionError("The generated SQL contains an unsupported operation.")
    return query.strip()


def _json_value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return str(value)


def execute_query(connection_name: str, query: str) -> dict:
    """Run generated SQL, log the returned rows, and return a JSON-safe result."""
    query = validate_query(query)
    url, connect_args, schema = _get_connection(connection_name)
    engine = None
    try:
        engine = create_engine(url, connect_args=connect_args, poolclass=NullPool)
        if engine.dialect.name not in {"postgresql", "mysql", "mariadb", "sqlite"}:
            raise SQLExecutionError("Query execution is not supported for this database dialect yet.")
        with engine.connect() as connection:
            if engine.dialect.name == "postgresql":
                connection.exec_driver_sql("SET TRANSACTION READ ONLY")
                connection.exec_driver_sql("SET LOCAL statement_timeout = 30000")
                quoted_schema = engine.dialect.identifier_preparer.quote_schema(schema)
                connection.exec_driver_sql(f"SET LOCAL search_path TO {quoted_schema}")
            elif engine.dialect.name in {"mysql", "mariadb"}:
                if getattr(engine.dialect, "is_mariadb", False):
                    connection.exec_driver_sql("SET SESSION max_statement_time = 30")
                else:
                    connection.exec_driver_sql("SET SESSION max_execution_time = 30000")
                connection.exec_driver_sql("START TRANSACTION READ ONLY")
            else:
                connection.exec_driver_sql("PRAGMA query_only = ON")

            with connection.execution_options(stream_results=True).execute(text(query)) as result:
                if not result.returns_rows:
                    raise SQLExecutionError("The generated query did not return rows.")
                columns = list(result.keys())
                rows = result.fetchmany(MAX_RESULT_ROWS + 1)
                output = {
                    "query": query,
                    "columns": columns,
                    "rows": [[_json_value(value) for value in row] for row in rows[:MAX_RESULT_ROWS]],
                    "row_count": min(len(rows), MAX_RESULT_ROWS),
                    "truncated": len(rows) > MAX_RESULT_ROWS,
                }
            # No commit: leaving the connection context rolls back the read-only transaction.
    except (SQLAlchemyError, ImportError) as exc:
        logger.exception("SQL execution failed: %s", exc)
        raise SQLExecutionError("Could not execute the generated SQL. Check the query, connection, and database permissions.") from None
    finally:
        if engine is not None:
            engine.dispose()

    print(f"[sql-result] {json.dumps(output, ensure_ascii=False)}", file=sys.stderr, flush=True)
    return output
