"""
Emulator Pool Manager - maintains warm pool of ready emulators
"""
import asyncio
from typing import Optional
from emulator_manager import EmulatorManager, AndroidEmulator, EmulatorState


class EmulatorPool:
    """Manages a warm pool of ready-to-use emulators"""

    def __init__(self, pool_size: int = 1, avd_name: str = "test_avd"):
        self.pool_size = pool_size
        self.avd_name = avd_name
        self.manager = EmulatorManager(pool_size=pool_size)
        self.warm_pool: list[str] = []  # IDs of ready, unassigned emulators
        self.assigned: dict[str, str] = {}  # emulator_id -> user_id mapping
        self._initialized = False
        self._initializing = False

    async def initialize(self):
        """Initialize the warm pool"""
        if self._initialized or self._initializing:
            return

        self._initializing = True
        print(f"Initializing warm pool with {self.pool_size} emulators...")

        # Start health check loop in background
        asyncio.create_task(self.manager.health_check_loop())

        # Create initial warm pool sequentially to avoid overwhelming the system
        for i in range(self.pool_size):
            try:
                print(f"Creating warm emulator {i+1}/{self.pool_size}...")
                emulator = await self.manager.create_emulator(self.avd_name)
                self.warm_pool.append(emulator.id)
                print(f"✓ Warm emulator ready: {emulator.id}")
            except Exception as e:
                print(f"✗ Failed to create warm emulator {i+1}: {e}")

        self._initialized = True
        print(f"Pool initialized with {len(self.warm_pool)} ready emulators")

    async def assign_emulator(self, user_id: str, snapshot: Optional[str] = None) -> Optional[AndroidEmulator]:
        """
        Assign an emulator to a user. If snapshot is provided, boot from that snapshot.
        If pool is exhausted, provision on-demand.
        """
        if not self._initialized:
            await self.initialize()

        # Try to get from warm pool first
        if self.warm_pool:
            emulator_id = self.warm_pool.pop(0)
            emulator = self.manager.emulators[emulator_id]

            # If snapshot requested, restart with snapshot
            if snapshot:
                await emulator.stop()
                await emulator.start(snapshot)

            self.assigned[emulator_id] = user_id
            print(f"Assigned {emulator_id} to user {user_id}")

            # Replenish pool in background
            asyncio.create_task(self._replenish_pool())

            return emulator

        # Pool exhausted - provision on demand
        print(f"Pool exhausted, provisioning on-demand for user {user_id}")
        try:
            emulator = await self.manager.create_emulator(self.avd_name, snapshot)
            self.assigned[emulator.id] = user_id
            return emulator
        except Exception as e:
            print(f"On-demand provisioning failed: {e}")
            return None

    async def release_emulator(self, emulator_id: str):
        """Release an emulator back to the warm pool"""
        if emulator_id not in self.assigned:
            return

        del self.assigned[emulator_id]

        # Check if emulator is healthy
        emulator = self.manager.emulators.get(emulator_id)
        if emulator and emulator.state == EmulatorState.READY:
            # Return to warm pool if we're below target size
            if len(self.warm_pool) < self.pool_size:
                self.warm_pool.append(emulator_id)
                print(f"Returned {emulator_id} to warm pool")
            else:
                # Destroy if pool is full
                await self.manager.destroy_emulator(emulator_id)
                print(f"Destroyed excess emulator {emulator_id}")
        else:
            # Destroy unhealthy emulator
            await self.manager.destroy_emulator(emulator_id)

    async def _replenish_pool(self):
        """Replenish the warm pool to target size"""
        # Count booting emulators (not yet in warm pool)
        booting_count = sum(
            1 for emu in self.manager.emulators.values()
            if emu.state == EmulatorState.BOOTING and emu.id not in self.assigned
        )

        needed = self.pool_size - len(self.warm_pool) - booting_count

        if needed <= 0:
            return  # Already have enough (ready + booting)

        for _ in range(needed):
            try:
                emulator = await self.manager.create_emulator(self.avd_name)
                self.warm_pool.append(emulator.id)
                print(f"Replenished pool with {emulator.id}")
            except Exception as e:
                print(f"Failed to replenish pool: {e}")
                break

    def get_pool_stats(self) -> dict:
        """Get pool statistics"""
        total = len(self.manager.emulators)
        warm = len(self.warm_pool)
        assigned_count = len(self.assigned)

        return {
            "pool_size": self.pool_size,
            "total_emulators": total,
            "warm_available": warm,
            "assigned": assigned_count,
            "emulators": self.manager.list_emulators()
        }
