import json
import logging

from strands import Agent, tool
from strands_tools import calculator, current_time

# Import the AgentCore SDK
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Import ServiceNow client
import sys
import os
# Add parent directory to path to import servicenow module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from servicenow.client import update_ticket_with_resolution, ServiceNowError

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = """
Welcome to the ServiceNow Backoffice Support Assistant!
I can help you analyze tickets, search the knowledge base, and prepare ticket updates.
"""

SYSTEM_PROMPT = """
You are a helpful backoffice support assistant for ServiceNow ticket management.
Your role is to:
1. Analyze incoming support tickets received via webhook
2. Search the knowledge base for relevant solutions
3. Update ServiceNow tickets directly with proposed resolutions
4. Provide clear, professional responses

When analyzing a ticket:
- Extract key information from the ticket data provided
- Search the knowledge base for similar issues
- Propose a resolution based on available information
- Update the ticket in ServiceNow with your findings

You receive complete ticket data via webhook and should analyze it immediately.
Always be concise and professional in your responses.
"""

@tool
def parse_ticket_data(ticket_json: str) -> str:
    """
    Parse and format ticket data received from ServiceNow webhook.

    This tool extracts key information from the ticket data for analysis.
    """
    try:
        ticket = json.loads(ticket_json)

        formatted = {
            "ticket_number": ticket.get("number", "Unknown"),
            "short_description": ticket.get("short_description", ""),
            "description": ticket.get("description", ""),
            "priority": ticket.get("priority", ""),
            "state": ticket.get("state", ""),
            "assigned_to": ticket.get("assigned_to", ""),
            "requester": ticket.get("caller_id", ""),
            "created_date": ticket.get("sys_created_on", ""),
            "category": ticket.get("category", ""),
            "subcategory": ticket.get("subcategory", "")
        }

        return json.dumps(formatted, indent=2)
    except Exception as e:
        logger.error(f"Error parsing ticket data: {e}")
        return json.dumps({"error": f"Failed to parse ticket data: {str(e)}"})


@tool
def search_knowledge_base(query: str) -> str:
    """Search the knowledge base for solutions related to the query"""
    # Simulated knowledge base - will be replaced with AWS Bedrock Knowledge Base in Article 3
    knowledge_articles = []

    query_lower = query.lower()

    if "vpn" in query_lower:
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

    if "password" in query_lower or "reset" in query_lower:
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

    if "email" in query_lower or "sync" in query_lower or "mobile" in query_lower or "iphone" in query_lower:
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

    if len(knowledge_articles) == 0:
        response = {
            "message": "No relevant knowledge base articles found",
            "suggestion": "This may require manual investigation or escalation"
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


@tool
def update_servicenow_ticket(ticket_number: str, resolution_notes: str) -> str:
    """
    Update a ServiceNow ticket with resolution notes and set it to In Progress.

    This tool makes a real API call to ServiceNow to update the ticket.
    """
    try:
        logger.info(f"Updating ServiceNow ticket {ticket_number}")

        # Call ServiceNow API to update the ticket
        result = update_ticket_with_resolution(
            ticket_number=ticket_number,
            resolution_notes=resolution_notes,
            set_in_progress=True
        )

        response = {
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket updated successfully in ServiceNow",
            "state": "In Progress",
            "work_notes_added": resolution_notes[:100] + "..." if len(resolution_notes) > 100 else resolution_notes
        }

        logger.info(f"Successfully updated ticket {ticket_number}")
        return json.dumps(response, indent=2)

    except ServiceNowError as e:
        logger.error(f"ServiceNow API error updating ticket {ticket_number}: {e}")
        error_response = {
            "success": False,
            "ticket_number": ticket_number,
            "error": f"Failed to update ServiceNow ticket: {str(e)}"
        }
        return json.dumps(error_response, indent=2)

    except Exception as e:
        logger.error(f"Unexpected error updating ticket {ticket_number}: {e}")
        error_response = {
            "success": False,
            "ticket_number": ticket_number,
            "error": f"Unexpected error: {str(e)}"
        }
        return json.dumps(error_response, indent=2)


# Create an AgentCore app
app = BedrockAgentCoreApp()

agent = Agent(
    model="eu.amazon.nova-lite-v1:0",
    system_prompt=SYSTEM_PROMPT,
    tools=[
        calculator,
        current_time,
        parse_ticket_data,
        search_knowledge_base,
        update_servicenow_ticket
    ]
)

# Specify the entry point function invoking the agent
@app.entrypoint
def invoke(payload):
    """Handler for agent invocation"""
    user_message = payload.get(
        "prompt",
        "No prompt found in input. Please provide a 'prompt' key in the JSON payload."
    )
    response = agent(user_message)
    return response.message['content'][0]['text']


if __name__ == "__main__":
    app.run()
