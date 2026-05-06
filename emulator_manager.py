"""
Simple Android Emulator Manager - POC
Manages Android emulator lifecycle with snapshot support
"""
import asyncio
import subprocess
import time
import os
from typing import Optional, Dict, List
from enum import Enum
import psutil


class EmulatorState(str, Enum):
    CREATING = "creating"
    BOOTING = "booting"
    READY = "ready"
    UNHEALTHY = "unhealthy"
    STOPPED = "stopped"


class AndroidEmulator:
    def __init__(self, emulator_id: str, avd_name: str, port: int):
        self.id = emulator_id
        self.avd_name = avd_name
        self.port = port
        self.state = EmulatorState.CREATING
        self.process: Optional[subprocess.Popen] = None
        self.created_at = time.time()
        self.last_health_check = 0

    @property
    def serial(self) -> str:
        """ADB serial identifier"""
        return f"emulator-{self.port}"

    async def start(self, snapshot: Optional[str] = None, boot_timeout: int = 180):
        """Start the emulator, optionally from a snapshot"""
        self.boot_timeout = boot_timeout
        cmd = [
            "emulator",
            "-avd", self.avd_name,
            "-port", str(self.port),
            "-no-window",
            "-no-audio",
            "-no-boot-anim",
            "-gpu", "swiftshader_indirect",
            "-memory", "2048",
            "-cores", "2",
        ]

        if snapshot:
            cmd.extend(["-snapshot", snapshot])

        self.state = EmulatorState.BOOTING
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for boot
        await self._wait_for_boot()

    async def _wait_for_boot(self, timeout: int = None):
        """Wait for emulator to finish booting"""
        if timeout is None:
            timeout = getattr(self, 'boot_timeout', 180)
        start_time = time.time()
        print(f"[{self.id}] Waiting for boot (timeout: {timeout}s)...")

        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(
                    ["adb", "-s", self.serial, "shell", "getprop", "sys.boot_completed"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.stdout.strip() == "1":
                    self.state = EmulatorState.READY
                    elapsed = time.time() - start_time
                    print(f"[{self.id}] Boot complete in {elapsed:.1f}s")
                    return

            except Exception:
                pass

            await asyncio.sleep(3)  # Check every 3 seconds

        self.state = EmulatorState.UNHEALTHY
        print(f"[{self.id}] Boot timeout after {timeout}s")
        raise TimeoutError(f"Emulator {self.id} failed to boot within {timeout}s")

    async def create_snapshot(self, snapshot_name: str):
        """Create a snapshot of current emulator state"""
        try:
            # Save snapshot via ADB console
            result = subprocess.run(
                ["adb", "-s", self.serial, "emu", "avd", "snapshot", "save", snapshot_name],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                return True

            return False

        except Exception as e:
            print(f"Snapshot creation failed: {e}")
            return False

    async def health_check(self) -> bool:
        """Check if emulator is healthy"""
        try:
            # Check process is alive
            if self.process and self.process.poll() is not None:
                self.state = EmulatorState.UNHEALTHY
                return False

            # Check ADB connectivity
            result = subprocess.run(
                ["adb", "-s", self.serial, "shell", "echo", "ping"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0 and "ping" in result.stdout:
                self.state = EmulatorState.READY
                self.last_health_check = time.time()
                return True

            self.state = EmulatorState.UNHEALTHY
            return False

        except Exception:
            self.state = EmulatorState.UNHEALTHY
            return False

    async def stop(self):
        """Stop the emulator"""
        try:
            subprocess.run(
                ["adb", "-s", self.serial, "emu", "kill"],
                timeout=10
            )
        except Exception:
            pass

        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=10)
            except Exception:
                self.process.kill()

        self.state = EmulatorState.STOPPED


class EmulatorManager:
    """Manages a pool of Android emulators"""

    def __init__(self, pool_size: int = 2, base_port: int = 5554):
        self.pool_size = pool_size
        self.base_port = base_port
        self.emulators: Dict[str, AndroidEmulator] = {}
        self.available_ports = list(range(base_port, base_port + 100, 2))
        self._next_id = 1

    def _get_next_port(self) -> int:
        """Get next available port"""
        if not self.available_ports:
            raise RuntimeError("No available ports")
        return self.available_ports.pop(0)

    def _release_port(self, port: int):
        """Release a port back to the pool"""
        if port not in self.available_ports:
            self.available_ports.append(port)
            self.available_ports.sort()

    async def create_emulator(
        self,
        avd_name: str = "test_avd",
        snapshot: Optional[str] = None
    ) -> AndroidEmulator:
        """Create and start a new emulator"""
        emulator_id = f"emu-{self._next_id}"
        self._next_id += 1

        port = self._get_next_port()
        emulator = AndroidEmulator(emulator_id, avd_name, port)

        self.emulators[emulator_id] = emulator

        try:
            await emulator.start(snapshot)
            return emulator
        except Exception as e:
            # Cleanup on failure
            await self.destroy_emulator(emulator_id)
            raise e

    async def destroy_emulator(self, emulator_id: str):
        """Stop and remove an emulator"""
        if emulator_id not in self.emulators:
            return

        emulator = self.emulators[emulator_id]
        await emulator.stop()

        self._release_port(emulator.port)
        del self.emulators[emulator_id]

    async def get_status(self, emulator_id: str) -> Dict:
        """Get emulator status"""
        if emulator_id not in self.emulators:
            return {"error": "Emulator not found"}

        emulator = self.emulators[emulator_id]
        return {
            "id": emulator.id,
            "state": emulator.state,
            "port": emulator.port,
            "serial": emulator.serial,
            "uptime": time.time() - emulator.created_at,
            "last_health_check": emulator.last_health_check
        }

    async def health_check_loop(self):
        """Background loop to check emulator health"""
        while True:
            for emulator_id, emulator in list(self.emulators.items()):
                if emulator.state == EmulatorState.READY:
                    healthy = await emulator.health_check()

                    if not healthy:
                        print(f"Emulator {emulator_id} unhealthy, replacing...")
                        avd_name = emulator.avd_name
                        await self.destroy_emulator(emulator_id)

                        # Auto-replace if we're below pool size
                        if len(self.emulators) < self.pool_size:
                            try:
                                await self.create_emulator(avd_name)
                            except Exception as e:
                                print(f"Failed to replace emulator: {e}")

            await asyncio.sleep(30)

    def list_emulators(self) -> List[Dict]:
        """List all emulators"""
        return [
            {
                "id": emu.id,
                "state": emu.state,
                "port": emu.port,
                "serial": emu.serial
            }
            for emu in self.emulators.values()
        ]
