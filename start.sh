#!/bin/bash
# Launcher script that sets environment and starts the API

# Set Android SDK paths (Homebrew installation)
export ANDROID_SDK_ROOT=/opt/homebrew/share/android-commandlinetools
export ANDROID_HOME=/opt/homebrew/share/android-commandlinetools
export ANDROID_AVD_HOME=~/.android/avd
export PATH=$PATH:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin
export PATH=$PATH:$ANDROID_SDK_ROOT/platform-tools
export PATH=$PATH:$ANDROID_SDK_ROOT/emulator

echo "Android SDK configured:"
echo "  ANDROID_SDK_ROOT: $ANDROID_SDK_ROOT"
echo "  Emulator: $(which emulator)"
echo "  ADB: $(which adb)"
echo ""

# Check if AVD exists
echo "Available AVDs:"
emulator -list-avds
echo ""

# Start the main API server (combined emulator + session management)
echo "Starting Mobile Agent Session Manager..."
python3 api_main.py
