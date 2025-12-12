#!/usr/bin/env python3
"""
Diagnostic script for testing AgentCore Gateway integration.

This script tests each component of the Gateway integration independently:
1. Cognito token acquisition
2. Gateway tools/list endpoint
3. Gateway tools/call endpoint

Usage:
    # Using environment variables
    export AGENTCORE_GATEWAY_URL="https://..."
    export COGNITO_TOKEN_ENDPOINT="https://..."
    export COGNITO_CLIENT_ID="..."
    export COGNITO_CLIENT_SECRET="..."
    python scripts/test_gateway_integration.py

    # Using gateway_config.json (requires client_secret as argument)
    python scripts/test_gateway_integration.py --config gateway_config.json --client-secret "..."

    # Run specific tests
    python scripts/test_gateway_integration.py --test token
    python scripts/test_gateway_integration.py --test list
    python scripts/test_gateway_integration.py --test call --ticket INC0010466
"""

import argparse
import base64
import json
import os
import sys
from typing import Any, Dict, Optional

import requests


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f" {title}")
    print("=" * 60)


def print_result(success: bool, message: str) -> None:
    """Print a formatted result."""
    status = "[OK]" if success else "[FAIL]"
    print(f"{status} {message}")


def decode_jwt_header(token: str) -> Dict[str, Any]:
    """Decode JWT header (without verification) to inspect claims."""
    try:
        # JWT format: header.payload.signature
        header_b64 = token.split(".")[0]
        # Add padding if needed
        padding = 4 - len(header_b64) % 4
        if padding != 4:
            header_b64 += "=" * padding
        header_json = base64.urlsafe_b64decode(header_b64)
        return json.loads(header_json)
    except Exception as e:
        return {"error": str(e)}


def decode_jwt_payload(token: str) -> Dict[str, Any]:
    """Decode JWT payload (without verification) to inspect claims."""
    try:
        # JWT format: header.payload.signature
        payload_b64 = token.split(".")[1]
        # Add padding if needed
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_json = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_json)
    except Exception as e:
        return {"error": str(e)}


def load_config(config_path: Optional[str] = None, client_secret: Optional[str] = None) -> Dict[str, str]:
    """Load configuration from environment or config file."""
    config = {
        "gateway_url": os.environ.get("AGENTCORE_GATEWAY_URL"),
        "token_endpoint": os.environ.get("COGNITO_TOKEN_ENDPOINT"),
        "client_id": os.environ.get("COGNITO_CLIENT_ID"),
        "client_secret": os.environ.get("COGNITO_CLIENT_SECRET"),
        "scope": os.environ.get("COGNITO_SCOPE", "agentcore-gateway/tools.invoke"),
    }

    # Load from config file if provided
    if config_path and os.path.exists(config_path):
        print(f"Loading config from: {config_path}")
        with open(config_path) as f:
            file_config = json.load(f)

        config["gateway_url"] = config.get("gateway_url") or file_config.get("gateway_url")

        client_info = file_config.get("client_info", {})
        config["client_id"] = config.get("client_id") or client_info.get("client_id")

        # Build token endpoint from user_pool_id if not in env
        if not config["token_endpoint"]:
            user_pool_id = client_info.get("user_pool_id")
            region = file_config.get("region", "eu-central-1")
            if user_pool_id:
                # Need to get the domain name - construct from account ID or use default pattern
                # The domain is usually agentcore-gateway-{account} but we need to derive it
                # For now, require token_endpoint in env or config
                print("WARNING: token_endpoint not found in environment.")
                print(f"  User pool ID: {user_pool_id}")
                print(f"  Please set COGNITO_TOKEN_ENDPOINT environment variable.")

    # Override client_secret if provided as argument
    if client_secret:
        config["client_secret"] = client_secret

    return config


