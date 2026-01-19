# Protea Web UI - Technical Specification

**Version:** 1.1
**Date:** January 13, 2026
**Status:** Design Complete

---

## Overview

A lightweight web interface for browsing, searching, and managing inventory items. Complements the existing MCP-based input workflow (Claude Desktop + vision extraction) by providing read/browse/search capabilities accessible from any device.

### Design Principles

1. **MCP for input, Web UI for output** - Photo-based item addition stays in Claude Desktop; web UI focuses on search, browse, and quick edits
2. **Mobile-first** - Primary use case is checking inventory from phone while away from computer
3. **Simple and fast** - No complex JavaScript frameworks; server-rendered pages with minimal JS for interactions
4. **Single data source** - Reads/writes same SQLite database as MCP server

---

## Visual Design

### Layout: Sidebar Navigation (Layout A)

Selected layout features:
- **Fixed left sidebar** with navigation, always visible on desktop
- **Mobile:** Hamburger menu reveals sidebar as overlay
- **Item detail:** Slide-in panel from right side
- **Search:** Prominent search bar in content header

Layout reference: `docs/layouts/layout-a-protea.html`

### Color Scheme: King Protea

Inspired by the South African King Protea flower - dusty rose/coral petals against rich forest green foliage with creamy white center.

**Feel:** Organic, elegant, natural, warm

#### Color Palette

| Role | Name | Hex | Usage |
|------|------|-----|-------|
| **Sidebar Background** | Deep Forest | `#324032` | Main sidebar bg |
| **Sidebar Dark** | Deepest Green | `#2a352a` | Logo area, user section |
| **Nav Active** | Dusty Rose | `#a94f54` | Active navigation item |
| **Nav Text** | Sage Light | `#c9d7c9` | Inactive nav items |
| **Nav Hover** | Forest | `#3b4f3b` | Navigation hover state |
| **Content Background** | Warm Cream | `#f7f2e8` | Main content area |
| **Card Background** | Light Cream | `#fefcf8` | Cards, panels |
| **Card Border** | Deep Cream | `#e8dfc8` | Card borders |
| **Primary Button** | Rose | `#a94f54` | Primary actions |
| **Secondary Button** | Sage | `#c9d7c9` | Secondary actions |
| **Text Primary** | Forest Dark | `#2a352a` | Headings, important text |
| **Text Secondary** | Forest Muted | `#5c7a5c` | Secondary text, labels |
| **Text Light** | Forest Light | `#7a967a` | Placeholder, hints |
| **High Match** | Rose | `#c96b6b` | 80%+ search match |
| **Medium Match** | Forest Sage | `#7a967a` | 60-79% search match |
| **Low Match** | Sage Light | `#a3b9a3` | Below 60% match |
| **Success** | Forest Green | `#5c7a5c` | Success states |
| **Warning** | Coral | `#dc8f8f` | Warning states |
| **Error** | Deep Coral | `#a94f54` | Error states |

#### Extended Palette (Tailwind)

```
protea (rose/coral tones):
  50:  #fdf5f5   - Palest pink
  100: #fae8e8   - Light blush
  200: #f5d0d0   - Soft rose
  300: #ebb5b5   - Dusty rose
  400: #dc8f8f   - Coral pink
  500: #c96b6b   - Rose
  600: #a94f54   - Deep coral (PRIMARY)
  700: #8d3f43   - Burgundy rose
  800: #753538   - Dark burgundy
  900: #632f31   - Deep burgundy
  950: #351617   - Darkest burgundy

fynbos (forest green tones):
  50:  #f4f7f4   - Palest green
  100: #e4ebe4   - Light sage
  200: #c9d7c9   - Soft green
  300: #a3b9a3   - Sage
  400: #7a967a   - Forest sage
  500: #5c7a5c   - Forest green
  600: #486248   - Deep forest
  700: #3b4f3b   - Dark forest
  800: #324032   - Very dark green (SIDEBAR)
  900: #2a352a   - Deepest green
  950: #151c15   - Near black green

cream (warm neutral tones):
  light:   #fefcf8   - Lightest cream (CARDS)
  DEFAULT: #f7f2e8   - Warm cream (CONTENT BG)
  dark:    #e8dfc8   - Deep cream (BORDERS)
```

---

## User Scenarios

### 1. Search Page (Primary View)
**Use case:** "Do I have this? Where is it?"

