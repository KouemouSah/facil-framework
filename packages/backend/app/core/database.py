"""
Database Compatibility Layer

This module provides backward compatibility for imports from app.core.database.
New code should import directly from app.database.connection.
"""

# Re-export everything from the actual database module
from app.database.connection import (
    db_manager,
    get_database,
    fetch_all,
    fetch_one,
    fetch_val,
    execute,
    DatabaseManager,
)

# Alias for backward compatibility
get_db_connection = get_database

__all__ = [
    "db_manager",
    "get_database",
    "get_db_connection",
    "fetch_all",
    "fetch_one",
    "fetch_val",
    "execute",
    "DatabaseManager",
]
