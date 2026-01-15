"""Page routes for web UI."""

import base64

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from inventory_mcp.db.connection import Database
from inventory_mcp.services.image_store import ImageStore
from inventory_mcp.tools import bins as bins_tools
from inventory_mcp.tools import items as items_tools
from inventory_mcp.tools import locations as locations_tools
from inventory_mcp.tools import search as search_tools
from inventory_mcp.web.app import templates
from inventory_mcp.web.dependencies import get_db, get_image_store

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def search_page(request: Request, q: str = "", db: Database = Depends(get_db)):
    """Render search page with optional results."""
    results = []
    if q.strip():
        results = search_tools.search_items(db, q.strip())

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "query": q,
            "results": results,
            "active_nav": "search",
        },
    )


@router.get("/search", response_class=HTMLResponse)
async def search_results_page(
    request: Request, q: str = "", db: Database = Depends(get_db)
):
    """Search results page (full page reload version)."""
    results = []
    if q.strip():
        results = search_tools.search_items(db, q.strip())

    return templates.TemplateResponse(
        request=request,
        name="search.html",
        context={
            "query": q,
            "results": results,
            "active_nav": "search",
        },
    )


@router.get("/item/{item_id}", response_class=HTMLResponse)
async def item_detail_page(
    request: Request, item_id: str, db: Database = Depends(get_db)
):
    """Render item detail page."""
    result = items_tools.get_item(db, item_id)

    # Check if error
    if isinstance(result, dict) and "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="item.html",
            context={
                "error": result["error"],
                "item": None,
                "active_nav": "search",
            },
            status_code=404,
        )

    # Get item history
    history = search_tools.get_item_history(db, item_id)
    if isinstance(history, dict):
        history = []

    # Get all bins for move dropdown (grouped by location)
    all_bins = []
    locations = locations_tools.get_locations(db)
    for loc in locations:
        loc_bins = bins_tools.get_bins(db, location_id=loc.id)
        for b in loc_bins:
            all_bins.append({
                "id": b.id,
                "name": b.name,
                "location_name": loc.name,
                "is_current": b.id == result.bin_id,
            })

    return templates.TemplateResponse(
        request=request,
        name="item.html",
        context={
            "item": result,
            "history": history,
            "all_bins": all_bins,
            "active_nav": "search",
        },
    )


