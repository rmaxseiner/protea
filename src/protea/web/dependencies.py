"""FastAPI dependency injection for web UI."""

from typing import Optional

from fastapi import Cookie, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from protea.config import auth_settings
from protea.db.connection import Database
from protea.db.models import User
from protea.services.image_store import ImageStore
from protea.tools import auth as auth_tools


def get_db(request: Request) -> Database:
    """Get database instance from app state."""
    return request.app.state.db


def get_image_store(request: Request) -> ImageStore:
    """Get image store instance from app state."""
    return request.app.state.image_store


def get_session_token(
    protea_session: Optional[str] = Cookie(default=None),
) -> Optional[str]:
    """Extract session token from cookie."""
    return protea_session


def get_current_user_optional(
    request: Request,
    token: Optional[str] = Depends(get_session_token),
    db: Database = Depends(get_db),
) -> Optional[User]:
    """Get current user if authenticated, None otherwise.

    Use this for routes that work with or without auth.
    """
    # If auth is disabled, return None (no user context)
    if not auth_settings.auth_required:
        return None

    if not token:
        return None

    return auth_tools.validate_session(db, token)


def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """Get current authenticated user.

    Raises 401 if not authenticated.
    Use this for API endpoints that require auth.
    """
    if not auth_settings.auth_required:
        # Return a dummy admin user when auth is disabled
        return User(
            id="system",
            username="system",
            password_hash="",
            is_admin=True,
        )

    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    return user


class RequireAuth:
    """Dependency that redirects to login if not authenticated.

    Use this for page routes that need authentication.
    """

    def __call__(
        self,
        request: Request,
        user: Optional[User] = Depends(get_current_user_optional),
    ) -> User:
        if not auth_settings.auth_required:
            # Return a dummy admin user when auth is disabled
            return User(
                id="system",
                username="system",
                password_hash="",
                is_admin=True,
            )

        if not user:
            # Store the original URL for redirect after login
            next_url = str(request.url.path)
            if request.url.query:
                next_url += f"?{request.url.query}"
            raise HTTPException(
                status_code=303,
                headers={"Location": f"/auth/login?next={next_url}"},
            )

        return user


require_auth = RequireAuth()


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Require that the current user is an admin.

    Raises 403 if not admin.
    """
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")

    return user
