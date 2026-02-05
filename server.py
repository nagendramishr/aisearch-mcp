from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse, Response
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from mcp.types import Tool, TextContent
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.core.credentials import AzureKeyCredential
import os
import json
import logging
import uvicorn
from dotenv import load_dotenv

# Setup logging and load environment variables
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

# Azure AI Search configuration
AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")  # e.g., https://<service-name>.search.windows.net
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")    # Admin or Query key
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")        # Default index name
MCP_PORT = int(os.getenv("MCP_PORT", "9000"))

# Initialize the MCP server
server = Server("azure-search-mcp")

# SSE transport for SSE-based clients
sse_transport = SseServerTransport("/messages")

def get_credential():
    """Get Azure credential - uses API key if provided, otherwise DefaultAzureCredential."""
    if AZURE_SEARCH_API_KEY:
        return AzureKeyCredential(AZURE_SEARCH_API_KEY)
    return DefaultAzureCredential()

def get_search_client(index_name: str = None) -> SearchClient:
    """Get a SearchClient for the specified index."""
    return SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=index_name or AZURE_SEARCH_INDEX,
        credential=get_credential()
    )

def get_index_client() -> SearchIndexClient:
    """Get a SearchIndexClient for index management operations."""
    return SearchIndexClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        credential=get_credential()
    )

@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools exposed by this MCP server."""
    return [
        Tool(
            name="search",
            description="Search for documents in Azure AI Search index using full-text search",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query text"
                    },
                    "index_name": {
                        "type": "string",
                        "description": "Name of the search index (uses default if not specified)"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10)",
                        "default": 10
                    },
                    "select": {
                        "type": "string",
                        "description": "Comma-separated list of fields to return"
                    },
                    "filter": {
                        "type": "string",
                        "description": "OData filter expression"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="vector_search",
            description="Perform vector/semantic search on Azure AI Search index",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query text for semantic search"
                    },
                    "index_name": {
                        "type": "string",
                        "description": "Name of the search index (uses default if not specified)"
                    },
                    "top": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10)",
                        "default": 10
                    },
                    "select": {
                        "type": "string",
                        "description": "Comma-separated list of fields to return"
                    },
                    "semantic_configuration": {
                        "type": "string",
                        "description": "Name of the semantic configuration to use"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="list_indexes",
            description="List all available search indexes in the Azure AI Search service",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_index_schema",
            description="Get the schema/fields of a specific search index",
            inputSchema={
                "type": "object",
                "properties": {
                    "index_name": {
                        "type": "string",
                        "description": "Name of the search index"
                    }
                },
                "required": ["index_name"]
            }
        ),
        Tool(
            name="get_document",
            description="Retrieve a specific document by its key",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "The document key/ID"
                    },
                    "index_name": {
                        "type": "string",
                        "description": "Name of the search index (uses default if not specified)"
                    },
                    "select": {
                        "type": "string",
                        "description": "Comma-separated list of fields to return"
                    }
                },
                "required": ["key"]
            }
        ),
        Tool(
            name="get_document_count",
            description="Get the total number of documents in a search index",
            inputSchema={
                "type": "object",
                "properties": {
                    "index_name": {
                        "type": "string",
                        "description": "Name of the search index (uses default if not specified)"
                    }
                },
                "required": []
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls from MCP clients."""
    
    try:
        if name == "search":
            query = arguments.get("query")
            index_name = arguments.get("index_name")
            top = arguments.get("top", 10)
            select = arguments.get("select")
            filter_expr = arguments.get("filter")
            
            client = get_search_client(index_name)
            
            search_options = {"top": top}
            if select:
                search_options["select"] = select.split(",")
            if filter_expr:
                search_options["filter"] = filter_expr
            
            results = client.search(search_text=query, **search_options)
            
            documents = []
            for result in results:
                doc = {k: v for k, v in result.items() if not k.startswith("@")}
                doc["_score"] = result.get("@search.score")
                documents.append(doc)
            
            return [TextContent(
                type="text",
                text=json.dumps({"results": documents, "count": len(documents)}, indent=2, default=str)
            )]
        
        elif name == "vector_search":
            query = arguments.get("query")
            index_name = arguments.get("index_name")
            top = arguments.get("top", 10)
            select = arguments.get("select")
            semantic_config = arguments.get("semantic_configuration")
            
            client = get_search_client(index_name)
            
            search_options = {
                "top": top,
                "query_type": "semantic",
                "semantic_configuration_name": semantic_config or "default"
            }
            if select:
                search_options["select"] = select.split(",")
            
            results = client.search(search_text=query, **search_options)
            
            documents = []
            for result in results:
                doc = {k: v for k, v in result.items() if not k.startswith("@")}
                doc["_score"] = result.get("@search.score")
                doc["_reranker_score"] = result.get("@search.reranker_score")
                documents.append(doc)
            
            return [TextContent(
                type="text",
                text=json.dumps({"results": documents, "count": len(documents)}, indent=2, default=str)
            )]
        
        elif name == "list_indexes":
            client = get_index_client()
            indexes = client.list_indexes()
            
            index_list = []
            for index in indexes:
                index_list.append({
                    "name": index.name,
                    "fields_count": len(index.fields) if index.fields else 0
                })
            
            return [TextContent(
                type="text",
                text=json.dumps({"indexes": index_list}, indent=2)
            )]
        
        elif name == "get_index_schema":
            index_name = arguments.get("index_name")
            client = get_index_client()
            index = client.get_index(index_name)
            
            fields = []
            for field in index.fields:
                fields.append({
                    "name": field.name,
                    "type": str(field.type),
                    "searchable": field.searchable,
                    "filterable": field.filterable,
                    "sortable": field.sortable,
                    "facetable": field.facetable,
                    "key": field.key
                })
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "index_name": index.name,
                    "fields": fields,
                    "semantic_configurations": [sc.name for sc in (index.semantic_search.configurations if index.semantic_search else [])]
                }, indent=2)
            )]
        
        elif name == "get_document":
            key = arguments.get("key")
            index_name = arguments.get("index_name")
            select = arguments.get("select")
            
            client = get_search_client(index_name)
            
            selected_fields = select.split(",") if select else None
            document = client.get_document(key=key, selected_fields=selected_fields)
            
            return [TextContent(
                type="text",
                text=json.dumps(dict(document), indent=2, default=str)
            )]
        
        elif name == "get_document_count":
            index_name = arguments.get("index_name")
            client = get_search_client(index_name)
            count = client.get_document_count()
            
            return [TextContent(
                type="text",
                text=json.dumps({"index": index_name or AZURE_SEARCH_INDEX, "document_count": count}, indent=2)
            )]
        
        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, indent=2)
        )]

