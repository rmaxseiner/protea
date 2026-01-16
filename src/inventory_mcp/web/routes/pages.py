"""Page routes for web UI."""

import base64
import io
import re
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse

from inventory_mcp.config import settings
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


@router.get("/browse/location/{location_id}", response_class=HTMLResponse)
async def browse_location_page(
    request: Request,
    location_id: str,
    error: str = None,
    db: Database = Depends(get_db),
):
    """Render location detail page."""
    result = locations_tools.get_location(db, location_id=location_id)

    if isinstance(result, dict) and "error" in result:
        return templates.TemplateResponse(
            request=request,
            name="location.html",
            context={
                "error": result["error"],
                "location": None,
                "active_nav": "browse",
            },
            status_code=404,
        )

    # Get bins in this location (top-level only, not nested)
    bins = bins_tools.get_bins(db, location_id=location_id)

    # Count items in each bin
    bins_with_counts = []
    for b in bins:
        item_count = db.execute_one(
            "SELECT COUNT(*) as cnt FROM items WHERE bin_id = ?", (b.id,)
        )["cnt"]
        # Count child bins
        child_count = db.execute_one(
            "SELECT COUNT(*) as cnt FROM bins WHERE parent_bin_id = ?", (b.id,)
        )["cnt"]
        bins_with_counts.append({
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "item_count": item_count,
            "child_count": child_count,
        })

    return templates.TemplateResponse(
        request=request,
        name="location.html",
        context={
            "location": result,
            "bins": bins_with_counts,
            "active_nav": "browse",
            "error_message": error,
        },
    )


