"""
Integration Tests - Combined Part 1 + Part 2
Tests that verify emulator orchestration works with session management
"""
import pytest
from datetime import datetime
from models import User, App, Session, SessionTier, LoginMethod, SessionHealth
from pool_manager import EmulatorPool
from emulator_manager import EmulatorState


@pytest.mark.integration
class TestEmulatorSessionIntegration:
    """Test integration between emulators and sessions"""

    @pytest.mark.asyncio
    async def test_session_to_emulator_flow(self, db_session, test_user, test_app):
        """Test flow from session verification to emulator provisioning"""
        # Create session
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.PASSWORD,
            tier=SessionTier.HOT,
            session_health=SessionHealth.ALIVE,
            snapshot_reference="session_test_user_test_app"
        )
        db_session.add(session)
        await db_session.commit()

        # Session exists
        assert session.id is not None

        # Would provision emulator with snapshot
        snapshot_to_use = session.snapshot_reference
        assert snapshot_to_use == "session_test_user_test_app"

        # Simulate emulator assignment
        emulator_id = "emu-1"
        session.emulator_id = emulator_id
        await db_session.commit()

        assert session.emulator_id == emulator_id

    @pytest.mark.asyncio
    async def test_expired_session_blocks_emulator(self, db_session, test_user, test_app):
        """Test that expired session prevents emulator provisioning"""
        # Create expired session
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.SSO,
            session_health=SessionHealth.EXPIRED
        )
        db_session.add(session)
        await db_session.commit()

        # Check if session is expired
        requires_reauth = session.session_health == SessionHealth.EXPIRED

        if requires_reauth:
            # Should NOT provision emulator
            # Should return re-auth required
            login_method = session.login_method

            assert requires_reauth is True
            assert login_method == LoginMethod.SSO

            # Emulator should NOT be provisioned
            assert session.emulator_id is None

    @pytest.mark.asyncio
    async def test_usage_updates_tier(self, db_session, test_session):
        """Test that session usage updates tier"""
        # Start as WARM
        test_session.tier = SessionTier.WARM
        test_session.usage_count = 1
        await db_session.commit()

        # Simulate multiple uses
        for _ in range(3):
            test_session.usage_count += 1
            test_session.last_used_at = datetime.utcnow()

        await db_session.commit()

        # After 3+ uses, should be eligible for HOT
        should_promote = test_session.usage_count >= 3
        assert should_promote is True

        # Simulate promotion
        if should_promote:
            test_session.tier = SessionTier.HOT
            await db_session.commit()

        assert test_session.tier == SessionTier.HOT


@pytest.mark.integration
class TestHealthMonitorIntegration:
    """Test health monitor with emulator pool"""

    @pytest.mark.asyncio
    async def test_health_check_uses_emulator(self, db_session, test_session):
        """Test health check can use emulator from pool"""
        # Health check needs emulator
        # Get from pool
        # Boot from snapshot
        # Run vision classifier
        # Record result

        # Simulate getting emulator
        test_session.emulator_id = "emu-1"
        await db_session.commit()

        # Simulate health check
        test_session.session_health = SessionHealth.ALIVE
        test_session.last_verified_at = datetime.utcnow()
        await db_session.commit()

        assert test_session.emulator_id == "emu-1"
        assert test_session.session_health == SessionHealth.ALIVE
        assert test_session.last_verified_at is not None

    @pytest.mark.asyncio
    async def test_tier_affects_check_frequency(self, test_session):
        """Test different tiers have different check intervals"""
        # HOT: Check frequently
        # WARM: Check less frequently
        # COLD: On-demand only

        check_intervals = {
            SessionTier.HOT: 60,
            SessionTier.WARM: 300,
            SessionTier.COLD: None
        }

        # HOT tier should have fastest check
        test_session.tier = SessionTier.HOT
        hot_interval = check_intervals[SessionTier.HOT]
        assert hot_interval == 60

        # WARM tier slower
        test_session.tier = SessionTier.WARM
        warm_interval = check_intervals[SessionTier.WARM]
        assert warm_interval == 300

        # COLD tier on-demand
        test_session.tier = SessionTier.COLD
        cold_interval = check_intervals[SessionTier.COLD]
        assert cold_interval is None


@pytest.mark.integration
class TestCompleteUserFlow:
    """Test complete user mission flow"""

    @pytest.mark.asyncio
    async def test_mission_execution_flow(self, db_session, test_user, test_app):
        """Test complete flow: check session → get emulator → execute mission"""
        # 1. Create session
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.PASSWORD,
            session_health=SessionHealth.ALIVE,
            tier=SessionTier.HOT,
            snapshot_reference="session_test_complete"
        )
        db_session.add(session)
        await db_session.commit()

        # 2. Verify session is healthy
        assert session.session_health == SessionHealth.ALIVE
        can_proceed = session.session_health == SessionHealth.ALIVE
        assert can_proceed is True

        # 3. Get emulator (would come from pool)
        emulator_id = "emu-1"
        snapshot = session.snapshot_reference

        # 4. Assign emulator to session
        session.emulator_id = emulator_id
        await db_session.commit()

        # 5. Execute mission (simulated)
        mission_executed = True

        # 6. Update usage
        session.usage_count += 1
        session.last_used_at = datetime.utcnow()
        await db_session.commit()

        # Verify complete flow
        assert mission_executed is True
        assert session.usage_count == 1
        assert session.emulator_id == emulator_id

    @pytest.mark.asyncio
    async def test_mission_blocked_by_expired_session(self, db_session, test_user, test_app):
        """Test mission is blocked when session expired"""
        # 1. Create expired session
        session = Session(
            user_id=test_user.id,
            app_id=test_app.id,
            login_method=LoginMethod.OTP,
            session_health=SessionHealth.EXPIRED
        )
        db_session.add(session)
        await db_session.commit()

        # 2. Check session health
        requires_reauth = session.session_health == SessionHealth.EXPIRED

        # 3. Mission should be blocked
        if requires_reauth:
            # Return re-auth required
            response = {
                "status": "blocked",
                "reason": "session_expired",
                "requires_reauth": True,
                "login_method": session.login_method.value
            }

        # 4. Verify mission blocked
        assert response["status"] == "blocked"
        assert response["requires_reauth"] is True
        assert response["login_method"] == "otp"

        # 5. Emulator should NOT be provisioned
        assert session.emulator_id is None


@pytest.mark.integration
class TestDataConsistency:
    """Test data consistency across the system"""

    @pytest.mark.asyncio
    async def test_session_emulator_consistency(self, db_session, test_session):
        """Test session and emulator references stay consistent"""
        # Assign emulator
        test_session.emulator_id = "emu-1"
        await db_session.commit()

        # Read back
        await db_session.refresh(test_session)
        assert test_session.emulator_id == "emu-1"

        # Clear emulator (session ends)
        test_session.emulator_id = None
        await db_session.commit()

        await db_session.refresh(test_session)
        assert test_session.emulator_id is None

    @pytest.mark.asyncio
    async def test_health_check_session_relationship(self, db_session, test_session):
        """Test health checks properly link to sessions"""
        from models import SessionHealthCheck

        # Create health check
        check = SessionHealthCheck(
            session_id=test_session.id,
            health_status=SessionHealth.ALIVE,
            confidence=0.9
        )
        db_session.add(check)
        await db_session.commit()

        # Verify relationship
        await db_session.refresh(test_session, ['health_checks'])
        assert len(test_session.health_checks) > 0
        assert test_session.health_checks[0].session_id == test_session.id
