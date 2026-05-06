"""
Session Lifecycle API endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    User, App, Session, SessionHealthCheck,
    SessionHealth, SessionTier, LoginMethod,
    get_db, AsyncSessionLocal
)
from session_monitor import get_monitor
from tier_manager import get_tier_manager

router = APIRouter(prefix="/users", tags=["sessions"])


# Pydantic models for API
class SessionResponse(BaseModel):
    id: int
    user_id: str
    app_id: str
    app_name: str
    session_health: str
    tier: str
    login_method: str
    last_verified_at: Optional[datetime]
    last_used_at: datetime
    usage_count: int
    snapshot_reference: Optional[str]

    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    id: int
    checked_at: datetime
    health_status: str
    check_duration: Optional[float]
    screen_state: Optional[str]
    confidence: Optional[float]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class VerifySessionRequest(BaseModel):
    force: bool = False  # Force immediate check even if recently checked


class VerifySessionResponse(BaseModel):
    session_id: int
    health_status: str
    requires_reauth: bool
    login_method: Optional[str]
    checked_at: datetime
    confidence: Optional[float]


class CreateSessionRequest(BaseModel):
    app_id: str
    login_method: str
    snapshot_reference: Optional[str] = None


# API Endpoints

@router.get("/{user_id}/sessions", response_model=List[SessionResponse])
async def get_user_sessions(
    user_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all sessions for a user

    Returns list of sessions with their current health status and tier
    """
    # Get user
    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Get sessions with relationships loaded
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id)
        .order_by(Session.last_used_at.desc())
    )
    sessions = result.scalars().all()

    # Load relationships
    response_sessions = []
    for session in sessions:
        await db.refresh(session, ['app', 'user'])
        response_sessions.append(SessionResponse(
            id=session.id,
            user_id=session.user.user_id,
            app_id=session.app.app_id,
            app_name=session.app.app_name,
            session_health=session.session_health.value,
            tier=session.tier.value,
            login_method=session.login_method.value,
            last_verified_at=session.last_verified_at,
            last_used_at=session.last_used_at,
            usage_count=session.usage_count,
            snapshot_reference=session.snapshot_reference
        ))

    return response_sessions


@router.post("/{user_id}/sessions/{app_id}/verify", response_model=VerifySessionResponse)
async def verify_session(
    user_id: str,
    app_id: str,
    request: VerifySessionRequest = VerifySessionRequest(),
    db: AsyncSession = Depends(get_db)
):
    """
    Verify session health for a specific user-app combination

    If session is expired, returns requires_reauth=True with login method
    This implements the "lazy re-auth flow"
    """
    # Get user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Get app
    app_result = await db.execute(
        select(App).where(App.app_id == app_id)
    )
    app = app_result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App {app_id} not found"
        )

    # Get session
    session_result = await db.execute(
        select(Session).where(
            and_(
                Session.user_id == user.id,
                Session.app_id == app.id
            )
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No session found for user {user_id} and app {app_id}"
        )

    # Check if we need to verify (force or not recently checked)
    needs_check = request.force or session.session_health == SessionHealth.UNKNOWN

    if needs_check:
        # Trigger on-demand health check
        from pool_manager import EmulatorPool
        # In real implementation, get pool from app state
        # For now, we'll use the monitor
        monitor = get_monitor(None)  # Will use mock
        health = await monitor.check_session_health(session.id, db)
    else:
        health = session.session_health

    # Get latest health check for metadata
    latest_check_result = await db.execute(
        select(SessionHealthCheck)
        .where(SessionHealthCheck.session_id == session.id)
        .order_by(SessionHealthCheck.checked_at.desc())
        .limit(1)
    )
    latest_check = latest_check_result.scalar_one_or_none()

    requires_reauth = health == SessionHealth.EXPIRED

    return VerifySessionResponse(
        session_id=session.id,
        health_status=health.value,
        requires_reauth=requires_reauth,
        login_method=session.login_method.value if requires_reauth else None,
        checked_at=latest_check.checked_at if latest_check else datetime.utcnow(),
        confidence=latest_check.confidence if latest_check else None
    )


@router.get("/{user_id}/sessions/{app_id}/health-history", response_model=List[HealthCheckResponse])
async def get_health_history(
    user_id: str,
    app_id: str,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    Get health check history for a session

    Returns list of past health checks with timestamps and results
    """
    # Get user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    # Get app
    app_result = await db.execute(
        select(App).where(App.app_id == app_id)
    )
    app = app_result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App {app_id} not found"
        )

    # Get session
    session_result = await db.execute(
        select(Session).where(
            and_(
                Session.user_id == user.id,
                Session.app_id == app.id
            )
        )
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No session found for user {user_id} and app {app_id}"
        )

    # Get health check history
    checks_result = await db.execute(
        select(SessionHealthCheck)
        .where(SessionHealthCheck.session_id == session.id)
        .order_by(SessionHealthCheck.checked_at.desc())
        .limit(limit)
    )
    checks = checks_result.scalars().all()

    return [
        HealthCheckResponse(
            id=check.id,
            checked_at=check.checked_at,
            health_status=check.health_status.value,
            check_duration=check.check_duration,
            screen_state=check.screen_state,
            confidence=check.confidence,
            error_message=check.error_message
        )
        for check in checks
    ]


@router.post("/{user_id}/sessions", response_model=SessionResponse)
async def create_session(
    user_id: str,
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new session for a user-app combination
    """
    # Get or create user
    user_result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user:
        user = User(user_id=user_id)
        db.add(user)
        await db.flush()

    # Get app
    app_result = await db.execute(
        select(App).where(App.app_id == request.app_id)
    )
    app = app_result.scalar_one_or_none()

    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"App {request.app_id} not found. Create app first."
        )

    # Check if session already exists
    existing = await db.execute(
        select(Session).where(
            and_(
                Session.user_id == user.id,
                Session.app_id == app.id
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session already exists for user {user_id} and app {request.app_id}"
        )

    # Create session
    session = Session(
        user_id=user.id,
        app_id=app.id,
        login_method=LoginMethod(request.login_method),
        snapshot_reference=request.snapshot_reference,
        tier=SessionTier.WARM  # Default to warm tier
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)
    await db.refresh(session, ['app', 'user'])

    return SessionResponse(
        id=session.id,
        user_id=session.user.user_id,
        app_id=session.app.app_id,
        app_name=session.app.app_name,
        session_health=session.session_health.value,
        tier=session.tier.value,
        login_method=session.login_method.value,
        last_verified_at=session.last_verified_at,
        last_used_at=session.last_used_at,
        usage_count=session.usage_count,
        snapshot_reference=session.snapshot_reference
    )


# Admin/utility endpoints

@router.get("/sessions/tiers/distribution")
async def get_tier_distribution():
    """Get distribution of sessions across tiers"""
    tier_manager = get_tier_manager()
    return await tier_manager.get_tier_distribution()
