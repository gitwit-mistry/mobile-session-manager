# Mobile Agent Session Manager

Infrastructure for managing Android emulator instances and per-user app sessions with health monitoring and tiered prioritization.

## What This Does

- **Emulator Orchestration**: Programmatically manage Android emulators with warm pool and snapshots
- **Session Lifecycle**: Track user sessions across apps with automatic health monitoring
- **Tiered Priority**: HOT (daily checks) / WARM (weekly) / COLD (on-demand)
- **Lazy Re-Auth**: Returns login method when session expires instead of failing
- **10 REST APIs**: Complete control over emulators and sessions

## Quick Start

### 1. Install Android SDK

```bash
brew install --cask android-commandlinetools

sdkmanager "platform-tools" "platforms;android-33" \
  "system-images;android-33;google_apis;arm64-v8a" "emulator"
```

### 2. Setup Environment

Add to `~/.zshrc`:
```bash
export ANDROID_SDK_ROOT=/opt/homebrew/share/android-commandlinetools
export PATH=$PATH:$ANDROID_SDK_ROOT/emulator:$ANDROID_SDK_ROOT/platform-tools
```

Then: `source ~/.zshrc`

### 3. Create Test AVD

```bash
cd emulator-poc
./setup_avd.sh
```

### 4. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 5. Initialize Database

```bash
python3 seed_data.py
```

This creates test users (alice, bob, charlie), apps (Instagram, Twitter, LinkedIn), and sessions.

### 6. Run the Server

```bash
./start.sh
```

Server runs on http://localhost:8000

API docs: http://localhost:8000/docs

## Testing

### Run All Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run all 48 tests
./run_tests.sh all
```

### Test Categories

```bash
./run_tests.sh fast          # Unit tests only (~2s)
./run_tests.sh integration   # Integration tests
./run_tests.sh coverage      # With coverage report

# Or use pytest directly
pytest tests/ -v
pytest tests/test_part1_emulator.py -v    # Emulator tests (15)
pytest tests/test_part2_sessions.py -v    # Session tests (24)
pytest tests/test_integration.py -v       # Integration tests (9)
```

### What's Tested

**Part 1: Emulator Orchestration (15 tests)**
- Emulator lifecycle, state management, port allocation
- Pool management, snapshots, health checks, auto-recovery

**Part 2: Session Lifecycle (24 tests)**
- Session model, tiers (hot/warm/cold), tier promotion/demotion
- Vision classifier (80/20 mock), lazy re-auth, health history

**Integration (9 tests)**
- Session → Emulator flow, mission execution, data consistency

## API Endpoints

### Emulator Management

```bash
# Create emulator
POST /emulators
curl -X POST http://localhost:8000/emulators \
  -d '{"user_id": "alice", "avd_name": "test_avd"}'

# Get status
GET /emulators/:id/status

# Create snapshot
POST /emulators/:id/snapshot

# Delete emulator
DELETE /emulators/:id

# Pool stats
GET /pool/stats
```

### Session Management

```bash
# List user sessions
GET /users/:id/sessions
curl http://localhost:8000/users/alice/sessions

# Verify session (returns requires_reauth if expired)
POST /users/:id/sessions/:app/verify
curl -X POST http://localhost:8000/users/alice/sessions/instagram/verify \
  -d '{"force": true}'

# Health history
GET /users/:id/sessions/:app/health-history

# Create session
POST /users/:id/sessions

# Tier distribution
GET /users/sessions/tiers/distribution
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         FastAPI REST API (10 endpoints)     │
└────────────┬──────────────┬─────────────────┘
             │              │
    ┌────────▼──────┐  ┌───▼────────────────┐
    │ EmulatorPool  │  │ SQLite Database    │
    │ (warm pool)   │  │ (sessions, health) │
    └────────┬──────┘  └───┬────────────────┘
             │              │
    ┌────────▼──────────────▼────────────────┐
    │ Background Workers:                     │
    │ - Health Monitor (tier-based checks)   │
    │ - Tier Manager (auto promote/demote)   │
    └─────────────────────────────────────────┘
