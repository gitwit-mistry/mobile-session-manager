"""
Simple test script for the Mobile Agent Session Manager API
"""
import requests
import time
import sys

BASE_URL = "http://localhost:8000"


def test_health():
    """Test health endpoint"""
    print("Testing health endpoint...")
    resp = requests.get(f"{BASE_URL}/health")
    print(f"✓ Health check: {resp.json()}")
    return resp.status_code == 200


def test_create_emulator():
    """Test creating an emulator"""
    print("\nCreating emulator...")
    resp = requests.post(
        f"{BASE_URL}/emulators",
        json={"user_id": "test_user", "avd_name": "test_avd"}
    )

    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Emulator created: {data['id']} on port {data['port']}")
        return data['id']
    else:
        print(f"✗ Failed to create emulator: {resp.text}")
        return None


def test_get_status(emulator_id):
    """Test getting emulator status"""
    print(f"\nGetting status for {emulator_id}...")
    resp = requests.get(f"{BASE_URL}/emulators/{emulator_id}/status")

    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Status: {data['state']}, uptime: {data['uptime']:.1f}s")
        return True
    else:
        print(f"✗ Failed to get status: {resp.text}")
        return False


def test_pool_stats():
    """Test getting pool statistics"""
    print("\nGetting pool stats...")
    resp = requests.get(f"{BASE_URL}/pool/stats")

    if resp.status_code == 200:
        data = resp.json()
        print(f"✓ Pool stats:")
        print(f"  Total emulators: {data['total_emulators']}")
        print(f"  Warm available: {data['warm_available']}")
        print(f"  Assigned: {data['assigned']}")
        return True
    else:
        print(f"✗ Failed to get pool stats: {resp.text}")
        return False


def test_create_snapshot(emulator_id):
    """Test creating a snapshot"""
    print(f"\nCreating snapshot for {emulator_id}...")
    snapshot_name = f"test_snapshot_{int(time.time())}"

    resp = requests.post(
        f"{BASE_URL}/emulators/{emulator_id}/snapshot",
        json={"snapshot_name": snapshot_name}
    )

    if resp.status_code == 200:
        print(f"✓ Snapshot created: {snapshot_name}")
        return True
    else:
        print(f"✗ Failed to create snapshot: {resp.text}")
        return False


def test_delete_emulator(emulator_id):
    """Test deleting an emulator"""
    print(f"\nDeleting emulator {emulator_id}...")
    resp = requests.delete(f"{BASE_URL}/emulators/{emulator_id}")

    if resp.status_code == 200:
        print(f"✓ Emulator deleted")
        return True
    else:
        print(f"✗ Failed to delete emulator: {resp.text}")
        return False


def main():
    print("=" * 50)
    print("Mobile Agent Session Manager - API Test")
    print("=" * 50)

    # Check if server is running
    try:
        requests.get(f"{BASE_URL}/health", timeout=2)
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to {BASE_URL}")
        print("Make sure the server is running: python3 api.py")
        sys.exit(1)

    # Run tests
    if not test_health():
        sys.exit(1)

    test_pool_stats()

    # Note: These tests require Android SDK to be installed
    print("\n" + "=" * 50)
    print("Note: The following tests require Android SDK")
    print("and a test AVD to be created.")
    print("Run ./setup_avd.sh first if you haven't.")
    print("=" * 50)

    input("\nPress Enter to continue with emulator tests (or Ctrl+C to exit)...")

    emulator_id = test_create_emulator()

    if emulator_id:
        time.sleep(2)
        test_get_status(emulator_id)
        test_pool_stats()

        # Uncomment to test snapshot
        # test_create_snapshot(emulator_id)

        test_delete_emulator(emulator_id)
        time.sleep(1)
        test_pool_stats()

    print("\n" + "=" * 50)
    print("Tests completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
