"""
EdgeTX Firmware Web Builder — FastAPI application entry point.

Run with:
    python webapp/main.py

Or from the project root:
    python -m webapp.main
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so that `webapp` package is importable
# when running as `python webapp/main.py` from the project root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import argparse

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from webapp.backend.routes import models, builds, config, artifacts, history, settings, health

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="EdgeTX Firmware Web Builder",
    description="Web UI for managing and triggering EdgeTX firmware builds.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Register API routers under /api prefix
app.include_router(models.router, prefix="/api")
app.include_router(builds.router, prefix="/api")
app.include_router(config.router, prefix="/api")
app.include_router(artifacts.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(health.router, prefix="/api")

# Serve frontend static files — must be mounted AFTER API routes
_FRONTEND_DIR = Path(__file__).resolve().parent / "frontend"
if _FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

# Loopback addresses that are safe to bind to without a warning.
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="EdgeTX Firmware Web Builder",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--debug", action="store_true", help="Enable debug/reload mode")
    args = parser.parse_args()

    # Security: warn loudly when the server is bound to a non-loopback address.
    # This application has no authentication and is designed for local use only.
    # Binding to 0.0.0.0 or any other non-loopback address exposes the build
    # system, firmware artifacts, and project configuration to every host on the
    # local network.
    if args.host not in _LOOPBACK_HOSTS:
        print(
            "\n"
            "WARNING: EdgeTX Firmware Web Builder is being started on a non-loopback address.\n"
            f"         Host: {args.host}  Port: {args.port}\n"
            "\n"
            "         This application has NO authentication. Any host that can reach\n"
            "         this address will be able to trigger firmware builds, read build\n"
            "         logs, download artifacts, and modify the radio model configuration.\n"
            "\n"
            "         Use --host 127.0.0.1 (the default) unless you fully understand\n"
            "         and accept this risk.\n",
            file=sys.stderr,
        )

    uvicorn.run(
        "webapp.main:app",
        host=args.host,
        port=args.port,
        reload=args.debug,
        log_level="info",
    )


if __name__ == "__main__":
    main()
