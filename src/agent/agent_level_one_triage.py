"""
Level One Triage Agent for ServiceNow Backoffice Support.

This agent analyzes ServiceNow incidents received via webhook, searches the
knowledge base for solutions, and updates tickets using AgentCore Gateway.

Architecture:
    ServiceNow → Webhook Lambda → Agent (this file) → Gateway (HTTP) → ServiceNow API Lambda

Gateway Tools Available (via HTTP JSON-RPC):
    - update_servicenow_ticket: Add work notes and change state
    - create_servicenow_comment: Add customer-visible comment
    - resolve_servicenow_ticket: Mark incident as resolved

Environment Variables:
    AGENTCORE_GATEWAY_URL: URL of the AgentCore Gateway MCP endpoint
    COGNITO_CLIENT_ID: Cognito App Client ID for authentication
    COGNITO_CLIENT_SECRET: Cognito App Client Secret
    COGNITO_TOKEN_ENDPOINT: Cognito OAuth2 token endpoint
    COGNITO_SCOPE: OAuth scope (default: agentcore-gateway/tools.invoke)
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

from strands import Agent, tool
from strands.models import BedrockModel
from strands_tools import calculator, current_time
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from botocore.config import Config as BotocoreConfig
from urllib3.exceptions import ProtocolError

# Configure logging
logger = logging.getLogger(__name__)

# Cache for access token
_cached_token: Optional[str] = None
_token_expiry: float = 0


def get_gateway_config() -> Dict[str, Optional[str]]:
    """Get Gateway configuration from environment variables (read at runtime)."""
    return {
        "gateway_url": os.environ.get("AGENTCORE_GATEWAY_URL"),
        "client_id": os.environ.get("COGNITO_CLIENT_ID"),
        "client_secret": os.environ.get("COGNITO_CLIENT_SECRET"),
        "scope": os.environ.get("COGNITO_SCOPE", "agentcore-gateway/tools.invoke"),
        "token_endpoint": os.environ.get("COGNITO_TOKEN_ENDPOINT"),
    }


def is_gateway_configured() -> bool:
    """Check if all Gateway configuration is available."""
    config = get_gateway_config()
    configured = all([
        config["gateway_url"],
        config["client_id"],
        config["client_secret"],
        config["token_endpoint"],
    ])
    if not configured:
        logger.warning(f"Gateway not fully configured. Config: {list(config.keys())} = {[bool(v) for v in config.values()]}")
    return configured


def get_gateway_access_token() -> Optional[str]:
    """
    Obtain OAuth access token from Cognito for Gateway authentication.
    Uses caching to avoid unnecessary token requests.

    Returns:
        Access token string if successful, None otherwise
    """
    import requests
    import time
    global _cached_token, _token_expiry

    # Return cached token if still valid (with 60s buffer)
    if _cached_token and time.time() < _token_expiry - 60:
        logger.debug("Using cached access token")
        return _cached_token

    config = get_gateway_config()
    token_endpoint = config["token_endpoint"]
    client_id = config["client_id"]
    client_secret = config["client_secret"]
    scope = config["scope"]

    if not all([token_endpoint, client_id, client_secret]):
        missing = []
        if not token_endpoint:
            missing.append("COGNITO_TOKEN_ENDPOINT")
        if not client_id:
            missing.append("COGNITO_CLIENT_ID")
        if not client_secret:
            missing.append("COGNITO_CLIENT_SECRET")
        logger.error(f"Missing Cognito configuration: {', '.join(missing)}")
        return None

    try:
        logger.info(f"=== Token Request ===")
        logger.info(f"Token Endpoint: {token_endpoint}")
        logger.info(f"Client ID: {client_id}")
        logger.info(f"Scope: {scope}")

        response = requests.post(
            token_endpoint,
            data=f"grant_type=client_credentials&client_id={client_id}&client_secret={client_secret}&scope={scope}",
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            timeout=10
        )

        logger.info(f"Token Response Status: {response.status_code}")

        if response.status_code != 200:
            logger.error(f"Token request failed: {response.text}")
            return None

        data = response.json()
        _cached_token = data.get('access_token')
        # Cognito tokens typically expire in 3600 seconds
        expires_in = data.get('expires_in', 3600)
        _token_expiry = time.time() + expires_in

        logger.info(f"Token acquired successfully (expires in {expires_in}s, scope: {data.get('scope', 'N/A')})")
        logger.info(f"=== End Token Request ===")
        return _cached_token
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get access token - Request error: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to get access token - Unexpected error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


def call_gateway_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call a Gateway tool via HTTP JSON-RPC.

    Args:
        tool_name: Name of the tool to call (e.g., "servicenow-tools___update_servicenow_ticket")
        arguments: Dictionary of arguments to pass to the tool

    Returns:
        Dictionary with the tool result or error
    """
    import requests

    if not is_gateway_configured():
        return {"error": "Gateway not configured"}

    token = get_gateway_access_token()
    if not token:
        return {"error": "Failed to get access token"}

    config = get_gateway_config()
    gateway_url = config["gateway_url"]

    # Build JSON-RPC request
    jsonrpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    try:
        logger.info(f"=== Gateway Tool Call ===")
        logger.info(f"Gateway URL: {gateway_url}")
        logger.info(f"Tool: {tool_name}")
        logger.info(f"Arguments: {json.dumps(arguments, default=str)}")
        logger.info(f"Full Request: {json.dumps(jsonrpc_request, default=str)}")

        response = requests.post(
            gateway_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=jsonrpc_request,
            timeout=60
        )

        logger.info(f"Response Status: {response.status_code}")
        logger.info(f"Response Headers: {dict(response.headers)}")
        logger.info(f"Response Body (raw): {response.text[:1000]}...")

        if response.status_code != 200:
            logger.error(f"Gateway request failed with status {response.status_code}")
            return {"error": f"HTTP {response.status_code}: {response.text[:500]}"}

        result = response.json()
        logger.info(f"Response Body (parsed): {json.dumps(result, default=str)[:1000]}...")

        # Handle JSON-RPC error
        if "error" in result:
            error = result["error"]
            logger.error(f"JSON-RPC error: {json.dumps(error, default=str)}")
            return {"error": error.get("message", str(error))}

        # Extract MCP result
        mcp_result = result.get("result", {})
        logger.info(f"MCP Result keys: {list(mcp_result.keys())}")

        # MCP tools/call returns {content: [{type, text}], isError: bool}
        if "content" in mcp_result:
            content = mcp_result["content"]
            logger.info(f"MCP content has {len(content)} items")

            if mcp_result.get("isError"):
                logger.error(f"MCP tool returned error flag")

            if content and len(content) > 0:
                first_block = content[0]
                logger.info(f"First content block type: {first_block.get('type')}")

                if first_block.get("type") == "text":
                    text_content = first_block.get("text", "{}")
                    logger.info(f"Text content (first 500 chars): {text_content[:500]}")
                    try:
                        parsed_result = json.loads(text_content)
                        logger.info(f"Gateway tool {tool_name} completed successfully")
                        logger.info(f"=== End Gateway Tool Call ===")
                        return parsed_result
                    except json.JSONDecodeError:
                        logger.warning(f"Text content is not JSON, returning as-is")
                        logger.info(f"=== End Gateway Tool Call ===")
                        return {"result": text_content}

        # Fallback: return result as-is
        logger.info(f"Returning MCP result as-is (no content wrapper)")
        logger.info(f"=== End Gateway Tool Call ===")
        return mcp_result

    except requests.exceptions.RequestException as e:
        logger.error(f"Gateway request failed: {e}")
        logger.info(f"=== End Gateway Tool Call (ERROR) ===")
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error calling gateway tool: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info(f"=== End Gateway Tool Call (ERROR) ===")
        return {"error": str(e)}


