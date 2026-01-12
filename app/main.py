import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from app.core.error_handler import global_exception_handler
from app.core.response_interceptor import (
    SuccessResponseInterceptor,
    CustomAPIRoute,
)
from app.core.config import config
from app.core.backup import create_daily_backup, get_backup_manager
from app.modules.users import router as users_router
from app.modules.products import router as products_router
from app.modules.containers import router as containers_router
from app.modules.container_products import router as container_products_router
from app.modules.contacts import router as contacts_router
from app.modules.transactions import router as transactions_router
from app.modules.inventory_logs import router as inventory_logs_router
from app.modules.payments import router as payments_router
from app.modules.users.auth import get_current_user
from app.modules.users.models import User, Role

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Set logger for your app
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    - On startup: Create a daily backup (SQLite only)
    - On shutdown: Clean up resources
    """
    logger.info("Starting MyStock API...")
    
    # Create daily backup on startup (SQLite only)
    if config.is_sqlite:
        logger.info(f"Using SQLite database: {config.sqlite_db_path}")
        try:
            backup_path = await create_daily_backup()
            if backup_path:
                logger.info(f"Startup backup created: {backup_path}")
        except Exception as e:
            logger.warning(f"Startup backup failed (non-fatal): {e}")
    else:
        logger.info("Using PostgreSQL database")
    
    yield  # App runs here
    
    # Cleanup on shutdown
    logger.info("Shutting down MyStock API...")


app = FastAPI(
    title="MyStock API",
    description="Inventory management system with SQLite backend",
    version="1.0.0",
    lifespan=lifespan,
)

# Override the default route class to support skip_interceptor decorator
app.router.route_class = CustomAPIRoute

# Add global exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Middlewares
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://mayuragency.surge.sh",
    "https://mystockapp.duckdns.org",
    "https://kraftculture.surge.sh",  # production frontend
    "https://adminstock.duckdns.org",  # production API (for same-origin)
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Success Response Interceptor (must be added after CORS)
app.add_middleware(SuccessResponseInterceptor)

# Include routers with /api prefix
app.include_router(users_router, prefix="/api")
app.include_router(products_router, prefix="/api")
app.include_router(containers_router, prefix="/api")
app.include_router(container_products_router, prefix="/api")
app.include_router(contacts_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(inventory_logs_router, prefix="/api")
app.include_router(payments_router, prefix="/api")


@app.get("/demo")
async def demo() -> dict[str, str]:
    return {"message": "Hello World"}


# =============================================================================
# Admin Backup Endpoints (SQLite only, requires ADMIN role)
# =============================================================================

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that requires ADMIN role."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@app.get("/api/admin/backup", tags=["Admin"])
async def create_backup(admin: User = Depends(require_admin)):
    """
    Create a new database backup (SQLite only).
    Returns backup metadata.
    """
    if not config.is_sqlite:
        raise HTTPException(status_code=400, detail="Backups only available for SQLite")
    
    manager = get_backup_manager()
    backup_path = manager.create_backup(suffix="manual")
    info = manager.get_backup_info(backup_path)
    
    return {"message": "Backup created successfully", "backup": info}


@app.get("/api/admin/backup/list", tags=["Admin"])
async def list_backups(admin: User = Depends(require_admin)):
    """
    List all available backups (SQLite only).
    """
    if not config.is_sqlite:
        raise HTTPException(status_code=400, detail="Backups only available for SQLite")
    
    manager = get_backup_manager()
    backups = manager.list_backups()
    
    return {
        "backups": [manager.get_backup_info(b) for b in backups[:20]]  # Limit to 20
    }


@app.get("/api/admin/backup/download", tags=["Admin"])
async def download_backup(admin: User = Depends(require_admin)):
    """
    Create and download a fresh database backup (SQLite only).
    Returns the backup file for download.
    """
    if not config.is_sqlite:
        raise HTTPException(status_code=400, detail="Backups only available for SQLite")
    
    manager = get_backup_manager()
    backup_path = manager.create_backup(suffix="download")
    
    return FileResponse(
        path=str(backup_path),
        filename=backup_path.name,
        media_type="application/x-sqlite3",
    )


@app.get("/api/admin/db/info", tags=["Admin"])
async def database_info(admin: User = Depends(require_admin)):
    """
    Get database information and statistics.
    """
    info = {
        "type": "sqlite" if config.is_sqlite else "postgresql",
        "url_prefix": config.database_url.split(":")[0] if config.database_url else None,
    }
    
    if config.is_sqlite and config.sqlite_db_path:
        db_path = config.sqlite_db_path
        if db_path.exists():
            stat = db_path.stat()
            info["path"] = str(db_path)
            info["size_mb"] = round(stat.st_size / (1024 * 1024), 2)
            
            # Check for WAL file
            wal_path = db_path.with_suffix(".db-wal")
            if wal_path.exists():
                info["wal_size_mb"] = round(wal_path.stat().st_size / (1024 * 1024), 2)
    
    return info
