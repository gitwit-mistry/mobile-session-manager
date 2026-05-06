#!/bin/bash
# Setup script to create a test AVD

set -e

AVD_NAME="test_avd"
ANDROID_API="33"
SYSTEM_IMAGE="system-images;android-${ANDROID_API};google_apis;arm64-v8a"

echo "Creating AVD: ${AVD_NAME}"

# Create AVD
echo "no" | avdmanager create avd \
    -n "${AVD_NAME}" \
    -k "${SYSTEM_IMAGE}" \
    -d "pixel_5" \
    --force

echo "AVD created successfully!"
echo "AVD name: ${AVD_NAME}"
echo ""
echo "You can now start the API server with:"
echo "  python3 api.py"