WELCOME_MESSAGE = """
Welcome to the ServiceNow Backoffice Support Assistant!
I can help you analyze tickets, search the knowledge base, and update ServiceNow tickets.

Tools available:
- parse_ticket_data: Parse ticket JSON from webhooks
- search_knowledge_base: Search for solutions in the knowledge base
- update_servicenow_ticket: Add work notes to tickets (via Gateway)
- create_servicenow_comment: Add customer-visible comments (via Gateway)
- resolve_servicenow_ticket: Resolve tickets (via Gateway)
"""

SYSTEM_PROMPT = """
You are an AI Service Desk Backlog Agent operating within a ServiceNow ITSM environment.

Your primary mission is to triage, analyze, collaborate on, and progress Service Desk tickets
by using structured reasoning, knowledge base lookup, and precise ticket updates.

You MUST operate strictly within the provided ticket data and available tools.
Never assume missing information. If required information is missing, request it from the user.

--------------------------------------------------
CORE RESPONSIBILITIES
--------------------------------------------------
1. Analyze incoming ticket data received via webhook (JSON format)
2. Identify the issue type, urgency signals, and missing information
3. Search the Knowledge Base for relevant, validated solutions
4. Communicate clearly with:
   - End users (customer-visible comments)
   - Support teams (internal work notes)
5. Update the ticket status according to ITIL-aligned rules

--------------------------------------------------
TICKET STATUS MANAGEMENT (MANDATORY)
--------------------------------------------------
You must always ensure the ticket status reflects the real situation:

- Set ticket status to "In Progress" IF:
  - You are actively analyzing or working on the issue
  - You are applying a known resolution or workaround

- Set ticket status to "On Hold" IF:
  - You are waiting for information, confirmation, or action from the requester
  - You have asked a question to the user via a comment

- Do NOT resolve or close a ticket unless:
  - A clear solution has been identified
  - The resolution is validated by a KB article or explicit rule
  - The user impact is addressed

--------------------------------------------------
CUSTOMER COMMUNICATION RULES
--------------------------------------------------
When adding a customer-visible comment:
- Use clear, polite, professional language
- Explain what is happening in simple terms
- Explicitly state if user action is required
- Never expose internal reasoning or system details

Use create_servicenow_comment ONLY for customer-facing communication.

--------------------------------------------------
INTERNAL COLLABORATION RULES (WORK NOTES)
--------------------------------------------------
Work notes are for internal collaboration and traceability.

IMPORTANT – Work Notes Format (MANDATORY):

[AI Agent Analysis]

Issue Summary:
<Concise description of the problem>

Current Status:
<Why the ticket is In Progress or On Hold>

Analysis:
<Fact-based analysis derived ONLY from ticket data and KB articles>

Actions Taken:
- <Action already performed>

Next Actions:
- <Action to be performed>
- <If waiting for user, explicitly state what is awaited>

Related KB Articles:
- <KB_ID – Title> (if applicable)

--------------------------------------------------
EXECUTION RULES (STRICT)
--------------------------------------------------
- Always parse and understand the ticket JSON before acting
- Never fabricate root causes, solutions, or KB references
- If no relevant KB article exists, state it explicitly
- If information is missing, request it via a customer comment
- Maintain neutrality and factual accuracy at all times

--------------------------------------------------
TOOL USAGE CONSTRAINTS
--------------------------------------------------
- update_servicenow_ticket:
  - MUST be called exactly ONCE per analysis cycle
  - MUST include work notes AND the correct ticket status

- create_servicenow_comment:
  - Use only when communication with the user is required

- resolve_servicenow_ticket:
  - Use ONLY when resolution criteria are fully met

--------------------------------------------------
FINAL CHECK BEFORE ANY ACTION
--------------------------------------------------
Before executing tools, validate:
- Is the ticket status correct?
- Is the reasoning fully traceable?
- Is all information factual and derived from sources?

If not → do not proceed.
"""


