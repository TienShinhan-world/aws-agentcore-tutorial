#!/usr/bin/env python3
"""
Script to set up AgentCore Gateway with ServiceNow tool targets.

This script creates or updates an AgentCore Gateway endpoint and configures
Lambda-based MCP tools for ServiceNow operations:
- update_servicenow_ticket: Add work notes and change state
- create_servicenow_comment: Add customer-visible comment
- resolve_servicenow_ticket: Mark incident as resolved

Usage:
    python scripts/setup_gateway.py \
        --lambda-arn arn:aws:lambda:eu-central-1:123456789:function:ServiceNowApiHandler \
        --role-arn arn:aws:iam::123456789:role/AgentCoreGatewayServiceNowRole \
        --user-pool-id eu-central-1_XXXXXXX \
        --client-id XXXXXXXXXXXXXXXXXXXX \
        --region eu-central-1

Prerequisites:
    1. AWS CLI configured with appropriate permissions
    2. bedrock-agentcore-starter-toolkit installed
"""

import argparse
import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ServiceNow tool schema definition - matches lambda_handler.py operations
SERVICENOW_TOOL_SCHEMA = {
    "inlinePayload": [
        {
            "name": "update_servicenow_ticket",
            "description": "Update a ServiceNow incident with work notes and optionally change its state. Use this tool for adding internal notes visible to support staff.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "ticket_number": {
                        "type": "string",
                        "description": "ServiceNow incident number (e.g., INC0001234)"
                    },
                    "work_notes": {
                        "type": "string",
                        "description": "Work notes to add to the incident (internal, visible to support staff only)"
                    },
                    "state": {
                        "type": "string",
                        "description": "New state for the incident: 1=New, 2=In Progress, 3=On Hold (default: 2)"
                    }
                },
                "required": ["ticket_number", "work_notes"]
            }
        },
        {
            "name": "create_servicenow_comment",
            "description": "Add a customer-visible comment to a ServiceNow incident. Use this tool when you need to communicate with the ticket requester.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "ticket_number": {
                        "type": "string",
                        "description": "ServiceNow incident number (e.g., INC0001234)"
                    },
                    "comment": {
                        "type": "string",
                        "description": "Comment text that will be visible to the customer/requester"
                    }
                },
                "required": ["ticket_number", "comment"]
            }
        },
        {
            "name": "resolve_servicenow_ticket",
            "description": "Mark a ServiceNow incident as resolved with resolution notes. Use this tool when the issue has been fixed and you want to close the ticket.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "ticket_number": {
                        "type": "string",
                        "description": "ServiceNow incident number (e.g., INC0001234)"
                    },
                    "resolution_notes": {
                        "type": "string",
                        "description": "Notes explaining how the issue was resolved"
                    },
                    "resolution_code": {
                        "type": "string",
                        "description": "Resolution code categorizing the fix (default: Solved (Permanently))"
                    }
                },
                "required": ["ticket_number", "resolution_notes"]
            }
        }
    ]
}


def find_existing_gateway(client, gateway_name: str) -> Optional[Dict[str, Any]]:
    """
    Find an existing gateway by name.

    Args:
        client: GatewayClient instance
        gateway_name: Name of the gateway to find

    Returns:
        Gateway dict if found, None otherwise
    """
    try:
        gateways = client.client.list_gateways()
        for gw in gateways.get("gateways", []):
            if gw.get("name", "").lower() == gateway_name.lower():
                logger.info(f"Found existing gateway: {gw.get('gatewayId')}")
                # Get full gateway details
                gateway_details = client.client.get_gateway(
                    gatewayIdentifier=gw["gatewayId"]
                )
                return gateway_details
    except Exception as e:
        logger.debug(f"Error listing gateways: {e}")
    return None