@router.post("/browse/location/{location_id}/edit")
async def edit_location(
    request: Request,
    location_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Handle location edit form submission."""
    result = locations_tools.update_location(
        db=db,
        location_id=location_id,
        name=name,
        description=description if description else None,
    )

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/browse/location/{location_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/browse/location/{location_id}", status_code=303)


@router.post("/browse/location/{location_id}/delete")
async def delete_location(
    request: Request,
    location_id: str,
    db: Database = Depends(get_db),
):
    """Handle location delete."""
    result = locations_tools.delete_location(db=db, location_id=location_id)

    if isinstance(result, dict) and not result.get("success"):
        error_msg = result.get("error", "Failed to delete location")
        return RedirectResponse(
            url=f"/browse/location/{location_id}?error={error_msg}",
            status_code=303,
        )

    return RedirectResponse(url="/browse", status_code=303)


@router.post("/browse/location/{location_id}/create-bin")
async def create_location_bin(
    request: Request,
    location_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Create a new bin in this location."""
    result = bins_tools.create_bin(
        db=db,
        name=name,
        location_id=location_id,
        description=description if description else None,
    )

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/browse/location/{location_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/browse/location/{location_id}", status_code=303)


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


@router.post("/browse/bin/{bin_id}/create-child")
async def create_child_bin(
    request: Request,
    bin_id: str,
    name: str = Form(...),
    description: str = Form(default=""),
    db: Database = Depends(get_db),
):
    """Create a child bin inside the current bin."""
    # Get parent bin to find location_id
    parent_bin = bins_tools.get_bin(db, bin_id=bin_id, include_items=False)
    if isinstance(parent_bin, dict) and "error" in parent_bin:
        return RedirectResponse(
            url=f"/browse/bin/{bin_id}?error={parent_bin['error']}",
            status_code=303,
        )

    result = bins_tools.create_bin(
        db=db,
        name=name,
        location_id=parent_bin.location_id,
        parent_bin_id=bin_id,
        description=description if description else None,
    )

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/browse/bin/{bin_id}?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(url=f"/browse/bin/{bin_id}", status_code=303)


@router.post("/browse/bin/{bin_id}/delete-child/{child_id}")
async def delete_child_bin(
    request: Request,
    bin_id: str,
    child_id: str,
    db: Database = Depends(get_db),
):
    """Delete a child bin."""
    result = bins_tools.delete_bin(db=db, bin_id=child_id)

    if isinstance(result, dict) and not result.get("success"):
        error_msg = result.get("error", "Failed to delete bin")
        return RedirectResponse(
            url=f"/browse/bin/{bin_id}?error={error_msg}",
            status_code=303,
        )

    return RedirectResponse(url=f"/browse/bin/{bin_id}", status_code=303)


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


def _sanitize_name(name: str) -> str:
    """Sanitize name for filesystem: replace spaces with dashes, remove special chars."""
    # Replace spaces with dashes
    name = name.replace(" ", "-")
    # Remove characters that are problematic in filenames
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    return name


def _get_bin_path(db: Database, bin_id: str) -> list[str]:
    """Get the full path of bin names from root to this bin."""
    path = []
    current_id = bin_id

    while current_id:
        bin_row = db.execute_one(
            "SELECT id, name, parent_bin_id, location_id FROM bins WHERE id = ?",
            (current_id,)
        )
        if not bin_row:
            break
        path.insert(0, bin_row["name"])
        current_id = bin_row["parent_bin_id"]

    return path


def _get_all_child_bins(db: Database, bin_id: str) -> list[dict]:
    """Recursively get all child bins."""
    children = []

    rows = db.execute(
        "SELECT id, name FROM bins WHERE parent_bin_id = ?",
        (bin_id,)
    )

    for row in rows:
        children.append({"id": row["id"], "name": row["name"]})
        children.extend(_get_all_child_bins(db, row["id"]))

    return children


@router.get("/browse/bin/{bin_id}/download-images")
async def download_bin_images(
    request: Request,
    bin_id: str,
    db: Database = Depends(get_db),
):
    """Download all images from a bin and its children as a zip file."""
    # Get the bin
    bin_data = bins_tools.get_bin(db, bin_id=bin_id)
    if isinstance(bin_data, dict) and "error" in bin_data:
        return RedirectResponse(
            url=f"/browse/bin/{bin_id}?error=Bin not found",
            status_code=303
        )

    # Get the path to this bin for folder structure
    bin_path = _get_bin_path(db, bin_id)

    # Collect all bins to process (this bin + all children)
    bins_to_process = [{"id": bin_id, "name": bin_data.name, "path": bin_path}]

    # Get all child bins recursively
    def add_children(parent_id: str, parent_path: list[str]):
        rows = db.execute(
            "SELECT id, name FROM bins WHERE parent_bin_id = ?",
            (parent_id,)
        )
        for row in rows:
            child_path = parent_path + [row["name"]]
            bins_to_process.append({
                "id": row["id"],
                "name": row["name"],
                "path": child_path
            })
            add_children(row["id"], child_path)

    add_children(bin_id, bin_path)

    # Create zip file in memory
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for bin_info in bins_to_process:
            # Build sanitized folder path
            folder_path = "/".join(_sanitize_name(p) for p in bin_info["path"])
            sanitized_bin_name = _sanitize_name(bin_info["name"])

            # Get images for this bin
            images = bins_tools.get_bin_images(db, bin_info["id"])
            if isinstance(images, dict) and "error" in images:
                images = []

            if not images:
                # Create empty folder with .gitkeep or similar placeholder
                zip_file.writestr(f"{folder_path}/.empty", "")
            else:
                # Add images with proper naming
                for idx, image in enumerate(images):
                    image_path = Path(settings.image_base_path) / image.file_path

                    if not image_path.exists():
                        continue

                    # Determine extension from file
                    ext = image_path.suffix or ".jpg"

                    # Build filename: bin-name.jpg or bin-name-1.jpg, bin-name-2.jpg
                    if len(images) == 1:
                        filename = f"{sanitized_bin_name}{ext}"
                    else:
                        filename = f"{sanitized_bin_name}-{idx + 1}{ext}"

                    # Add to zip
                    zip_file.write(image_path, f"{folder_path}/{filename}")

    # Prepare response
    zip_buffer.seek(0)

    # Generate filename for the zip
    root_name = _sanitize_name(bin_data.name)

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{root_name}-images.zip"'
        }
    )


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
