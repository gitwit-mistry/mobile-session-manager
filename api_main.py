"""
Mobile Agent Session Manager - Full API with Session Lifecycle
Combines Part 1 (Emulator Orchestration) with Part 2 (Session Management)
"""
from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio

from pool_manager import EmulatorPool
from models import init_db
from session_api import router as session_router
from session_monitor import start_monitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown
    Replaces deprecated @app.on_event
    """
    # Startup
    print("🚀 Starting Mobile Agent Session Manager...")

    # Initialize database
    await init_db()
    print("✓ Database initialized")

    # Initialize emulator pool
    pool = EmulatorPool(pool_size=1, avd_name="test_avd")
    app.state.pool = pool
    asyncio.create_task(pool.initialize())
    print("✓ Emulator pool initializing...")

    # Start session health monitor
    monitor = await start_monitor(pool)
    app.state.monitor = monitor
    print("✓ Session health monitor started")

    yield

    # Shutdown
    print("🛑 Shutting down...")
    if hasattr(app.state, 'monitor'):
        await app.state.monitor.stop()


app = FastAPI(
    title="Mobile Agent Session Manager",
    version="2.0.0",
    description="Emulator orchestration + session lifecycle management",
    lifespan=lifespan
)

# Include session API routes
app.include_router(session_router)


# Original emulator management endpoints (Part 1)
from api_emulator_only import (
    create_emulator, get_emulator_status, create_snapshot,
    delete_emulator, get_pool_stats, health_check, root
)

# Re-register Part 1 endpoints
app.add_api_route("/", root, methods=["GET"])
app.add_api_route("/emulators", create_emulator, methods=["POST"])
app.add_api_route("/emulators/{emulator_id}/status", get_emulator_status, methods=["GET"])
app.add_api_route("/emulators/{emulator_id}/snapshot", create_snapshot, methods=["POST"])
app.add_api_route("/emulators/{emulator_id}", delete_emulator, methods=["DELETE"])
app.add_api_route("/pool/stats", get_pool_stats, methods=["GET"])
app.add_api_route("/health", health_check, methods=["GET"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
