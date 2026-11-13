import hashlib
import os
from pathlib import Path
from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models
from dotenv import load_dotenv

_BACKEND_DIRECTORY = Path(__file__).resolve().parent
load_dotenv(_BACKEND_DIRECTORY / ".env")

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "database_metadata")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
# Folder on disk where Qdrant data is persisted. Keep it outside any directory
# your dev reloader watches, and add it to .gitignore.
QDRANT_PATH = os.getenv("QDRANT_PATH", "./.qdrant_data")
if not os.path.isabs(QDRANT_PATH):
    QDRANT_PATH = str(_BACKEND_DIRECTORY / QDRANT_PATH)
_clients: dict[str, QdrantClient] = {}
_clients_lock = RLock()


class MetadataNotFoundError(Exception):
    """The connection has no metadata stored."""


def _connection_dir(connection_name: str) -> str:
    digest = hashlib.sha256(connection_name.encode("utf-8")).hexdigest()[:16]
    return os.path.join(QDRANT_PATH, digest)


def _get_client(connection_name: str, create: bool = False) -> QdrantClient | None:
    """Return the cached client, or reopen it from disk. Caller must hold _clients_lock."""
    client = _clients.get(connection_name)
    if client is not None:
        return client
    path = _connection_dir(connection_name)
    if not create and not os.path.isdir(path):
        return None
    client = QdrantClient(path=path)
    _clients[connection_name] = client
    return client


def _object_text(connection_name: str, database: str, schema: str, item: dict) -> str:
    columns = ", ".join(
        f"{column['name']} ({column['type']})"
        for column in item.get("columns", [])
    )
    relationships = []
    for foreign_key in item.get("foreign_keys", []):
        referenced_schema = foreign_key.get("referenced_schema")
        referenced_table = foreign_key.get("referenced_table")
        referenced_object = f"{referenced_schema}.{referenced_table}" if referenced_schema else referenced_table
        relationships.append(f"{', '.join(foreign_key['columns'])} references {referenced_object}")
    return (
        f"Connection {connection_name}, database {database}, schema {schema}. "
        f"{item['kind'].title()} {item['name']}. Columns: {columns or 'none'}. "
        f"Relationships: {'; '.join(relationships) or 'none'}. "
        f"View definition: {item.get('definition') or 'none'}."
    )


def _records(metadata: dict, source_id: str) -> tuple[list[str], list[dict], list[str]]:
    documents: list[str] = []
    payloads: list[dict] = []
    point_ids: list[str] = []

    for schema in metadata["schemas"]:
        schema_text = (
            f"Connection {metadata['connection_name']}, database {metadata['database']}, "
            f"schema {schema['name']}. This schema contains "
            f"{len(schema['objects'])} tables and views. Sequences: "
            f"{', '.join(schema['sequences']) or 'none'}."
        )
        schema_key = f"{source_id}:{schema['name']}:schema"
        documents.append(schema_text)
        payloads.append({
            "source_id": source_id,
            "connection_name": metadata["connection_name"],
            "database": metadata["database"],
            "provider": metadata["provider"],
            "dialect": metadata.get("dialect", metadata["provider"]),
            "schema": schema["name"],
            "metadata_type": "schema",
            "metadata": {"name": schema["name"], "sequences": schema["sequences"]},
        })
        point_ids.append(str(uuid5(NAMESPACE_URL, schema_key)))

        for item in schema["objects"]:
            item_key = f"{source_id}:{schema['name']}:{item['kind']}:{item['name']}"
            documents.append(_object_text(metadata["connection_name"], metadata["database"], schema["name"], item))
            payloads.append({
                "source_id": source_id,
                "connection_name": metadata["connection_name"],
                "database": metadata["database"],
                "provider": metadata["provider"],
                "dialect": metadata.get("dialect", metadata["provider"]),
                "schema": schema["name"],
                "metadata_type": item["kind"],
                "object_name": item["name"],
                "metadata": item,
            })
            point_ids.append(str(uuid5(NAMESPACE_URL, item_key)))

    return documents, payloads, point_ids


def store_schema_metadata(metadata: dict, host: str, port: int) -> int:
    """Replace a connection's persisted metadata after a successful upload."""
    source_key = "|".join((metadata["connection_name"], metadata["provider"], host, str(port), metadata["database"]))
    source_id = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    documents, payloads, point_ids = _records(metadata, source_id)

    with _clients_lock:
        client = _get_client(metadata["connection_name"], create=True)

        # Replace, don't merge: drop whatever was stored before
        if client.collection_exists(COLLECTION_NAME):
            client.delete_collection(COLLECTION_NAME)
        if not documents:
            return 0

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=client.get_embedding_size(EMBEDDING_MODEL),
                distance=models.Distance.COSINE,
            ),
        )
        client.upload_collection(
            collection_name=COLLECTION_NAME,
            vectors=[models.Document(text=document, model=EMBEDDING_MODEL) for document in documents],
            payload=payloads,
            ids=point_ids,
            wait=True,
        )

    return len(point_ids)


def fetch_schema_metadata(connection_name: str) -> list[dict]:
    """Read all schema payloads from this connection's persisted Qdrant store"""
    with _clients_lock:
        client = _get_client(connection_name)
        if client is None or not client.collection_exists(COLLECTION_NAME):
            raise MetadataNotFoundError("Database metadata is unavailable. Connect the database again.")

        payloads = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            payloads.extend(point.payload for point in points if point.payload)
            if offset is None:
                break

    if not payloads:
        raise MetadataNotFoundError("Database metadata is unavailable. Connect the database again.")
    return sorted(payloads, key=lambda item: (item["schema"], item["metadata_type"], item.get("object_name", "")))
