"""
Session Tier Manager
Automatically promotes/demotes sessions between hot/warm/cold tiers based on usage patterns
"""
from datetime import datetime, timedelta
from typing import List
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import Session, SessionTier, AsyncSessionLocal


class TierManager:
    """
    Manages session tier promotions and demotions based on usage patterns

    Rules:
    - Hot (check daily): Used 3+ times in last 7 days
    - Warm (check weekly): Used 1-2 times in last 7 days
    - Cold (on-demand): Used 0 times in last 30 days
    """

    def __init__(self):
        # Tier promotion/demotion thresholds
        self.hot_threshold = 3      # Uses in last 7 days
        self.warm_threshold = 1     # Uses in last 7 days
        self.cold_threshold_days = 30  # Days without use

    async def evaluate_session_tier(
        self,
        session: Session,
        db: AsyncSession
    ) -> SessionTier:
        """
        Evaluate what tier a session should be in based on usage

        Returns:
            The recommended tier for this session
        """
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=self.cold_threshold_days)

        # Count recent usage
        usage_last_week = await self._count_usage_since(session.id, week_ago, db)
        usage_last_month = await self._count_usage_since(session.id, month_ago, db)

        # Determine tier based on usage
        if usage_last_week >= self.hot_threshold:
            return SessionTier.HOT
        elif usage_last_week >= self.warm_threshold:
            return SessionTier.WARM
        elif usage_last_month == 0:
            return SessionTier.COLD
        else:
            return SessionTier.WARM  # Default

    async def _count_usage_since(
        self,
        session_id: int,
        since: datetime,
        db: AsyncSession
    ) -> int:
        """
        Count how many times a session was used since a given date

        For POC, we use usage_count field. In production, we'd query
        a session_usage_logs table.
        """
        # Simplified for POC - just return usage_count if last_used is recent
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session and session.last_used_at >= since:
            return session.usage_count

        return 0

    async def update_session_tier(
        self,
        session_id: int,
        new_tier: SessionTier,
        db: AsyncSession
    ):
        """
        Update a session's tier

        Args:
            session_id: Session ID
            new_tier: New tier to assign
            db: Database session
        """
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session and session.tier != new_tier:
            old_tier = session.tier
            session.tier = new_tier
            session.last_tier_change = datetime.utcnow()

            await db.commit()

            print(f"[Tier Manager] Session {session_id}: {old_tier.value} → {new_tier.value}")

    async def increment_usage(
        self,
        session_id: int,
        db: AsyncSession
    ):
        """
        Increment usage count for a session and update last_used

        This should be called whenever a session is used for a mission
        """
        result = await db.execute(
            select(Session).where(Session.id == session_id)
        )
        session = result.scalar_one_or_none()

        if session:
            session.usage_count += 1
            session.last_used_at = datetime.utcnow()

            await db.commit()

            # Re-evaluate tier after usage
            new_tier = await self.evaluate_session_tier(session, db)
            if new_tier != session.tier:
                await self.update_session_tier(session_id, new_tier, db)

    async def run_tier_evaluation(self):
        """
        Run tier evaluation for all sessions
        Should be run periodically (e.g., daily)
        """
        print("🔄 Running tier evaluation for all sessions...")

        async with AsyncSessionLocal() as db:
            # Get all sessions
            result = await db.execute(select(Session))
            sessions = result.scalars().all()

            promotions = 0
            demotions = 0
            unchanged = 0

            for session in sessions:
                old_tier = session.tier
                new_tier = await self.evaluate_session_tier(session, db)

                if new_tier != old_tier:
                    await self.update_session_tier(session.id, new_tier, db)

                    if self._tier_rank(new_tier) > self._tier_rank(old_tier):
                        promotions += 1
                    else:
                        demotions += 1
                else:
                    unchanged += 1

            print(f"✓ Tier evaluation complete: "
                  f"{promotions} promotions, {demotions} demotions, {unchanged} unchanged")

    def _tier_rank(self, tier: SessionTier) -> int:
        """Get numeric rank of tier (higher = more important)"""
        return {
            SessionTier.HOT: 3,
            SessionTier.WARM: 2,
            SessionTier.COLD: 1,
        }[tier]

    async def get_tier_distribution(self) -> dict:
        """Get distribution of sessions across tiers"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Session))
            sessions = result.scalars().all()

            distribution = {
                SessionTier.HOT: 0,
                SessionTier.WARM: 0,
                SessionTier.COLD: 0,
            }

            for session in sessions:
                distribution[session.tier] += 1

            return {
                "hot": distribution[SessionTier.HOT],
                "warm": distribution[SessionTier.WARM],
                "cold": distribution[SessionTier.COLD],
                "total": len(sessions)
            }


# Global tier manager instance
_tier_manager: TierManager = None


def get_tier_manager() -> TierManager:
    """Get or create the global tier manager"""
    global _tier_manager
    if _tier_manager is None:
        _tier_manager = TierManager()
    return _tier_manager
