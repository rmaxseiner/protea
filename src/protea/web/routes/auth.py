"""Authentication routes for login, signup, and logout."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from protea.config import auth_settings
from protea.db.connection import Database
from protea.tools import auth as auth_tools
from protea.web.app import templates
from protea.web.dependencies import get_db, get_session_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = "/",
    error: str = None,
    db: Database = Depends(get_db),
    token: str = Depends(get_session_token),
):
    """Render login page."""
    # If already logged in, redirect
    if token:
        user = auth_tools.validate_session(db, token)
        if user:
            return RedirectResponse(url=next, status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "next_url": next,
            "error": error,
            "active_nav": None,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/"),
    db: Database = Depends(get_db),
):
    """Handle login form submission."""
    # Authenticate user
    result = auth_tools.authenticate_user(db, username, password)

    if isinstance(result, dict) and "error" in result:
        return RedirectResponse(
            url=f"/auth/login?next={next}&error={result['error']}",
            status_code=303,
        )

    user = result

    # Create session
    session, token = auth_tools.create_session(
        db,
        user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        session_hours=auth_settings.session_hours,
    )

    # If user must change password, redirect to change password page
    if user.must_change_password:
        response = RedirectResponse(url="/settings/change-password", status_code=303)
    else:
        response = RedirectResponse(url=next, status_code=303)

    # Set session cookie
    response.set_cookie(
        key="protea_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=auth_settings.session_hours * 3600,
    )

    return response


@router.get("/signup", response_class=HTMLResponse)
async def signup_page(
    request: Request,
    error: str = None,
    db: Database = Depends(get_db),
    token: str = Depends(get_session_token),
):
    """Render signup page.

    Only shows signup if users already exist (new users can be created).
    If no users exist, the bootstrap process handles admin creation.
    """
    # If already logged in, redirect
    if token:
        user = auth_tools.validate_session(db, token)
        if user:
            return RedirectResponse(url="/", status_code=303)

    # Check if any users exist
    user_count = auth_tools.get_user_count(db)
    if user_count == 0:
        # No users - redirect to login which will show the bootstrap message
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(
        request=request,
        name="signup.html",
        context={
            "error": error,
            "active_nav": None,
        },
    )


@router.post("/signup")
async def signup(
    request: Request,
    username: str = Form(...),
    email: str = Form(default=""),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Database = Depends(get_db),
):
    """Handle signup form submission."""
    # Check passwords match
    if password != confirm_password:
        return RedirectResponse(
            url="/auth/signup?error=Passwords do not match",
            status_code=303,
        )

    # Create user
    result = auth_tools.create_user(
        db,
        username=username,
        password=password,
        email=email if email else None,
        is_admin=False,
        must_change_password=False,
    )

    if isinstance(result, dict) and "error" in result:
        error_msg = result.get("error", "Failed to create account")
        if "details" in result:
            error_msg = "; ".join(result["details"])
        return RedirectResponse(
            url=f"/auth/signup?error={error_msg}",
            status_code=303,
        )

    user = result

    # Auto-login: create session
    session, token = auth_tools.create_session(
        db,
        user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        session_hours=auth_settings.session_hours,
    )

    response = RedirectResponse(url="/", status_code=303)

    # Set session cookie
    response.set_cookie(
        key="protea_session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=auth_settings.session_hours * 3600,
    )

    return response


@router.post("/logout")
async def logout(
    request: Request,
    db: Database = Depends(get_db),
    token: str = Depends(get_session_token),
):
    """Handle logout."""
    if token:
        auth_tools.delete_session(db, token)

    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="protea_session")

    return response


@router.get("/logout")
async def logout_get(
    request: Request,
    db: Database = Depends(get_db),
    token: str = Depends(get_session_token),
):
    """Handle logout via GET (for link-based logout)."""
    if token:
        auth_tools.delete_session(db, token)

    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(key="protea_session")

    return response