def find_existing_target(client, gateway_id: str, target_name: str) -> Optional[Dict[str, Any]]:
    """
    Find an existing target by name within a gateway.

    Args:
        client: GatewayClient instance
        gateway_id: Gateway identifier
        target_name: Name of the target to find

    Returns:
        Target dict if found, None otherwise
    """
    try:
        targets = client.client.list_gateway_targets(gatewayIdentifier=gateway_id)
        for target in targets.get("targets", []):
            if target.get("name", "").lower() == target_name.lower():
                logger.info(f"Found existing target: {target.get('targetId')}")
                return target
    except Exception as e:
        logger.debug(f"Error listing targets: {e}")
    return None


def delete_target(client, gateway_id: str, target_id: str) -> bool:
    """
    Delete a gateway target.

    Args:
        client: GatewayClient instance
        gateway_id: Gateway identifier
        target_id: Target identifier

    Returns:
        True if deleted successfully
    """
    try:
        client.client.delete_gateway_target(
            gatewayIdentifier=gateway_id,
            targetId=target_id
        )
        logger.info(f"Deleted target: {target_id}")
        return True
    except Exception as e:
        logger.error(f"Error deleting target: {e}")
        return False


def setup_gateway_with_toolkit(
    lambda_arn: str,
    region: str,
    role_arn: Optional[str] = None,
    user_pool_id: Optional[str] = None,
    client_id: Optional[str] = None,
    gateway_name: str = "ServiceNowGateway",
) -> Dict[str, Any]:
    """
    Set up or update AgentCore Gateway using the official toolkit.

    If a gateway with the same name exists, it will be updated.
    Otherwise, a new gateway will be created.

    Args:
        lambda_arn: ServiceNow API Lambda ARN
        region: AWS region
        role_arn: Optional IAM role ARN for Gateway (created if not provided)
        user_pool_id: Optional Cognito User Pool ID (created if not provided)
        client_id: Optional Cognito App Client ID
        gateway_name: Name for the Gateway

    Returns:
        Setup result with gateway details
    """
    from bedrock_agentcore_starter_toolkit.operations.gateway.client import GatewayClient

    logger.info("=" * 60)
    logger.info("AgentCore Gateway Setup for ServiceNow")
    logger.info("=" * 60)
    logger.info(f"Region: {region}")
    logger.info(f"Lambda ARN: {lambda_arn}")
    logger.info(f"Gateway Name: {gateway_name}")

    # Initialize client
    client = GatewayClient(region_name=region)
    client.logger.setLevel(logging.INFO)

    # Check for existing gateway
    existing_gateway = find_existing_gateway(client, gateway_name)

    if existing_gateway:
        logger.info("=" * 60)
        logger.info("EXISTING GATEWAY FOUND - Updating...")
        logger.info("=" * 60)
        gateway = existing_gateway
        gateway_id = gateway["gatewayId"]
        gateway_url = gateway.get("gatewayUrl")

        # Use existing client info
        client_info = {
            "note": "Using existing gateway configuration",
            "user_pool_id": user_pool_id,
            "client_id": client_id
        }
    else:
        logger.info("=" * 60)
        logger.info("CREATING NEW GATEWAY...")
        logger.info("=" * 60)

        # Step 1: Create or use OAuth authorizer
        if user_pool_id and client_id:
            logger.info("Using existing Cognito configuration...")
            discovery_url = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}/.well-known/openid-configuration"
            authorizer_config = {
                "customJWTAuthorizer": {
                    "allowedClients": [client_id],
                    "discoveryUrl": discovery_url
                }
            }
            client_info = {
                "user_pool_id": user_pool_id,
                "client_id": client_id,
                "note": "Using existing Cognito from CDK stack"
            }
        else:
            logger.info("Creating OAuth authorization server...")
            cognito_response = client.create_oauth_authorizer_with_cognito(gateway_name)
            authorizer_config = cognito_response["authorizer_config"]
            client_info = cognito_response["client_info"]
            logger.info("✓ Authorization server created")

        # Step 2: Create Gateway
        logger.info("Creating Gateway...")
        gateway = client.create_mcp_gateway(
            name=gateway_name,
            role_arn=role_arn,
            authorizer_config=authorizer_config,
            enable_semantic_search=True,
        )
        gateway_id = gateway["gatewayId"]
        gateway_url = gateway["gatewayUrl"]
        logger.info(f"✓ Gateway created: {gateway_url}")

        # Step 3: Fix IAM permissions if role was auto-created
        if role_arn is None:
            logger.info("Fixing IAM permissions for auto-created role...")
            client.fix_iam_permissions(gateway)
            logger.info("Waiting 30s for IAM propagation...")
            time.sleep(30)
            logger.info("✓ IAM permissions configured")

    # Step 4: Handle Lambda target
    target_name = "servicenow-tools"
    existing_target = find_existing_target(client, gateway_id, target_name)

    if existing_target:
        logger.info(f"Target '{target_name}' already exists - deleting to recreate with updated schema...")
        delete_target(client, gateway_id, existing_target["targetId"])
        # Wait for deletion to propagate
        time.sleep(5)

    # Step 5: Create Lambda target with ServiceNow tools
    logger.info("Adding Lambda target with ServiceNow tools...")
    logger.info(f"Tool schema contains {len(SERVICENOW_TOOL_SCHEMA['inlinePayload'])} tools:")
    for tool in SERVICENOW_TOOL_SCHEMA["inlinePayload"]:
        logger.info(f"  - {tool['name']}")

    lambda_target = client.create_mcp_gateway_target(
        gateway=gateway,
        name=target_name,
        target_type="lambda",
        target_payload={
            "lambdaArn": lambda_arn,
            "toolSchema": SERVICENOW_TOOL_SCHEMA
        },
        credentials=None,
    )
    logger.info("✓ Lambda target added")

    # Step 6: Save configuration
    config = {
        "gateway_url": gateway_url,
        "gateway_id": gateway_id,
        "region": region,
        "lambda_arn": lambda_arn,
        "target_name": target_name,
        "tools": [t["name"] for t in SERVICENOW_TOOL_SCHEMA["inlinePayload"]],
        "client_info": client_info
    }

    config_path = "gateway_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return config


