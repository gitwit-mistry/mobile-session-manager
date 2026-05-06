"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from models import Base, User, App, Session, SessionTier, LoginMethod, SessionHealth


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Create a test database"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    yield AsyncSessionLocal

    await engine.dispose()


@pytest.fixture
async def db_session(test_db):
    """Get a database session"""
    async with test_db() as session:
        yield session


@pytest.fixture
async def test_user(db_session):
    """Create a test user"""
    user = User(user_id="test_user", email="test@example.com")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_app(db_session):
    """Create a test app"""
    app = App(
        app_id="test_app",
        app_name="Test App",
        package_name="com.test.app"
    )
    db_session.add(app)
    await db_session.commit()
    await db_session.refresh(app)
    return app


@pytest.fixture
async def test_session(db_session, test_user, test_app):
    """Create a test session"""
    session = Session(
        user_id=test_user.id,
        app_id=test_app.id,
        login_method=LoginMethod.PASSWORD,
        tier=SessionTier.WARM,
        session_health=SessionHealth.UNKNOWN
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


@pytest.fixture
async def api_client():
    """HTTP client for API testing"""
    async with AsyncClient(base_url="http://localhost:8000", timeout=30.0) as client:
        yield client
