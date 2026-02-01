# Protea Presentation Materials

## Overview

This folder contains presentation materials for the Protea Home Inventory System.

## Files

| File | Content |
|------|---------|
| `01-architecture-diagram.md` | System architecture with Mermaid diagrams |
| `02-mcp-tools-overview.md` | MCP tools catalog organized by category |
| `03-use-case-1-import-items.md` | Phone → Photos → Claude Desktop workflow |
| `04-use-case-2-find-items.md` | Web/phone search workflow |
| `05-use-case-3-where-to-put.md` | AI-assisted storage recommendations |
| `06-use-case-4-organize.md` | Bin reorganization with Claude |
| `07-screenshot-checklist.md` | Screenshots needed for presentation |

## Using the Diagrams

### Mermaid Diagrams
All diagrams use Mermaid syntax. To render them:

1. **Mermaid Live Editor**: https://mermaid.live
   - Paste code, export as PNG/SVG

2. **VS Code Extension**: "Mermaid Preview"
   - Preview in editor, export images

3. **GitHub/GitLab**: Native Mermaid support in markdown

4. **Presentation Tools**:
   - Notion: Native Mermaid support
   - Obsidian: Native Mermaid support
   - Google Slides: Export images from mermaid.live

### Recommended Export Settings
- Format: PNG or SVG
- Background: Transparent or white
- Theme: Default or neutral

## Presentation Structure Suggestion

```
1. Introduction (2 min)
   - What is Protea?
   - Problem it solves

2. Architecture Overview (3 min)
   - System diagram
   - Components explanation

3. MCP Tools (2 min)
   - Tool categories
   - How Claude uses them

4. Use Cases (10 min, ~2.5 min each)
   - Use Case 1: Import Items
   - Use Case 2: Find Items
   - Use Case 3: Where to Put
   - Use Case 4: Organize

5. Demo (5 min)
   - Live demonstration

6. Q&A (3 min)
```

## Key Messages

### For Technical Audience
- MCP-first architecture enables AI integration
- SQLite + FTS5 + Vector embeddings for hybrid search
- Session-based workflow for batch operations
- FastAPI web UI with HTMX for responsive interface

### For General Audience
- Take photos → AI catalogs items automatically
- Natural language search finds anything
- AI suggests where to put new items
- Ask Claude to help organize your storage

## Project Links

- **GitHub**: https://github.com/rmaxseiner/protea
- **Docker Image**: ghcr.io/rmaxseiner/protea:latest
