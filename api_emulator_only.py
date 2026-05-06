"""
REST API for Mobile Agent Session Manager
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
import asyncio

from pool_manager import EmulatorPool

app = FastAPI(title="Mobile Agent Session Manager")

# Global pool instance
pool: Optional[EmulatorPool] = None


class CreateEmulatorRequest(BaseModel):
    avd_name: Optional[str] = "test_avd"
    snapshot: Optional[str] = None
    user_id: Optional[str] = "default_user"


class SnapshotRequest(BaseModel):
    snapshot_name: str


@app.on_event("startup")
async def startup():
    """Initialize the emulator pool on startup"""
    global pool
    # Reduced pool_size to 1 for Mac M4 (no KVM acceleration)
    pool = EmulatorPool(pool_size=1, avd_name="test_avd")
    # Initialize in background
    asyncio.create_task(pool.initialize())


@app.get("/")
async def root():
    return {
        "service": "Mobile Agent Session Manager",
        "version": "0.1.0",
        "status": "running"
    }


@app.post("/emulators")
async def create_emulator(request: CreateEmulatorRequest):
    """
    Provision an emulator from the pool or on-demand.
    Optionally boot from a snapshot.
    """
    if not pool:
        raise HTTPException(status_code=503, detail="Pool not initialized")

    emulator = await pool.assign_emulator(
        user_id=request.user_id,
        snapshot=request.snapshot
    )

    if not emulator:
        raise HTTPException(status_code=500, detail="Failed to provision emulator")

    return {
        "id": emulator.id,
        "serial": emulator.serial,
        "port": emulator.port,
        "state": emulator.state,
        "user_id": request.user_id
    }


@app.get("/emulators/{emulator_id}/status")
async def get_emulator_status(emulator_id: str):
    """Get the status of a specific emulator"""
    if not pool:
        raise HTTPException(status_code=503, detail="Pool not initialized")

    status = await pool.manager.get_status(emulator_id)

    if "error" in status:
        raise HTTPException(status_code=404, detail="Emulator not found")

    return status


@app.post("/emulators/{emulator_id}/snapshot")
async def create_snapshot(emulator_id: str, request: SnapshotRequest):
    """Create a snapshot of the emulator's current state"""
    if not pool:
        raise HTTPException(status_code=503, detail="Pool not initialized")

    if emulator_id not in pool.manager.emulators:
        raise HTTPException(status_code=404, detail="Emulator not found")

    emulator = pool.manager.emulators[emulator_id]
    success = await emulator.create_snapshot(request.snapshot_name)

    if not success:
        raise HTTPException(status_code=500, detail="Snapshot creation failed")

    return {
        "emulator_id": emulator_id,
        "snapshot_name": request.snapshot_name,
        "status": "created"
    }


@app.delete("/emulators/{emulator_id}")
async def delete_emulator(emulator_id: str):
    """Release/destroy an emulator"""
    if not pool:
        raise HTTPException(status_code=503, detail="Pool not initialized")

    if emulator_id not in pool.manager.emulators:
        raise HTTPException(status_code=404, detail="Emulator not found")

    await pool.release_emulator(emulator_id)

    return {
        "emulator_id": emulator_id,
        "status": "released"
    }


@app.get("/pool/stats")
async def get_pool_stats():
    """Get statistics about the emulator pool"""
    if not pool:
        raise HTTPException(status_code=503, detail="Pool not initialized")

    return pool.get_pool_stats()


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