def test_token_acquisition(config: Dict[str, str]) -> Optional[str]:
    """Test Cognito token acquisition."""
    print_header("TEST 1: Cognito Token Acquisition")

    token_endpoint = config.get("token_endpoint")
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    scope = config.get("scope")

    print(f"Token Endpoint: {token_endpoint}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {'*' * 10 if client_secret else 'NOT SET'}")
    print(f"Scope: {scope}")
    print()

    if not all([token_endpoint, client_id, client_secret]):
        missing = []
        if not token_endpoint:
            missing.append("COGNITO_TOKEN_ENDPOINT")
        if not client_id:
            missing.append("COGNITO_CLIENT_ID")
        if not client_secret:
            missing.append("COGNITO_CLIENT_SECRET")
        print_result(False, f"Missing configuration: {', '.join(missing)}")
        return None

    try:
        print("Sending token request...")
        response = requests.post(
            token_endpoint,
            data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}&scope={scope}",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print()

        if response.status_code != 200:
            print(f"Response Body: {response.text}")
            print_result(False, f"Token request failed with status {response.status_code}")
            return None

        data = response.json()
        print(f"Response Body (truncated):")
        display_data = {
            "access_token": data.get("access_token", "")[:50] + "..." if data.get("access_token") else None,
            "token_type": data.get("token_type"),
            "expires_in": data.get("expires_in"),
            "scope": data.get("scope"),
        }
        print(json.dumps(display_data, indent=2))
        print()

        access_token = data.get("access_token")
        if not access_token:
            print_result(False, "No access_token in response")
            return None

        # Decode and display JWT claims
        print("JWT Header:")
        print(json.dumps(decode_jwt_header(access_token), indent=2))
        print()

        print("JWT Payload (claims):")
        payload = decode_jwt_payload(access_token)
        print(json.dumps(payload, indent=2))
        print()

        print_result(True, f"Token acquired successfully (expires in {data.get('expires_in')}s)")
        return access_token

    except requests.exceptions.RequestException as e:
        print_result(False, f"Request error: {e}")
        return None
    except Exception as e:
        print_result(False, f"Unexpected error: {e}")
        return None