@router.post("/item/{item_id}/move")
async def move_item(
    request: Request,
    item_id: str,
    to_bin_id: str = Form(...),
    notes: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Handle move item form submission."""
    result = items_tools.move_item(
        db=db,
        item_id=item_id,
        to_bin_id=to_bin_id,
        notes=notes if notes else None,
    )

    # Redirect back to item page
    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/item/{item_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/item/{item_id}", status_code=303)


@router.post("/item/{item_id}/add-quantity")
async def add_quantity(
    request: Request,
    item_id: str,
    quantity: int = Form(default=1),
    notes: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Handle add quantity form submission."""
    # Get current item to find current quantity
    item = items_tools.get_item(db, item_id)
    if isinstance(item, dict) and "error" in item:
        return RedirectResponse(
            url=f"/item/{item_id}?error={item['error']}",
            status_code=303,
        )

    # Calculate new quantity
    current_qty = item.quantity_value or 0
    new_qty = current_qty + quantity

    # Update item with new quantity
    result = items_tools.update_item(
        db=db,
        item_id=item_id,
        quantity_value=new_qty,
    )

    # Log the addition manually since update_item logs "updated" not "added"
    from inventory_mcp.db.models import ActivityAction
    from inventory_mcp.tools.items import _log_activity
    _log_activity(
        db=db,
        item_id=item_id,
        action=ActivityAction.ADDED,
        quantity_change=quantity,
        notes=notes if notes else None,
    )

    return RedirectResponse(url=f"/item/{item_id}", status_code=303)


@router.post("/item/{item_id}/use")
async def use_item(
    request: Request,
    item_id: str,
    quantity: int = Form(default=1),
    notes: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Handle use item form submission."""
    result = items_tools.use_item(
        db=db,
        item_id=item_id,
        quantity=quantity,
        notes=notes if notes else None,
    )

    # Redirect back to item page
    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/item/{item_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/item/{item_id}", status_code=303)


@router.post("/item/{item_id}/edit")
async def edit_item(
    request: Request,
    item_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    quantity_type: str = Form(...),
    quantity_value: int = Form(default=1),
    quantity_label: str = Form(default=""),
    notes: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Handle item edit form submission."""
    result = items_tools.update_item(
        db=db,
        item_id=item_id,
        name=name,
        description=description if description else None,
        quantity_type=quantity_type,
        quantity_value=quantity_value,
        quantity_label=quantity_label if quantity_label else None,
        notes=notes if notes else None,
    )

    # Redirect back to item page
    if isinstance(result, dict) and "error" in result:
        # TODO: Flash error message
        return RedirectResponse(
            url=f"/item/{item_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/item/{item_id}", status_code=303)


@router.get("/browse", response_class=HTMLResponse)
async def browse_page(request: Request, db: Database = Depends(get_db)):
    """Render browse page with location/bin tree."""
    locations = locations_tools.get_locations(db)

    # Count bins recursively in tree
    def count_bins(nodes):
        total = len(nodes)
        for node in nodes:
            total += count_bins(node.get("children", []))
        return total

    # Convert flat bins list to tree format (fallback for pre-migration data)
    def bins_to_tree(bins_list):
        return [
            {
                "id": b.id,
                "name": b.name,
                "description": b.description,
                "parent_bin_id": getattr(b, "parent_bin_id", None),
                "item_count": db.execute_one(
                    "SELECT COUNT(*) as cnt FROM items WHERE bin_id = ?", (b.id,)
                )["cnt"],
                "child_count": 0,
                "children": [],
            }
            for b in bins_list
        ]

    # Build tree structure with bins for each location
    location_data = []
    for loc in locations:
        # Try to get nested bin tree
        bin_tree = bins_tools.get_bin_tree(db, location_id=loc.id)
        bins_tree = bin_tree.get("bins", [])

        # Fallback: if tree is empty, try getting bins directly
        # This handles the case where migration hasn't run yet
        if not bins_tree:
            flat_bins = bins_tools.get_bins(db, location_id=loc.id)
            if flat_bins:
                bins_tree = bins_to_tree(flat_bins)

        location_data.append({
            "location": loc,
            "bins_tree": bins_tree,
            "bin_count": count_bins(bins_tree),
        })

    return templates.TemplateResponse(
        request=request,
        name="browse.html",
        context={
            "locations": location_data,
            "active_nav": "browse",
        },
    )


@router.get("/browse/bin/{bin_id}", response_class=HTMLResponse)
async def browse_bin_page(
    request: Request,
    bin_id: str,
    error: str = None,
    db: Database = Depends(get_db),
):
    """Render bin detail page in browse context."""
    result = bins_tools.get_bin(db, bin_id=bin_id, include_items=True, include_images=True)

    if isinstance(result, dict) and "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="bin.html",
            context={
                "error": result["error"],
                "bin": None,
                "active_nav": "browse",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="bin.html",
        context={
            "bin": result,
            "active_nav": "browse",
            "upload_error": error,
        },
    )


@router.post("/browse/bin/{bin_id}/upload-image")
async def upload_bin_image(
    request: Request,
    bin_id: str,
    image: UploadFile,
    caption: str = Form(default=""),
    is_primary: bool = Form(default=False),
    db: Database = Depends(get_db),
    image_store: ImageStore = Depends(get_image_store),
):
    """Upload an image to a bin."""
    # Read and encode the image
    contents = await image.read()
    image_base64 = base64.b64encode(contents).decode("utf-8")

    # Add the image to the bin
    result = bins_tools.add_bin_image(
        db=db,
        image_store=image_store,
        bin_id=bin_id,
        image_base64=image_base64,
        caption=caption if caption else None,
        is_primary=is_primary,
    )

    # Redirect back to bin page
    if isinstance(result, dict) and "error" in result:
        # TODO: Flash error message
        return RedirectResponse(
            url=f"/browse/bin/{bin_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/browse/bin/{bin_id}", status_code=303)


@router.post("/browse/bin/{bin_id}/delete-image/{image_id}")
async def delete_bin_image(
    request: Request,
    bin_id: str,
    image_id: str,
    db: Database = Depends(get_db),
    image_store: ImageStore = Depends(get_image_store),
):
    """Delete an image from a bin."""
    bins_tools.remove_bin_image(db=db, image_store=image_store, image_id=image_id)
    return RedirectResponse(url=f"/browse/bin/{bin_id}", status_code=303)


@router.post("/browse/bin/{bin_id}/set-primary-image/{image_id}")
async def set_primary_bin_image(
    request: Request,
    bin_id: str,
    image_id: str,
    db: Database = Depends(get_db),
):
    """Set an image as the primary image for a bin."""
    bins_tools.set_primary_bin_image(db=db, bin_id=bin_id, image_id=image_id)
    return RedirectResponse(url=f"/browse/bin/{bin_id}", status_code=303)


@router.get("/history", response_class=HTMLResponse)
async def history_page(
    request: Request,
    limit: int = 50,
    db: Database = Depends(get_db),
):
    """Render activity history page."""
    # Get recent activity with item and location details
    rows = db.execute(
        """
        SELECT
            a.id,
            a.item_id,
            a.action,
            a.quantity_change,
            a.from_bin_id,
            a.to_bin_id,
            a.notes,
            a.created_at,
            i.name as item_name,
            i.photo_url as item_photo,
            b.name as bin_name,
            l.name as location_name
        FROM activity_log a
        LEFT JOIN items i ON a.item_id = i.id
        LEFT JOIN bins b ON i.bin_id = b.id
        LEFT JOIN locations l ON b.location_id = l.id
        ORDER BY a.created_at DESC
        LIMIT ?
        """,
        (limit,),
    )

    # Group by date for display
    from collections import defaultdict
    from datetime import datetime

    history_by_date = defaultdict(list)
    for row in rows:
        created_at = row["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        date_key = created_at.strftime("%Y-%m-%d")
        history_by_date[date_key].append({
            "id": row["id"],
            "item_id": row["item_id"],
            "item_name": row["item_name"] or "Unknown Item",
            "item_photo": row["item_photo"],
            "action": row["action"],
            "quantity_change": row["quantity_change"],
            "notes": row["notes"],
            "created_at": created_at,
            "bin_name": row["bin_name"],
            "location_name": row["location_name"],
        })

    # Convert to sorted list of (date, entries)
    history_dates = sorted(history_by_date.items(), key=lambda x: x[0], reverse=True)

    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={
            "history_dates": history_dates,
            "active_nav": "history",
        },
    )
