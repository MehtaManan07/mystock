#!/usr/bin/env python3
"""
migrate_pg_to_sqlite.py - Safe PostgreSQL to SQLite Data Migration

This script safely migrates all data from PostgreSQL to SQLite with:
- Dry run mode for testing
- Row count validation
- Transaction safety with rollback
- Detailed logging
- Progress tracking

Usage:
    # Dry run (no changes made)
    python scripts/migrate_pg_to_sqlite.py --dry-run
    
    # Actual migration
    python scripts/migrate_pg_to_sqlite.py
    
    # With custom paths
    DB_URL="postgresql://..." python scripts/migrate_pg_to_sqlite.py --sqlite-path ./data/inventory.db

Requirements:
    pip install asyncpg
"""

import os
import sys
import sqlite3
import asyncio
import argparse
import logging
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg is required. Install with: pip install asyncpg")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Tables in dependency order (parents before children)
# This order ensures foreign key constraints are satisfied
TABLES = [
    "contacts",
    "container", 
    "product",
    "users",
    "container_product",
    "inventory_log",
    "transactions",
    "payments",
    "transaction_items",
]


def convert_value(value: Any) -> Any:
    """
    Convert PostgreSQL types to SQLite-compatible types.
    
    SQLite has limited types: NULL, INTEGER, REAL, TEXT, BLOB
    Python's sqlite3 module handles most conversions, but we need
    to handle some edge cases.
    """
    if value is None:
        return None
    
    # Decimal -> float (SQLite REAL)
    if isinstance(value, Decimal):
        return float(value)
    
    # Date -> ISO string (SQLite TEXT)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    
    # Datetime -> ISO string (SQLite TEXT)
    if isinstance(value, datetime):
        return value.isoformat()
    
    # UUID -> string
    if hasattr(value, 'hex'):  # UUID type
        return str(value)
    
    # Lists/dicts -> string (shouldn't happen, but safety)
    if isinstance(value, (list, dict)):
        import json
        return json.dumps(value)
    
    # Everything else passes through
    return value


async def get_pg_row_count(conn: asyncpg.Connection, table: str) -> int:
    """Get row count from PostgreSQL table."""
    return await conn.fetchval(f'SELECT COUNT(*) FROM "{table}"')


def get_sqlite_row_count(conn: sqlite3.Connection, table: str) -> int:
    """Get row count from SQLite table."""
    cursor = conn.execute(f'SELECT COUNT(*) FROM "{table}"')
    return cursor.fetchone()[0]


