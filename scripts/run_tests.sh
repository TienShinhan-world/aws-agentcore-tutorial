#!/bin/bash
# Test runner script for AWS AgentCore ServiceNow integration
# This script runs the complete test suite with various options

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
COVERAGE=true
VERBOSE=false
MARKERS=""
PARALLEL=false

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Run tests for AWS AgentCore ServiceNow integration"
    echo ""
    echo "Options:"
    echo "  -t, --type TYPE        Test type: unit, integration, all (default: all)"
    echo "  -m, --markers MARKERS  Pytest markers to run (e.g., 'servicenow', 'webhook')"
    echo "  -c, --no-coverage      Disable coverage report"
    echo "  -v, --verbose          Verbose output"
    echo "  -p, --parallel         Run tests in parallel"
    echo "  -f, --failfast         Stop on first failure"
    echo "  -k, --keyword PATTERN  Run tests matching keyword pattern"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Run all tests with coverage"
    echo "  $0 --type unit                        # Run only unit tests"
    echo "  $0 --markers servicenow               # Run only ServiceNow tests"
    echo "  $0 --type integration --no-coverage   # Run integration tests without coverage"
    echo "  $0 -k test_webhook --verbose          # Run webhook tests with verbose output"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -m|--markers)
            MARKERS="$2"
            shift 2
            ;;
        -c|--no-coverage)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -p|--parallel)
            PARALLEL=true
            shift
            ;;
        -f|--failfast)
            FAILFAST=true
            shift
            ;;
        -k|--keyword)
            KEYWORD="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            usage
            exit 1
            ;;
    esac
done

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  AWS AgentCore ServiceNow Integration - Test Suite       ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠️  Warning: No virtual environment detected${NC}"
    echo "It's recommended to activate a virtual environment first:"
    echo "  source .venv/bin/activate"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}✗ pytest not found${NC}"
    echo "Installing test dependencies..."
    pip install -r tests/requirements-test.txt
    echo ""
fi

# Build pytest command
PYTEST_CMD="pytest"

# Add test type
case $TEST_TYPE in
    unit)
        PYTEST_CMD="$PYTEST_CMD -m unit"
        echo -e "${GREEN}Running unit tests only${NC}"
        ;;
    integration)
        PYTEST_CMD="$PYTEST_CMD -m integration"
        echo -e "${GREEN}Running integration tests only${NC}"
        ;;
    all)
        echo -e "${GREEN}Running all tests${NC}"
        ;;
    *)
        echo -e "${RED}Invalid test type: $TEST_TYPE${NC}"
        exit 1
        ;;
esac

# Add markers if specified
if [[ -n "$MARKERS" ]]; then
    PYTEST_CMD="$PYTEST_CMD -m $MARKERS"
    echo -e "${GREEN}Running tests with markers: $MARKERS${NC}"
fi

# Add keyword filter if specified
if [[ -n "$KEYWORD" ]]; then
    PYTEST_CMD="$PYTEST_CMD -k $KEYWORD"
    echo -e "${GREEN}Running tests matching: $KEYWORD${NC}"
fi

# Add coverage options
if [[ "$COVERAGE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml"
    echo -e "${GREEN}Coverage reporting enabled${NC}"
else
    PYTEST_CMD="$PYTEST_CMD --no-cov"
    echo -e "${YELLOW}Coverage reporting disabled${NC}"
fi

# Add verbose flag
if [[ "$VERBOSE" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD -vv"
    echo -e "${GREEN}Verbose output enabled${NC}"
fi

# Add parallel execution
if [[ "$PARALLEL" == true ]]; then
    # Check if pytest-xdist is installed
    if pip list | grep -q pytest-xdist; then
        PYTEST_CMD="$PYTEST_CMD -n auto"
        echo -e "${GREEN}Parallel execution enabled${NC}"
    else
        echo -e "${YELLOW}pytest-xdist not installed, running sequentially${NC}"
        echo "Install with: pip install pytest-xdist"
    fi
fi

# Add failfast flag
if [[ "$FAILFAST" == true ]]; then
    PYTEST_CMD="$PYTEST_CMD -x"
    echo -e "${GREEN}Fail-fast enabled${NC}"
fi

echo ""
echo -e "${BLUE}Running: $PYTEST_CMD${NC}"
echo ""

# Run tests
$PYTEST_CMD

TEST_EXIT_CODE=$?

echo ""
if [[ $TEST_EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                  ✓ All tests passed!                      ║${NC}"
    echo -e "${GREEN}╚═══════════════════════════════════════════════════════════╝${NC}"

    if [[ "$COVERAGE" == true ]]; then
        echo ""
        echo -e "${BLUE}Coverage report generated:${NC}"
        echo "  HTML: htmlcov/index.html"
        echo "  XML:  coverage.xml"
        echo ""
        echo "View HTML report:"
        echo "  python -m http.server 8000 --directory htmlcov"
        echo "  Then open: http://localhost:8000"
    fi
else
    echo -e "${RED}╔═══════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║                  ✗ Some tests failed                      ║${NC}"
    echo -e "${RED}╚═══════════════════════════════════════════════════════════╝${NC}"
fi

exit $TEST_EXIT_CODE
