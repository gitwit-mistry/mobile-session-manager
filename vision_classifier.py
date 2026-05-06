"""
Mock Vision Classifier for Session Health Detection
Simulates screen state classification for logged-in vs expired sessions
"""
import random
import asyncio
from typing import Tuple, Dict
from models import SessionHealth


class VisionClassifier:
    """
    Mock vision classifier that simulates screen state detection
    In production, this would use computer vision / OCR to detect login state
    """

    def __init__(self):
        # Simulate 80% logged in, 20% expired
        self.logged_in_probability = 0.8

    async def classify_screen_state(
        self,
        emulator_serial: str,
        package_name: str
    ) -> Tuple[SessionHealth, Dict]:
        """
        Classify the screen state of an app

        Returns:
            Tuple of (SessionHealth, metadata dict with confidence and screen_state)
        """
        # Simulate vision processing delay
        await asyncio.sleep(random.uniform(0.5, 2.0))

        # Mock classification with 80/20 split
        is_logged_in = random.random() < self.logged_in_probability

        if is_logged_in:
            health = SessionHealth.ALIVE
            screen_state = "logged_in"
            confidence = random.uniform(0.85, 0.99)
        else:
            health = SessionHealth.EXPIRED
            screen_state = "login_screen"
            confidence = random.uniform(0.75, 0.95)

        metadata = {
            "screen_state": screen_state,
            "confidence": confidence,
            "emulator": emulator_serial,
            "package": package_name
        }

        return health, metadata

    async def verify_app_screen(
        self,
        emulator_serial: str,
        package_name: str,
        expected_activity: str = None
    ) -> bool:
        """
        Verify if app is showing the expected screen

        Returns:
            True if app is on expected screen, False otherwise
        """
        # Simulate checking current activity
        await asyncio.sleep(random.uniform(0.2, 0.5))

        # 90% chance app is where we expect
        return random.random() < 0.9

    async def detect_login_prompt(
        self,
        emulator_serial: str,
        package_name: str
    ) -> Dict[str, any]:
        """
        Detect what kind of login prompt is showing

        Returns:
            Dict with login_type and detected elements
        """
        await asyncio.sleep(random.uniform(0.3, 0.8))

        login_types = ["otp", "password", "sso", "biometric"]
        detected_type = random.choice(login_types)

        return {
            "login_type": detected_type,
            "has_username_field": detected_type == "password",
            "has_otp_field": detected_type == "otp",
            "has_sso_button": detected_type == "sso",
            "confidence": random.uniform(0.7, 0.95)
        }


# Global classifier instance
classifier = VisionClassifier()


# Helper functions for integration
async def check_session_health(
    emulator_serial: str,
    package_name: str
) -> Tuple[SessionHealth, Dict]:
    """
    Check session health for a specific app on an emulator

    Args:
        emulator_serial: ADB serial (e.g., "emulator-5554")
        package_name: Android package name (e.g., "com.example.app")

    Returns:
        Tuple of (SessionHealth status, metadata dict)
    """
    return await classifier.classify_screen_state(emulator_serial, package_name)


async def verify_login_state(
    emulator_serial: str,
    package_name: str
) -> bool:
    """
    Quick check if app appears to be logged in

    Returns:
        True if logged in, False if login screen detected
    """
    health, _ = await classifier.classify_screen_state(emulator_serial, package_name)
    return health == SessionHealth.ALIVE


# For testing
async def test_classifier():
    """Test the mock classifier distribution"""
    print("Testing mock vision classifier...")
    print("=" * 50)

    results = {"logged_in": 0, "expired": 0}
    total_tests = 100

    for i in range(total_tests):
        health, metadata = await check_session_health("emulator-5554", "com.test.app")

        if health == SessionHealth.ALIVE:
            results["logged_in"] += 1
        else:
            results["expired"] += 1

        if i < 10:  # Print first 10 results
            print(f"Check {i+1}: {health.value} (confidence: {metadata['confidence']:.2f})")

    print("\n" + "=" * 50)
    print(f"Results over {total_tests} checks:")
    print(f"  Logged in: {results['logged_in']}% ({results['logged_in']} checks)")
    print(f"  Expired:   {results['expired']}% ({results['expired']} checks)")
    print(f"  Target:    80% logged in, 20% expired")


if __name__ == "__main__":
    asyncio.run(test_classifier())
