#!/bin/bash
# Test script for ServiceNow webhook integration
# This script can test both local agent and deployed webhook

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
WEBHOOK_URL=""
TEST_MODE="local"

# Sample ticket data
TICKET_DATA='{
  "record": {
    "number": "INC0001234",
    "sys_id": "abc123def456",
    "short_description": "Unable to access VPN from home",
    "description": "User reports that VPN client shows Connection timeout error when trying to connect from home network. Works fine from office. User is using Windows 10 and Cisco AnyConnect VPN client version 4.9.",
    "priority": "2",
    "state": "1",
    "caller_id": "john.doe@example.com",
    "assigned_to": "Support Team",
    "sys_created_on": "2025-10-31 10:30:00",
    "category": "Network",
    "subcategory": "VPN"
  }
}'

usage() {
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Test ServiceNow webhook integration"
    echo ""
    echo "Options:"
    echo "  -u, --url URL          Webhook URL (for testing deployed webhook)"
    echo "  -l, --local            Test local Lambda handler (default)"
    echo "  -t, --ticket FILE      Path to JSON file with custom ticket data"
    echo "  -h, --help             Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --local                                    # Test local Lambda handler"
    echo "  $0 --url https://api.example.com/webhook     # Test deployed webhook"
    echo "  $0 --ticket custom_ticket.json                # Test with custom ticket data"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            WEBHOOK_URL="$2"
            TEST_MODE="remote"
            shift 2
            ;;
        -l|--local)
            TEST_MODE="local"
            shift
            ;;
        -t|--ticket)
            if [[ -f "$2" ]]; then
                TICKET_DATA=$(cat "$2")
            else
                echo -e "${RED}Error: Ticket file not found: $2${NC}"
                exit 1
            fi
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

echo -e "${GREEN}ServiceNow Webhook Test Script${NC}"
echo "================================"
echo ""

if [[ "$TEST_MODE" == "local" ]]; then
    echo -e "${YELLOW}Testing local Lambda handler...${NC}"
    echo ""

    # Check if Python is available
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found${NC}"
        exit 1
    fi

    # Create temporary Python script to test handler
    cat > /tmp/test_webhook_handler.py << 'EOF'
import sys
import json
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../src'))

# Import the handler
from servicenow.webhook_handler import lambda_handler

# Read ticket data from stdin
ticket_data = json.loads(sys.stdin.read())

# Create Lambda event
event = {
    "body": json.dumps(ticket_data),
    "isBase64Encoded": False,
    "httpMethod": "POST",
    "path": "/webhook/servicenow"
}

# Call handler
try:
    response = lambda_handler(event, None)
    print(json.dumps(response, indent=2))
except Exception as e:
    print(json.dumps({
        "statusCode": 500,
        "body": json.dumps({"error": str(e)})
    }, indent=2))
    sys.exit(1)
EOF

    # Run the test
    echo "$TICKET_DATA" | python3 /tmp/test_webhook_handler.py

    # Cleanup
    rm /tmp/test_webhook_handler.py

    echo ""
    echo -e "${GREEN}Local test completed${NC}"

elif [[ "$TEST_MODE" == "remote" ]]; then
    echo -e "${YELLOW}Testing deployed webhook...${NC}"
    echo "Webhook URL: $WEBHOOK_URL"
    echo ""

    if [[ -z "$WEBHOOK_URL" ]]; then
        echo -e "${RED}Error: Webhook URL not provided${NC}"
        echo "Get the webhook URL from CDK output:"
        echo "  cd infrastructure/cdk && npm run cdk deploy"
        echo ""
        echo "Or retrieve it from CloudFormation:"
        echo "  aws cloudformation describe-stacks --stack-name ServiceNowWebhookStack \\"
        echo "    --query 'Stacks[0].Outputs[?OutputKey==\`WebhookURL\`].OutputValue' --output text"
        exit 1
    fi

    # Test with curl
    if ! command -v curl &> /dev/null; then
        echo -e "${RED}Error: curl not found${NC}"
        exit 1
    fi

    echo "Sending webhook request..."
    RESPONSE=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$WEBHOOK_URL" \
        -H "Content-Type: application/json" \
        -d "$TICKET_DATA")

    # Parse response
    HTTP_BODY=$(echo "$RESPONSE" | sed -e 's/HTTP_STATUS\:.*//g')
    HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\n' | sed -e 's/.*HTTP_STATUS://')

    echo ""
    echo "Response Status: $HTTP_STATUS"
    echo "Response Body:"
    echo "$HTTP_BODY" | python3 -m json.tool 2>/dev/null || echo "$HTTP_BODY"
    echo ""

    if [[ "$HTTP_STATUS" == "200" ]]; then
        echo -e "${GREEN}Webhook test successful!${NC}"
    else
        echo -e "${RED}Webhook test failed with status $HTTP_STATUS${NC}"
        exit 1
    fi
fi

echo ""
echo -e "${GREEN}Test complete!${NC}"