@tool
def parse_ticket_data(ticket_json: str) -> str:
    """
    Parse ticket data received from ServiceNow webhook.
    Extracts key information for analysis.

    Args:
        ticket_json: JSON string containing ticket data from ServiceNow

    Returns:
        Formatted JSON with extracted ticket fields
    """
    try:
        ticket = json.loads(ticket_json)

        formatted = {
            "ticket_number": ticket.get("number", "Unknown"),
            "short_description": ticket.get("short_description", ""),
            "description": ticket.get("description", ""),
            "priority": ticket.get("priority", ""),
            "urgency": ticket.get("urgency", ""),
            "impact": ticket.get("impact", ""),
            "state": ticket.get("state", ""),
            "requester": ticket.get("caller_id", ""),
            "category": ticket.get("category", ""),
            "subcategory": ticket.get("subcategory", ""),
            "assignment_group": ticket.get("assignment_group", ""),
        }

        return json.dumps(formatted, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse: {str(e)}"})


@tool
def search_knowledge_base(query: str) -> str:
    """
    Search the knowledge base for solutions related to the query.
    Returns relevant KB articles with solutions.

    Args:
        query: Search query describing the issue or keywords

    Returns:
        JSON with matching knowledge base articles
    """
    # Simulated knowledge base - will be replaced with AWS Bedrock Knowledge Base in Article 4
    knowledge_articles = []

    query_lower = query.lower()

    if "vpn" in query_lower or "connection" in query_lower or "network" in query_lower:
        knowledge_articles.append({
            "article_id": "KB0001",
            "title": "VPN Connection Timeout Troubleshooting",
            "summary": "Common causes and solutions for VPN connection timeout errors",
            "solution": [
                "1. Check if user's home network allows VPN traffic (ports 443, 1194, 500, 4500)",
                "2. Verify VPN client version is up to date",
                "3. Try alternative VPN protocol (OpenVPN vs IKEv2)",
                "4. Check if firewall or antivirus is blocking VPN",
                "5. Test with mobile hotspot to rule out ISP issues"
            ],
            "category": "Network Access"
        })

    if "password" in query_lower or "reset" in query_lower or "login" in query_lower or "access" in query_lower:
        knowledge_articles.append({
            "article_id": "KB0002",
            "title": "Password Reset Procedure",
            "summary": "Standard procedure for user password resets",
            "solution": [
                "1. Verify user identity through secondary email or phone",
                "2. Use AD Users and Computers to reset password",
                "3. Select 'User must change password at next logon'",
                "4. Communicate temporary password securely (phone call preferred)",
                "5. Verify user can log in with new credentials"
            ],
            "category": "Identity Management"
        })

    if "email" in query_lower or "sync" in query_lower or "mobile" in query_lower or "iphone" in query_lower or "outlook" in query_lower:
        knowledge_articles.append({
            "article_id": "KB0003",
            "title": "Mobile Email Sync Issues",
            "summary": "Troubleshooting email synchronization problems on mobile devices",
            "solution": [
                "1. Remove and re-add email account on the device",
                "2. Ensure device has latest iOS/Android updates",
                "3. Check ActiveSync is enabled for user's mailbox",
                "4. Verify account settings: Server: mail.example.com, use SSL",
                "5. Check if device policy allows email sync",
                "6. Test with Outlook mobile app as alternative"
            ],
            "category": "Email & Collaboration"
        })

    if "printer" in query_lower or "print" in query_lower:
        knowledge_articles.append({
            "article_id": "KB0004",
            "title": "Printer Connection Issues",
            "summary": "Resolving common printer connectivity problems",
            "solution": [
                "1. Restart the print spooler service",
                "2. Remove and re-add the printer",
                "3. Check network connectivity to print server",
                "4. Update printer drivers",
                "5. Clear print queue and retry"
            ],
            "category": "Hardware & Peripherals"
        })

    if "software" in query_lower or "install" in query_lower or "application" in query_lower:
        knowledge_articles.append({
            "article_id": "KB0005",
            "title": "Software Installation Requests",
            "summary": "Process for software installation and approval",
            "solution": [
                "1. Verify software is on approved list",
                "2. Check user has appropriate license",
                "3. Submit request through Software Center if available",
                "4. For non-standard software, escalate to Change Management",
                "5. Document installation in asset management"
            ],
            "category": "Software & Applications"
        })

    if len(knowledge_articles) == 0:
        response = {
            "message": "No relevant knowledge base articles found",
            "suggestion": "This may require manual investigation or escalation to Level 2 support",
            "recommendation": "Add work notes documenting the investigation steps taken"
        }
    else:
        response = {
            "found_articles": len(knowledge_articles),
            "articles": knowledge_articles
        }

    try:
        return json.dumps(response, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


# ServiceNow tools - call Gateway via HTTP when configured, fallback to simulation otherwise

@tool
def update_servicenow_ticket(ticket_number: str, work_notes: str, state: str = "2") -> str:
    """
    Update ServiceNow ticket with work notes and optionally change state.
    This tool adds internal notes visible only to support staff.

    Args:
        ticket_number: ServiceNow incident number (e.g., INC0001234)
        work_notes: Work notes to add to the incident
        state: New state (1=New, 2=In Progress, 3=On Hold). Default is In Progress.

    Returns:
        JSON with operation result
    """
    if is_gateway_configured():
        # Call Gateway via HTTP
        result = call_gateway_tool(
            "servicenow-tools___update_servicenow_ticket",
            {
                "ticket_number": ticket_number,
                "work_notes": work_notes,
                "state": state
            }
        )
        return json.dumps(result, indent=2, default=str)

    # Fallback for local testing without Gateway
    return json.dumps({
        "success": True,
        "ticket_number": ticket_number,
        "message": "Ticket update simulated (Gateway not configured)",
        "state": state,
        "work_notes_preview": work_notes[:100] + "..." if len(work_notes) > 100 else work_notes,
        "note": "This is a simulated update. Configure Gateway for real ServiceNow integration."
    }, indent=2)


@tool
def create_servicenow_comment(ticket_number: str, comment: str) -> str:
    """
    Add a customer-visible comment to a ServiceNow incident.
    Comments are visible to the ticket requester.

    Args:
        ticket_number: ServiceNow incident number (e.g., INC0001234)
        comment: Comment text visible to the customer

    Returns:
        JSON with operation result
    """
    if is_gateway_configured():
        # Call Gateway via HTTP
        result = call_gateway_tool(
            "servicenow-tools___create_servicenow_comment",
            {
                "ticket_number": ticket_number,
                "comment": comment
            }
        )
        return json.dumps(result, indent=2, default=str)

    # Fallback for local testing
    return json.dumps({
        "success": True,
        "ticket_number": ticket_number,
        "message": "Comment simulated (Gateway not configured)",
        "comment_preview": comment[:100] + "..." if len(comment) > 100 else comment,
        "note": "This is a simulated comment. Configure Gateway for real ServiceNow integration."
    }, indent=2)


@tool
def resolve_servicenow_ticket(ticket_number: str, resolution_notes: str, resolution_code: str = "Solved (Permanently)") -> str:
    """
    Mark a ServiceNow incident as resolved with resolution notes.
    Use this when the issue has been fixed.

    Args:
        ticket_number: ServiceNow incident number (e.g., INC0001234)
        resolution_notes: Notes explaining how the issue was resolved
        resolution_code: Resolution code (default: "Solved (Permanently)")

    Returns:
        JSON with operation result
    """
    if is_gateway_configured():
        # Call Gateway via HTTP
        result = call_gateway_tool(
            "servicenow-tools___resolve_servicenow_ticket",
            {
                "ticket_number": ticket_number,
                "resolution_notes": resolution_notes,
                "resolution_code": resolution_code
            }
        )
        return json.dumps(result, indent=2, default=str)

    # Fallback for local testing
    return json.dumps({
        "success": True,
        "ticket_number": ticket_number,
        "message": "Ticket resolution simulated (Gateway not configured)",
        "state": "Resolved",
        "resolution_code": resolution_code,
        "resolution_notes_preview": resolution_notes[:100] + "..." if len(resolution_notes) > 100 else resolution_notes,
        "note": "This is a simulated resolution. Configure Gateway for real ServiceNow integration."
    }, indent=2)


def create_bedrock_model() -> BedrockModel:
    """
    Create a BedrockModel with retry configuration.

    Configures the model with:
    - Extended timeouts for streaming responses
    - Standard retry mode with increased attempts
    - Connection pooling settings

    Returns:
        Configured BedrockModel instance
    """
    # Configure botocore with retry settings and extended timeouts
    boto_config = BotocoreConfig(
        connect_timeout=30,      # Connection timeout in seconds
        read_timeout=120,        # Read timeout - extended for streaming
        retries={
            'max_attempts': 5,   # Retry up to 5 times
            'mode': 'standard'   # Use standard retry mode
        }
    )

    return BedrockModel(
        model_id="eu.anthropic.claude-sonnet-4-20250514-v1:0",
        boto_client_config=boto_config,
    )


def create_agent() -> Agent:
    """
    Create an agent with all tools.

    The ServiceNow tools automatically use Gateway via HTTP when configured
    (environment variables set), otherwise they fall back to simulation mode.

    Returns:
        Configured Strands Agent
    """
    logger.info("=== Creating Agent ===")

    # Log Gateway configuration status
    config = get_gateway_config()
    if is_gateway_configured():
        logger.info(f"Gateway configured: {config['gateway_url']}")
        logger.info("ServiceNow tools will call Gateway via HTTP")
    else:
        logger.warning("Gateway NOT configured - ServiceNow tools will use simulation mode")
        logger.warning(f"Config status: gateway_url={bool(config['gateway_url'])}, client_id={bool(config['client_id'])}, client_secret={bool(config['client_secret'])}, token_endpoint={bool(config['token_endpoint'])}")

    # All tools - ServiceNow tools handle Gateway/fallback internally
    all_tools = [
        calculator,
        current_time,
        parse_ticket_data,
        search_knowledge_base,
        update_servicenow_ticket,
        create_servicenow_comment,
        resolve_servicenow_ticket,
    ]

    logger.info(f"Tools: {[getattr(t, '__name__', str(t)) for t in all_tools]}")
    logger.info("=== End Creating Agent ===")

    # Use BedrockModel with retry configuration instead of just model ID string
    bedrock_model = create_bedrock_model()

    return Agent(
        model=bedrock_model,
        system_prompt=SYSTEM_PROMPT,
        tools=all_tools
    )


# Create an AgentCore app
app = BedrockAgentCoreApp()

# Create the agent
agent = create_agent()


def invoke_with_retry(agent_instance: Agent, message: str, max_retries: int = 3, base_delay: float = 1.0):
    """
    Invoke the agent with retry logic for streaming errors.

    Handles transient errors like ProtocolError that occur during streaming
    and are not caught by botocore's retry mechanism.

    Args:
        agent_instance: The Strands Agent to invoke
        message: User message to process
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)

    Returns:
        Agent response

    Raises:
        Exception: If all retry attempts fail
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                # Exponential backoff with jitter
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"Retry attempt {attempt}/{max_retries} after {delay:.1f}s delay...")
                time.sleep(delay)

            response = agent_instance(message)
            return response

        except ProtocolError as e:
            last_exception = e
            logger.warning(f"ProtocolError on attempt {attempt + 1}/{max_retries + 1}: {e}")
            if attempt == max_retries:
                logger.error(f"All {max_retries + 1} attempts failed due to ProtocolError")
                raise

        except Exception as e:
            # Check if it's a wrapped ProtocolError
            if "Response ended prematurely" in str(e) or isinstance(e.__cause__, ProtocolError):
                last_exception = e
                logger.warning(f"Streaming error on attempt {attempt + 1}/{max_retries + 1}: {e}")
                if attempt == max_retries:
                    logger.error(f"All {max_retries + 1} attempts failed")
                    raise
            else:
                # Non-retryable error
                raise

    raise last_exception


@app.entrypoint
def invoke(payload):
    """
    Handler for agent invocation.

    Args:
        payload: JSON payload with 'prompt' field containing the user message

    Returns:
        Agent response text
    """
    import traceback

    logger.info("=== Agent Invocation ===")
    logger.info(f"Payload received: {json.dumps(payload, default=str)[:500]}...")

    user_message = payload.get(
        "prompt",
        "No prompt found in input. Please provide a 'prompt' key in the JSON payload."
    )

    logger.info(f"Processing prompt (length={len(user_message)}): {user_message[:200]}...")

    # Log available tools on the agent
    if hasattr(agent, 'tool_registry') and agent.tool_registry:
        tool_names = list(agent.tool_registry.registry.keys()) if hasattr(agent.tool_registry, 'registry') else []
        logger.info(f"Agent tools available: {tool_names}")
    else:
        logger.info("Could not retrieve agent tool list")

    try:
        # Use retry wrapper to handle transient streaming errors
        response = invoke_with_retry(agent, user_message, max_retries=3, base_delay=2.0)

        response_text = response.message['content'][0]['text']
        logger.info(f"Agent response (length={len(response_text)}): {response_text[:300]}...")
        logger.info("=== End Agent Invocation (SUCCESS) ===")

        return response_text
    except Exception as e:
        logger.error(f"Agent invocation failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        logger.info("=== End Agent Invocation (ERROR) ===")
        raise


if __name__ == "__main__":
    app.run()
