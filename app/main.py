import logging
import sys
import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.error_handler import global_exception_handler
from app.core.db.engine import get_db_util
from app.core.config import config
from app.core.response_interceptor import SuccessResponseInterceptor, CustomAPIRoute, skip_interceptor
from app.modules.users import router as users_router
from app.modules.products import router as products_router

# Configure logging to output to console
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# Set logger for your app
logger = logging.getLogger(__name__)
logger.info("🚀 Starting MyStock API...")

app = FastAPI(
    title="MyStock API",
    description="A messaging and user management API",
    version="1.0.0",
)

# Override the default route class to support skip_interceptor decorator
app.router.route_class = CustomAPIRoute

# Add global exception handler
app.add_exception_handler(Exception, global_exception_handler)

# Middlewares
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Success Response Interceptor (must be added after CORS)
app.add_middleware(SuccessResponseInterceptor)

# Include routers
app.include_router(users_router)
app.include_router(products_router)


@app.get("/demo")
async def demo() -> dict[str, str]:
    return {"message": "Hello World"}


@app.get("/debug/config")
async def debug_config() -> dict:
    """Debug endpoint to check config values"""
    return {
        "pg_host": config.pg_host,
        "pg_port": config.pg_port,
        "pg_database": config.pg_database,
        "pg_user": config.pg_user,
        "database_url": config.database_url,
        "ssl_cert_exists": os.path.exists(config.pg_ssl_cert_path),
        "ssl_cert_path": config.pg_ssl_cert_path,
    }


@app.get("/health/db")
@skip_interceptor
async def health_check_db(db: AsyncSession = Depends(get_db_util)) -> dict:
    """
    Health check endpoint that tests database connectivity with a simple SQL query.
    This endpoint skips the response interceptor to maintain the original format.
    """
    try:
        # Simple SQL query to check database connection and get version
        result = await db.execute(text("SELECT version() as version, current_database() as database"))
        row = result.fetchone()
        
        return {
            "status": "healthy",
            "database": row.database if row else "unknown",
            "postgres_version": row.version.split(" ")[0] if row else "unknown",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
