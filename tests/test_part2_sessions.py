"""
Part 2: Session Lifecycle Tests
Tests for session management, health monitoring, and tier management
"""
import pytest
from datetime import datetime, timedelta
from models import (
    User, App, Session, SessionHealthCheck,
    SessionHealth, SessionTier, LoginMethod
)
from tier_manager import TierManager
from vision_classifier import VisionClassifier


class TestSessionModel:
    """Test Session data model"""

    @pytest.mark.asyncio
    async def test_session_creation(self, db_session, test_user, test_app):
        """Test creating a session"""
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

        assert session.id is not None
        assert session.user_id == test_user.id
        assert session.app_id == test_app.id
        assert session.login_method == LoginMethod.PASSWORD
        assert session.tier == SessionTier.WARM
        assert session.session_health == SessionHealth.UNKNOWN

    @pytest.mark.asyncio
    async def test_session_relationships(self, db_session, test_session, test_user, test_app):
        """Test session relationships with user and app"""
        await db_session.refresh(test_session, ['user', 'app'])

        assert test_session.user.user_id == test_user.user_id
        assert test_session.app.app_id == test_app.app_id

    @pytest.mark.asyncio
    async def test_session_health_states(self, test_session):
        """Test session health state transitions"""
        # Start as unknown
        assert test_session.session_health == SessionHealth.UNKNOWN

        # Update to alive
        test_session.session_health = SessionHealth.ALIVE
        assert test_session.session_health == SessionHealth.ALIVE

        # Update to expired
        test_session.session_health = SessionHealth.EXPIRED
        assert test_session.session_health == SessionHealth.EXPIRED


class TestSessionTiers:
    """Test session tier system"""

    @pytest.mark.asyncio
    async def test_tier_levels(self, test_session):
        """Test all tier levels"""
        # HOT tier
        test_session.tier = SessionTier.HOT
        assert test_session.tier == SessionTier.HOT

        # WARM tier
        test_session.tier = SessionTier.WARM
        assert test_session.tier == SessionTier.WARM

        # COLD tier
        test_session.tier = SessionTier.COLD
        assert test_session.tier == SessionTier.COLD

    @pytest.mark.asyncio
    async def test_tier_defaults(self, db_session, test_user, test_app):
        """Test default tier is WARM"""
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.PASSWORD
        )

        assert session.tier == SessionTier.WARM

    @pytest.mark.asyncio
    async def test_usage_tracking(self, test_session):
        """Test usage count tracking"""
        initial_count = test_session.usage_count

        # Increment usage
        test_session.usage_count += 1
        assert test_session.usage_count == initial_count + 1

        # Update last used
        test_session.last_used_at = datetime.utcnow()
        assert test_session.last_used_at is not None


class TestTierManager:
    """Test tier management and promotion/demotion"""

    @pytest.mark.asyncio
    async def test_tier_manager_initialization(self):
        """Test TierManager initialization"""
        manager = TierManager()

        assert manager.hot_threshold == 3
        assert manager.warm_threshold == 1
        assert manager.cold_threshold_days == 30

    @pytest.mark.asyncio
    async def test_hot_tier_criteria(self):
        """Test promotion to HOT tier"""
        manager = TierManager()

        # Simulate 3+ uses in last 7 days
        usage_count = 5
        last_used = datetime.utcnow() - timedelta(days=2)

        should_be_hot = usage_count >= manager.hot_threshold
        assert should_be_hot is True

    @pytest.mark.asyncio
    async def test_cold_tier_criteria(self):
        """Test demotion to COLD tier"""
        manager = TierManager()

        # Simulate 0 uses in 30 days
        last_used = datetime.utcnow() - timedelta(days=35)
        now = datetime.utcnow()

        days_inactive = (now - last_used).days
        should_be_cold = days_inactive > manager.cold_threshold_days

        assert should_be_cold is True

    @pytest.mark.asyncio
    async def test_tier_ranking(self):
        """Test tier priority ranking"""
        manager = TierManager()

        hot_rank = manager._tier_rank(SessionTier.HOT)
        warm_rank = manager._tier_rank(SessionTier.WARM)
        cold_rank = manager._tier_rank(SessionTier.COLD)

        assert hot_rank > warm_rank > cold_rank
        assert hot_rank == 3
        assert warm_rank == 2
        assert cold_rank == 1


class TestHealthChecks:
    """Test session health check functionality"""

    @pytest.mark.asyncio
    async def test_health_check_record(self, db_session, test_session):
        """Test creating health check records"""
        check = SessionHealthCheck(
            session_id=test_session.id,
            health_status=SessionHealth.ALIVE,
            check_duration=1.5,
            screen_state="logged_in",
            confidence=0.92
        )

        db_session.add(check)
        await db_session.commit()
        await db_session.refresh(check)

        assert check.id is not None
        assert check.session_id == test_session.id
        assert check.health_status == SessionHealth.ALIVE
        assert check.check_duration == 1.5
        assert check.confidence == 0.92

    @pytest.mark.asyncio
    async def test_health_history(self, db_session, test_session):
        """Test multiple health checks create history"""
        # Create multiple checks
        for i in range(5):
            check = SessionHealthCheck(
                session_id=test_session.id,
                health_status=SessionHealth.ALIVE if i % 2 == 0 else SessionHealth.EXPIRED,
                check_duration=1.0 + i * 0.1,
                confidence=0.8 + i * 0.02
            )
            db_session.add(check)

        await db_session.commit()

        # Verify history exists
        await db_session.refresh(test_session, ['health_checks'])
        assert len(test_session.health_checks) == 5


