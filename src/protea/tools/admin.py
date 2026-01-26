"""Admin utilities for bootstrapping and system management."""

import logging
import sys

from protea.config import auth_settings
from protea.db.connection import Database
from protea.tools import auth as auth_tools

logger = logging.getLogger("protea.admin")


def bootstrap_admin_user(db: Database) -> None:
    """Create admin user if no users exist.

    This is called during server startup to ensure an admin user exists
    for first-run authentication. If no users exist, creates an admin user
    with either the configured password or a randomly generated one.

    Args:
        db: Database connection instance
    """
    user_count = auth_tools.get_user_count(db)
    if user_count > 0:
        return

    # Generate or use provided password
    password = auth_settings.admin_password
    if not password:
        password = auth_tools.generate_random_password()

    result = auth_tools.create_user(
        db,
        username="admin",
        password=password,
        is_admin=True,
        must_change_password=True,
    )

    if isinstance(result, dict) and "error" in result:
        logger.error(f"Failed to create admin user: {result['error']}")
        return

    # Use print() to ensure this critical message is always visible in logs
    print("=" * 50, file=sys.stderr, flush=True)
    print("FIRST-RUN: Admin user created", file=sys.stderr, flush=True)
    print("Username: admin", file=sys.stderr, flush=True)
    print(f"Password: {password}", file=sys.stderr, flush=True)
    print("=" * 50, file=sys.stderr, flush=True)