def main():
    parser = argparse.ArgumentParser(
        description="Set up or update AgentCore Gateway with ServiceNow tools"
    )
    parser.add_argument(
        "--lambda-arn",
        required=True,
        help="ARN of the ServiceNow API Lambda function"
    )
    parser.add_argument(
        "--role-arn",
        default=None,
        help="ARN of the IAM role for Gateway (optional, will be created if not provided)"
    )
    parser.add_argument(
        "--user-pool-id",
        default=None,
        help="Cognito User Pool ID (optional, will be created if not provided)"
    )
    parser.add_argument(
        "--client-id",
        default=None,
        help="Cognito App Client ID (optional, will be created if not provided)"
    )
    parser.add_argument(
        "--region",
        default="eu-central-1",
        help="AWS region (default: eu-central-1)"
    )
    parser.add_argument(
        "--gateway-name",
        default="ServiceNowGateway",
        help="Name for the Gateway (default: ServiceNowGateway)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        result = setup_gateway_with_toolkit(
            lambda_arn=args.lambda_arn,
            region=args.region,
            role_arn=args.role_arn,
            user_pool_id=args.user_pool_id,
            client_id=args.client_id,
            gateway_name=args.gateway_name,
        )

        logger.info("")
        logger.info("=" * 60)
        logger.info("GATEWAY SETUP COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Gateway ID: {result['gateway_id']}")
        logger.info(f"Gateway URL: {result['gateway_url']}")
        logger.info(f"Tools configured: {', '.join(result['tools'])}")
        logger.info("")
        logger.info("Configuration saved to: gateway_config.json")
        logger.info("")
        logger.info("Next Steps:")
        logger.info("1. Update your agent to use the Gateway URL")
        logger.info("2. Set the AGENTCORE_GATEWAY_URL environment variable:")
        logger.info(f"   export AGENTCORE_GATEWAY_URL={result['gateway_url']}")
        logger.info("")

        # Output as JSON for scripting
        print("\n--- JSON Output ---")
        print(json.dumps(result, indent=2))

    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.error("Please install the toolkit: pip install bedrock-agentcore-starter-toolkit")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Gateway setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
