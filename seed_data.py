"""
Seed database with test data
"""
import asyncio
from models import (
    init_db, AsyncSessionLocal,
    User, App, Session, SessionTier, LoginMethod, SessionHealth
)
from datetime import datetime, timedelta


async def seed_database():
    """Create test users, apps, and sessions"""
    print("🌱 Seeding database...")

    await init_db()

    async with AsyncSessionLocal() as db:
        # Create test apps
        apps_data = [
            {"app_id": "instagram", "app_name": "Instagram", "package_name": "com.instagram.android"},
            {"app_id": "twitter", "app_name": "Twitter", "package_name": "com.twitter.android"},
            {"app_id": "linkedin", "app_name": "LinkedIn", "package_name": "com.linkedin.android"},
        ]

        apps = {}
        for app_data in apps_data:
            app = App(**app_data)
            db.add(app)
            apps[app_data["app_id"]] = app

        await db.flush()

        # Create test users
        users_data = [
            {"user_id": "alice", "email": "alice@example.com"},
            {"user_id": "bob", "email": "bob@example.com"},
            {"user_id": "charlie", "email": "charlie@example.com"},
        ]

        users = {}
        for user_data in users_data:
            user = User(**user_data)
            db.add(user)
            users[user_data["user_id"]] = user

        await db.flush()

        # Create test sessions
        sessions_data = [
            # Alice - active user (hot tier)
            {
                "user": users["alice"],
                "app": apps["instagram"],
                "login_method": LoginMethod.PASSWORD,
                "tier": SessionTier.HOT,
                "usage_count": 15,
                "last_used_at": datetime.utcnow() - timedelta(hours=2),
                "last_verified_at": datetime.utcnow() - timedelta(hours=12),
                "session_health": SessionHealth.ALIVE,
                "snapshot_reference": "alice_instagram_session"
            },
            {
                "user": users["alice"],
                "app": apps["twitter"],
                "login_method": LoginMethod.OTP,
                "tier": SessionTier.WARM,
                "usage_count": 5,
                "last_used_at": datetime.utcnow() - timedelta(days=3),
                "last_verified_at": datetime.utcnow() - timedelta(days=3),
                "session_health": SessionHealth.UNKNOWN,
            },

            # Bob - moderate user (warm tier)
            {
                "user": users["bob"],
                "app": apps["linkedin"],
                "login_method": LoginMethod.SSO,
                "tier": SessionTier.WARM,
                "usage_count": 3,
                "last_used_at": datetime.utcnow() - timedelta(days=2),
                "last_verified_at": datetime.utcnow() - timedelta(days=5),
                "session_health": SessionHealth.EXPIRED,
                "snapshot_reference": "bob_linkedin_session"
            },

            # Charlie - inactive user (cold tier)
            {
                "user": users["charlie"],
                "app": apps["instagram"],
                "login_method": LoginMethod.PASSWORD,
                "tier": SessionTier.COLD,
                "usage_count": 0,
                "last_used_at": datetime.utcnow() - timedelta(days=45),
                "last_verified_at": datetime.utcnow() - timedelta(days=45),
                "session_health": SessionHealth.UNKNOWN,
            },
        ]

        for session_data in sessions_data:
            session = Session(
                user_id=session_data["user"].id,
                app_id=session_data["app"].id,
                login_method=session_data["login_method"],
                tier=session_data["tier"],
                usage_count=session_data["usage_count"],
                last_used_at=session_data["last_used_at"],
                last_verified_at=session_data.get("last_verified_at"),
                session_health=session_data["session_health"],
                snapshot_reference=session_data.get("snapshot_reference")
            )
            db.add(session)

        await db.commit()

        print("✓ Seed data created:")
        print(f"  - {len(apps_data)} apps")
        print(f"  - {len(users_data)} users")
        print(f"  - {len(sessions_data)} sessions")


if __name__ == "__main__":
    asyncio.run(seed_database())