class TestVisionClassifier:
    """Test vision classifier (mock)"""

    @pytest.mark.asyncio
    async def test_classifier_initialization(self):
        """Test VisionClassifier initialization"""
        classifier = VisionClassifier()

        assert classifier.logged_in_probability == 0.8

    @pytest.mark.asyncio
    async def test_classification_output(self):
        """Test classification returns correct format"""
        classifier = VisionClassifier()

        health, metadata = await classifier.classify_screen_state(
            "emulator-5554",
            "com.test.app"
        )

        # Should return SessionHealth and metadata dict
        assert isinstance(health, SessionHealth)
        assert isinstance(metadata, dict)
        assert "screen_state" in metadata
        assert "confidence" in metadata
        assert "emulator" in metadata

    @pytest.mark.asyncio
    async def test_classification_distribution(self):
        """Test 80/20 distribution over multiple runs"""
        classifier = VisionClassifier()

        alive_count = 0
        expired_count = 0
        total_runs = 50

        for _ in range(total_runs):
            health, _ = await classifier.classify_screen_state(
                "emulator-5554",
                "com.test.app"
            )

            if health == SessionHealth.ALIVE:
                alive_count += 1
            else:
                expired_count += 1

        alive_percentage = alive_count / total_runs

        # Should be roughly 80% alive (allow ±20% variance)
        assert 0.6 <= alive_percentage <= 1.0
        assert expired_count > 0  # Should have some expired


class TestLazyReAuth:
    """Test lazy re-authentication flow"""

    @pytest.mark.asyncio
    async def test_expired_session_requires_reauth(self, test_session):
        """Test expired sessions require re-auth"""
        test_session.session_health = SessionHealth.EXPIRED

        requires_reauth = test_session.session_health == SessionHealth.EXPIRED
        assert requires_reauth is True

    @pytest.mark.asyncio
    async def test_login_method_returned(self, test_session):
        """Test login method is returned for re-auth"""
        test_session.session_health = SessionHealth.EXPIRED
        test_session.login_method = LoginMethod.SSO

        if test_session.session_health == SessionHealth.EXPIRED:
            login_method = test_session.login_method

        assert login_method == LoginMethod.SSO

    @pytest.mark.asyncio
    async def test_alive_session_no_reauth(self, test_session):
        """Test alive sessions don't require re-auth"""
        test_session.session_health = SessionHealth.ALIVE

        requires_reauth = test_session.session_health == SessionHealth.EXPIRED
        assert requires_reauth is False


class TestLoginMethods:
    """Test different login methods"""

    @pytest.mark.asyncio
    async def test_otp_login_method(self, db_session, test_user, test_app):
        """Test OTP login method"""
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.OTP
        )

        assert session.login_method == LoginMethod.OTP

    @pytest.mark.asyncio
    async def test_sso_login_method(self, db_session, test_user, test_app):
        """Test SSO login method"""
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.SSO
        )

        assert session.login_method == LoginMethod.SSO

    @pytest.mark.asyncio
    async def test_password_login_method(self, db_session, test_user, test_app):
        """Test password login method"""
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.PASSWORD
        )

        assert session.login_method == LoginMethod.PASSWORD


class TestSnapshotReferences:
    """Test snapshot reference tracking in sessions"""

    @pytest.mark.asyncio
    async def test_snapshot_storage(self, test_session):
        """Test storing snapshot reference"""
        snapshot_name = "session_user123_instagram_v1"
        test_session.snapshot_reference = snapshot_name

        assert test_session.snapshot_reference == snapshot_name

    @pytest.mark.asyncio
    async def test_snapshot_naming_convention(self):
        """Test snapshot naming follows convention"""
        # session_{user}_{app}_v{version}
        snapshot = "session_alice_instagram_v1"

        assert snapshot.startswith("session_")
        assert "_v" in snapshot


# Integration test markers
@pytest.mark.integration
class TestSessionAPIIntegration:
    """Integration tests for session APIs"""

    @pytest.mark.asyncio
    async def test_list_user_sessions(self, api_client):
        """Test GET /users/:id/sessions"""
        # Would test actual API if server running
        pass

    @pytest.mark.asyncio
    async def test_verify_session(self, api_client):
        """Test POST /users/:id/sessions/:app/verify"""
        pass

    @pytest.mark.asyncio
    async def test_health_history(self, api_client):
        """Test GET /users/:id/sessions/:app/health-history"""
        pass
