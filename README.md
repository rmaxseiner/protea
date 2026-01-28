# Protea Inventory System

> MCP-powered inventory management for makers, homelabbers, and tinkerers

Protea is a physical inventory management system built on the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). Manage your workshop, lab, or home inventory through natural language conversations with Claude or any MCP-compatible AI assistant, or use the included web UI.

## Features

- **MCP-Native Architecture** - Built from the ground up for AI assistant integration
- **Natural Language Interface** - "Add these resistors to my electronics bin" + photo
- **Vision Extraction** - Identify items from photos using Claude's vision capabilities
- **Web UI** - Mobile-friendly interface for browsing, searching, and quick edits
- **Hierarchical Organization** - Locations → Bins → Items (with nested sub-bins)
- **Full-Text Search** - Find anything instantly with SQLite FTS5
- **Image Attachments** - Photo your bins and items for visual reference
- **Session Workflow** - Review and edit extracted items before committing
- **Activity History** - Track when items were added, moved, or used
- **Self-Hosted** - Your data stays on your hardware

## Quick Start

### Docker (Recommended)

```bash
# Create data directory
mkdir -p data/db data/images

# Run with Docker Compose
docker compose up -d

# Access web UI at http://localhost:8080
```

### Local Development

```bash
# Clone the repository
git clone https://github.com/rmaxseiner/protea.git
cd protea

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"

# Run the web UI
protea-web
```

## MCP Integration

### Claude Desktop

Add to your Claude Desktop configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "protea": {
      "command": "protea",
      "env": {
        "INVENTORY_DATABASE_PATH": "/path/to/data/inventory.db",
        "INVENTORY_IMAGE_BASE_PATH": "/path/to/data/images"
      }
    }
  }
}
```

Or with Docker:

```json
{
  "mcpServers": {
    "protea": {
      "command": "docker",
      "args": ["exec", "-i", "protea-web", "protea"]
    }
  }
}
```

### Example Conversations

**Adding items with a photo:**
> "Add these to my hardware bin" + [photo of screws]
>
> Claude: "I see M3 socket head screws (~50), M4 hex nuts (~30), and assorted washers. Add these to Hardware Bin in Garage?"

**Finding items:**
> "Do I have any M3 screws?"
>
> Claude: "Yes, you have M3 socket head cap screws (~50) in Hardware Bin, Garage."

**Inventory queries:**
> "What tape do I have?"
>
> Claude: "You have 3 types of tape: Masking tape in Garage/Workbench, Electrical tape in Electronics Bin, and Scotch tape in Office/Desk Drawer."

## Web UI

The web interface provides:

- **Browse** - Navigate locations and bins hierarchically
- **Search** - Full-text search across all items
- **Quick Add** - Fast item entry from any device
- **Item Details** - View and edit items with images
- **History** - Activity feed of recent changes

Access at `http://localhost:8080` after starting the server.

## Configuration

Configure via environment variables (prefix: `INVENTORY_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `INVENTORY_DATABASE_PATH` | `data/inventory.db` | SQLite database location |
| `INVENTORY_IMAGE_BASE_PATH` | `data/images` | Image storage directory |
| `INVENTORY_WEB_HOST` | `0.0.0.0` | Web server bind address |
| `INVENTORY_WEB_PORT` | `8080` | Web server port |
| `INVENTORY_CLAUDE_API_KEY` | - | Optional: Enable direct vision extraction |

## Architecture

```
┌─────────────────┐     ┌─────────────────┐
│  Claude/AI      │     │   Web Browser   │
│  Assistant      │     │                 │
└────────┬────────┘     └────────┬────────┘
         │ MCP                   │ HTTP
         ▼                       ▼
┌─────────────────────────────────────────┐
│           Protea Server                  │
├─────────────────────────────────────────┤
│  MCP Handler  │  FastAPI Web Routes     │
├─────────────────────────────────────────┤
│           Business Logic                 │
├─────────────────────────────────────────┤
│           SQLite + FTS5                  │
└─────────────────────────────────────────┘
```

## MCP Tools

Protea exposes these tools to MCP clients:

| Category | Tools |
|----------|-------|
| **Locations** | `get_locations`, `create_location`, `update_location`, `delete_location` |
| **Bins** | `get_bins`, `get_bin`, `create_bin`, `update_bin`, `delete_bin` |
| **Items** | `add_item`, `get_item`, `update_item`, `remove_item`, `move_item`, `use_item` |
| **Search** | `search_items`, `find_item`, `list_items`, `get_item_history` |
| **Sessions** | `create_session`, `add_image_to_session`, `commit_session`, `cancel_session` |
| **Categories** | `get_categories`, `create_category`, `update_category`, `delete_category` |

See [docs/protea-spec.md](docs/protea-spec.md) for complete tool documentation.

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=protea

# Lint
ruff check src/

# Format
ruff format src/
```

## Project Structure

```
protea/
├── src/protea/
│   ├── server.py          # MCP server entry point
│   ├── config.py          # Configuration
│   ├── db/                # Database layer
│   ├── tools/             # MCP tool implementations
│   ├── services/          # Business logic services
│   └── web/               # FastAPI web application
├── tests/                 # pytest test suite
├── docs/                  # Documentation
└── docker-compose.yml     # Docker deployment
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- Built with the [Model Context Protocol](https://modelcontextprotocol.io/) by Anthropic
- Named after the Protea flower, native to South Africa - resilient, adaptable, and unique
