# Feature: DrawerDone Integration

**Status:** Planning
**Priority:** Medium
**Target:** v1.2.0
**Dependency:** Item Dimensions feature

---

## Overview

Enable export of bin contents with item dimensions to DrawerDone format, allowing users to generate optimized drawer organizer layouts for 3D printing.

---

## What is DrawerDone?

DrawerDone is a tool/format for designing 3D-printable drawer organizers. Given:
- Drawer dimensions
- Item dimensions and quantities

It generates optimized layouts with compartments sized for each item.

**Resources:**
- [DrawerDone GitHub](https://github.com/BigBrain3D/DrawerDone) (if exists)
- [Similar: Gridfinity generators]

---

## Goals

1. Export bin contents to DrawerDone-compatible format
2. Allow users to generate custom organizers for their bins
3. Support common 3D printing workflows
4. Optional: Preview layout in web UI

---

## Integration Approach

### Export Format

Generate JSON/CSV that DrawerDone (or similar tools) can import:

```json
{
  "drawer": {
    "name": "Electronics Bin",
    "length_mm": 300,
    "width_mm": 200,
    "height_mm": 50
  },
  "items": [
    {
      "name": "Arduino Uno",
      "length_mm": 68.6,
      "width_mm": 53.4,
      "height_mm": 15,
      "quantity": 2,
      "outline": "rectangle"
    },
    {
      "name": "Jumper Wires (bundle)",
      "length_mm": 100,
      "width_mm": 30,
      "height_mm": 20,
      "quantity": 1,
      "outline": "rectangle"
    }
  ]
}
```

### MCP Tool

```python
def export_bin_for_drawerdone(
    bin_id: str,
    drawer_length_mm: float = None,  # Override bin dimensions
    drawer_width_mm: float = None,
    drawer_height_mm: float = None,
    format: str = "json"  # "json" or "csv"
) -> ExportResult:
    """
    Export bin contents with dimensions for DrawerDone import.

    Returns items with dimensions. Items without dimensions are
    listed separately for manual measurement.
    """
```

### Web UI

Add "Export for DrawerDone" button on bin page:

```
┌─ Bin: Electronics Workbench ─────────────────┐
│                                              │
│ [Add Item] [Edit Bin] [Export DrawerDone ▼]  │
│                        ├─ JSON               │
│                        ├─ CSV                │
│                        └─ Gridfinity         │
└──────────────────────────────────────────────┘
```

---

## Workflow

### User Flow

1. User measures bin/drawer dimensions (or bin has dimensions stored)
2. User ensures items have dimensions recorded
3. User clicks "Export for DrawerDone"
4. System generates export file
5. User imports into DrawerDone or compatible tool
6. Tool generates 3D model for printing
7. User prints and organizes

### Handling Missing Dimensions

```
┌─ Export for DrawerDone ──────────────────────┐
│                                              │
│ 8 of 12 items have dimensions recorded.      │
│                                              │
│ Missing dimensions:                          │
│ • Resistor Assortment                        │
│ • Capacitor Kit                              │
│ • USB Cables (assorted)                      │
│ • Breadboard                                 │
│                                              │
│ [Export Available Items] [Measure Items First] │
└──────────────────────────────────────────────┘
```

---

## Export Formats

### 1. DrawerDone JSON
Native format for DrawerDone tool.

### 2. Generic CSV
For spreadsheet import or custom tools:

```csv
name,length_mm,width_mm,height_mm,quantity,outline
"Arduino Uno",68.6,53.4,15,2,rectangle
"Jumper Wires",100,30,20,1,rectangle
```

### 3. Gridfinity Compatible
For Gridfinity ecosystem:

```json
{
  "grid_units_x": 4,
  "grid_units_y": 3,
  "items": [...]
}
```

---

## Bin Dimensions

### Option 1: Store Bin Dimensions
Extend bin model:

```sql
ALTER TABLE bins ADD COLUMN interior_length_mm REAL;
ALTER TABLE bins ADD COLUMN interior_width_mm REAL;
ALTER TABLE bins ADD COLUMN interior_height_mm REAL;
```

### Option 2: Prompt at Export
Ask for dimensions when exporting:

```
Enter drawer dimensions:
Length: [____] mm
Width:  [____] mm
Height: [____] mm
```

**Recommendation:** Support both - store if known, prompt if not.

---

## Advanced Features (Future)

### 1. Layout Preview
Show 2D preview of item arrangement in web UI.

### 2. Direct STL Generation
Generate 3D model directly without external tool.

### 3. Optimization Suggestions
"If you rotate the Arduino 90°, you can fit one more in."

### 4. Standard Organizer Templates
Pre-made templates for common bin sizes (IKEA Alex, Harbor Freight, etc.).

---

## Tasks

- [ ] Research DrawerDone format specification
- [ ] Implement JSON export function
- [ ] Implement CSV export function
- [ ] Add export button to bin page UI
- [ ] Handle missing dimensions gracefully
- [ ] Add bin dimension fields (optional)
- [ ] Write export tests
- [ ] Document export workflow

---

## Open Questions

1. Is DrawerDone still maintained? What's the exact format?
2. Should we support Gridfinity directly?
3. Do we want to generate STL files ourselves (OpenSCAD integration)?
4. Should bin dimensions be required or optional?
5. How to handle items with irregular shapes?

---

## Related Features

- **Item Dimensions** - Required dependency for export
- **Bulk Dimension Entry** - Quick way to measure multiple items
- **3D Preview** - Nice-to-have visual feedback
