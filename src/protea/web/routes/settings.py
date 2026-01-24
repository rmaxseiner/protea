"""Settings routes for user profile and API key management."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from protea.db.connection import Database
from protea.db.models import User
from protea.services import system_settings
from protea.tools import auth as auth_tools
from protea.web.app import templates
from protea.web.dependencies import get_db, require_auth

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    message: str = None,
    error: str = None,
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Render settings page with profile, API keys, and embedding settings."""
    # Get user's API keys
    api_keys = auth_tools.get_user_api_keys(db, user.id)

    # Get embedding model settings
    current_model = system_settings.get_current_model(db)
    regen_status = system_settings.get_regen_status(db)

    return templates.TemplateResponse(
        request=request,
        name="settings.html",
        context={
            "user": user,
            "api_keys": api_keys,
            "message": message,
            "error": error,
            "active_nav": "settings",
            "embedding_models": system_settings.EMBEDDING_MODELS,
            "current_model": current_model,
            "regen_status": regen_status,
        },
    )


@router.get("/change-password", response_class=HTMLResponse)
async def change_password_page(
    request: Request,
    error: str = None,
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Render change password page."""
    return templates.TemplateResponse(
        request=request,
        name="change_password.html",
        context={
            "user": user,
            "error": error,
            "must_change": user.must_change_password,
            "active_nav": "settings",
        },
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Handle password change form submission."""
    # Verify current password
    if not auth_tools.verify_password(current_password, user.password_hash):
        return RedirectResponse(
            url="/settings/change-password?error=Current password is incorrect",
            status_code=303,
        )

    # Check new passwords match
    if new_password != confirm_password:
        return RedirectResponse(
            url="/settings/change-password?error=New passwords do not match",
            status_code=303,
        )

    # Update password
    result = auth_tools.update_user_password(db, user.id, new_password)

    if isinstance(result, dict) and "error" in result:
        error_msg = result.get("error", "Failed to update password")
        if "details" in result:
            error_msg = "; ".join(result["details"])
        return RedirectResponse(
            url=f"/settings/change-password?error={error_msg}",
            status_code=303,
        )

    return RedirectResponse(
        url="/settings?message=Password changed successfully",
        status_code=303,
    )


@router.post("/embedding-model")
async def change_embedding_model(
    request: Request,
    model: str = Form(...),
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Change the embedding model and regenerate embeddings."""
    result = system_settings.change_embedding_model(db, model)

    if "error" in result:
        return RedirectResponse(
            url=f"/settings?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/settings?message={result.get('message', 'Model updated')}",
        status_code=303,
    )


@router.get("/embedding-status")
async def get_embedding_status(
    request: Request,
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Get current embedding regeneration status (for polling)."""
    return system_settings.get_regen_status(db)


@router.post("/api-keys/create")
async def create_api_key(
    request: Request,
    name: str = Form(...),
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Create a new API key."""
    result = auth_tools.create_api_key(db, user.id, name)

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/settings?error={result['error']}",
            status_code=303,
        )

    # Redirect to page showing the new key
    return templates.TemplateResponse(
        request=request,
        name="api_key_created.html",
        context={
            "user": user,
            "api_key": result,
            "active_nav": "settings",
        },
    )


@router.post("/api-keys/{key_id}/revoke")
async def revoke_api_key(
    request: Request,
    key_id: str,
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Revoke an API key (deactivate but keep for records)."""
    result = auth_tools.revoke_api_key(db, key_id, user.id)

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/settings?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(
        url="/settings?message=API key revoked",
        status_code=303,
    )


@router.post("/api-keys/{key_id}/delete")
async def delete_api_key(
    request: Request,
    key_id: str,
    db: Database = Depends(get_db),
    user: User = Depends(require_auth),
):
    """Permanently delete an API key."""
    result = auth_tools.delete_api_key(db, key_id, user.id)

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/settings?error={result['error']}",
            status_code=303,
        )

    return RedirectResponse(
        url="/settings?message=API key deleted",
        status_code=303,
    )
