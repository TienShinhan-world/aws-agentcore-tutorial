"""
AWS Lambda handler for ServiceNow API operations via AgentCore Gateway.

This Lambda is exposed as MCP tools through AgentCore Gateway:
- update_servicenow_ticket: Add work notes and change state
- create_servicenow_comment: Add customer-visible comment
- resolve_servicenow_ticket: Mark incident as resolved

The Lambda receives tool invocations from AgentCore Gateway (not API Gateway),
so the event format is the tool arguments directly.

Environment Variables:
    SERVICENOW_SECRET_NAME: Secrets Manager secret name (default: servicenow/credentials)
    AWS_REGION: AWS region (default: eu-central-1)
    LOG_LEVEL: Logging level (default: INFO)
"""

import json
import logging
import os
from typing import Any, Dict

# Import from local modules (will be packaged with Lambda)
from config import ServiceNowConfig
from client import ServiceNowClient, ServiceNowError, INCIDENT_STATES

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Global config (reused across Lambda invocations)
_config: ServiceNowConfig = None


def get_config() -> ServiceNowConfig:
    """Get or create ServiceNow configuration (singleton pattern for Lambda reuse)."""
    global _config
    if _config is None:
        secret_name = os.environ.get("SERVICENOW_SECRET_NAME", "servicenow/credentials")
        region = os.environ.get("AWS_REGION", "eu-central-1")
        logger.info(f"Loading ServiceNow config from secret: {secret_name}")
        _config = ServiceNowConfig.from_secrets_manager(secret_name, region)
    return _config


