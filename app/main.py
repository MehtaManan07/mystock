import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.error_handler import global_exception_handler
from app.core.response_interceptor import (
    SuccessResponseInterceptor,
    CustomAPIRoute,
)
from app.modules.users import router as users_router
from app.modules.products import router as products_router
from app.modules.containers import router as containers_router
from app.modules.container_products import router as container_products_router
from app.modules.contacts import router as contacts_router
from app.modules.transactions import router as transactions_router
from app.modules.inventory_logs import router as inventory_logs_router
from app.modules.payments import router as payments_router

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
origins = [
    "http://localhost",
    "http://localhost:5173",
    "http://mayuragency.surge.sh",
    "https://mystockapp.duckdns.org",  # production
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