- Single search box (Google-style homepage)
- Fuzzy matching against:
  - Item names
  - Item aliases
  - Item descriptions
  - Bin names
- Results ranked by match quality (best first)
- Each result displays:
  - Item name + quantity (with quantity type indicator)
  - Location → Bin breadcrumb path
  - Thumbnail of source photo (if available, clickable to expand)
  - Category tag
- Click result → Navigate to item detail with actions

**Wireframe:**
```
┌─────────────────────────────────────────┐
│  🔍 [Search inventory...           ]    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│ M3 Socket Head Screws         ~50 pcs   │
│ Garage → Hardware Bin                   │
│ [thumb]  Fasteners                      │
├─────────────────────────────────────────┤
│ M3 Nuts                       ~30 pcs   │
│ Garage → Hardware Bin                   │
│ [thumb]  Fasteners                      │
├─────────────────────────────────────────┤
│ M3 Standoffs                  12 pcs    │
│ Spare Bedroom → Computer Parts          │
│ [thumb]  Electronics                    │
└─────────────────────────────────────────┘
```

### 2. Room/Area Browser
**Use case:** "What's in this area? Should I add something here?"

- Hierarchical tree navigation: Location → Bins → Items
- Expandable/collapsible nodes
- Location level shows:
  - Location name and description
  - Count of bins
  - Count of total items
- Bin level shows:
  - Bin name and description
  - Primary photo (if available)
  - Item count
  - Expandable item list
- "Add item" action available at bin level
- Click any item → Navigate to item detail

**Wireframe:**
```
┌─────────────────────────────────────────┐
│ 📍 Locations                            │
├─────────────────────────────────────────┤
│ ▼ Garage (3 bins, 47 items)             │
│   ├─ ▼ Hardware Bin (32 items)          │
│   │   │ [photo]                         │
│   │   ├─ M3 Socket Head Screws (~50)    │
│   │   ├─ M3 Nuts (~30)                  │
│   │   ├─ Assorted Washers               │
│   │   └─ ... 29 more                    │
│   │   [+ Add Item]                      │
│   ├─ ▶ Workbench Drawer (8 items)       │
│   └─ ▶ Tool Cabinet (7 items)           │
├─────────────────────────────────────────┤
│ ▶ Spare Bedroom (2 bins, 11 items)      │
├─────────────────────────────────────────┤
│ ▶ Office (1 bin, 5 items)               │
└─────────────────────────────────────────┘
```

### 3. Activity History
**Use case:** "What changed recently? When did I add that?"

- Chronological feed of inventory activity (newest first)
- Filters:
  - Action type: added, removed, moved, used, updated
  - Date range picker
  - Location/bin filter
  - User filter (when auth enabled)
- Each entry shows:
  - Timestamp (relative + absolute on hover)
  - Action icon and description
  - Item name with link
  - Location → Bin path
  - User who made change (when auth enabled)
  - Quantity change (if applicable)

**Wireframe:**
```
┌─────────────────────────────────────────┐
│ 📜 Activity History                     │
│ [All Actions ▼] [All Time ▼] [All ▼]   │
├─────────────────────────────────────────┤
│ 🕐 2 hours ago                          │
│ ➕ Added Arctic P12 120mm Fan (×2)      │
│    → Spare Bedroom / Computer Parts     │
│    by Ron                               │
├─────────────────────────────────────────┤
│ 🕐 2 hours ago                          │
│ ➕ Added 10GbE Network Card             │
│    → Spare Bedroom / Computer Parts     │
│    by Ron                               │
├─────────────────────────────────────────┤
│ 🕐 Yesterday                            │
│ 📦 Used M3 Screws (×4)                  │
│    → Garage / Hardware Bin              │
│    by Ron                               │
└─────────────────────────────────────────┘
```

### 4. Item Actions
**Use case:** "Quick inventory updates from any view"

Available actions when viewing any item:

| Action | Description |
|--------|-------------|
| **Add quantity** | Increment item count |
| **Use quantity** | Decrement with reason (used, consumed) |
| **Remove quantity** | Decrement with reason (lost, discarded, broken) |
| **Edit item** | Update name, description, category, notes |
| **Move item** | Relocate to different bin (full or partial quantity) |
| **Delete item** | Remove entirely from inventory |
| **Add new item** | Quick-add another item to same bin |