def update_ticket_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle update_servicenow_ticket tool invocations.

    Updates an incident with work notes and optionally changes its state.

    Args:
        event: Tool arguments containing:
            - ticket_number (required): ServiceNow incident number
            - work_notes (required): Work notes to add
            - state (optional): New state (1=New, 2=In Progress, 3=On Hold)

    Returns:
        Result dictionary with success status and details.
    """
    ticket_number = event.get("ticket_number")
    work_notes = event.get("work_notes")
    state = event.get("state", INCIDENT_STATES["IN_PROGRESS"])

    # Validate required fields
    if not ticket_number:
        return {
            "success": False,
            "error": "Missing required parameter: ticket_number",
        }
    if not work_notes:
        return {
            "success": False,
            "error": "Missing required parameter: work_notes",
        }

    try:
        config = get_config()
        with ServiceNowClient(config) as client:
            # Add prefix to work notes to identify AI agent updates
            formatted_notes = f"[AI Agent Analysis]\n\n{work_notes}"
            result = client.add_work_notes(
                number=ticket_number,
                notes=formatted_notes,
                state=state,
            )

        logger.info(f"Successfully updated ticket {ticket_number}")
        return {
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket updated successfully",
            "state": state,
            "sys_id": result.get("sys_id"),
        }

    except ServiceNowError as e:
        logger.error(f"ServiceNow error updating {ticket_number}: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": e.status_code,
        }
    except Exception as e:
        logger.error(f"Unexpected error updating {ticket_number}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


def create_comment_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle create_servicenow_comment tool invocations.

    Adds a customer-visible comment to an incident.

    Args:
        event: Tool arguments containing:
            - ticket_number (required): ServiceNow incident number
            - comment (required): Comment text visible to customer

    Returns:
        Result dictionary with success status and details.
    """
    ticket_number = event.get("ticket_number")
    comment = event.get("comment")

    # Validate required fields
    if not ticket_number:
        return {
            "success": False,
            "error": "Missing required parameter: ticket_number",
        }
    if not comment:
        return {
            "success": False,
            "error": "Missing required parameter: comment",
        }

    try:
        config = get_config()
        with ServiceNowClient(config) as client:
            result = client.add_comment(
                number=ticket_number,
                comment=comment,
            )

        logger.info(f"Successfully added comment to {ticket_number}")
        return {
            "success": True,
            "ticket_number": ticket_number,
            "message": "Comment added successfully",
            "sys_id": result.get("sys_id"),
        }

    except ServiceNowError as e:
        logger.error(f"ServiceNow error adding comment to {ticket_number}: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": e.status_code,
        }
    except Exception as e:
        logger.error(f"Unexpected error adding comment to {ticket_number}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


def resolve_ticket_handler(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle resolve_servicenow_ticket tool invocations.

    Marks an incident as resolved with resolution notes.

    Args:
        event: Tool arguments containing:
            - ticket_number (required): ServiceNow incident number
            - resolution_notes (required): Notes explaining the resolution
            - resolution_code (optional): Resolution code (default: "Solved (Permanently)")

    Returns:
        Result dictionary with success status and details.
    """
    ticket_number = event.get("ticket_number")
    resolution_notes = event.get("resolution_notes")
    resolution_code = event.get("resolution_code", "Solved (Permanently)")

    # Validate required fields
    if not ticket_number:
        return {
            "success": False,
            "error": "Missing required parameter: ticket_number",
        }
    if not resolution_notes:
        return {
            "success": False,
            "error": "Missing required parameter: resolution_notes",
        }

    try:
        config = get_config()
        with ServiceNowClient(config) as client:
            result = client.resolve_incident(
                number=ticket_number,
                resolution_notes=resolution_notes,
                resolution_code=resolution_code,
            )

        logger.info(f"Successfully resolved ticket {ticket_number}")
        return {
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket resolved successfully",
            "state": "Resolved",
            "resolution_code": resolution_code,
            "sys_id": result.get("sys_id"),
        }

    except ServiceNowError as e:
        logger.error(f"ServiceNow error resolving {ticket_number}: {e}")
        return {
            "success": False,
            "error": str(e),
            "status_code": e.status_code,
        }
    except Exception as e:
        logger.error(f"Unexpected error resolving {ticket_number}: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}",
        }


# Operation dispatcher
HANDLERS = {
    "update_ticket": update_ticket_handler,
    "create_comment": create_comment_handler,
    "resolve_ticket": resolve_ticket_handler,
}


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Main Lambda handler for AgentCore Gateway tool invocations.

    AgentCore Gateway passes tool arguments directly (not wrapped in API Gateway format).
    The operation is determined by:
    1. Explicit 'operation' field in the event
    2. Inference from available parameters

    Response format for AgentCore Gateway:
    {
        "statusCode": 200,  # or 400/500 for errors
        "body": "JSON string with result"
    }

    Args:
        event: Tool arguments from AgentCore Gateway.
        context: Lambda context object with Gateway metadata.

    Returns:
        Response dict with statusCode and body for AgentCore Gateway.
    """
    logger.info(f"=== Lambda Handler Invoked ===")
    logger.info(f"Event: {json.dumps(event)}")

    # Log context info if available (AgentCore Gateway passes metadata here)
    if context and hasattr(context, 'client_context') and context.client_context:
        try:
            custom = getattr(context.client_context, 'custom', {})
            if custom:
                logger.info(f"Gateway Context: {json.dumps(custom)}")
                # Available metadata from AgentCore Gateway:
                # - bedrockagentcoreEndpointId: Gateway endpoint identifier
                # - bedrockagentcoreTargetId: Target route identifier
                # - bedrockagentcoreToolName: Name of the tool being invoked
                # - bedrockagentcoreMessageVersion: Message format version
                # - bedrockagentcoreSessionId: Session identifier
        except Exception as e:
            logger.debug(f"Could not read context: {e}")

    # Determine operation
    operation = event.get("operation")

    if not operation:
        # Infer operation from available parameters
        if "resolution_notes" in event:
            operation = "resolve_ticket"
        elif "comment" in event:
            operation = "create_comment"
        elif "work_notes" in event:
            operation = "update_ticket"
        else:
            logger.error("Unable to determine operation from event")
            error_response = {
                "success": False,
                "error": "Unable to determine operation. Provide 'operation' field or operation-specific parameters.",
            }
            return {
                "statusCode": 400,
                "body": json.dumps(error_response)
            }

    # Get and execute handler
    handler = HANDLERS.get(operation)
    if not handler:
        logger.error(f"Unknown operation: {operation}")
        error_response = {
            "success": False,
            "error": f"Unknown operation: {operation}. Valid operations: {list(HANDLERS.keys())}",
        }
        return {
            "statusCode": 400,
            "body": json.dumps(error_response)
        }

    logger.info(f"Executing operation: {operation}")
    result = handler(event)

    logger.info(f"Operation result: {json.dumps(result)}")
    logger.info(f"=== Lambda Handler Complete ===")

    # Return in AgentCore Gateway expected format
    status_code = 200 if result.get("success", True) else 500
    return {
        "statusCode": status_code,
        "body": json.dumps(result)
    }
