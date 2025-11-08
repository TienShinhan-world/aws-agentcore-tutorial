#!/bin/bash

###############################################################################
# ServiceNow Webhook Test Script
#
# This script tests the ServiceNow webhook integration by sending sample
# incident payloads to the deployed API Gateway endpoint or local handler.
#
# Usage:
#   ./test_webhook.sh --url <webhook-url>    # Test deployed webhook
#   ./test_webhook.sh --local                # Test local Lambda handler
#   ./test_webhook.sh --ticket <file.json>   # Use custom ticket data
###############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
WEBHOOK_URL=""
LOCAL_MODE=false
TICKET_FILE=""

# Sample incident data
SAMPLE_INCIDENT='{
  "number": "INC0001234",
  "short_description": "User cannot access shared drive",
  "description": "User reports that they cannot access the shared drive Z: since this morning. Error message: Network path not found",
  "urgency": "2",
  "impact": "2",
  "priority": "2",
  "state": "1",
  "assigned_to": "",
  "assignment_group": "IT Support Level 1",
  "category": "Network",
  "subcategory": "File Share",
  "caller_id": "john.doe@example.com",
  "sys_created_on": "2025-01-15 10:30:00",
  "sys_updated_on": "2025-01-15 10:30:00"
}'

###############################################################################
# Functions
###############################################################################

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Test the ServiceNow webhook integration.

OPTIONS:
    -u, --url <url>         Webhook URL (API Gateway endpoint)
    -l, --local             Test locally using Python
    -t, --ticket <file>     Path to JSON file with ticket data
    -h, --help              Show this help message

EXAMPLES:
    # Test deployed webhook
    $0 --url https://xxx.execute-api.eu-central-1.amazonaws.com/prod/webhook/servicenow

    # Test local handler
    $0 --local

    # Test with custom ticket data
    $0 --url <url> --ticket my_ticket.json

EOF
    exit 0
}

test_deployed_webhook() {
    local url="$1"
    local payload="$2"

    print_header "Testing Deployed Webhook"
    print_info "URL: $url"
    print_info "Sending incident payload..."

    # Send POST request
    response=$(curl -s -w "\n%{http_code}" -X POST "$url" \
        -H "Content-Type: application/json" \
        -d "$payload")

    # Extract status code and body
    http_code=$(echo "$response" | tail -n 1)
    body=$(echo "$response" | sed '$d')

    echo -e "\n${BLUE}Response (HTTP $http_code):${NC}"
    echo "$body" | jq '.' 2>/dev/null || echo "$body"

    if [ "$http_code" -eq 200 ]; then
        print_success "Webhook responded successfully"

        # Check if response has expected structure
        if echo "$body" | jq -e '.success' > /dev/null 2>&1; then
            success=$(echo "$body" | jq -r '.success')
            if [ "$success" = "true" ]; then
                print_success "Agent analysis completed"
                incident_number=$(echo "$body" | jq -r '.incident_number')
                print_info "Incident: $incident_number"

                echo -e "\n${BLUE}Agent Analysis:${NC}"
                echo "$body" | jq -r '.analysis' 2>/dev/null || echo "N/A"
            else
                print_error "Agent analysis failed"
                echo "$body" | jq -r '.error' 2>/dev/null
            fi
        fi
    else
        print_error "Webhook request failed (HTTP $http_code)"
        return 1
    fi
}

test_local_handler() {
    local payload="$1"

    print_header "Testing Local Lambda Handler"

    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 not found"
        exit 1
    fi

    # Check if boto3 is installed
    if ! python3 -c "import boto3" 2>/dev/null; then
        print_warning "boto3 not installed - installing..."
        pip install boto3 > /dev/null
    fi

    # Create test event
    local event=$(cat <<EOF
{
    "body": $payload,
    "headers": {
        "Content-Type": "application/json"
    },
    "httpMethod": "POST",
    "path": "/webhook/servicenow"
}
EOF
)

    print_info "Creating test event..."
    echo "$event" > /tmp/test_event.json

    # Set environment variables
    export AGENT_ID="${AGENT_ID:-test-agent-id}"
    export AGENT_ALIAS_ID="${AGENT_ALIAS_ID:-TSTALIASID}"
    export LOG_LEVEL="INFO"

    print_info "AGENT_ID: $AGENT_ID"
    print_info "Running handler..."

    # Run the handler
    python3 << 'PYTHON_SCRIPT'
import json
import sys
import os

# Add src/webhook to path
sys.path.insert(0, 'src/webhook')

# Import handler
import handler

# Load test event
with open('/tmp/test_event.json') as f:
    event = json.load(f)

# Invoke handler
try:
    response = handler.lambda_handler(event, None)
    print("\nResponse:")
    print(json.dumps(response, indent=2))

    if response['statusCode'] == 200:
        sys.exit(0)
    else:
        sys.exit(1)
except Exception as e:
    print(f"\nError: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_SCRIPT

    local exit_code=$?

    if [ $exit_code -eq 0 ]; then
        print_success "Local test passed"
    else
        print_error "Local test failed"
        return 1
    fi
}

###############################################################################
# Main Script
###############################################################################

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            WEBHOOK_URL="$2"
            shift 2
            ;;
        -l|--local)
            LOCAL_MODE=true
            shift
            ;;
        -t|--ticket)
            TICKET_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            ;;
    esac
done

# Determine payload to use
if [ -n "$TICKET_FILE" ]; then
    if [ ! -f "$TICKET_FILE" ]; then
        print_error "Ticket file not found: $TICKET_FILE"
        exit 1
    fi
    PAYLOAD=$(cat "$TICKET_FILE")
    print_info "Using ticket data from: $TICKET_FILE"
else
    PAYLOAD="$SAMPLE_INCIDENT"
    print_info "Using sample incident data"
fi

# Run tests
if [ "$LOCAL_MODE" = true ]; then
    test_local_handler "$PAYLOAD"
elif [ -n "$WEBHOOK_URL" ]; then
    test_deployed_webhook "$WEBHOOK_URL" "$PAYLOAD"
else
    print_error "Please specify either --url or --local"
    echo ""
    show_usage
fi

print_success "Test completed"
