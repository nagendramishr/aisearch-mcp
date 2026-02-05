# Azure AI Search MCP Server

An MCP (Model Context Protocol) server that exposes Azure AI Search functionality as tools for AI assistants.

## Features

- **Full-text search** - Search documents using Azure AI Search
- **Semantic/vector search** - Perform semantic search with reranking
- **Index management** - List indexes and get schema information
- **Document retrieval** - Get documents by key or count documents

## Available Tools

| Tool | Description |
|------|-------------|
| `search` | Full-text search with filters and field selection |
| `vector_search` | Semantic search with reranking scores |
| `list_indexes` | List all available search indexes |
| `get_index_schema` | Get fields and schema of an index |
| `get_document` | Retrieve a specific document by key |
| `get_document_count` | Count documents in an index |

## Setup

### Prerequisites

- Python 3.10+
- Azure AI Search service
- Azure Search API key or Azure credentials

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd aisearch-mcp
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your Azure Search credentials
   ```

### Configuration

Set the following environment variables in your `.env` file:

| Variable | Description | Required |
|----------|-------------|----------|
| `AZURE_SEARCH_ENDPOINT` | Azure Search service URL (e.g., `https://mysearch.search.windows.net`) | Yes |
| `AZURE_SEARCH_API_KEY` | Azure Search admin or query key | Yes* |
| `AZURE_SEARCH_INDEX` | Default search index name | Yes |
| `MCP_PORT` | Server port (default: 9000) | No |

*If not provided, the server will use `DefaultAzureCredential` for authentication.

## Running the Server

### Local

```bash
python server.py
```

The server will start on `http://0.0.0.0:9000` with the following endpoints:

- **SSE Transport**: `GET /sse` (establish connection), `POST /messages` (send messages)
- **Streamable HTTP**: `POST /mcp`

### Docker

Build and run with Docker:

```bash
# Build the image
docker build -t azure-search-mcp .

# Run with environment variables
docker run -p 9000:9000 \
  -e AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net \
  -e AZURE_SEARCH_API_KEY=your-api-key \
  -e AZURE_SEARCH_INDEX=your-index \
  azure-search-mcp

# Or run with .env file
docker run -p 9000:9000 --env-file .env azure-search-mcp
```

## Connecting MCP Clients

### VS Code / Claude Desktop (SSE)

Add to your MCP configuration:

```json
{
  "mcpServers": {
    "azure-search": {
      "url": "http://localhost:9000/sse"
    }
  }
}
```

### Streamable HTTP Clients

```json
{
  "mcpServers": {
    "azure-search": {
      "url": "http://localhost:9000/mcp"
    }
  }
}
```

### Stdio (Local Process)

For clients that support stdio transport, run directly:

```json
{
  "mcpServers": {
    "azure-search": {
      "command": "python",
      "args": ["/path/to/server.py"]
    }
  }
}
```

## Example Usage

Once connected, you can use the tools through your MCP client:

- **Search for hotels**: "Search for hotels with pool in Seattle"
- **Get index schema**: "What fields are in the hotels-sample-index?"
- **Count documents**: "How many documents are in the index?"

## License

MIT
