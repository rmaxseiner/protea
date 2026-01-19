"""Image serving routes for web UI."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from protea.services.image_store import ImageStore
from protea.web.dependencies import get_image_store

router = APIRouter()


@router.get("/{path:path}")
async def serve_image(
    path: str,
    thumb: bool = Query(False, description="Return thumbnail instead of full image"),
    image_store: ImageStore = Depends(get_image_store),
):
    """Serve images from the image store.

    Args:
        path: Relative path to image (e.g., bins/uuid/image.webp)
        thumb: If True, serve thumbnail version

    Returns:
        FileResponse with the image
    """
    # Security: prevent path traversal
    if ".." in path:
        raise HTTPException(status_code=400, detail="Invalid path")

    # Get absolute path
    if thumb:
        # Convert path to thumbnail path
        p = Path(path)
        thumb_path = p.parent / f"{p.stem}_thumb{p.suffix}"
        full_path = image_store.get_absolute_path(str(thumb_path))
        if not full_path.exists():
            # Fall back to main image if thumbnail doesn't exist
            full_path = image_store.get_absolute_path(path)
    else:
        full_path = image_store.get_absolute_path(path)

    if not full_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    # Determine media type
    suffix = full_path.suffix.lower()
    media_types = {
        ".webp": "image/webp",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    return FileResponse(
        full_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000"},  # 1 year cache
    )