**Item Detail View Wireframe:**
```
┌─────────────────────────────────────────┐
│ ← Back                                  │
├─────────────────────────────────────────┤
│ Arctic P12 120mm Fan                    │
│ Quantity: 2                             │
│ Category: Electronics > Components      │
│ Location: Spare Bedroom → Computer Parts│
├─────────────────────────────────────────┤
│ [Photo from session]                    │
├─────────────────────────────────────────┤
│ Notes:                                  │
│ PWM fan, 120mm, black                   │
├─────────────────────────────────────────┤
│ Added: Jan 13, 2026 by Ron              │
│ Source: Vision extraction               │
├─────────────────────────────────────────┤
│ [+ Add] [- Use] [✏️ Edit] [↗️ Move]     │
└─────────────────────────────────────────┘
```

---

## Authentication

### Requirements
- **Optional** - Can be disabled for trusted home networks
- **Purpose** - Track who made changes (audit trail)
- **Simple** - No complex user management needed

### Implementation
- Basic username/password authentication
- Session-based (cookie)
- Users stored in database (simple table)
- Default admin user created on first run
- All write operations log the authenticated user

### User Model
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);
```

### Activity Log Enhancement
```sql
-- Add user tracking to activity_log
ALTER TABLE activity_log ADD COLUMN user_id TEXT REFERENCES users(id);
```

---

## Technical Architecture

### Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Web Framework | FastAPI | Async, fast, good OpenAPI support |
| Templates | Jinja2 | Server-rendered, simple, fast |
| CSS | Tailwind CSS (CDN) | Utility-first, responsive, no build step |
| JavaScript | Vanilla JS + htmx | Minimal JS, progressive enhancement |
| Database | SQLite (shared) | Same database as MCP server |
| Auth | Session cookies | Simple, secure enough for home use |

### Project Structure
```
src/protea/
├── web/
│   ├── __init__.py
│   ├── app.py              # FastAPI app setup
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── search.py       # Search page routes
│   │   ├── browse.py       # Room/area browser routes
│   │   ├── history.py      # Activity history routes
│   │   ├── items.py        # Item CRUD routes
│   │   └── auth.py         # Authentication routes
│   ├── templates/
│   │   ├── base.html       # Base template with nav
│   │   ├── search.html     # Search page
│   │   ├── browse.html     # Room browser
│   │   ├── history.html    # Activity feed
│   │   ├── item.html       # Item detail
│   │   ├── login.html      # Login form
│   │   └── partials/       # htmx partials
│   │       ├── search_results.html
│   │       ├── tree_node.html
│   │       └── activity_entry.html
│   └── static/
│       ├── app.css         # Custom styles
│       └── app.js          # Minimal JS helpers
```

### Deployment Architecture
```
┌──────────────────────────────────────────────────────┐
│                  Docker Container                     │
├──────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────┐       ┌─────────────────────┐   │
│  │   MCP Server    │       │      Web UI         │   │
│  │   (stdio)       │       │   (FastAPI :8080)   │   │
│  │                 │       │                     │   │
│  │ Claude Desktop  │       │  Browser/Phone      │   │
│  │ connects here   │       │  connects here      │   │
│  └────────┬────────┘       └──────────┬──────────┘   │
│           │                           │               │
│           └─────────────┬─────────────┘               │
│                         ▼                             │
│                 ┌───────────────┐                     │
│                 │    SQLite     │                     │
│                 │   Database    │                     │
│                 └───────────────┘                     │
│                         │                             │
│                 ┌───────────────┐                     │
│                 │    Images     │                     │
│                 │   Directory   │                     │
│                 └───────────────┘                     │
│                    (volumes)                          │
└──────────────────────────────────────────────────────┘
```

### Docker Compose
```yaml
version: '3.8'

services:
  inventory:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - inventory-data:/app/data
    environment:
      - INVENTORY_DATABASE_PATH=/app/data/inventory.db
      - INVENTORY_IMAGE_BASE_PATH=/app/data/images
      - INVENTORY_WEB_PORT=8080
      - INVENTORY_AUTH_ENABLED=true
      - INVENTORY_SECRET_KEY=${SECRET_KEY}

volumes:
  inventory-data:
