#!/bin/bash
# Comprehensive test runner for Mobile Agent Session Manager

set -e

echo "🧪 Mobile Agent Session Manager - Test Suite"
echo "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "=" "="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest not found. Installing test dependencies..."
    pip install -r requirements-test.txt
fi

# Test categories
run_unit_tests() {
    echo -e "${BLUE}📋 Running Unit Tests${NC}"
    echo "Testing individual components..."
    pytest tests/test_part1_emulator.py tests/test_part2_sessions.py -v -m "not integration"
}

run_integration_tests() {
    echo ""
    echo -e "${BLUE}🔗 Running Integration Tests${NC}"
    echo "Testing combined functionality..."
    pytest tests/test_integration.py -v
}

run_all_tests() {
    echo -e "${BLUE}🎯 Running All Tests${NC}"
    pytest tests/ -v
}

generate_coverage() {
    echo ""
    echo -e "${BLUE}📊 Generating Coverage Report${NC}"
    pytest tests/ --cov=. --cov-report=html --cov-report=term
    echo ""
    echo "Coverage report generated in htmlcov/index.html"
}

run_fast_tests() {
    echo -e "${BLUE}⚡ Running Fast Tests (Unit Only)${NC}"
    pytest tests/ -v -m "not integration and not slow"
}

# Parse arguments
case "${1:-all}" in
    unit)
        run_unit_tests
        ;;
    integration)
        run_integration_tests
        ;;
    fast)
        run_fast_tests
        ;;
    coverage)
        generate_coverage
        ;;
    all)
        run_all_tests
        ;;
    *)
        echo "Usage: $0 {unit|integration|fast|coverage|all}"
        echo ""
        echo "  unit        - Run unit tests only (Part 1 & 2)"
        echo "  integration - Run integration tests"
        echo "  fast        - Run fast tests (exclude slow/integration)"
        echo "  coverage    - Run all tests with coverage report"
        echo "  all         - Run all tests (default)"
        exit 1
        ;;
esac

# Test result summary
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "Test Summary:"
    pytest tests/ --collect-only -q | tail -5
else
    echo ""
    echo -e "${YELLOW}⚠️  Some tests failed${NC}"
    exit 1
fi
