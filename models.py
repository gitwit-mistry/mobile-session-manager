"""
Database models for Session Lifecycle Manager
"""
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, Float, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class SessionHealth(str, Enum):
    """Session health status"""
    ALIVE = "alive"
    EXPIRED = "expired"
    UNKNOWN = "unknown"


class SessionTier(str, Enum):
    """Session tier based on usage frequency"""
    HOT = "hot"      # Check daily - high priority
    WARM = "warm"    # Check weekly - medium priority
    COLD = "cold"    # Check on-demand - low priority


class LoginMethod(str, Enum):
    """Login authentication method"""
    OTP = "otp"
    SSO = "sso"
    PASSWORD = "password"


class User(Base):
    """User model"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(user_id='{self.user_id}')>"


class App(Base):
    """App model"""
    __tablename__ = "apps"

    id = Column(Integer, primary_key=True, index=True)
    app_id = Column(String, unique=True, index=True, nullable=False)
    app_name = Column(String, nullable=False)
    package_name = Column(String, nullable=False)  # Android package name
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    sessions = relationship("Session", back_populates="app", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<App(app_id='{self.app_id}', name='{self.app_name}')>"


class Session(Base):
    """Session model - tracks user app sessions"""
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    app_id = Column(Integer, ForeignKey("apps.id"), nullable=False)

    # Session metadata
    session_health = Column(SQLEnum(SessionHealth), default=SessionHealth.UNKNOWN)
    snapshot_reference = Column(String, nullable=True)  # Snapshot name
    emulator_id = Column(String, nullable=True)  # Current emulator if active

    # Timestamps
    last_verified_at = Column(DateTime, nullable=True)
    last_used_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Authentication
    login_method = Column(SQLEnum(LoginMethod), nullable=False)
    login_credentials = Column(JSON, nullable=True)  # Encrypted credentials if stored

    # Tier management
    tier = Column(SQLEnum(SessionTier), default=SessionTier.WARM)
    usage_count = Column(Integer, default=0)  # Number of times used
    last_tier_change = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="sessions")
    app = relationship("App", back_populates="sessions")
    health_checks = relationship("SessionHealthCheck", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Session(user_id={self.user_id}, app_id={self.app_id}, health={self.session_health}, tier={self.tier})>"


class SessionHealthCheck(Base):
    """Session health check history"""
    __tablename__ = "session_health_checks"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)

    # Check results
    checked_at = Column(DateTime, default=datetime.utcnow)
    health_status = Column(SQLEnum(SessionHealth), nullable=False)

    # Check metadata
    check_duration = Column(Float, nullable=True)  # seconds
    emulator_used = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    # Vision classification results (mock)
    screen_state = Column(String, nullable=True)  # "logged_in", "login_screen", "error"
    confidence = Column(Float, nullable=True)  # Mock confidence score

    # Relationships
    session = relationship("Session", back_populates="health_checks")

    def __repr__(self):
        return f"<HealthCheck(session_id={self.session_id}, status={self.health_status}, at={self.checked_at})>"


# Database setup
DATABASE_URL = "sqlite+aiosqlite:///./sessions.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL debugging
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
