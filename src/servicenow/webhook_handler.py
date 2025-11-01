"""
ServiceNow Webhook Handler for AWS Lambda

This Lambda function receives webhook calls from ServiceNow when new tickets are created,
parses the ticket data, and invokes the AgentCore agent for analysis.
"""
import json
import logging
import os
from typing import Dict, Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_servicenow_payload(body: str) -> Dict[str, Any]:
    """
    Parse ServiceNow webhook payload.

    ServiceNow typically sends webhook data as JSON in the request body.

    Args:
        body: Request body string

    Returns:
        Dict: Parsed ticket data

    Raises:
        ValueError: If payload cannot be parsed
    """
    try:
        payload = json.loads(body)

        # ServiceNow webhook can send data in different formats
        # Usually it's in a "record" field or directly in the root
        if "record" in payload:
            ticket_data = payload["record"]
        elif "result" in payload:
            ticket_data = payload["result"]
        else:
            # Assume the entire payload is the ticket data
            ticket_data = payload

        logger.info(f"Parsed ticket data for incident: {ticket_data.get('number', 'Unknown')}")

        return ticket_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON payload: {e}")
        raise ValueError(f"Invalid JSON payload: {e}")


def invoke_agent(ticket_data: Dict[str, Any]) -> str:
    """
    Invoke the AgentCore agent with ticket data.

    This function calls the agent deployed via Bedrock AgentCore to analyze
    the ticket and update ServiceNow.

    Args:
        ticket_data: Ticket data from ServiceNow

    Returns:
        str: Agent response

    Raises:
        Exception: If agent invocation fails
    """
    # Format the prompt for the agent
    ticket_json = json.dumps(ticket_data)
    prompt = f"""New ServiceNow ticket received via webhook:

{ticket_json}

Please analyze this ticket, search the knowledge base for relevant solutions,
and update the ticket in ServiceNow with your recommended resolution.
"""

    logger.info(f"Invoking agent for ticket {ticket_data.get('number', 'Unknown')}")

    # Import agent module and invoke
    try:
        # Import the agent module
        import sys
        import os
        # Add src directory to path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

        from agent.my_agent import agent

        # Invoke the agent
        response = agent(prompt)

        # Extract text from response
        if hasattr(response, 'message'):
            agent_response = response.message['content'][0]['text']
        else:
            agent_response = str(response)

        logger.info(f"Agent completed analysis for ticket {ticket_data.get('number', 'Unknown')}")

        return agent_response

    except Exception as e:
        logger.error(f"Failed to invoke agent: {e}", exc_info=True)
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for ServiceNow webhook.

    This function is triggered by API Gateway when ServiceNow sends a webhook
    notification about a new or updated ticket.

    Args:
        event: Lambda event from API Gateway
        context: Lambda context

    Returns:
        Dict: HTTP response for API Gateway
    """
    try:
        logger.info("Received ServiceNow webhook request")
        logger.info(f"Event: {json.dumps(event)}")

        # Extract body from API Gateway event
        body = event.get('body', '{}')

        # If body is base64 encoded (from API Gateway), decode it
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')

        # Parse ServiceNow payload
        ticket_data = parse_servicenow_payload(body)

        # Get ticket number for logging
        ticket_number = ticket_data.get('number', 'Unknown')

        logger.info(f"Processing ticket {ticket_number}")

        # Invoke the agent
        agent_response = invoke_agent(ticket_data)

        # Return success response
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "success": True,
                "ticket_number": ticket_number,
                "message": "Ticket processed successfully",
                "agent_analysis": agent_response
            })
        }

        logger.info(f"Successfully processed ticket {ticket_number}")

        return response

    except ValueError as e:
        # Invalid payload
        logger.error(f"Invalid payload: {e}")
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "success": False,
                "error": "Invalid payload",
                "details": str(e)
            })
        }

    except Exception as e:
        # Internal error
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "success": False,
                "error": "Internal server error",
                "details": str(e)
            })
        }


# For local testing
if __name__ == "__main__":
    # Sample ServiceNow webhook payload for testing
    test_event = {
        "body": json.dumps({
            "record": {
                "number": "INC0001234",
                "short_description": "Unable to access VPN from home",
                "description": "User reports that VPN client shows 'Connection timeout' error when trying to connect from home network. Works fine from office.",
                "priority": "2",
                "state": "1",
                "sys_id": "abc123",
                "caller_id": "john.doe@example.com",
                "assigned_to": "Support Team",
                "sys_created_on": "2025-10-31 10:30:00",
                "category": "Network",
                "subcategory": "VPN"
            }
        })
    }

    print("Testing webhook handler locally...")
    response = lambda_handler(test_event, None)
    print(f"Response: {json.dumps(response, indent=2)}")
