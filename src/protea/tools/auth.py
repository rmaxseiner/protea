"""Authentication tools for user management, sessions, and API keys."""

import hashlib
import re
import secrets
import string
from datetime import datetime, timedelta
from typing import Optional

import bcrypt

from protea.db.connection import Database
from protea.db.models import (
    ApiKey,
    ApiKeyPublic,
    ApiKeyWithPlaintext,
    AuthSession,
    User,
    UserPublic,
    generate_id,
)


# =============================================================================
# Password Utilities
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def validate_password_complexity(password: str) -> Optional[dict]:
    """Validate password meets complexity requirements.

    Requirements:
    - Minimum 8 characters
    - At least 1 uppercase letter
    - At least 1 number
    - At least 1 special character (!@#$%^&*_+-=)

    Returns:
        None if valid, error dict if invalid
    """
    errors = []

    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")

    if not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least 1 uppercase letter")

    if not re.search(r"[0-9]", password):
        errors.append("Password must contain at least 1 number")

    if not re.search(r"[!@#$%^&*_+\-=]", password):
        errors.append("Password must contain at least 1 special character (!@#$%^&*_+-=)")

    if errors:
        return {
            "error": "Password does not meet complexity requirements",
            "error_code": "WEAK_PASSWORD",
            "details": errors,
        }

    return None


def generate_random_password(length: int = 16) -> str:
    """Generate a random password that meets complexity requirements."""
    # Ensure at least one of each required type
    password_chars = [
        secrets.choice(string.ascii_uppercase),  # 1 uppercase
        secrets.choice(string.digits),  # 1 digit
        secrets.choice("!@#$%^&*_+-="),  # 1 special
    ]

    # Fill the rest with a mix
    all_chars = string.ascii_letters + string.digits + "!@#$%^&*_+-="
    password_chars.extend(secrets.choice(all_chars) for _ in range(length - 3))

    # Shuffle to avoid predictable positions
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


# =============================================================================
# Token Utilities
# =============================================================================


def _hash_token(token: str) -> str:
    """Hash a token using SHA-256 for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_session_token() -> str:
    """Generate a secure session token."""
    return secrets.token_urlsafe(32)


def generate_api_key() -> str:
    """Generate a secure API key with prefix."""
    return f"prot_{secrets.token_urlsafe(32)}"


# =============================================================================
# User CRUD Operations
# =============================================================================


def create_user(
    db: Database,
    username: str,
    password: str,
    email: Optional[str] = None,
    is_admin: bool = False,
    must_change_password: bool = False,
) -> User | dict:
    """Create a new user.

    Args:
        db: Database connection
        username: Unique username
        password: Plain text password (will be hashed)
        email: Optional email address
        is_admin: Whether user has admin privileges
        must_change_password: Force password change on next login

    Returns:
        User object or error dict
    """
    # Validate password complexity
    complexity_error = validate_password_complexity(password)
    if complexity_error:
        return complexity_error

    # Check for existing username
    existing = db.execute_one(
        "SELECT id FROM users WHERE username = ?", (username,)
    )
    if existing:
        return {
            "error": "Username already exists",
            "error_code": "DUPLICATE_USERNAME",
        }

    # Check for existing email
    if email:
        existing = db.execute_one(
            "SELECT id FROM users WHERE email = ?", (email,)
        )
        if existing:
            return {
                "error": "Email already in use",
                "error_code": "DUPLICATE_EMAIL",
            }

    now = datetime.utcnow()
    user = User(
        id=generate_id(),
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_admin=is_admin,
        must_change_password=must_change_password,
        created_at=now,
        updated_at=now,
    )

    db.execute(
        """
        INSERT INTO users (id, username, email, password_hash, is_admin,
                          must_change_password, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.id,
            user.username,
            user.email,
            user.password_hash,
            user.is_admin,
            user.must_change_password,
            user.created_at,
            user.updated_at,
        ),
    )

    return user


