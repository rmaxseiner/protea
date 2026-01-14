"""htmx partial routes for web UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from inventory_mcp.db.connection import Database
from inventory_mcp.tools import search as search_tools
from inventory_mcp.web.app import templates
from inventory_mcp.web.dependencies import get_db

router = APIRouter()


@router.get("/search", response_class=HTMLResponse)
async def search_results_partial(
    request: Request, q: str = "", db: Database = Depends(get_db)
):
    """Return search results as htmx partial."""
    results = []
    if q.strip():
        results = search_tools.search_items(db, q.strip())

    return templates.TemplateResponse(
        request=request,
        name="partials/search_results.html",
        context={
            "results": results,
            "query": q,
        },
    )
