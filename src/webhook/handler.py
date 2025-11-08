"""
AWS Lambda handler for ServiceNow webhook integration.

This handler receives POST requests from ServiceNow containing incident data,
invokes the AgentCore agent for analysis, and returns the agent's response.

Architecture:
    ServiceNow → API Gateway → Lambda (this handler) → AgentCore Agent → Response

Environment Variables:
    AGENT_RUNTIME_ENDPOINT: URL of the deployed AgentCore agent runtime
    LOG_LEVEL: Logging level (default: INFO)
"""

import json
import logging
import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Initialize Bedrock Agent Runtime client
bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")

# Get agent configuration from environment
AGENT_ID = os.environ.get("AGENT_ID")
AGENT_ALIAS_ID = os.environ.get("AGENT_ALIAS_ID", "TSTALIASID")


def parse_servicenow_payload(body: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse ServiceNow webhook payload and extract incident data.

    ServiceNow can send webhooks in different formats:
    - Direct incident object
    - Nested under 'record' key
    - Custom webhook format

    Args:
        body: The parsed JSON body from ServiceNow

    Returns:
        Structured incident data

    Raises:
        ValueError: If required fields are missing
    """
    # Try to extract incident from various ServiceNow formats
    incident = body.get("record") or body

    # Extract key fields with defaults
    incident_data = {
        "number": incident.get("number", "UNKNOWN"),
        "short_description": incident.get("short_description", ""),
        "description": incident.get("description", ""),
        "urgency": incident.get("urgency", "3"),
        "impact": incident.get("impact", "3"),
        "priority": incident.get("priority", "4"),
        "state": incident.get("state", "1"),
        "assigned_to": incident.get("assigned_to", ""),
        "assignment_group": incident.get("assignment_group", ""),
        "category": incident.get("category", ""),
        "subcategory": incident.get("subcategory", ""),
        "caller": incident.get("caller_id", ""),
        "sys_created_on": incident.get("sys_created_on", ""),
        "sys_updated_on": incident.get("sys_updated_on", ""),
    }

    # Validate required fields
    if not incident_data["number"] or incident_data["number"] == "UNKNOWN":
        raise ValueError("Missing required field: incident number")

    return incident_data


def build_agent_prompt(incident_data: Dict[str, Any]) -> str:
    """
    Build a prompt for the AgentCore agent based on incident data.

    Args:
        incident_data: Structured incident data

    Returns:
        Formatted prompt string
    """
    prompt = f"""Analyze the following ServiceNow incident:

Ticket Number: {incident_data['number']}
Short Description: {incident_data['short_description']}
Description: {incident_data['description']}
Priority: {incident_data['priority']}
Urgency: {incident_data['urgency']}
Impact: {incident_data['impact']}
Category: {incident_data['category']}
Subcategory: {incident_data['subcategory']}
Assignment Group: {incident_data['assignment_group']}

Please analyze this incident and provide:
1. A summary of the issue
2. Potential root causes
3. Recommended resolution steps
4. Relevant knowledge base articles (if any)
"""
    return prompt


def invoke_agent(prompt: str, session_id: str = None) -> str:
    """
    Invoke the AgentCore agent via Bedrock Agent Runtime.

    Args:
        prompt: The prompt to send to the agent
        session_id: Optional session ID for conversation continuity

    Returns:
        The agent's response text

    Raises:
        RuntimeError: If agent invocation fails
    """
    if not AGENT_ID:
        raise RuntimeError("AGENT_ID environment variable not set")

    try:
        # Prepare invocation parameters
        invoke_params = {
            "agentId": AGENT_ID,
            "agentAliasId": AGENT_ALIAS_ID,
            "inputText": prompt,
        }

        # Add session ID if provided
        if session_id:
            invoke_params["sessionId"] = session_id

        logger.info(f"Invoking agent {AGENT_ID} with prompt length: {len(prompt)}")

        # Invoke the agent
        response = bedrock_agent_runtime.invoke_agent(**invoke_params)

        # Extract response text from event stream
        response_text = ""
        event_stream = response.get("completion", [])

        for event in event_stream:
            if "chunk" in event:
                chunk = event["chunk"]
                if "bytes" in chunk:
                    response_text += chunk["bytes"].decode("utf-8")

        logger.info(f"Agent response length: {len(response_text)}")
        return response_text

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"Bedrock Agent Runtime error [{error_code}]: {error_message}")
        raise RuntimeError(f"Failed to invoke agent: {error_message}")
    except Exception as e:
        logger.error(f"Unexpected error invoking agent: {str(e)}")
        raise RuntimeError(f"Unexpected error: {str(e)}")


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for ServiceNow webhook.

    Args:
        event: Lambda event containing API Gateway request
        context: Lambda context object

    Returns:
        API Gateway response with status code and body
    """
    logger.info("Received ServiceNow webhook request")
    logger.debug(f"Event: {json.dumps(event)}")

    try:
        # Parse request body
        body = event.get("body", "{}")
        if isinstance(body, str):
            body = json.loads(body)

        logger.info(f"Parsed request body with keys: {list(body.keys())}")

        # Extract incident data from ServiceNow payload
        incident_data = parse_servicenow_payload(body)
        logger.info(f"Processing incident: {incident_data['number']}")

        # Build prompt for agent
        prompt = build_agent_prompt(incident_data)

        # Generate session ID from incident number for continuity
        session_id = f"servicenow-{incident_data['number']}"

        # Invoke agent
        agent_response = invoke_agent(prompt, session_id)

        # Build success response
        response_body = {
            "success": True,
            "incident_number": incident_data["number"],
            "analysis": agent_response,
            "message": "Incident analyzed successfully",
        }

        logger.info(f"Successfully processed incident {incident_data['number']}")

        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            },
            "body": json.dumps(response_body),
        }

    except ValueError as e:
        # Invalid request payload
        logger.error(f"Invalid payload: {str(e)}")
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": False,
                "error": "Invalid request payload",
                "details": str(e),
            }),
        }

    except RuntimeError as e:
        # Agent invocation failed
        logger.error(f"Agent invocation error: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": False,
                "error": "Failed to invoke agent",
                "details": str(e),
            }),
        }

    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": False,
                "error": "Internal server error",
                "details": str(e),
            }),
        }
