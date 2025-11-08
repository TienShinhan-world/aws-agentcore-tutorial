import json
from strands import Agent, tool
from strands_tools import calculator, current_time
from bedrock_agentcore.runtime import BedrockAgentCoreApp

WELCOME_MESSAGE = """
Welcome to the ServiceNow Backoffice Support Assistant!
I can help you analyze tickets, search the knowledge base, and prepare ticket updates.
"""

SYSTEM_PROMPT = """
You are a helpful backoffice support assistant for ServiceNow ticket management.
Your role is to:
1. Parse and analyze ticket data received from webhooks
2. Search the knowledge base for relevant solutions
3. Update ServiceNow tickets with proposed resolutions
4. Provide clear, professional responses to support staff

When analyzing a ticket:
- Parse the ticket data JSON to extract key information
- Search the knowledge base for similar issues
- Propose a resolution based on available information
- Update the ServiceNow ticket with work notes and resolution

You receive complete ticket data via webhook.
Always be concise and professional in your responses.
"""

@tool
def parse_ticket_data(ticket_json: str) -> str:
    """
    Parse ticket data received from ServiceNow webhook.
    Extracts key information for analysis.
    """
    try:
        ticket = json.loads(ticket_json)

        formatted = {
            "ticket_number": ticket.get("number", "Unknown"),
            "short_description": ticket.get("short_description", ""),
            "description": ticket.get("description", ""),
            "priority": ticket.get("priority", ""),
            "state": ticket.get("state", ""),
            "requester": ticket.get("caller_id", ""),
            "category": ticket.get("category", "")
        }

        return json.dumps(formatted, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Failed to parse: {str(e)}"})


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
    Update ServiceNow ticket with resolution notes.
    Makes real API call to ServiceNow (in Article 2).
    """
    try:
        # Simulated update - will be replaced with real ServiceNow API call in Article 2
        result = {
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket update prepared",
            "state": "In Progress",
            "work_notes": resolution_notes,
            "note": "This is a simulated update. In Article 2, this will make a real API call to ServiceNow."
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Failed to update: {str(e)}"
        }, indent=2)


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
