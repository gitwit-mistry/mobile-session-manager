#!/bin/bash
# Test script for Session Lifecycle API

BASE_URL="http://localhost:8000"

echo "🧪 Testing Session Lifecycle Manager"
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "="

echo ""
echo "1️⃣ Get all sessions for Alice"
curl -s "$BASE_URL/users/alice/sessions" | python3 -m json.tool

echo ""
echo ""
echo "2️⃣ Verify Alice's Instagram session"
curl -s -X POST "$BASE_URL/users/alice/sessions/instagram/verify" \
  -H "Content-Type: application/json" \
  -d '{"force": true}' | python3 -m json.tool

echo ""
echo ""
echo "3️⃣ Get health history for Alice's Instagram"
curl -s "$BASE_URL/users/alice/sessions/instagram/health-history?limit=5" | python3 -m json.tool

echo ""
echo ""
echo "4️⃣ Verify Bob's LinkedIn session (should show expired with re-auth required)"
curl -s -X POST "$BASE_URL/users/bob/sessions/linkedin/verify" \
  -H "Content-Type: application/json" \
  -d '{"force": true}' | python3 -m json.tool

echo ""
echo ""
echo "5️⃣ Get tier distribution"
curl -s "$BASE_URL/users/sessions/tiers/distribution" | python3 -m json.tool

echo ""
echo ""
echo "✅ Tests complete!"
