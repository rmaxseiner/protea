# Screenshot Checklist for Presentation

Use this checklist to capture all screenshots needed for the presentation.

## General Setup

Before capturing screenshots:
- [ ] Ensure inventory has sample data
- [ ] Have Claude Desktop configured with Protea MCP
- [ ] Web app running at localhost:8080
- [ ] Clean browser (no personal bookmarks visible)
- [ ] Mobile device or emulator ready

---

## Architecture Section

No screenshots needed - uses Mermaid diagrams.

---

## Use Case 1: Import Items

### Phone Screenshots
- [ ] **1.1** Camera viewfinder showing a bin
- [ ] **1.2** Photo of bin with label visible
- [ ] **1.3** Photo of bin contents (items clearly visible)
- [ ] **1.4** Camera roll showing multiple bin photos

### Transfer Screenshots
- [ ] **1.5** Phone showing photo sharing/transfer options
- [ ] **1.6** Computer file browser with downloaded photos

### Claude Desktop Screenshots
- [ ] **1.7** Claude Desktop: Starting a new session
  - Show: User message asking to catalog a bin
  - Show: Claude's response creating session

- [ ] **1.8** Claude Desktop: Sharing photos
  - Show: Photo attachment in conversation
  - Show: Claude acknowledging receipt

- [ ] **1.9** Claude Desktop: Vision extraction results
  - Show: Claude listing extracted items
  - Show: Item names, quantities, categories

- [ ] **1.10** Claude Desktop: Correction conversation
  - Show: User correcting an item ("that's not a flathead, it's Robertson")
  - Show: Claude confirming the update

- [ ] **1.11** Claude Desktop: Commit confirmation
  - Show: User saying "save these"
  - Show: Claude's success message with item count

### Web UI Verification
- [ ] **1.12** Web UI: Bin view showing newly added items

---

## Use Case 2: Find Items

### Web UI Desktop Screenshots
- [ ] **2.1** Home page with search box (Google-style clean)
- [ ] **2.2** Typing a search query
- [ ] **2.3** Search results showing multiple items with location paths
- [ ] **2.4** Item detail page with full location breadcrumb
- [ ] **2.5** Empty search results ("No items found")

### Web UI Mobile Screenshots
- [ ] **2.6** Mobile home page (responsive search interface)
- [ ] **2.7** Mobile search results (compact cards)
- [ ] **2.8** Mobile item detail

---

## Use Case 3: Where to Put Item

### Claude Desktop Screenshots
- [ ] **3.1** User asking where to put an item
  - Show: "I have a new [item]. Where should I put it?"

- [ ] **3.2** Claude searching inventory
  - Show: Claude's message about searching
  - (Optional: Show tool calls if visible in UI)

- [ ] **3.3** Claude's recommendation
  - Show: Primary bin suggestion
  - Show: Reasoning explanation
  - Show: Alternative options

- [ ] **3.4** User accepting and adding to inventory
  - Show: User confirmation
  - Show: Claude's success message

### Web UI Verification
- [ ] **3.5** Web UI: Suggested bin showing related items
- [ ] **3.6** Web UI: Newly added item in the bin

---

## Use Case 4: Organize Bins

### Claude Desktop Screenshots
- [ ] **4.1** User requesting organization help
  - Show: "Help me organize these bins..."

- [ ] **4.2** Claude's current state analysis
  - Show: List of bins being analyzed
  - Show: Item counts and current mess description

- [ ] **4.3** Claude's reorganization proposal
  - Show: Proposed new organization
  - Show: Item distribution per bin
  - Show: "Should I proceed?" question

- [ ] **4.4** User providing feedback/modifications
  - Show: User adjustment request
  - Show: Claude acknowledging modification

- [ ] **4.5** Claude executing reorganization
  - Show: Progress messages as items are moved
  - (Or: Summary of moves being made)

- [ ] **4.6** Completion summary
  - Show: Final counts per bin
  - Show: "All changes logged" confirmation

### Web UI Before/After
- [ ] **4.7** BEFORE: Bin view showing mixed/messy contents
- [ ] **4.8** AFTER: Same bin with organized contents
- [ ] **4.9** Activity log showing move operations

---

## Optional: Demo Screenshots

If doing a live demo, capture these as backup:
- [ ] **D.1** MCP server configuration in Claude Desktop
- [ ] **D.2** Docker containers running
- [ ] **D.3** Terminal showing server logs

---

## Screenshot Tips

### Clarity
- Use high resolution (retina if available)
- Crop to focus on relevant content
- Remove personal/sensitive information

### Consistency
- Use same browser for all web screenshots
- Use consistent window sizes
- Same zoom level throughout

### Annotations
- Consider adding arrows/highlights in presentation software
- Number sequence steps
- Add brief captions

### File Naming
Suggested format: `UC[case]-[step]-[description].png`

Examples:
- `UC1-07-claude-session-start.png`
- `UC2-03-search-results.png`
- `UC4-08-bin-after-reorg.png`

---

## Capture Order Suggestion

To minimize setup changes, capture in this order:

1. **Web UI desktop** (UC2: 2.1-2.5)
2. **Web UI mobile** (UC2: 2.6-2.8)
3. **Claude Desktop UC1** (1.7-1.11)
4. **Claude Desktop UC3** (3.1-3.4)
5. **Claude Desktop UC4** (4.1-4.6)
6. **Web UI verification** (1.12, 3.5-3.6, 4.7-4.9)
7. **Phone screenshots** (1.1-1.6)
