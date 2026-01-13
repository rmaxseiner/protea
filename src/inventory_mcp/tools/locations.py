"""Location management tools for inventory-mcp."""

from datetime import datetime

from inventory_mcp.db.connection import Database
from inventory_mcp.db.models import Location


def get_locations(db: Database) -> list[Location]:
    """List all locations.

    Args:
        db: Database connection

    Returns:
        List of all locations
    """
    rows = db.execute(
        "SELECT * FROM locations ORDER BY name"
    )
    return [
        Location(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        for row in rows
    ]


def get_location(
    db: Database,
    location_id: str | None = None,
    name: str | None = None,
) -> Location | dict:
    """Get a location by ID or name.

    Args:
        db: Database connection
        location_id: Location UUID
        name: Location name

    Returns:
        Location or error dict
    """
    if location_id:
        row = db.execute_one(
            "SELECT * FROM locations WHERE id = ?",
            (location_id,),
        )
    elif name:
        row = db.execute_one(
            "SELECT * FROM locations WHERE name = ?",
            (name,),
        )
    else:
        return {
            "error": "Must provide either location_id or name",
            "error_code": "INVALID_INPUT",
        }

    if not row:
        return {
            "error": f"Location not found",
            "error_code": "NOT_FOUND",
        }

    return Location(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_location(
    db: Database,
    name: str,
    description: str | None = None,
) -> Location | dict:
    """Create a new location.

    Args:
        db: Database connection
        name: Location name (must be unique)
        description: Optional description

    Returns:
        Created Location or error dict
    """
    # Check for duplicate name
    existing = db.execute_one(
        "SELECT id FROM locations WHERE name = ?",
        (name,),
    )
    if existing:
        return {
            "error": f"Location with name '{name}' already exists",
            "error_code": "ALREADY_EXISTS",
        }

    location = Location(name=name, description=description)

    with db.connection() as conn:
        conn.execute(
            """
            INSERT INTO locations (id, name, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                location.id,
                location.name,
                location.description,
                location.created_at.isoformat(),
                location.updated_at.isoformat(),
            ),
        )

    return location


def update_location(
    db: Database,
    location_id: str,
    name: str | None = None,
    description: str | None = None,
) -> Location | dict:
    """Update a location.

    Args:
        db: Database connection
        location_id: Location UUID
        name: New name (optional)
        description: New description (optional)

    Returns:
        Updated Location or error dict
    """
    # Get existing location
    row = db.execute_one(
        "SELECT * FROM locations WHERE id = ?",
        (location_id,),
    )
    if not row:
        return {
            "error": "Location not found",
            "error_code": "NOT_FOUND",
            "details": {"location_id": location_id},
        }

    # Check for name conflict if changing name
    if name and name != row["name"]:
        existing = db.execute_one(
            "SELECT id FROM locations WHERE name = ? AND id != ?",
            (name, location_id),
        )
        if existing:
            return {
                "error": f"Location with name '{name}' already exists",
                "error_code": "ALREADY_EXISTS",
            }

    # Build update
    new_name = name if name is not None else row["name"]
    new_description = description if description is not None else row["description"]
    updated_at = datetime.utcnow()

    with db.connection() as conn:
        conn.execute(
            """
            UPDATE locations
            SET name = ?, description = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_name, new_description, updated_at.isoformat(), location_id),
        )

    return Location(
        id=location_id,
        name=new_name,
        description=new_description,
        created_at=row["created_at"],
        updated_at=updated_at,
    )


def delete_location(db: Database, location_id: str) -> dict:
    """Delete a location.

    Fails if the location has bins.

    Args:
        db: Database connection
        location_id: Location UUID

    Returns:
        Success/error dict
    """
    # Check location exists
    row = db.execute_one(
        "SELECT * FROM locations WHERE id = ?",
        (location_id,),
    )
    if not row:
        return {
            "error": "Location not found",
            "error_code": "NOT_FOUND",
            "details": {"location_id": location_id},
        }

    # Check for bins
    bin_count = db.execute_one(
        "SELECT COUNT(*) as cnt FROM bins WHERE location_id = ?",
        (location_id,),
    )
    if bin_count and bin_count["cnt"] > 0:
        return {
            "success": False,
            "error": f"Cannot delete location with {bin_count['cnt']} bins. Remove bins first.",
            "error_code": "HAS_DEPENDENCIES",
            "details": {"bin_count": bin_count["cnt"]},
        }

    with db.connection() as conn:
        conn.execute("DELETE FROM locations WHERE id = ?", (location_id,))

    return {
        "success": True,
        "message": f"Location '{row['name']}' deleted",
    }