```

---

## API Endpoints

### Pages (HTML)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Search homepage |
| GET | `/search?q=...` | Search results |
| GET | `/browse` | Room/area browser |
| GET | `/browse/{location_id}` | Location detail |
| GET | `/browse/{location_id}/{bin_id}` | Bin detail |
| GET | `/history` | Activity history |
| GET | `/item/{item_id}` | Item detail |
| GET | `/login` | Login form |
| POST | `/login` | Process login |
| POST | `/logout` | Logout |

### Actions (Form POST / htmx)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/item/{item_id}/add` | Add quantity |
| POST | `/item/{item_id}/use` | Use quantity |
| POST | `/item/{item_id}/remove` | Remove quantity |
| POST | `/item/{item_id}/edit` | Update item |
| POST | `/item/{item_id}/move` | Move to different bin |
| POST | `/item/{item_id}/delete` | Delete item |
| POST | `/bin/{bin_id}/add-item` | Add new item to bin |

### htmx Partials
| Method | Path | Description |
|--------|------|-------------|
| GET | `/partials/search?q=...` | Search results fragment |
| GET | `/partials/tree/{node_id}` | Tree expansion fragment |
| GET | `/partials/history?...` | Filtered history fragment |

---

## Configuration

### New Settings
```python
# src/protea/config.py (additions)

class Settings(BaseSettings):
    # ... existing settings ...

    # Web UI settings
    web_port: int = 8080
    web_host: str = "0.0.0.0"
    auth_enabled: bool = True
    secret_key: str = "change-me-in-production"
    session_expire_hours: int = 24 * 7  # 1 week

    class Config:
        env_prefix = "INVENTORY_"
```

---

## Database Migrations

### Migration 003: Add Users Table
```sql
-- migrations/003_add_users.sql

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Add user_id to activity_log for audit trail
ALTER TABLE activity_log ADD COLUMN user_id TEXT REFERENCES users(id);

-- Create index for user lookups
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_activity_log_user ON activity_log(user_id);

-- Insert schema version
INSERT INTO schema_version (version) VALUES (3);
```

---

## Implementation Phases

### Phase 1: Core Search (MVP)
- [ ] FastAPI app setup with Jinja2
- [ ] Base template with responsive nav
- [ ] Search page with FTS query
- [ ] Search results display with thumbnails
- [ ] Item detail view (read-only)
- [ ] Image serving endpoint

### Phase 2: Browse & Actions
- [ ] Room/area tree browser
- [ ] Expandable tree with htmx
- [ ] Item action forms (add/use/remove quantity)
- [ ] Edit item modal/page
- [ ] Move item functionality
- [ ] Add new item to bin

### Phase 3: History & Auth
- [ ] Activity history feed
- [ ] History filtering (date, action, location)
- [ ] User authentication
- [ ] Login/logout flow
- [ ] User tracking on actions
- [ ] Session management

### Phase 4: Containerization
- [ ] Dockerfile
- [ ] docker-compose.yml
- [ ] Volume configuration
- [ ] Environment variable handling
- [ ] Health check endpoint
- [ ] Documentation

---

## Future Considerations (Out of Scope)

These features are explicitly not in scope for v1 but noted for future:

1. **Photo upload via web** - Keep in Claude Desktop for now
2. **Vision extraction via web** - Requires API key management, keep in MCP
3. **Barcode scanning** - Could add camera-based scanning later
4. **Low stock alerts** - Notification system for running low
5. **Shopping lists** - Generate lists from low stock items
6. **Data export** - CSV/JSON export for backup
7. **Multi-household** - Separate inventories for different users

---

## Design Decisions Log

| Decision | Choice | Date |
|----------|--------|------|
| Authentication | Yes, for user tracking | Jan 13, 2026 |
| Photo upload via web | No, keep in Claude Desktop | Jan 13, 2026 |
| Layout | Sidebar Navigation (Layout A) | Jan 13, 2026 |
| Color Scheme | King Protea (forest green + dusty rose) | Jan 13, 2026 |

---

## Open Questions

1. ~~Authentication needed?~~ **Yes, for user tracking**
2. ~~Photo upload via web?~~ **No, keep in Claude Desktop**
3. ~~Layout style?~~ **Sidebar Navigation (Layout A)**
4. ~~Color scheme?~~ **King Protea**
5. **Offline support?** - Service worker for viewing cached data?
6. **Dark mode?** - Follow system preference? (Could invert to dark forest bg with cream accents)

---

*Specification created: January 13, 2026*
*Last updated: January 13, 2026 - Added visual design decisions*
