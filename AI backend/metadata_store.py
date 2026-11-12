import hashlib
import os
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "database_metadata")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"


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
                "schema": schema["name"],
                "metadata_type": item["kind"],
                "object_name": item["name"],
                "metadata": item,
            })
            point_ids.append(str(uuid5(NAMESPACE_URL, item_key)))

    return documents, payloads, point_ids


def store_schema_metadata(metadata: dict, host: str, port: int) -> int:
    """Embed selected-schema metadata in an ephemeral in-memory Qdrant; return point count."""
    source_key = "|".join((metadata["connection_name"], metadata["provider"], host, str(port), metadata["database"]))
    source_id = hashlib.sha256(source_key.encode("utf-8")).hexdigest()
    documents, payloads, point_ids = _records(metadata, source_id)

    if not documents:
        return 0

    client = QdrantClient(location=":memory:")
    try:
        if not client.collection_exists(COLLECTION_NAME):
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

        source_filter = models.Filter(
            must=[models.FieldCondition(key="source_id", match=models.MatchValue(value=source_id))]
        )
        existing_ids = []
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=COLLECTION_NAME,
                scroll_filter=source_filter,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            existing_ids.extend(point.id for point in points)
            if offset is None:
                break

        stale_ids = [point_id for point_id in existing_ids if point_id not in point_ids]
        if stale_ids:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=stale_ids),
                wait=True,
            )
    finally:
        client.close()

    return len(point_ids)
