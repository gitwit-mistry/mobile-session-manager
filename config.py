"""
Configuration for Mobile Agent Session Manager
"""
import os

# Pool Configuration
POOL_SIZE = 1  # Reduced for Mac M4 - start with 1 warm emulator
MAX_EMULATORS = 5  # Maximum concurrent emulators
BASE_PORT = 5554

# Emulator Boot Configuration
BOOT_TIMEOUT = 180  # Increased to 3 minutes for Mac M4 (no KVM)
HEALTH_CHECK_INTERVAL = 30  # seconds

# Android SDK paths
ANDROID_SDK_ROOT = os.environ.get(
    'ANDROID_SDK_ROOT',
    '/opt/homebrew/share/android-commandlinetools'
)

# Default AVD name
DEFAULT_AVD_NAME = "test_avd"

# Emulator startup options (optimized for Mac M4)
EMULATOR_ARGS = [
    "-no-window",       # Headless
    "-no-audio",        # No audio
    "-no-boot-anim",    # Skip boot animation
    "-gpu", "swiftshader_indirect",  # Software rendering
    "-memory", "2048",  # 2GB RAM per emulator
    "-cores", "2",      # 2 CPU cores
]
