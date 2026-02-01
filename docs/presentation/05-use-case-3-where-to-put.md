# Use Case 3: Where to Put Item

## Overview
Ask Claude where to store a new item based on existing inventory organization.

## Workflow Summary

```mermaid
flowchart LR
    A["🖥️ Claude Desktop:<br/>Describe Item"] --> B["🤖 Claude Analyzes<br/>Existing Bins"]
    B --> C["💡 Best Bin<br/>Suggested"]
    C --> D["📦 Put Item<br/>in Suggested Bin"]
```

---

## Workflow Detail

### Step 1: Describe Item to Claude

User describes the item they want to store, including relevant details.

```mermaid
sequenceDiagram
    participant User
    participant Claude as Claude Desktop

    User->>Claude: "I have a new soldering iron stand.<br/>Where should I put it?"
```

**What to include:**
- Item name/type
- Category hint (optional)
- Size considerations (optional)
- Related items (optional)

---

### Step 2: Claude Analyzes Inventory

Claude searches existing inventory to find where similar items are stored.

```mermaid
sequenceDiagram
    participant User
    participant Claude as Claude Desktop
    participant MCP as Protea MCP

    Claude->>MCP: search_items("soldering")
    MCP-->>Claude: Found: Soldering Iron, Solder Wire, Tips...
    Note over Claude: All in "Electronics Bench > Bin E1"

    Claude->>MCP: get_bin(bin_id=15)
    MCP-->>Claude: Bin E1 details, current items
    Note over Claude: Bin has space, related items present

    Claude->>MCP: get_bin_tree(location_id=1)
    MCP-->>Claude: All bins in location
    Note over Claude: Alternative options if primary is full
```

**Claude Tool Calls:**
```json
// Tool: search_items - Find similar items
{ "query": "soldering" }

// Tool: get_bin - Check suggested bin details
{ "bin_id": 15 }

// Tool: get_bin_tree - See organization structure
{ "location_id": 1 }
```

---

### Step 3: Claude Suggests Best Bin

Claude provides a recommendation with reasoning.

```mermaid
sequenceDiagram
    participant User
    participant Claude as Claude Desktop

    Claude->>User: "Based on your inventory organization:<br/><br/>📍 Recommended: Garage > Electronics Bench > Bin E1<br/><br/>Reason: This bin contains your other soldering equipment<br/>(soldering iron, solder wire, tips, flux).<br/><br/>Alternative: Bin E2 has desoldering tools if E1 is full."
```

**Recommendation Factors:**
| Factor | Why It Matters |
|--------|----------------|
| Similar items | Keep related items together |
| Same category | Logical organization |
| Available space | Bin shouldn't be overfull |
| User's existing pattern | Match their organization style |

---

### Step 4: User Stores Item

User places item in suggested bin and optionally adds to inventory.

```mermaid
sequenceDiagram
    participant User
    participant Claude as Claude Desktop
    participant MCP as Protea MCP

    User->>Claude: "Good idea, I'll put it there. Add it to inventory."

    Claude->>MCP: add_item(bin_id=15, name="Soldering Iron Stand", quantity=1, category="Tools")
    MCP-->>Claude: Item added, id: 156

    Claude->>User: "✓ Added 'Soldering Iron Stand' to<br/>Garage > Electronics Bench > Bin E1"
```

**Claude Tool Call:**
```json
// Tool: add_item
{
  "bin_id": 15,
  "name": "Soldering Iron Stand",
  "quantity": 1,
  "category": "Tools",
  "description": "Holder for soldering iron when not in use"
}
```

---

## Complete Conversation Example

```
User: I just bought a new heat gun. Where should I store it?

Claude: Let me check where you keep similar items...
        [calls search_items("heat gun"), search_items("heat shrink"),
         search_items("electronics tools")]

        Based on your current organization, I recommend:

        📍 Primary: Garage > Electronics Bench > Bin E3

        Reason: This bin contains your heat shrink tubing, cable ties,
        and wire management supplies. A heat gun is commonly used with
        these items.

        📍 Alternative: Garage > Power Tools > Shelf 2

        This is where you keep larger power tools (drill, sander).
        If the heat gun is large or if you think of it more as a
        power tool than an electronics tool, this could work too.

        Which would you prefer?

User: The electronics bench makes sense. Add it there.

Claude: [calls add_item]

        ✓ Added "Heat Gun" to Garage > Electronics Bench > Bin E3

        Tip: I also noticed you have heat shrink tubing in Bin E2.
        You might want to consolidate those together.

User: Good point, can you move the heat shrink to E3 too?

Claude: [calls move_items_bulk]

        ✓ Moved 3 heat shrink items from E2 to E3:
        - Heat Shrink Tubing, Assorted Sizes
        - Heat Shrink Tubing, 1/4"
        - Heat Shrink Tubing, 1/2"
```

---

## Workflow Diagram

```mermaid
flowchart TB
    subgraph Input["User Input"]
        i1["Describe item to store"]
    end

    subgraph Analysis["Claude Analysis"]
        a1["Search for similar items"]
        a2["Analyze bin contents"]
        a3["Check organization patterns"]
        a4["Consider alternatives"]
    end

    subgraph Recommendation["Recommendation"]
        r1["Primary bin suggestion"]
        r2["Reasoning explanation"]
        r3["Alternative options"]
    end

    subgraph Action["User Action"]
        u1["Accept recommendation"]
        u2["Store item physically"]
        u3["Add to inventory"]
    end

    Input --> a1
    a1 --> a2 --> a3 --> a4
    a4 --> r1 --> r2 --> r3
    r3 --> u1 --> u2 --> u3
```

---

## Screenshots Needed

### Claude Desktop Conversation
1. **User question** - "Where should I put this new [item]?"
2. **Claude searching** - Showing tool calls to search inventory
3. **Recommendation** - Claude's suggestion with reasoning
4. **Confirmation** - User accepts, item added

### Supporting Screenshots
5. **Web UI bin view** - Showing the suggested bin contents
6. **Physical location** - Photo of actual bin (before/after)

---

## Recommendation Logic

Claude considers these factors when suggesting bins:

```mermaid
flowchart TB
    subgraph Factors["Decision Factors"]
        f1["🔗 Related Items<br/>Same category/use"]
        f2["📍 User Patterns<br/>Existing organization"]
        f3["📦 Bin Capacity<br/>Space available"]
        f4["🏷️ Category Match<br/>Logical grouping"]
    end

    subgraph Weights["Priority"]
        w1["High: Related items together"]
        w2["Medium: Match existing patterns"]
        w3["Low: Available space"]
    end

    f1 --> w1
    f2 --> w2
    f3 --> w3
    f4 --> w1
```

---

## Edge Cases

| Scenario | Claude's Approach |
|----------|------------------|
| No similar items exist | Suggest based on category, or ask user |
| Multiple good options | Present top 2-3 with tradeoffs |
| All relevant bins full | Suggest creating new bin or reorganizing |
| Item spans categories | Ask user which use case is primary |
| First item in new location | Help set up initial organization |