```

## Configuration

**Pool size** (api_main.py line 29):
```python
pool = EmulatorPool(pool_size=1, avd_name="test_avd")
```

**Check intervals** (session_monitor.py line 30):
```python
self.test_mode = True  # False for production
self.check_intervals = {
    SessionTier.HOT: 60,      # 1 min (24h prod)
    SessionTier.WARM: 300,    # 5 min (7d prod)
    SessionTier.COLD: None,   # On-demand
}
```

**Tier thresholds** (tier_manager.py line 18):
```python
self.hot_threshold = 3       # Uses in 7 days → HOT
self.warm_threshold = 1      # Uses in 7 days → WARM
self.cold_threshold_days = 30  # No use → COLD
```

## Project Structure

```
emulator-poc/
├── api_main.py              # Main server (START THIS)
├── emulator_manager.py      # Emulator lifecycle
├── pool_manager.py          # Warm pool management
├── models.py                # Database schema
├── session_api.py           # Session endpoints
├── session_monitor.py       # Background health checks
├── tier_manager.py          # Auto tier management
├── vision_classifier.py     # Mock classifier (80/20)
├── seed_data.py            # Test data generator
├── start.sh                # Launcher script
├── cleanup.sh              # Kill stuck emulators
├── test_sessions.sh        # Session API tests
├── requirements.txt        # Python dependencies
├── requirements-test.txt   # Test dependencies
├── sessions.db             # SQLite database
└── tests/                  # Test suite (48 tests)
    ├── test_part1_emulator.py
    ├── test_part2_sessions.py
    └── test_integration.py
```

## Test Data

After running `python3 seed_data.py`:

**Users:**
- alice (2 sessions: Instagram HOT/alive, Twitter WARM/unknown)
- bob (1 session: LinkedIn WARM/expired)
- charlie (1 session: Instagram COLD/unknown)

**Apps:**
- Instagram (com.instagram.android)
- Twitter (com.twitter.android)
- LinkedIn (com.linkedin.android)

## Session Tiers

- **HOT**: Checked every 60s (test) / 24h (prod) - 3+ uses/week
- **WARM**: Checked every 5min (test) / 7d (prod) - 1-2 uses/week
- **COLD**: On-demand only - 0 uses/month

Sessions auto-promote/demote based on usage.

## Example Usage

```bash
# 1. List Alice's sessions
curl http://localhost:8000/users/alice/sessions

# 2. Verify Instagram session
curl -X POST http://localhost:8000/users/alice/sessions/instagram/verify \
  -d '{"force": true}'

# Response if expired:
{
  "requires_reauth": true,
  "login_method": "password",
  "health_status": "expired"
}

# 3. Get an emulator (if session was alive)
curl -X POST http://localhost:8000/emulators \
  -d '{"user_id": "alice", "snapshot": "session_alice_instagram"}'

# 4. Check pool stats
curl http://localhost:8000/pool/stats

# 5. View health history
curl http://localhost:8000/users/alice/sessions/instagram/health-history
```

## Docker (Alternative)

```bash
docker-compose up --build
```

**Note**: Slow on Mac M4 without KVM. Local setup recommended.

## Troubleshooting

### Emulator won't start
```bash
# Check Android SDK
which emulator
emulator -list-avds

# Clean up stuck emulators
./cleanup.sh
```

### Tests fail
```bash
# Check Python version (need 3.9+)
python3 --version

# Reinstall dependencies
pip install -r requirements-test.txt
```

### Database issues
```bash
# Reset database
rm sessions.db
python3 seed_data.py
```

## Performance

**Mac M4 (no KVM):**
- Emulator boot: 120-180s
- Warm assignment: <1s
- Health check: 1-2s (mock)

**Linux with KVM (expected):**
- Emulator boot: 20-40s
- From snapshot: 5-15s

## POC Limitations

This is a proof-of-concept. For production:
- Replace mock vision classifier with real computer vision
- Implement actual snapshot booting (currently simulated)
- Add login automation (Appium, UI Automator)
- Migrate to PostgreSQL
- Add authentication and security
- Implement mission execution framework

## Statistics

- **Code**: ~2,100 lines Python
- **Tests**: 48 tests (15 emulator, 24 session, 9 integration)
- **APIs**: 10 REST endpoints
- **Database**: 4 tables with relationships
- **Time**: ~3-5s to run all tests

## License

POC - No license
