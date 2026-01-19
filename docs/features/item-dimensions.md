# Feature: Item Dimensions & Outline

**Status:** Planning
**Priority:** Medium
**Target:** v1.1.0

---

## Overview

Extend item records to capture physical dimensions, weight, and outline shape for better organization and future integrations (e.g., DrawerDone bin layout optimization).

---

## Goals

1. Record item dimensions for space planning
2. Capture outline shape for 2D layout tools
3. Enable "will it fit?" queries
4. Support DrawerDone export feature

---

## Data Model

### New Item Fields

| Field | Type | Unit | Description |
|-------|------|------|-------------|
| `length` | float | mm | Length in millimeters |
| `width` | float | mm | Width in millimeters |
| `height` | float | mm | Height in millimeters |
| `weight` | float | g | Weight in grams |
| `outline_type` | enum | - | Shape category |
| `outline_data` | JSON | - | Shape-specific data |

### Outline Types

| Type | Description | Outline Data |
|------|-------------|--------------|
| `rectangle` | Simple rectangular | `{}` (uses length × width) |
| `circle` | Circular | `{"diameter": float}` |
| `oval` | Elliptical | `{}` (uses length × width) |
| `polygon` | Custom shape | `{"points": [[x,y], ...]}` |
| `irregular` | Cannot be simplified | `{"notes": string}` |

---

## Database Schema Changes

```sql
ALTER TABLE items ADD COLUMN length_mm REAL;
ALTER TABLE items ADD COLUMN width_mm REAL;
ALTER TABLE items ADD COLUMN height_mm REAL;
ALTER TABLE items ADD COLUMN weight_g REAL;
ALTER TABLE items ADD COLUMN outline_type TEXT DEFAULT 'rectangle';
ALTER TABLE items ADD COLUMN outline_data TEXT;  -- JSON
```

---

## MCP Tool Updates

### create_item / update_item

Add optional parameters:

```python
def create_item(
    name: str,
    bin_id: str,
    description: str = None,
    # ... existing params ...
    length_mm: float = None,
    width_mm: float = None,
    height_mm: float = None,
    weight_g: float = None,
    outline_type: str = "rectangle",
    outline_data: dict = None
) -> ItemResult:
```

### get_item

Return dimensions in response:

```json
{
  "id": "abc123",
  "name": "Arduino Uno",
  "dimensions": {
    "length_mm": 68.6,
    "width_mm": 53.4,
    "height_mm": 15.0,
    "weight_g": 25.0,
    "outline_type": "rectangle"
  }
}
```

### New Tool: find_items_that_fit

```python
def find_items_that_fit(
    max_length_mm: float,
    max_width_mm: float,
    max_height_mm: float = None
) -> List[Item]:
    """Find items that would fit in a given space."""
```

---

## Web UI Changes

### Item Form

Add collapsible "Dimensions" section:

```
┌─ Dimensions (optional) ──────────────────┐
│ Length: [____] mm   Width: [____] mm     │
│ Height: [____] mm   Weight: [____] g     │
│                                          │
│ Outline: [Rectangle ▼]                   │
│                                          │
│ [ ] I have measured this item            │
└──────────────────────────────────────────┘
```

### Item Display

Show dimensions badge on item cards:

```
┌────────────────────────────────────┐
│ Arduino Uno                        │
│ 68.6 × 53.4 × 15 mm  |  25g       │
│ [View] [Edit]                      │
└────────────────────────────────────┘
```

---

## Unit Handling

### Input Flexibility

Accept common units and convert:

| Input | Converts To |
|-------|-------------|
| `5cm` | 50 mm |
| `2in` | 50.8 mm |
| `0.5kg` | 500 g |
| `1lb` | 453.6 g |

### Storage

Always store in metric (mm, g) for consistency.

### Display

User preference for metric/imperial display.

---

## Use Cases

### 1. Workshop Organization
"What items would fit in a 100mm × 50mm drawer compartment?"

### 2. Shipping Planning
"How much does all the stuff in my 'To Ship' bin weigh?"

### 3. DrawerDone Export
Generate 2D layouts based on item outlines.

### 4. Space Optimization
"Which bin has the most empty space for my new item?"

---

## Tasks

- [ ] Add database migration for dimension fields
- [ ] Update Item model with dimension properties
- [ ] Modify create_item/update_item tools
- [ ] Add find_items_that_fit tool
- [ ] Update web UI item form
- [ ] Update web UI item display
- [ ] Add unit conversion utilities
- [ ] Write tests for dimension features

---

## Open Questions

1. Should we support 3D outline data for complex shapes?
2. Do we want a "measure with camera" feature (AR-style)?
3. Should dimensions be required or always optional?
4. How to handle items with variable dimensions (e.g., cables)?
