#!/bin/bash
# Cleanup script to kill all running emulators

export ANDROID_SDK_ROOT=/opt/homebrew/share/android-commandlinetools
export PATH=$PATH:$ANDROID_SDK_ROOT/platform-tools

echo "Killing all running emulators..."

# List current devices
echo "Current devices:"
adb devices

# Kill all emulators via ADB
for device in $(adb devices | grep emulator | awk '{print $1}'); do
    echo "Killing $device..."
    adb -s $device emu kill
done

# Force kill any remaining emulator processes
pkill -9 qemu-system-aarch64 2>/dev/null || true
pkill -9 emulator 2>/dev/null || true

echo "Cleanup complete!"
adb devices
