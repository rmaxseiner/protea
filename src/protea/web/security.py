"""Security utilities for the web UI - CSRF protection and rate limiting."""

import secrets
import time
from collections import defaultdict
from typing import Optional

from fastapi import Form, HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from protea.config import auth_settings


# =============================================================================
# CSRF Protection
# =============================================================================

CSRF_COOKIE_NAME = "protea_csrf"
CSRF_FORM_FIELD = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_LENGTH = 32


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def get_csrf_token(request: Request) -> str:
    """Get or create CSRF token for the current request.

    The token is stored in request state to ensure consistency
    between cookie and form field within a single request.
    """
    if hasattr(request.state, "csrf_token"):
        return request.state.csrf_token

    # Check for existing token in cookie
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = generate_csrf_token()

    request.state.csrf_token = token
    return token


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF token cookie on response."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,  # Must be readable by JavaScript for AJAX
        samesite="lax",
        secure=auth_settings.secure_cookies,
        max_age=3600 * 24,  # 24 hours
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    """Middleware to set CSRF cookies and validate header-based CSRF for AJAX.

    Form-based CSRF is validated via the validate_csrf_token dependency
    to avoid consuming the request body in middleware.

    For AJAX requests, validation is done via X-CSRF-Token header.
    """

    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
    # Paths that don't require CSRF
    EXEMPT_PATHS = {"/images/", "/partials/"}

    def __init__(self, app, exempt_paths: Optional[set] = None):
        super().__init__(app)
        self.exempt_paths = exempt_paths or self.EXEMPT_PATHS

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always ensure CSRF token exists in request state
        token = get_csrf_token(request)

        # For AJAX requests (with X-CSRF-Token header), validate in middleware
        if request.method in self.PROTECTED_METHODS:
            if not self._is_exempt(request.url.path):
                # Only validate header-based CSRF in middleware
                # Form-based CSRF is validated by the dependency
                csrf_header = request.headers.get(CSRF_HEADER_NAME)
                if csrf_header:
                    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
                    if not cookie_token or not secrets.compare_digest(cookie_token, csrf_header):
                        raise HTTPException(status_code=403, detail="CSRF token mismatch")

        # Process request
        response = await call_next(request)

        # Set CSRF cookie on response
        set_csrf_cookie(response, token)

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF validation."""
        for exempt in self.exempt_paths:
            if path.startswith(exempt):
                return True
        return False


def validate_csrf_token(
    request: Request,
    csrf_token: Optional[str] = Form(None, alias="csrf_token"),
) -> None:
    """FastAPI dependency to validate CSRF token from form data.

    Use this dependency in route handlers that accept form submissions.
    The token is validated against the cookie value.

    Usage:
        @router.post("/submit")
        async def submit(request: Request, _: None = Depends(validate_csrf_token)):
            ...
    """
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token:
        raise HTTPException(status_code=403, detail="CSRF cookie missing")

    if not csrf_token:
        raise HTTPException(status_code=403, detail="CSRF token not provided")

    if not secrets.compare_digest(cookie_token, csrf_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


# =============================================================================
# Rate Limiting
# =============================================================================


class RateLimiter:
    """Simple in-memory rate limiter for authentication endpoints.

    Uses a sliding window approach to track requests per IP.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _cleanup(self) -> None:
        """Remove expired entries to prevent memory growth."""
        now = time.time()
        # Only cleanup every minute
        if now - self._last_cleanup < 60:
            return

        self._last_cleanup = now
        cutoff = now - self.window_seconds

        keys_to_delete = []
        for key, timestamps in self._requests.items():
            # Remove old timestamps
            self._requests[key] = [t for t in timestamps if t > cutoff]
            if not self._requests[key]:
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._requests[key]

    def is_allowed(self, key: str) -> bool:
        """Check if request is allowed and record it if so.

        Args:
            key: Identifier (usually IP address)

        Returns:
            True if request is allowed, False if rate limited
        """
        self._cleanup()

        now = time.time()
        cutoff = now - self.window_seconds

        # Get recent requests
        timestamps = self._requests[key]
        recent = [t for t in timestamps if t > cutoff]

        if len(recent) >= self.max_requests:
            return False

        # Record this request
        recent.append(now)
        self._requests[key] = recent
        return True

    def get_retry_after(self, key: str) -> int:
        """Get seconds until the client can retry.

        Returns:
            Seconds to wait, or 0 if not rate limited
        """
        now = time.time()
        cutoff = now - self.window_seconds

        timestamps = self._requests.get(key, [])
        recent = [t for t in timestamps if t > cutoff]

        if len(recent) < self.max_requests:
            return 0

        # Find oldest request in window
        oldest = min(recent)
        return int(oldest + self.window_seconds - now) + 1


# Global rate limiter instance for auth endpoints
auth_rate_limiter = RateLimiter(
    max_requests=auth_settings.auth_rate_limit,
    window_seconds=60,
)


def check_rate_limit(request: Request) -> None:
    """Check rate limit for authentication endpoints.

    Raises HTTPException 429 if rate limited.
    """
    # Use client IP as key
    client_ip = request.client.host if request.client else "unknown"

    if not auth_rate_limiter.is_allowed(client_ip):
        retry_after = auth_rate_limiter.get_retry_after(client_ip)
        raise HTTPException(
            status_code=429,
            detail=f"Too many login attempts. Try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
