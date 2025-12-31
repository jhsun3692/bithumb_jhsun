"""Main FastAPI application."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import analytics, auth, web, ai_optimizer
from app.core.database import init_db
from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.services.scheduler import trading_scheduler

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

# Create FastAPI app
# Swagger/ReDoc는 enable_docs 설정에 따라 활성화/비활성화
app = FastAPI(
    title="Bithumb Auto Trading System",
    description="Cryptocurrency auto-trading system using Bithumb API",
    version="0.1.0",
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include API routers
app.include_router(analytics.router)
app.include_router(auth.router)
app.include_router(ai_optimizer.router)

# Include web page routers (must be last to avoid conflicts)
app.include_router(web.router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and start scheduler on startup."""
    logger.info("Starting application...")
    init_db()
    trading_scheduler.start()
    logger.info("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop scheduler on shutdown."""
    logger.info("Shutting down application...")
    trading_scheduler.stop()
    logger.info("Application stopped")


@app.get("/api")
async def api_root():
    """API root endpoint."""
    return {
        "message": "Bithumb Auto Trading System API",
        "version": "0.1.0",
        "docs": "/docs",
        "trading_enabled": settings.trading_enabled
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}