def test_gateway_list_tools(config: Dict[str, str], token: str) -> Optional[list]:
    """Test Gateway tools/list endpoint."""
    print_header("TEST 2: Gateway tools/list")

    gateway_url = config.get("gateway_url")
    print(f"Gateway URL: {gateway_url}")
    print()

    if not gateway_url:
        print_result(False, "Gateway URL not configured (AGENTCORE_GATEWAY_URL)")
        return None

    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        }

        print("Request Payload:")
        print(json.dumps(payload, indent=2))
        print()

        print("Sending request...")
        response = requests.post(
            gateway_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            if key.lower() in ["content-type", "x-amzn-requestid", "x-amz-apigw-id"]:
                print(f"  {key}: {value}")
        print()

        print("Response Body:")
        try:
            result = response.json()
            print(json.dumps(result, indent=2))
        except json.JSONDecodeError:
            print(response.text)
            print_result(False, "Response is not valid JSON")
            return None
        print()

        if response.status_code != 200:
            print_result(False, f"Request failed with status {response.status_code}")
            return None

        if "error" in result:
            error = result["error"]
            print_result(False, f"JSON-RPC error: {error.get('message', error)}")
            return None

        # Extract tools from result
        mcp_result = result.get("result", {})
        tools = mcp_result.get("tools", [])

        print(f"\nFound {len(tools)} tools:")
        for tool in tools:
            print(f"  - {tool.get('name')}: {tool.get('description', '')[:50]}...")

        print_result(True, f"Successfully listed {len(tools)} tools")
        return tools

    except requests.exceptions.RequestException as e:
        print_result(False, f"Request error: {e}")
        return None
    except Exception as e:
        print_result(False, f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_gateway_tool_call(config: Dict[str, str], token: str, ticket_number: str = "INC0010466") -> bool:
    """Test Gateway tools/call endpoint."""
    print_header("TEST 3: Gateway tools/call")

    gateway_url = config.get("gateway_url")
    print(f"Gateway URL: {gateway_url}")
    print(f"Test Ticket: {ticket_number}")
    print()

    if not gateway_url:
        print_result(False, "Gateway URL not configured")
        return False

    # Test with update_servicenow_ticket tool
    tool_name = "servicenow-tools___update_servicenow_ticket"
    tool_arguments = {
        "ticket_number": ticket_number,
        "work_notes": "[TEST] Gateway integration diagnostic test - please ignore",
        "state": "2",
    }

    try:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": tool_arguments,
            },
        }

        print("Request Payload:")
        print(json.dumps(payload, indent=2))
        print()

        print("WARNING: This will attempt to update a real ServiceNow ticket!")
        print("Sending request...")

        response = requests.post(
            gateway_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=60,
        )

        print(f"Response Status: {response.status_code}")
        print(f"Response Headers:")
        for key, value in response.headers.items():
            if key.lower() in ["content-type", "x-amzn-requestid", "x-amz-apigw-id"]:
                print(f"  {key}: {value}")
        print()

        print("Response Body (raw):")
        print(response.text)
        print()

        try:
            result = response.json()
            print("Response Body (parsed):")
            print(json.dumps(result, indent=2))
        except json.JSONDecodeError:
            print_result(False, "Response is not valid JSON")
            return False
        print()

        if response.status_code != 200:
            print_result(False, f"Request failed with status {response.status_code}")
            return False

        if "error" in result:
            error = result["error"]
            print_result(False, f"JSON-RPC error: {error.get('message', error)}")
            return False

        # Analyze the result structure
        mcp_result = result.get("result", {})
        print("\nAnalyzing MCP result structure:")
        print(f"  Keys in result: {list(mcp_result.keys())}")

        if "content" in mcp_result:
            content = mcp_result["content"]
            print(f"  Content is a list with {len(content)} items")
            for i, item in enumerate(content):
                print(f"    [{i}] type: {item.get('type')}, text length: {len(item.get('text', ''))}")
                if item.get("type") == "text":
                    try:
                        parsed = json.loads(item.get("text", "{}"))
                        print(f"    [{i}] Parsed text content:")
                        print(json.dumps(parsed, indent=6))
                    except json.JSONDecodeError:
                        print(f"    [{i}] Text content (not JSON): {item.get('text')[:100]}...")

        if "isError" in mcp_result:
            print(f"  isError: {mcp_result['isError']}")

        print_result(True, "Tool call completed")
        return True

    except requests.exceptions.RequestException as e:
        print_result(False, f"Request error: {e}")
        return False
    except Exception as e:
        print_result(False, f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests(config: Dict[str, str], ticket_number: str = "INC0010466") -> None:
    """Run all diagnostic tests."""
    print_header("AGENTCORE GATEWAY INTEGRATION DIAGNOSTICS")
    print(f"Gateway URL: {config.get('gateway_url')}")
    print(f"Token Endpoint: {config.get('token_endpoint')}")
    print(f"Client ID: {config.get('client_id')}")
    print()

    # Test 1: Token acquisition
    token = test_token_acquisition(config)
    if not token:
        print("\n[STOPPED] Cannot continue without valid token")
        return

    # Test 2: List tools
    tools = test_gateway_list_tools(config, token)
    if tools is None:
        print("\n[STOPPED] Cannot list tools")
        return

    # Test 3: Call tool (optional - requires confirmation)
    print_header("TEST 3: Gateway tools/call")
    print(f"This test will attempt to update ticket: {ticket_number}")
    print("This may create real data in ServiceNow if the ticket exists.")
    confirm = input("\nProceed with tool call test? [y/N]: ")
    if confirm.lower() == "y":
        test_gateway_tool_call(config, token, ticket_number)
    else:
        print("Skipped tools/call test")

    print_header("DIAGNOSTIC COMPLETE")


def main():
    parser = argparse.ArgumentParser(
        description="Test AgentCore Gateway integration components",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run all tests with environment variables
    python test_gateway_integration.py

    # Run only token test
    python test_gateway_integration.py --test token

    # Run only list tools test
    python test_gateway_integration.py --test list

    # Run tool call test with specific ticket
    python test_gateway_integration.py --test call --ticket INC0001234

    # Use config file
    python test_gateway_integration.py --config gateway_config.json --client-secret "..."
        """,
    )
    parser.add_argument(
        "--config",
        default="gateway_config.json",
        help="Path to gateway_config.json (default: gateway_config.json)",
    )
    parser.add_argument(
        "--client-secret",
        help="Cognito client secret (overrides environment variable)",
    )
    parser.add_argument(
        "--test",
        choices=["token", "list", "call", "all"],
        default="all",
        help="Specific test to run (default: all)",
    )
    parser.add_argument(
        "--ticket",
        default="INC0010466",
        help="Ticket number for tools/call test (default: INC0010466)",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config, args.client_secret)

    # Validate minimum configuration
    if not config.get("gateway_url"):
        print("ERROR: Gateway URL not configured")
        print("Set AGENTCORE_GATEWAY_URL environment variable or provide --config")
        sys.exit(1)

    if args.test == "all":
        run_all_tests(config, args.ticket)
    elif args.test == "token":
        test_token_acquisition(config)
    elif args.test == "list":
        token = test_token_acquisition(config)
        if token:
            test_gateway_list_tools(config, token)
    elif args.test == "call":
        token = test_token_acquisition(config)
        if token:
            test_gateway_tool_call(config, token, args.ticket)


if __name__ == "__main__":
    main()
