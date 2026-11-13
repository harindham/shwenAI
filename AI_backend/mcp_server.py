"""MCP server entry point for shwenAI backend services."""

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
import logging

logger = logging.getLogger(__name__)


from metadata_store import MetadataNotFoundError, fetch_schema_metadata
from sql_execution_service import (
    SQLConnectionNotFoundError,
    SQLConnectionStorageError,
    SQLExecutionError,
    execute_query as execute_sql_query,
    list_saved_connections,
)

mcp = MCPServer("shwenAI")


@mcp.tool()
def select_connection(connection_name: str) -> dict:
    """Select a saved database connection before using Get_context or execute_query.

    If the name is not found, tell the user which saved names are available and
    ask them to enter another connection name, then call this tool again.
    """
    requested_name = connection_name.strip()
    try:
        available_names = list_saved_connections()
    except SQLConnectionStorageError as error:
        raise ToolError(str(error)) from None

    if requested_name in available_names:
        return {"found": True, "connection_name": requested_name}
    return {
        "found": False,
        "connection_name": None,
        "available_connections": available_names,
        "message": (
            f"Connection '{requested_name}' was not found. Ask the user to enter "
            "one of the available connection names, then call select_connection again."
            if available_names
            else "No saved connections were found. Ask the user to connect a database in shwenAI first."
        ),
    }


@mcp.tool()
def execute_query(connection_name: str, query: str) -> dict:
    """Execute one read-only SQL query on a saved connection.

    Returns the SQL, column names, rows, row count, and truncation flag.
    Use Get_context first to inspect the connection's schema and SQL dialect.
    """
    try:
        return execute_sql_query(connection_name.strip(), query)
    except (SQLConnectionNotFoundError, SQLConnectionStorageError, SQLExecutionError) as error:
        raise ToolError(str(error)) from None


@mcp.tool(name="Get_context")
def get_context(connection_name: str) -> dict:
    """Get stored database schema context for a saved connection from Qdrant.

    Includes database dialect, tables, views, columns, and relationships.
    Returns metadata only, not table rows or connection credentials.
    """
    try:
        records = fetch_schema_metadata(connection_name.strip())
    except MetadataNotFoundError as error:
        logger.exception(
            "Get_context failed for database: %s",
            connection_name
        )
        raise ToolError(str(error)) from None
    return {"connection_name": connection_name.strip(), "metadata": records}

if __name__ == "__main__":
    mcp.run(transport="stdio")
