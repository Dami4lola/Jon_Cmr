"""
OBATEK FastAPI Application Entry Point
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os

from .config import settings
from .database import create_db_and_tables
from .seed import seed_roles
from .middleware import LoggingMiddleware, register_exception_handlers

logger = logging.getLogger(__name__)

# Import routers
from .api import auth, jobs, timesheets, invoices, purchases, inspections, workers, clients, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup: create tables and seed data
    create_db_and_tables()
    seed_roles()

    # Log bcrypt version for debugging password issues
    try:
        import bcrypt
        logger.info(f"bcrypt version: {bcrypt.__version__}")
    except Exception as e:
        logger.warning(f"Could not detect bcrypt version: {e}")

    # Create upload directories
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "receipts"), exist_ok=True)
    os.makedirs(os.path.join(settings.UPLOAD_DIR, "inspections"), exist_ok=True)

    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="OBATEK API",
    description="Worker Portal API for timesheet management, invoicing, and job scheduling",
    version="1.0.0",
    lifespan=lifespan,
)

# Register exception handlers
register_exception_handlers(app)

# Add middleware
app.add_middleware(LoggingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for uploads
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(workers.router, prefix="/api/workers", tags=["Workers"])
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(timesheets.router, prefix="/api/timesheets", tags=["Timesheets"])
app.include_router(invoices.router, prefix="/api/invoices", tags=["Invoices"])
app.include_router(purchases.router, prefix="/api/purchases", tags=["Purchase List"])
app.include_router(inspections.router, prefix="/api/inspections", tags=["Inspections"])
app.include_router(users.router, prefix="/api/users", tags=["User Management"])


@app.get("/")
def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "OBATEK API"}


@app.get("/api/health")
def health_check():
    """API health check"""
    return {"status": "ok"}