def get_user(
    db: Database,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> User | dict | None:
    """Get a user by ID or username.

    Args:
        db: Database connection
        user_id: User UUID
        username: Username

    Returns:
        User object, None if not found, or error dict
    """
    if not user_id and not username:
        return {
            "error": "Must provide user_id or username",
            "error_code": "MISSING_PARAMETER",
        }

    if user_id:
        row = db.execute_one("SELECT * FROM users WHERE id = ?", (user_id,))
    else:
        row = db.execute_one("SELECT * FROM users WHERE username = ?", (username,))

    if not row:
        return None

    return User(
        id=row["id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        must_change_password=bool(row["must_change_password"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_user_public(user: User) -> UserPublic:
    """Convert User to UserPublic (without password hash)."""
    return UserPublic(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=user.is_admin,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def get_user_count(db: Database) -> int:
    """Get total number of users."""
    row = db.execute_one("SELECT COUNT(*) as count FROM users")
    return row["count"] if row else 0


def authenticate_user(db: Database, username: str, password: str) -> User | dict:
    """Authenticate a user with username and password.

    Args:
        db: Database connection
        username: Username
        password: Plain text password

    Returns:
        User object or error dict
    """
    user = get_user(db, username=username)

    if user is None:
        return {
            "error": "Invalid username or password",
            "error_code": "INVALID_CREDENTIALS",
        }

    if isinstance(user, dict):
        return user

    if not verify_password(password, user.password_hash):
        return {
            "error": "Invalid username or password",
            "error_code": "INVALID_CREDENTIALS",
        }

    return user


def update_user_password(
    db: Database,
    user_id: str,
    new_password: str,
    clear_must_change: bool = True,
) -> User | dict:
    """Update a user's password.

    Args:
        db: Database connection
        user_id: User UUID
        new_password: New plain text password
        clear_must_change: Clear the must_change_password flag

    Returns:
        Updated User object or error dict
    """
    # Validate password complexity
    complexity_error = validate_password_complexity(new_password)
    if complexity_error:
        return complexity_error

    user = get_user(db, user_id=user_id)
    if user is None:
        return {
            "error": "User not found",
            "error_code": "NOT_FOUND",
        }
    if isinstance(user, dict):
        return user

    now = datetime.utcnow()
    password_hash = hash_password(new_password)

    db.execute(
        """
        UPDATE users
        SET password_hash = ?, must_change_password = ?, updated_at = ?
        WHERE id = ?
        """,
        (password_hash, not clear_must_change and user.must_change_password, now, user_id),
    )

    user.password_hash = password_hash
    user.must_change_password = not clear_must_change and user.must_change_password
    user.updated_at = now

    return user


def delete_user(db: Database, user_id: str) -> dict:
    """Delete a user and all associated data.

    Args:
        db: Database connection
        user_id: User UUID

    Returns:
        Success or error dict
    """
    user = get_user(db, user_id=user_id)
    if user is None:
        return {
            "error": "User not found",
            "error_code": "NOT_FOUND",
        }
    if isinstance(user, dict):
        return user

    # Delete user (cascades to sessions and API keys)
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))

    return {"success": True, "message": f"User {user.username} deleted"}


def get_all_users(db: Database) -> list[UserPublic]:
    """Get all users (for admin use)."""
    rows = db.execute("SELECT * FROM users ORDER BY username")
    return [
        UserPublic(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            is_admin=bool(row["is_admin"]),
            must_change_password=bool(row["must_change_password"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


# =============================================================================
# Session Management
# =============================================================================


def create_session(
    db: Database,
    user_id: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    session_hours: int = 24,
) -> tuple[AuthSession, str]:
    """Create a new authentication session.

    Args:
        db: Database connection
        user_id: User UUID
        ip_address: Client IP address
        user_agent: Client user agent
        session_hours: Session validity in hours

    Returns:
        Tuple of (AuthSession, plain_text_token)
    """
    token = generate_session_token()
    token_hash = _hash_token(token)
    now = datetime.utcnow()
    expires_at = now + timedelta(hours=session_hours)

    session = AuthSession(
        id=generate_id(),
        user_id=user_id,
        token_hash=token_hash,
        created_at=now,
        expires_at=expires_at,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    db.execute(
        """
        INSERT INTO auth_sessions (id, user_id, token_hash, created_at,
                                   expires_at, ip_address, user_agent)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session.id,
            session.user_id,
            session.token_hash,
            session.created_at,
            session.expires_at,
            session.ip_address,
            session.user_agent,
        ),
    )

    return session, token


def validate_session(db: Database, token: str) -> User | None:
    """Validate a session token and return the associated user.

    Args:
        db: Database connection
        token: Plain text session token

    Returns:
        User object or None if invalid/expired
    """
    token_hash = _hash_token(token)
    now = datetime.utcnow()

    row = db.execute_one(
        """
        SELECT s.*, u.* FROM auth_sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token_hash = ? AND s.expires_at > ?
        """,
        (token_hash, now),
    )

    if not row:
        return None

    return User(
        id=row["user_id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        must_change_password=bool(row["must_change_password"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def delete_session(db: Database, token: str) -> bool:
    """Delete a session (logout).

    Args:
        db: Database connection
        token: Plain text session token

    Returns:
        True if session was deleted, False if not found
    """
    token_hash = _hash_token(token)
    rowcount = db.execute_update("DELETE FROM auth_sessions WHERE token_hash = ?", (token_hash,))
    return rowcount > 0


def delete_user_sessions(db: Database, user_id: str) -> int:
    """Delete all sessions for a user.

    Args:
        db: Database connection
        user_id: User UUID

    Returns:
        Number of sessions deleted
    """
    return db.execute_update("DELETE FROM auth_sessions WHERE user_id = ?", (user_id,))


def cleanup_expired_sessions(db: Database) -> int:
    """Remove expired sessions from the database.

    Args:
        db: Database connection

    Returns:
        Number of sessions cleaned up
    """
    now = datetime.utcnow()
    return db.execute_update("DELETE FROM auth_sessions WHERE expires_at <= ?", (now,))


# =============================================================================
# API Key Management
# =============================================================================


def create_api_key(
    db: Database,
    user_id: str,
    name: str,
    expires_at: Optional[datetime] = None,
) -> ApiKeyWithPlaintext | dict:
    """Create a new API key for a user.

    Args:
        db: Database connection
        user_id: User UUID
        name: Descriptive name for the key
        expires_at: Optional expiration datetime

    Returns:
        ApiKeyWithPlaintext (includes one-time visible key) or error dict
    """
    # Verify user exists
    user = get_user(db, user_id=user_id)
    if user is None:
        return {
            "error": "User not found",
            "error_code": "NOT_FOUND",
        }
    if isinstance(user, dict):
        return user

    plaintext_key = generate_api_key()
    key_hash = _hash_token(plaintext_key)
    now = datetime.utcnow()

    api_key = ApiKey(
        id=generate_id(),
        user_id=user_id,
        key_hash=key_hash,
        name=name,
        created_at=now,
        last_used_at=None,
        expires_at=expires_at,
        is_active=True,
    )

    db.execute(
        """
        INSERT INTO api_keys (id, user_id, key_hash, name, created_at,
                             last_used_at, expires_at, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            api_key.id,
            api_key.user_id,
            api_key.key_hash,
            api_key.name,
            api_key.created_at,
            api_key.last_used_at,
            api_key.expires_at,
            api_key.is_active,
        ),
    )

    return ApiKeyWithPlaintext(
        id=api_key.id,
        user_id=api_key.user_id,
        name=api_key.name,
        created_at=api_key.created_at,
        last_used_at=api_key.last_used_at,
        expires_at=api_key.expires_at,
        is_active=api_key.is_active,
        plaintext_key=plaintext_key,
    )


def validate_api_key(db: Database, key: str) -> User | None:
    """Validate an API key and return the associated user.

    Also updates the last_used_at timestamp.

    Args:
        db: Database connection
        key: Plain text API key

    Returns:
        User object or None if invalid/expired/inactive
    """
    key_hash = _hash_token(key)
    now = datetime.utcnow()

    row = db.execute_one(
        """
        SELECT k.*, u.* FROM api_keys k
        JOIN users u ON k.user_id = u.id
        WHERE k.key_hash = ?
          AND k.is_active = TRUE
          AND (k.expires_at IS NULL OR k.expires_at > ?)
        """,
        (key_hash, now),
    )

    if not row:
        return None

    # Update last_used_at
    db.execute(
        "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
        (now, row["id"]),
    )

    return User(
        id=row["user_id"],
        username=row["username"],
        email=row["email"],
        password_hash=row["password_hash"],
        is_admin=bool(row["is_admin"]),
        must_change_password=bool(row["must_change_password"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_user_api_keys(db: Database, user_id: str) -> list[ApiKeyPublic]:
    """Get all API keys for a user (without hashes).

    Args:
        db: Database connection
        user_id: User UUID

    Returns:
        List of ApiKeyPublic objects
    """
    rows = db.execute(
        """
        SELECT id, user_id, name, created_at, last_used_at, expires_at, is_active
        FROM api_keys
        WHERE user_id = ?
        ORDER BY created_at DESC
        """,
        (user_id,),
    )

    return [
        ApiKeyPublic(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
            expires_at=row["expires_at"],
            is_active=bool(row["is_active"]),
        )
        for row in rows
    ]


def revoke_api_key(db: Database, key_id: str, user_id: str) -> dict:
    """Revoke (deactivate) an API key.

    Args:
        db: Database connection
        key_id: API key UUID
        user_id: User UUID (for verification)

    Returns:
        Success or error dict
    """
    row = db.execute_one(
        "SELECT * FROM api_keys WHERE id = ? AND user_id = ?",
        (key_id, user_id),
    )

    if not row:
        return {
            "error": "API key not found",
            "error_code": "NOT_FOUND",
        }

    db.execute(
        "UPDATE api_keys SET is_active = FALSE WHERE id = ?",
        (key_id,),
    )

    return {"success": True, "message": "API key revoked"}


def delete_api_key(db: Database, key_id: str, user_id: str) -> dict:
    """Permanently delete an API key.

    Args:
        db: Database connection
        key_id: API key UUID
        user_id: User UUID (for verification)

    Returns:
        Success or error dict
    """
    row = db.execute_one(
        "SELECT * FROM api_keys WHERE id = ? AND user_id = ?",
        (key_id, user_id),
    )

    if not row:
        return {
            "error": "API key not found",
            "error_code": "NOT_FOUND",
        }

    db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))

    return {"success": True, "message": "API key deleted"}
