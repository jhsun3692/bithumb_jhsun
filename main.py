"""Bithumb Auto Trading System - Main entry point."""
import uvicorn
from app.core.config import get_settings

settings = get_settings()


def main():
    """Run the FastAPI application."""
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )


if __name__ == "__main__":
    main()
