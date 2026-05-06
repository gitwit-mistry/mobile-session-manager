#!/usr/bin/env python3
"""
Test script to verify pool replenishment logic
"""
import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def check_stats():
    resp = requests.get(f"{BASE_URL}/pool/stats")
    stats = resp.json()
    print(f"\n📊 Pool Stats:")
    print(f"  Pool Size (target): {stats['pool_size']}")
    print(f"  Total Emulators:    {stats['total_emulators']}")
    print(f"  Warm Available:     {stats['warm_available']}")
    print(f"  Assigned:           {stats['assigned']}")

    booting = sum(1 for e in stats['emulators'] if e['state'] == 'booting')
    ready = sum(1 for e in stats['emulators'] if e['state'] == 'ready')

    print(f"  Ready:              {ready}")
    print(f"  Booting:            {booting}")

    for emu in stats['emulators']:
        print(f"    - {emu['id']}: {emu['state']} (port {emu['port']})")

    return stats

print("🧪 Testing Pool Replenishment Logic")
print("=" * 50)

print("\n1️⃣ Initial State")
stats1 = check_stats()

print("\n2️⃣ Requesting an emulator...")
resp = requests.post(
    f"{BASE_URL}/emulators",
    json={"user_id": "test_user", "avd_name": "test_avd"}
)

if resp.status_code == 200:
    emu = resp.json()
    print(f"✅ Got emulator: {emu['id']}")
else:
    print(f"❌ Failed: {resp.text}")
    sys.exit(1)

print("\n3️⃣ After Assignment")
stats2 = check_stats()

print("\n🔍 Analysis:")
booting = sum(1 for e in stats2['emulators'] if e['state'] == 'booting')
expected_total = stats2['pool_size'] + stats2['assigned']

if stats2['total_emulators'] > expected_total + 1:
    print(f"⚠️  BUG: Too many emulators!")
    print(f"   Expected max: {expected_total} (pool_size + assigned)")
    print(f"   Actual: {stats2['total_emulators']}")
    print(f"   Booting unnecessarily: {booting}")
elif booting <= stats2['pool_size']:
    print(f"✅ CORRECT: Only {booting} emulator(s) booting to replenish pool")
    print(f"   This matches pool_size = {stats2['pool_size']}")
