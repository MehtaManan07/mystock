"""
SQLite Backup Utilities

Provides WAL-safe backup functionality for SQLite databases.
Uses SQLite's Online Backup API for consistent backups even during active writes.

Key features:
- WAL-safe: Backups are consistent even with concurrent writes
- Atomic: Uses SQLite's backup API, not file copy
- Retention: Automatic cleanup of old backups
- Restore: Simple restore from backup file
"""

import sqlite3
import shutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List

from app.core.config import config

logger = logging.getLogger(__name__)


class BackupManager:
    """
    Manages SQLite database backups with WAL-safe operations.
    
    Usage:
        manager = BackupManager()
        backup_path = manager.create_backup()
        manager.restore_from_backup(backup_path)
    """
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        backup_dir: Optional[Path] = None,
        retention_days: int = 7
    ):
        """
        Initialize backup manager.
        
        Args:
            db_path: Path to SQLite database (default: from config)
            backup_dir: Directory for backups (default: from config)
            retention_days: Days to keep backups (default: 7)
        """
        self.db_path = db_path or config.sqlite_db_path
        self.backup_dir = Path(backup_dir or config.backup_dir)
        self.retention_days = retention_days
        
        if not self.db_path:
            raise ValueError("No SQLite database path configured. Is DB_URL set correctly?")
        
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, suffix: str = "") -> Path:
        """
        Create a WAL-safe backup of the SQLite database.
        
        Uses SQLite's backup API which is safe for databases in WAL mode.
        The backup is atomic and consistent even during active writes.
        
        Args:
            suffix: Optional suffix for backup filename
            
        Returns:
            Path to the created backup file
        """
        if not self.db_path or not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix_str = f"_{suffix}" if suffix else ""
        backup_name = f"inventory_backup_{timestamp}{suffix_str}.db"
        backup_path = self.backup_dir / backup_name
        
        logger.info(f"Creating backup: {backup_path}")
        
        try:
            # Use SQLite's backup API for WAL-safe backup
            # This is the recommended way to backup SQLite databases
            source = sqlite3.connect(str(self.db_path))
            dest = sqlite3.connect(str(backup_path))
            
            with dest:
                source.backup(dest, pages=100, progress=self._backup_progress)
            
            source.close()
            dest.close()
            
            logger.info(f"Backup created successfully: {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            # Clean up partial backup
            if backup_path.exists():
                backup_path.unlink()
            raise
    
    def _backup_progress(self, status: int, remaining: int, total: int) -> None:
        """Log backup progress."""
        if total > 0:
            progress = (total - remaining) / total * 100
            logger.debug(f"Backup progress: {progress:.1f}%")
    
    def restore_from_backup(self, backup_path: Path, target_path: Optional[Path] = None) -> Path:
        """
        Restore database from a backup file.
        
        WARNING: This will overwrite the current database!
        
        Args:
            backup_path: Path to the backup file
            target_path: Where to restore (default: original db location)
            
        Returns:
            Path to the restored database
        """
        backup_path = Path(backup_path)
        target_path = Path(target_path or self.db_path)
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        logger.warning(f"Restoring database from {backup_path} to {target_path}")
        
        # Create a backup of current state before restore
        if target_path.exists():
            pre_restore_backup = target_path.with_suffix(".pre_restore.db")
            shutil.copy2(target_path, pre_restore_backup)
            logger.info(f"Pre-restore backup saved: {pre_restore_backup}")
        
        # Perform restore using SQLite backup API
        source = sqlite3.connect(str(backup_path))
        dest = sqlite3.connect(str(target_path))
        
        with dest:
            source.backup(dest)
        
        source.close()
        dest.close()
        
        # Also remove any WAL/SHM files from previous state
        for ext in ["-wal", "-shm"]:
            wal_file = Path(str(target_path) + ext)
            if wal_file.exists():
                wal_file.unlink()
        
        logger.info(f"Database restored successfully to {target_path}")
        return target_path
    
    def list_backups(self) -> List[Path]:
        """
        List all available backup files, sorted by date (newest first).
        
        Returns:
            List of backup file paths
        """
        backups = list(self.backup_dir.glob("inventory_backup_*.db"))
        # Sort by modification time, newest first
        backups.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return backups
    
    def cleanup_old_backups(self) -> int:
        """
        Remove backups older than retention_days.
        
        Returns:
            Number of backups removed
        """
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        removed = 0
        
        for backup in self.list_backups():
            mtime = datetime.fromtimestamp(backup.stat().st_mtime)
            if mtime < cutoff:
                logger.info(f"Removing old backup: {backup}")
                backup.unlink()
                removed += 1
        
        if removed:
            logger.info(f"Cleaned up {removed} old backup(s)")
        
        return removed
    
    def get_backup_info(self, backup_path: Path) -> dict:
        """
        Get information about a backup file.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Dictionary with backup metadata
        """
        backup_path = Path(backup_path)
        
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        
        stat = backup_path.stat()
        
        # Try to get table counts from backup
        table_counts = {}
        try:
            conn = sqlite3.connect(str(backup_path))
            cursor = conn.cursor()
            
            # Get list of tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'")
            tables = cursor.fetchall()
            
            for (table_name,) in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                table_counts[table_name] = count
            
            conn.close()
        except Exception as e:
            logger.warning(f"Could not read backup contents: {e}")
        
        return {
            "path": str(backup_path),
            "filename": backup_path.name,
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "table_counts": table_counts,
        }


# Global backup manager instance
backup_manager: Optional[BackupManager] = None


def get_backup_manager() -> BackupManager:
    """
    Get or create the global backup manager instance.
    Only works when using SQLite database.
    """
    global backup_manager
    
    if not config.is_sqlite:
        raise RuntimeError("Backup manager is only available for SQLite databases")
    
    if backup_manager is None:
        backup_manager = BackupManager()
    
    return backup_manager


async def create_daily_backup() -> Optional[Path]:
    """
    Create a daily backup and clean up old ones.
    Suitable for calling from a startup hook or scheduled task.
    
    Returns:
        Path to backup if created, None if not using SQLite
    """
    if not config.is_sqlite:
        logger.info("Skipping backup - not using SQLite")
        return None
    
    try:
        manager = get_backup_manager()
        backup_path = manager.create_backup(suffix="daily")
        manager.cleanup_old_backups()
        return backup_path
    except Exception as e:
        logger.error(f"Daily backup failed: {e}")
        return None