async def migrate_table(
    pg_conn: asyncpg.Connection,
    sqlite_conn: sqlite3.Connection,
    table: str,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Migrate a single table from PostgreSQL to SQLite.
    
    Returns:
        Dict with migration statistics
    """
    stats = {
        "table": table,
        "pg_count": 0,
        "migrated": 0,
        "sqlite_count": 0,
        "success": False,
        "error": None,
    }
    
    try:
        # Get PostgreSQL row count
        stats["pg_count"] = await get_pg_row_count(pg_conn, table)
        
        if stats["pg_count"] == 0:
            logger.info(f"  {table}: No data to migrate")
            stats["success"] = True
            return stats
        
        # Fetch all rows from PostgreSQL
        rows = await pg_conn.fetch(f'SELECT * FROM "{table}" ORDER BY id')
        
        if not rows:
            stats["success"] = True
            return stats
        
        # Get column names from first row
        columns = list(rows[0].keys())
        col_names = ", ".join([f'"{col}"' for col in columns])
        placeholders = ", ".join(["?" for _ in columns])
        
        insert_sql = f'INSERT INTO "{table}" ({col_names}) VALUES ({placeholders})'
        
        if dry_run:
            logger.info(f"  {table}: Would migrate {len(rows)} rows")
            stats["migrated"] = len(rows)
            stats["sqlite_count"] = len(rows)
            stats["success"] = True
            return stats
        
        # Insert rows into SQLite
        migrated = 0
        for row in rows:
            values = tuple(convert_value(row[col]) for col in columns)
            try:
                sqlite_conn.execute(insert_sql, values)
                migrated += 1
            except Exception as e:
                logger.error(f"  Failed to insert row {row.get('id', '?')}: {e}")
                logger.error(f"  Values: {values}")
                raise
        
        stats["migrated"] = migrated
        
        # Verify count
        stats["sqlite_count"] = get_sqlite_row_count(sqlite_conn, table)
        
        if stats["sqlite_count"] != stats["pg_count"]:
            raise ValueError(
                f"Count mismatch! PostgreSQL: {stats['pg_count']}, "
                f"SQLite: {stats['sqlite_count']}"
            )
        
        stats["success"] = True
        logger.info(f"  {table}: Migrated {migrated} rows ✓")
        
    except Exception as e:
        stats["error"] = str(e)
        logger.error(f"  {table}: FAILED - {e}")
    
    return stats


async def run_migration(
    pg_url: str,
    sqlite_path: Path,
    dry_run: bool = False,
    clear_existing: bool = False,
) -> bool:
    """
    Run the full migration from PostgreSQL to SQLite.
    
    Args:
        pg_url: PostgreSQL connection URL
        sqlite_path: Path to SQLite database file
        dry_run: If True, don't actually write to SQLite
        clear_existing: If True, clear existing data before migration
        
    Returns:
        True if migration succeeded, False otherwise
    """
    logger.info("=" * 60)
    logger.info("PostgreSQL to SQLite Migration")
    logger.info("=" * 60)
    logger.info(f"SQLite path: {sqlite_path}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")
    
    # Validate SQLite database exists
    if not sqlite_path.exists():
        logger.error(f"SQLite database not found: {sqlite_path}")
        logger.error("Run 'make migrate' first to create the schema.")
        return False
    
    # Convert async URL to sync URL for asyncpg
    pg_url_sync = pg_url.replace("postgresql+asyncpg://", "postgresql://")
    pg_url_sync = pg_url_sync.replace("postgresql+psycopg2://", "postgresql://")
    
    logger.info("Connecting to databases...")
    
    try:
        # Connect to PostgreSQL
        pg_conn = await asyncpg.connect(pg_url_sync)
        logger.info("  PostgreSQL: Connected ✓")
    except Exception as e:
        logger.error(f"  PostgreSQL: Failed to connect - {e}")
        return False
    
    try:
        # Connect to SQLite
        sqlite_conn = sqlite3.connect(str(sqlite_path))
        # Disable foreign keys during import for flexibility
        sqlite_conn.execute("PRAGMA foreign_keys = OFF")
        logger.info("  SQLite: Connected ✓")
        
        # Check if SQLite has existing data
        existing_data = False
        for table in TABLES:
            try:
                count = get_sqlite_row_count(sqlite_conn, table)
                if count > 0:
                    existing_data = True
                    break
            except:
                pass
        
        if existing_data and not clear_existing and not dry_run:
            logger.warning("")
            logger.warning("SQLite database already contains data!")
            logger.warning("Options:")
            logger.warning("  1. Run with --clear to delete existing data first")
            logger.warning("  2. Run 'make migrate-fresh' to reset the database")
            logger.warning("  3. Manually clear the data you want to replace")
            await pg_conn.close()
            sqlite_conn.close()
            return False
        
        if clear_existing and not dry_run:
            logger.info("")
            logger.info("Clearing existing SQLite data...")
            # Delete in reverse order (children before parents)
            for table in reversed(TABLES):
                try:
                    sqlite_conn.execute(f'DELETE FROM "{table}"')
                    logger.info(f"  Cleared {table}")
                except Exception as e:
                    logger.warning(f"  Could not clear {table}: {e}")
            sqlite_conn.commit()
        
        logger.info("")
        logger.info("Starting migration...")
        logger.info("-" * 40)
        
        # Begin transaction
        if not dry_run:
            sqlite_conn.execute("BEGIN TRANSACTION")
        
        all_stats = []
        success = True
        
        try:
            for table in TABLES:
                stats = await migrate_table(pg_conn, sqlite_conn, table, dry_run)
                all_stats.append(stats)
                
                if not stats["success"]:
                    success = False
                    break
            
            if success and not dry_run:
                sqlite_conn.execute("COMMIT")
                logger.info("")
                logger.info("Transaction committed ✓")
            elif not success and not dry_run:
                sqlite_conn.execute("ROLLBACK")
                logger.error("")
                logger.error("Transaction rolled back due to errors!")
                
        except Exception as e:
            if not dry_run:
                sqlite_conn.execute("ROLLBACK")
            logger.error(f"Migration failed: {e}")
            success = False
        
        # Re-enable foreign keys
        if not dry_run:
            sqlite_conn.execute("PRAGMA foreign_keys = ON")
        
        # Print summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("Migration Summary")
        logger.info("=" * 60)
        
        total_pg = sum(s["pg_count"] for s in all_stats)
        total_migrated = sum(s["migrated"] for s in all_stats)
        
        for stats in all_stats:
            status = "✓" if stats["success"] else "✗"
            logger.info(
                f"  {stats['table']:20} | "
                f"PG: {stats['pg_count']:6} | "
                f"Migrated: {stats['migrated']:6} | "
                f"{status}"
            )
        
        logger.info("-" * 60)
        logger.info(f"  {'TOTAL':20} | PG: {total_pg:6} | Migrated: {total_migrated:6}")
        logger.info("")
        
        if success:
            if dry_run:
                logger.info("DRY RUN COMPLETE - No changes were made")
                logger.info("Run without --dry-run to perform actual migration")
            else:
                logger.info("MIGRATION SUCCESSFUL!")
        else:
            logger.error("MIGRATION FAILED - See errors above")
        
        return success
        
    finally:
        await pg_conn.close()
        sqlite_conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate data from PostgreSQL to SQLite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Dry run (recommended first)
    python scripts/migrate_pg_to_sqlite.py --dry-run
    
    # Actual migration
    python scripts/migrate_pg_to_sqlite.py
    
    # Clear existing data and migrate
    python scripts/migrate_pg_to_sqlite.py --clear
    
    # Custom paths
    DB_URL="postgresql://..." python scripts/migrate_pg_to_sqlite.py
        """,
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Test migration without writing to SQLite",
    )
    
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing SQLite data before migration",
    )
    
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=PROJECT_ROOT / "data" / "inventory.db",
        help="Path to SQLite database (default: ./data/inventory.db)",
    )
    
    parser.add_argument(
        "--pg-url",
        type=str,
        default=os.getenv("DB_URL", ""),
        help="PostgreSQL URL (default: from DB_URL env var)",
    )
    
    args = parser.parse_args()
    
    # Validate PostgreSQL URL
    if not args.pg_url:
        logger.error("PostgreSQL URL required!")
        logger.error("Set DB_URL environment variable or use --pg-url")
        logger.error("")
        logger.error("Example:")
        logger.error('  DB_URL="postgresql://user:pass@host/db" python scripts/migrate_pg_to_sqlite.py')
        sys.exit(1)
    
    if not args.pg_url.startswith("postgresql"):
        logger.error(f"Invalid PostgreSQL URL: {args.pg_url}")
        logger.error("URL must start with 'postgresql://'")
        sys.exit(1)
    
    # Run migration
    success = asyncio.run(
        run_migration(
            pg_url=args.pg_url,
            sqlite_path=args.sqlite_path,
            dry_run=args.dry_run,
            clear_existing=args.clear,
        )
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