# SSE handlers
async def handle_sse(request):
    """Handle SSE connections from MCP clients (GET /sse)."""
    async with sse_transport.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )

async def handle_messages(request):
    """Handle POST messages from SSE clients (POST /messages)."""
    await sse_transport.handle_post_message(request.scope, request.receive, request._send)

def main():
    """Run the MCP server on HTTP port."""
    logger.info(f"Starting Azure AI Search MCP Server on http://0.0.0.0:{MCP_PORT}")
    logger.info(f"SSE endpoint: GET http://localhost:{MCP_PORT}/sse")
    logger.info(f"Messages endpoint: POST http://localhost:{MCP_PORT}/messages")
    logger.info(f"Streamable HTTP endpoint: POST http://localhost:{MCP_PORT}/mcp")
    
    # Streamable HTTP endpoint handler
    async def mcp_endpoint(request):
        transport = StreamableHTTPServerTransport(
            mcp_session_id=request.headers.get("mcp-session-id"),
            is_json_response_enabled=True
        )
        return await transport.handle_request(
            request.scope, request.receive, request._send,
            server, server.create_initialization_options()
        )
    
    app = Starlette(
        debug=True,
        middleware=[
            Middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_methods=["GET", "POST", "OPTIONS", "DELETE"],
                allow_headers=["*"],
                expose_headers=["mcp-session-id"],
            )
        ],
        routes=[
            # SSE transport (for Claude Desktop, etc.)
            Route("/sse", endpoint=handle_sse, methods=["GET"]),
            Route("/messages", endpoint=handle_messages, methods=["POST"]),
            # Streamable HTTP transport (for other clients)
            Route("/mcp", endpoint=mcp_endpoint, methods=["GET", "POST", "DELETE"]),
        ],
    )
    
    uvicorn.run(app, host="0.0.0.0", port=MCP_PORT)

if __name__ == "__main__":
    main()
