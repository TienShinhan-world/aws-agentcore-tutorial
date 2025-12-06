"""
AWS Lambda handler for ServiceNow webhook integration.

This handler receives POST requests from ServiceNow containing incident data,
invokes the AgentCore agent for analysis, and returns the agent's response.

Architecture:
    ServiceNow → API Gateway → Lambda (this handler) → AgentCore Agent → Response

Environment Variables:
    AGENT_RUNTIME_ARN: ARN of the deployed AgentCore agent runtime
    LOG_LEVEL: Logging level (default: INFO)
"""

import json
import logging
import os
import uuid
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError

# Configure logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
logger = logging.getLogger()
logger.setLevel(LOG_LEVEL)

# Initialize Bedrock AgentCore client
REGION = os.environ.get("AWS_REGION", "eu-central-1")
bedrock_agentcore = boto3.client("bedrock-agentcore", region_name=REGION)

# Get agent configuration from environment
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")


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


def generate_session_id(incident_number: str) -> str:
    """
    Generate a session ID that meets AgentCore requirements (33+ characters).

    Args:
        incident_number: The ServiceNow incident number

    Returns:
        A valid session ID string (33+ characters)
    """
    # Combine incident number with UUID to ensure uniqueness and length
    base = f"servicenow-{incident_number}-{uuid.uuid4().hex}"
    # Ensure minimum 33 characters
    return base[:50] if len(base) >= 33 else base + "0" * (33 - len(base))


def invoke_agent(prompt: str, session_id: str) -> str:
    """
    Invoke the AgentCore agent via Bedrock AgentCore API.

    Args:
        prompt: The prompt to send to the agent
        session_id: Session ID for conversation continuity (must be 33+ chars)

    Returns:
        The agent's response text

    Raises:
        RuntimeError: If agent invocation fails
    """
    if not AGENT_RUNTIME_ARN:
        raise RuntimeError("AGENT_RUNTIME_ARN environment variable not set")

    try:
        # Prepare payload
        payload = json.dumps({"prompt": prompt})

        logger.info(f"Invoking agent {AGENT_RUNTIME_ARN} with prompt length: {len(prompt)}")
        logger.debug(f"Session ID: {session_id}")

        # Invoke the agent using bedrock-agentcore client
        response = bedrock_agentcore.invoke_agent_runtime(
            agentRuntimeArn=AGENT_RUNTIME_ARN,
            runtimeSessionId=session_id,
            payload=payload,
            qualifier="DEFAULT"
        )

        # Read and parse response
        response_body = response["response"].read()
        response_data = json.loads(response_body)

        # Extract response text
        if isinstance(response_data, dict):
            response_text = response_data.get("response", str(response_data))
        else:
            response_text = str(response_data)

        logger.info(f"Agent response length: {len(response_text)}")
        return response_text

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]
        logger.error(f"Bedrock AgentCore error [{error_code}]: {error_message}")
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

        # Generate session ID from incident number (must be 33+ chars for AgentCore)
        session_id = generate_session_id(incident_data["number"])

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
