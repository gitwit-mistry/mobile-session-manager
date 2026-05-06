"""
Session Health Monitor - Background worker
Checks session health at configurable intervals based on tier
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    Session, SessionHealthCheck, SessionHealth, SessionTier,
    get_db, AsyncSessionLocal
)
from vision_classifier import check_session_health
from pool_manager import EmulatorPool


class SessionHealthMonitor:
    """
    Background worker that monitors session health
    - Hot tier: Check daily (24h)
    - Warm tier: Check weekly (7d)
    - Cold tier: Check on-demand only
    """

    def __init__(self, emulator_pool: EmulatorPool):
        self.pool = emulator_pool
        self.running = False

        # Check intervals per tier (in seconds)
        self.check_intervals = {
            SessionTier.HOT: 24 * 60 * 60,    # 24 hours
            SessionTier.WARM: 7 * 24 * 60 * 60,  # 7 days
            SessionTier.COLD: None,            # On-demand only
        }

        # For POC, use shorter intervals for testing
        self.test_mode = True
        if self.test_mode:
            self.check_intervals = {
                SessionTier.HOT: 60,      # 1 minute
                SessionTier.WARM: 300,    # 5 minutes
                SessionTier.COLD: None,   # On-demand
            }

    async def start(self):
        """Start the background health check loop"""
        self.running = True
        print("🔍 Session health monitor started")
        print(f"Check intervals: HOT={self.check_intervals[SessionTier.HOT]}s, "
              f"WARM={self.check_intervals[SessionTier.WARM]}s")

        while self.running:
            try:
                await self._check_due_sessions()
            except Exception as e:
                print(f"Error in health monitor: {e}")

            # Check every minute for due sessions
            await asyncio.sleep(60)

    async def stop(self):
        """Stop the health monitor"""
        self.running = False
        print("🛑 Session health monitor stopped")

    async def _check_due_sessions(self):
        """Find and check sessions that are due for health check"""
        async with AsyncSessionLocal() as db:
            now = datetime.utcnow()

            # Get sessions that need checking
            for tier in [SessionTier.HOT, SessionTier.WARM]:
                interval = self.check_intervals.get(tier)
                if interval is None:
                    continue

                due_time = now - timedelta(seconds=interval)

                # Query sessions due for check
                query = select(Session).where(
                    and_(
                        Session.tier == tier,
                        Session.last_verified_at < due_time
                    )
                ).limit(5)  # Check max 5 at a time to avoid overwhelming system

                result = await db.execute(query)
                sessions = result.scalars().all()

                for session in sessions:
                    print(f"Checking session {session.id} (tier: {tier.value})")
                    await self.check_session_health(session.id, db)

    async def check_session_health(
        self,
        session_id: int,
        db: Optional[AsyncSession] = None
    ) -> SessionHealth:
        """
        Check health of a specific session by:
        1. Getting an emulator from pool
        2. Booting from session snapshot
        3. Opening the app
        4. Using vision classifier to determine login state
        5. Recording the result
        """
        should_close_db = False
        if db is None:
            db = AsyncSessionLocal()
            should_close_db = True

        try:
            start_time = time.time()

            # Get session from DB
            result = await db.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one_or_none()

            if not session:
                print(f"Session {session_id} not found")
                return SessionHealth.UNKNOWN

            # Load relationships
            await db.refresh(session, ['app', 'user'])

            print(f"[Session {session_id}] Checking health for user={session.user.user_id}, "
                  f"app={session.app.app_id}")

            # TODO: In production, we would:
            # 1. Get emulator from pool
            # 2. Boot from session snapshot
            # 3. Launch the app
            # 4. Use vision classifier to check login state

            # For POC, simulate with mock
            emulator_serial = session.emulator_id or "emulator-5554"
            package_name = session.app.package_name

            health, metadata = await check_session_health(emulator_serial, package_name)

            check_duration = time.time() - start_time

            # Record health check
            health_check = SessionHealthCheck(
                session_id=session_id,
                health_status=health,
                check_duration=check_duration,
                emulator_used=emulator_serial,
                screen_state=metadata.get("screen_state"),
                confidence=metadata.get("confidence")
            )

            db.add(health_check)

            # Update session
            session.session_health = health
            session.last_verified_at = datetime.utcnow()

            await db.commit()

            print(f"[Session {session_id}] Health check complete: {health.value} "
                  f"(confidence: {metadata.get('confidence', 0):.2f})")

            return health

        except Exception as e:
            print(f"Error checking session {session_id}: {e}")
            await db.rollback()
            return SessionHealth.UNKNOWN

        finally:
            if should_close_db:
                await db.close()

    async def verify_session_on_demand(
        self,
        session_id: int
    ) -> SessionHealth:
        """
        Immediately verify a session (used for on-demand checks)
        """
        print(f"[On-demand] Verifying session {session_id}")
        async with AsyncSessionLocal() as db:
            return await self.check_session_health(session_id, db)


# Global monitor instance
_monitor: Optional[SessionHealthMonitor] = None


def get_monitor(emulator_pool: EmulatorPool) -> SessionHealthMonitor:
    """Get or create the global monitor instance"""
    global _monitor
    if _monitor is None:
        _monitor = SessionHealthMonitor(emulator_pool)
    return _monitor


async def start_monitor(emulator_pool: EmulatorPool):
    """Start the health monitor as a background task"""
    monitor = get_monitor(emulator_pool)
    asyncio.create_task(monitor.start())
    return monitor
