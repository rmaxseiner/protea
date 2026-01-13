"""SQLite database connection management for inventory-mcp."""

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger("inventory_mcp")


class Database:
    """SQLite database manager with migration support."""

    def __init__(self, db_path: Path | str):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Enable foreign keys and WAL mode
        self._init_connection()

    def _init_connection(self) -> None:
        """Initialize database with required settings."""
        with self.connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager for database connections.

        Yields:
            sqlite3.Connection with row factory set to sqlite3.Row
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def run_migrations(self) -> None:
        """Run all pending database migrations."""
        migrations_dir = Path(__file__).parent / "migrations"

        with self.connection() as conn:
            # Create schema_version table if not exists
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Get current version
            result = conn.execute(
                "SELECT MAX(version) as version FROM schema_version"
            ).fetchone()
            current_version = result["version"] or 0

            # Find and run pending migrations
            if migrations_dir.exists():
                migration_files = sorted(migrations_dir.glob("*.sql"))
                for migration_file in migration_files:
                    version = int(migration_file.stem.split("_")[0])
                    if version > current_version:
                        logger.info(f"Running migration {migration_file.name}")
                        sql = migration_file.read_text()
                        conn.executescript(sql)
                        logger.info(f"Migration {migration_file.name} completed")

    def execute(
        self, query: str, params: tuple = ()
    ) -> list[sqlite3.Row]:
        """Execute a query and return all results.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            List of Row objects
        """
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()

    def execute_one(
        self, query: str, params: tuple = ()
    ) -> sqlite3.Row | None:
        """Execute a query and return first result.

        Args:
            query: SQL query to execute
            params: Query parameters

        Returns:
            Single Row object or None
        """
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()

    def execute_insert(
        self, query: str, params: tuple = ()
    ) -> int:
        """Execute an insert query and return lastrowid.

        Args:
            query: SQL INSERT query
            params: Query parameters

        Returns:
            Last inserted row ID
        """
        with self.connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid

    def execute_many(
        self, query: str, params_list: list[tuple]
    ) -> int:
        """Execute a query multiple times with different params.

        Args:
            query: SQL query to execute
            params_list: List of parameter tuples

        Returns:
            Number of rows affected
        """
        with self.connection() as conn:
            cursor = conn.executemany(query, params_list)
            return cursor.rowcount
