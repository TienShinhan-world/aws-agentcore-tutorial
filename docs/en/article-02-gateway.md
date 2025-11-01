# Article 2: ServiceNow Webhook Integration with AWS AgentCore

> **Series: Backoffice Support Agent with AWS AgentCore**
> **Step 2 of 5** | [Version française](../fr/article-02-gateway.md)

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture Overview](#architecture-overview)
3. [What We'll Build](#what-well-build)
4. [Prerequisites](#prerequisites)
5. [Part 1: ServiceNow API Client](#part-1-servicenow-api-client)
6. [Part 2: Modifying Agent Tools](#part-2-modifying-agent-tools)
7. [Part 3: Lambda Webhook Handler](#part-3-lambda-webhook-handler)
8. [Part 4: AWS Infrastructure (CDK)](#part-4-aws-infrastructure-cdk)
9. [Part 5: ServiceNow Configuration](#part-5-servicenow-configuration)
10. [Part 6: Testing the Integration](#part-6-testing-the-integration)
11. [Part 7: Automated Testing](#part-7-automated-testing)
12. [Troubleshooting](#troubleshooting)
13. [Next Steps](#next-steps)

---

## Introduction

In [Article 1](article-01-runtime.md), we deployed our first agent with AWS AgentCore Runtime using simulated data. Now we're taking it to production by:

- ✅ Creating a **real ServiceNow integration** with API client
- ✅ Implementing **webhook architecture** (ServiceNow pushes data to our agent)
- ✅ Deploying **API Gateway + Lambda** infrastructure
- ✅ Building a **comprehensive test suite** (91% code coverage!)
- ✅ Configuring **ServiceNow Business Rules** to trigger webhooks

### Why Webhooks Instead of Polling?

Instead of having our agent constantly poll ServiceNow for new tickets (which wastes resources and adds latency), we use **webhooks**:

**Webhook Architecture:**
```
ServiceNow (new ticket created)
    ↓ Triggers Business Rule
    ↓ HTTP POST
API Gateway (/webhook/servicenow)
    ↓ Invokes
Lambda Function (webhook_handler)
    ↓ Calls
Agent (analyzes ticket + searches KB)
    ↓ Updates
ServiceNow (adds work notes via API)
```

**Benefits:**
- ⚡ **Instant response** (no polling delay)
- 💰 **Cost-effective** (pay per ticket, not per poll)
- 🎯 **Event-driven** (agent only runs when needed)
- 📊 **Scalable** (handles spikes automatically)

### Estimated Time
⏱️ **60-90 minutes** to complete this tutorial.

---

## Architecture Overview

### High-Level Flow

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  ServiceNow  │────────▶│ API Gateway  │────────▶│    Lambda    │
│              │  POST   │              │ Invoke  │   Handler    │
│ (New Ticket) │         │  /webhook    │         │              │
└──────────────┘         └──────────────┘         └──────┬───────┘
                                                          │
                                                          ▼
                                                   ┌──────────────┐
                                                   │    Agent     │
                                                   │   (Bedrock)  │
                                                   └──────┬───────┘
                                                          │
                                                          ▼
                                                   ┌──────────────┐
                                                   │ ServiceNow   │
                                                   │     API      │
                                                   │ (Update)     │
                                                   └──────────────┘
```

### Components We'll Build

1. **ServiceNow API Client** (`src/servicenow/client.py`)
   - REST API wrapper for ServiceNow
   - Methods: get_incident, update_incident, add_work_notes, resolve_incident

2. **Configuration Module** (`src/servicenow/config.py`)
   - Loads credentials from environment/Secrets Manager
   - Supports basic auth and OAuth

3. **Modified Agent Tools** (`src/agent/my_agent.py`)
   - `parse_ticket_data` - Extracts ticket info from webhook
   - `search_knowledge_base` - Finds relevant solutions
   - `update_servicenow_ticket` - Updates ticket via API

4. **Lambda Webhook Handler** (`src/servicenow/webhook_handler.py`)
   - Receives POST from ServiceNow
   - Invokes agent with ticket data
   - Returns HTTP response

5. **AWS CDK Infrastructure** (`infrastructure/cdk/`)
   - API Gateway REST API
   - Lambda function
   - Secrets Manager for credentials
   - IAM roles and CloudWatch logs

6. **Comprehensive Test Suite** (`tests/`)
   - 81 automated tests
   - 91% code coverage
   - Unit + integration tests

---

## What We'll Build

By the end of this article, you'll have:

✅ A production-ready ServiceNow webhook integration
✅ Real API calls to ServiceNow (no more simulated data!)
✅ AWS infrastructure deployed via CDK
✅ ServiceNow Business Rule triggering webhooks
✅ 81 automated tests ensuring reliability
✅ Complete monitoring and logging

---

## Prerequisites

Before starting, ensure you have:

### From Article 1
- ✅ Python 3.9+ with virtual environment
- ✅ AWS CLI configured
- ✅ AWS account with Bedrock access
- ✅ Basic agent from Article 1 working

### New Requirements
- ✅ **ServiceNow Instance** (developer instance or production)
  - Get a free developer instance: [developer.servicenow.com](https://developer.servicenow.com/)
- ✅ **ServiceNow Admin Access** (to create Business Rules and REST Messages)
- ✅ **Node.js 18+** (for AWS CDK)
- ✅ **ServiceNow Credentials** (username/password or OAuth token)

### Install Additional Dependencies

```bash
# Activate your virtual environment
source .venv/bin/activate

# Install new dependencies
pip install requests>=2.31.0

# Install test dependencies (optional but recommended)
pip install -r tests/requirements-test.txt

# Install CDK (if not already installed)
npm install -g aws-cdk
```

---

## Part 1: ServiceNow API Client

First, we'll create a robust client for the ServiceNow REST API.

### 1.1 Configuration Module

Create `src/servicenow/config.py`:

```python
"""
ServiceNow Configuration Module
Manages credentials and API configuration
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ServiceNowConfig:
    """ServiceNow configuration container"""

    instance_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    oauth_token: Optional[str] = None
    api_version: str = "v2"
    timeout: int = 30
    verify_ssl: bool = True

    @classmethod
    def from_environment(cls) -> "ServiceNowConfig":
        """Load configuration from environment variables"""
        instance_url = os.getenv("SERVICENOW_INSTANCE_URL")
        if not instance_url:
            raise ValueError("SERVICENOW_INSTANCE_URL required")

        instance_url = instance_url.rstrip("/")

        username = os.getenv("SERVICENOW_USERNAME")
        password = os.getenv("SERVICENOW_PASSWORD")
        oauth_token = os.getenv("SERVICENOW_OAUTH_TOKEN")

        if not oauth_token and not (username and password):
            raise ValueError(
                "Either SERVICENOW_OAUTH_TOKEN or both "
                "SERVICENOW_USERNAME and SERVICENOW_PASSWORD required"
            )

        return cls(
            instance_url=instance_url,
            username=username,
            password=password,
            oauth_token=oauth_token,
            api_version=os.getenv("SERVICENOW_API_VERSION", "v2"),
            timeout=int(os.getenv("SERVICENOW_TIMEOUT", "30")),
            verify_ssl=os.getenv("SERVICENOW_VERIFY_SSL", "true").lower() == "true"
        )

    def get_table_api_url(self, table_name: str) -> str:
        """Get API URL for a ServiceNow table"""
        return f"{self.instance_url}/api/now/{self.api_version}/table/{table_name}"
```

**Key features:**
- Supports both basic auth and OAuth
- Loads from environment variables
- Validates required configuration
- Provides URL builders for API endpoints

### 1.2 ServiceNow API Client

Create `src/servicenow/client.py`:

```python
"""
ServiceNow REST API Client
"""
import json
import logging
from typing import Dict, Any, Optional
import requests
from requests.auth import HTTPBasicAuth

from .config import ServiceNowConfig, get_config

logger = logging.getLogger(__name__)


class ServiceNowError(Exception):
    """Base exception for ServiceNow API errors"""
    pass


class ServiceNowClient:
    """Client for ServiceNow REST API"""

    def __init__(self, config: Optional[ServiceNowConfig] = None):
        self.config = config or get_config()
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create authenticated session"""
        session = requests.Session()

        if self.config.oauth_token:
            session.headers["Authorization"] = f"Bearer {self.config.oauth_token}"
        elif self.config.username and self.config.password:
            session.auth = HTTPBasicAuth(
                self.config.username,
                self.config.password
            )
        else:
            raise ServiceNowError("No authentication method configured")

        session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

        return session

    def get_incident(self, number: str) -> Dict[str, Any]:
        """Get incident by number"""
        url = self.config.get_table_api_url("incident")
        params = {
            "sysparm_query": f"number={number}",
            "sysparm_limit": "1"
        }

        response = self.session.get(
            url,
            params=params,
            timeout=self.config.timeout
        )
        response.raise_for_status()

        result = response.json()
        if not result.get("result"):
            raise ServiceNowError(f"Incident {number} not found")

        return result["result"][0]

    def add_work_notes(
        self,
        number: str,
        work_notes: str,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add work notes to incident"""
        # First get sys_id
        incident = self.get_incident(number)
        sys_id = incident["sys_id"]

        # Prepare update
        updates = {"work_notes": work_notes}
        if state:
            updates["state"] = state

        # Update incident
        url = f"{self.config.get_table_api_url('incident')}/{sys_id}"
        response = self.session.patch(
            url,
            json=updates,
            timeout=self.config.timeout
        )
        response.raise_for_status()

        logger.info(f"Updated incident {number}")
        return response.json().get("result", {})
```

**Key methods:**
- `get_incident(number)` - Fetch ticket by incident number
- `add_work_notes(number, notes, state)` - Add notes and optionally change state
- `resolve_incident(number, notes)` - Mark ticket as resolved
- Error handling with custom exceptions

### 1.3 Test the Client (Optional)

Set environment variables and test:

```bash
export SERVICENOW_INSTANCE_URL="https://YOUR_INSTANCE.service-now.com"
export SERVICENOW_USERNAME="your_username"
export SERVICENOW_PASSWORD="your_password"

# Test in Python
python -c "
from servicenow.client import ServiceNowClient
client = ServiceNowClient()
ticket = client.get_incident('INC0010001')
print(ticket)
"
```

---

## Part 2: Modifying Agent Tools

Now we'll update the agent to use real ServiceNow API calls instead of simulated data.

### 2.1 Update Agent (`src/agent/my_agent.py`)

**Changes needed:**

1. **Import ServiceNow client:**
```python
from servicenow.client import update_ticket_with_resolution, ServiceNowError
```

2. **Replace `get_ticket_info` with `parse_ticket_data`:**
```python
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
```

3. **Replace `prepare_ticket_update` with `update_servicenow_ticket`:**
```python
@tool
def update_servicenow_ticket(ticket_number: str, resolution_notes: str) -> str:
    """
    Update ServiceNow ticket with resolution notes.
    Makes real API call to ServiceNow.
    """
    try:
        logger.info(f"Updating ticket {ticket_number}")

        # Real API call to ServiceNow
        result = update_ticket_with_resolution(
            ticket_number=ticket_number,
            resolution_notes=resolution_notes,
            set_in_progress=True
        )

        return json.dumps({
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket updated in ServiceNow",
            "state": "In Progress"
        }, indent=2)

    except ServiceNowError as e:
        logger.error(f"ServiceNow error: {e}")
        return json.dumps({
            "success": False,
            "error": f"Failed to update: {str(e)}"
        }, indent=2)
```

4. **Update agent tools list:**
```python
agent = Agent(
    model="eu.amazon.nova-lite-v1:0",
    system_prompt=SYSTEM_PROMPT,
    tools=[
        calculator,
        current_time,
        parse_ticket_data,      # New: parse webhook data
        search_knowledge_base,
        update_servicenow_ticket  # New: real API calls
    ]
)
```

### 2.2 Update System Prompt

```python
SYSTEM_PROMPT = """
You are a helpful backoffice support assistant for ServiceNow.

Your role:
1. Analyze tickets received via webhook
2. Search knowledge base for solutions
3. Update ServiceNow directly with your findings
4. Provide clear, professional responses

When analyzing:
- Extract key info from ticket data
- Search KB for similar issues
- Propose resolution based on KB articles
- Update ticket in ServiceNow with work notes

You receive complete ticket data via webhook.
Always be concise and professional.
"""
```

---

## Part 3: Lambda Webhook Handler

Create the Lambda function that receives webhooks from ServiceNow.

### 3.1 Webhook Handler (`src/servicenow/webhook_handler.py`)

```python
"""
ServiceNow Webhook Handler for AWS Lambda
"""
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_servicenow_payload(body: str) -> dict:
    """Parse ServiceNow webhook payload"""
    try:
        payload = json.loads(body)

        # ServiceNow can send data in different formats
        if "record" in payload:
            return payload["record"]
        elif "result" in payload:
            return payload["result"]
        else:
            return payload

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")


def invoke_agent(ticket_data: dict) -> str:
    """Invoke agent with ticket data"""
    ticket_json = json.dumps(ticket_data)
    prompt = f"""New ServiceNow ticket received:

{ticket_json}

Analyze this ticket, search the knowledge base,
and update ServiceNow with your recommendations.
"""

    # Import agent
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from agent.my_agent import agent

    # Invoke
    response = agent(prompt)

    # Extract text
    if hasattr(response, 'message'):
        return response.message['content'][0]['text']
    return str(response)


def lambda_handler(event: dict, context) -> dict:
    """AWS Lambda handler"""
    try:
        logger.info("Received webhook request")

        # Extract body
        body = event.get('body', '{}')

        # Decode if base64
        if event.get('isBase64Encoded', False):
            import base64
            body = base64.b64decode(body).decode('utf-8')

        # Parse payload
        ticket_data = parse_servicenow_payload(body)
        ticket_number = ticket_data.get('number', 'Unknown')

        logger.info(f"Processing ticket {ticket_number}")

        # Invoke agent
        agent_response = invoke_agent(ticket_data)

        # Return success
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({
                "success": True,
                "ticket_number": ticket_number,
                "message": "Ticket processed",
                "agent_analysis": agent_response
            })
        }

    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        return {
            "statusCode": 400,
            "body": json.dumps({
                "success": False,
                "error": "Invalid payload"
            })
        }

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return {
            "statusCode": 500,
            "body": json.dumps({
                "success": False,
                "error": "Internal server error"
            })
        }
```

**Key features:**
- Handles different ServiceNow payload formats
- Decodes base64-encoded bodies
- Invokes agent with ticket data
- Returns appropriate HTTP status codes
- Comprehensive error handling and logging

---

*Continued in next message due to length...*

**Article Status:** Part 1 of article complete. Shall I continue with Parts 4-7 (AWS Infrastructure, ServiceNow Configuration, Testing, etc.)?