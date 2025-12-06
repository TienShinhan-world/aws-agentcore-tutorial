# Article 3: Bidirectional ServiceNow Integration

> **Series: Backoffice Support Agent with AWS AgentCore**
> **Step 3** | [Version française](../fr/article-03-servicenow.md)

## Table of Contents

1. [Introduction](#introduction)
2. [Bidirectional Architecture](#bidirectional-architecture)
3. [Prerequisites](#prerequisites)
4. [Part 1: ServiceNow to Agent (Webhook)](#part-1-servicenow-to-agent-webhook)
5. [Part 2: Agent to ServiceNow (API)](#part-2-agent-to-servicenow-api)
6. [Part 3: Credentials Configuration](#part-3-credentials-configuration)
7. [Part 4: Agent Modification](#part-4-agent-modification)
8. [End-to-End Testing](#end-to-end-testing)
9. [Security and Best Practices](#security-and-best-practices)
10. [Troubleshooting](#troubleshooting)
11. [Next Steps](#next-steps)

---

## Introduction

In [Article 2](article-02-gateway.md), we exposed our agent via a REST API. Now, we'll establish a **real bidirectional connection** with ServiceNow:

- ✅ **ServiceNow → Agent**: ServiceNow automatically triggers our agent via webhook
- ✅ **Agent → ServiceNow**: The agent updates tickets directly in ServiceNow
- ✅ **Secure credentials**: Using AWS Secrets Manager
- ✅ **Complete flow**: Ticket creation → Automatic analysis → Update

### What You Will Build

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BIDIRECTIONAL FLOW                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────┐         ┌──────────────┐         ┌──────────────┐        │
│   │  ServiceNow  │────────▶│    Agent     │────────▶│  ServiceNow  │        │
│   │              │  HTTP   │   AgentCore  │   API   │              │        │
│   │ (New         │  POST   │              │  REST   │ (Ticket      │        │
│   │  ticket)     │         │  (Analysis)  │         │  update)     │        │
│   └──────────────┘         └──────────────┘         └──────────────┘        │
│         │                         │                        ▲                │
│         │    Business Rule        │    Work Notes          │                │
│         └─────────────────────────┼────────────────────────┘                │
│                                   │                                         │
│                            AWS Secrets                                      │
│                             Manager                                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Estimated Time
⏱️ **45-60 minutes** to complete this tutorial.

---

## Bidirectional Architecture

### Components

| Direction | Source | Destination | Mechanism |
|-----------|--------|-------------|-----------|
| **Inbound** | ServiceNow | Agent | Business Rule → REST Message → API Gateway → Lambda → AgentCore |
| **Outbound** | Agent | ServiceNow | Tool `update_servicenow_ticket` → ServiceNow REST API |

### Detailed Flow

1. **Trigger**: A new ticket is created in ServiceNow
2. **Business Rule**: Automatically triggers on creation
3. **REST Message**: Sends ticket data to our API Gateway
4. **Lambda**: Receives webhook, invokes AgentCore agent
5. **Agent**: Analyzes ticket, searches KB
6. **ServiceNow Tool**: Updates ticket with work notes
7. **ServiceNow**: Displays agent analysis in the ticket

---

## Prerequisites

### From Previous Articles

- ✅ Agent deployed (Article 1)
- ✅ Webhook infrastructure deployed (Article 2)
- ✅ Working API Gateway with API Key

### New Prerequisites

1. **ServiceNow Instance**
   - Developer instance (PDI): [developer.servicenow.com](https://developer.servicenow.com/)
   - Or production instance with admin access

2. **ServiceNow User with API Permissions**
   - Role `rest_api_explorer` or equivalent
   - Access to `incident` table

3. **ServiceNow Credentials**
   - Instance URL (e.g., `https://devXXXXX.service-now.com`)
   - Username and password (or OAuth token)

---

## Part 1: ServiceNow to Agent (Webhook)

### 1.1 Create a REST Message in ServiceNow

1. **Navigate to**: System Web Services → Outbound → REST Message
2. **Click**: New
3. **Fill in**:
   - **Name**: `AWS AgentCore Webhook`
   - **Endpoint**: `https://YOUR_API_GATEWAY_URL/prod/webhook/servicenow`
   - **Authentication**: `No authentication` (we use API Key in header)

4. **Save**

### 1.2 Add an HTTP Method

1. In the created REST Message, go to **HTTP Methods** tab
2. **Click**: New
3. **Fill in**:
   - **Name**: `POST Incident`
   - **HTTP method**: `POST`
   - **Endpoint**: Leave empty (inherits from parent)

4. **HTTP Headers**: Add the following headers:

| Name | Value |
|------|-------|
| `Content-Type` | `application/json` |
| `x-api-key` | `YOUR_API_KEY` |

5. **HTTP Query Parameters**: None

6. **Content** (Request Body):
```json
{
    "number": "${number}",
    "short_description": "${short_description}",
    "description": "${description}",
    "urgency": "${urgency}",
    "impact": "${impact}",
    "priority": "${priority}",
    "category": "${category}",
    "subcategory": "${subcategory}",
    "assignment_group": "${assignment_group}",
    "caller_id": "${caller_id}",
    "sys_id": "${sys_id}",
    "sys_created_on": "${sys_created_on}"
}
```

7. **Variable Substitutions**: The `${...}` variables will be substituted automatically

8. **Save**

### 1.3 Create a Business Rule

1. **Navigate to**: System Definition → Business Rules
2. **Click**: New
3. **Fill in**:
   - **Name**: `Trigger AWS Agent on Incident Create`
   - **Table**: `Incident [incident]`
   - **Active**: Checked
   - **Advanced**: Checked

4. **When to run**:
   - **When**: `after`
   - **Insert**: Checked
   - **Update**: Unchecked (optional: check if you also want updates)

5. **Filter Conditions** (optional):
   - For example: `Priority is 1 - Critical` to only process critical tickets

6. **Script**:
```javascript
(function executeRule(current, previous /*null when async*/) {
    try {
        // Create REST Message
        var r = new sn_ws.RESTMessageV2('AWS AgentCore Webhook', 'POST Incident');

        // Substitute variables
        r.setStringParameterNoEscape('number', current.getValue('number'));
        r.setStringParameterNoEscape('short_description', current.getValue('short_description'));
        r.setStringParameterNoEscape('description', current.getValue('description'));
        r.setStringParameterNoEscape('urgency', current.getValue('urgency'));
        r.setStringParameterNoEscape('impact', current.getValue('impact'));
        r.setStringParameterNoEscape('priority', current.getValue('priority'));
        r.setStringParameterNoEscape('category', current.getValue('category'));
        r.setStringParameterNoEscape('subcategory', current.getValue('subcategory'));
        r.setStringParameterNoEscape('assignment_group', current.getValue('assignment_group'));
        r.setStringParameterNoEscape('caller_id', current.getValue('caller_id'));
        r.setStringParameterNoEscape('sys_id', current.getValue('sys_id'));
        r.setStringParameterNoEscape('sys_created_on', current.getValue('sys_created_on'));

        // Execute request
        var response = r.execute();
        var responseBody = response.getBody();
        var httpStatus = response.getStatusCode();

        // Log response
        gs.info('AWS Agent Response [' + httpStatus + ']: ' + responseBody);

    } catch (ex) {
        gs.error('Error calling AWS Agent: ' + ex.getMessage());
    }

})(current, previous);
```

7. **Save**

### 1.4 Test the Webhook

1. **Create a test incident** in ServiceNow
2. **Check logs**: System Logs → System Log → All
3. **Search for**: `AWS Agent Response`

---

## Part 2: Agent to ServiceNow (API)

### 2.1 ServiceNow Client

The ServiceNow client (`src/servicenow/client.py`) allows the agent to update tickets.

**Main methods:**

```python
class ServiceNowClient:
    def get_incident(self, number: str) -> Dict[str, Any]:
        """Get incident by number"""

    def update_incident(self, sys_id: str, updates: Dict) -> Dict[str, Any]:
        """Update an incident"""

    def add_work_notes(self, number: str, notes: str, state: str = None) -> Dict:
        """Add work notes and optionally change state"""

    def resolve_incident(self, number: str, notes: str) -> Dict:
        """Mark incident as resolved"""
```

### 2.2 Configuration

The `src/servicenow/config.py` file manages configuration:

```python
@dataclass
class ServiceNowConfig:
    instance_url: str          # https://devXXXXX.service-now.com
    username: Optional[str]    # Basic auth
    password: Optional[str]    # Basic auth
    oauth_token: Optional[str] # OAuth alternative
```

---

## Part 3: Credentials Configuration

### 3.1 Create a Secret in AWS Secrets Manager

```bash
aws secretsmanager create-secret \
    --name servicenow/credentials \
    --description "ServiceNow API credentials for AgentCore" \
    --secret-string '{
        "instance_url": "https://YOUR_INSTANCE.service-now.com",
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD"
    }'
```

### 3.2 Update the Secret (if already exists)

```bash
aws secretsmanager update-secret \
    --secret-id servicenow/credentials \
    --secret-string '{
        "instance_url": "https://YOUR_INSTANCE.service-now.com",
        "username": "YOUR_USERNAME",
        "password": "YOUR_PASSWORD"
    }'
```

### 3.3 Verify the Secret

```bash
aws secretsmanager get-secret-value \
    --secret-id servicenow/credentials \
    --query 'SecretString' \
    --output text | jq .
```

### 3.4 Configure IAM Permissions

The agent must have permission to read the secret. Add this policy to the execution role:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "secretsmanager:GetSecretValue"
            ],
            "Resource": "arn:aws:secretsmanager:eu-central-1:ACCOUNT_ID:secret:servicenow/*"
        }
    ]
}
```

---

## Part 4: Agent Modification

### 4.1 Modify the `update_servicenow_ticket` Tool

In `src/agent/agent_level_one_triage.py`, replace the simulated tool with a real API call:

```python
import os
import boto3
import json

def get_servicenow_credentials():
    """Get credentials from Secrets Manager"""
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='servicenow/credentials')
    return json.loads(response['SecretString'])

@tool
def update_servicenow_ticket(ticket_number: str, resolution_notes: str) -> str:
    """
    Update ServiceNow ticket with resolution notes.
    Makes real API call to ServiceNow.
    """
    try:
        # Get credentials
        creds = get_servicenow_credentials()

        # Create ServiceNow client
        from servicenow.client import ServiceNowClient
        from servicenow.config import ServiceNowConfig

        config = ServiceNowConfig(
            instance_url=creds['instance_url'],
            username=creds['username'],
            password=creds['password']
        )
        client = ServiceNowClient(config)

        # Add work notes
        result = client.add_work_notes(
            number=ticket_number,
            work_notes=f"[AI Agent Analysis]\n\n{resolution_notes}",
            state="2"  # 2 = In Progress
        )

        return json.dumps({
            "success": True,
            "ticket_number": ticket_number,
            "message": "Ticket updated in ServiceNow",
            "state": "In Progress"
        }, indent=2)

    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        }, indent=2)
```

### 4.2 Redeploy the Agent

```bash
agentcore launch
```

---

## End-to-End Testing

### Test 1: Create a Ticket in ServiceNow

1. Go to ServiceNow → Incident → Create New
2. Fill in:
   - **Short description**: `Cannot connect to VPN from home`
   - **Description**: `User reports VPN connection timeout when working from home`
   - **Category**: `Network`
   - **Priority**: `3 - Moderate`
3. Submit the ticket

### Test 2: Verify Triggering

1. **ServiceNow Logs**: System Logs → System Log → All
   - Search for `AWS Agent Response`
   - Verify HTTP status 200

2. **CloudWatch Logs**:
   ```bash
   aws logs tail /aws/lambda/ServiceNowWebhookStack-WebhookHandler-xxx --follow
   ```

### Test 3: Verify Ticket Update

1. Return to the ticket in ServiceNow
2. Check the **Activity** or **Work Notes** tab
3. You should see the agent's notes with:
   - Problem summary
   - Potential causes
   - Recommended resolution steps
   - Relevant KB articles

---

## Security and Best Practices

### 1. Never Hardcode Credentials

❌ **Bad**:
```python
password = "my_secret_password"
```

✅ **Good**:
```python
creds = get_servicenow_credentials()  # From Secrets Manager
```

### 2. Validate Webhook Payloads

```python
def validate_payload(body: dict) -> bool:
    required_fields = ['number', 'short_description']
    return all(field in body for field in required_fields)
```

### 3. Limit IAM Permissions

- Principle of least privilege
- Scope resources specifically
- Use conditions where possible

### 4. Monitor API Calls

- Enable CloudWatch Logs
- Configure alerts on errors
- Track metrics (latency, error rate)

### 5. Rate Limiting

ServiceNow has API limits. Implement:
- Retry with exponential backoff
- Queue for load spikes
- Cache for static data

---

## Troubleshooting

### Error: "SERVICENOW_INSTANCE_URL not found"

**Cause**: Secret doesn't exist or is misconfigured.

**Solution**:
```bash
aws secretsmanager get-secret-value --secret-id servicenow/credentials
```

### Error: "401 Unauthorized" from ServiceNow

**Cause**: Invalid credentials.

**Solution**:
1. Check username/password in Secrets Manager
2. Test credentials manually:
   ```bash
   curl -u "username:password" \
     "https://YOUR_INSTANCE.service-now.com/api/now/table/incident?sysparm_limit=1"
   ```

### Error: "Business Rule not firing"

**Cause**: Rule is not active or conditions don't match.

**Solution**:
1. Verify rule is **Active**
2. Check filter conditions
3. Test with an incident that matches conditions

### Error: "REST Message failed"

**Cause**: Incorrect REST Message configuration.

**Solution**:
1. Test REST Message manually in ServiceNow
2. Verify API Key in headers
3. Verify endpoint URL

---

## Next Steps

Congratulations! 🎉 You now have a complete bidirectional ServiceNow integration.

In the **next article (Article 4)**, we will:

🔜 **Replace the simulated KB** with AWS Bedrock Knowledge Bases
🔜 **Implement semantic search** with embeddings
🔜 **Connect to your real documents** (PDF, Confluence, SharePoint)
🔜 **Optimize responses** with RAG (Retrieval-Augmented Generation)

**Git Branch:** `step-04-knowledge-base`

---

## Resources

### ServiceNow Documentation
- [REST API Guide](https://developer.servicenow.com/dev.do#!/reference/api/tokyo/rest/)
- [Business Rules](https://docs.servicenow.com/bundle/tokyo-application-development/page/script/business-rules/concept/c_BusinessRules.html)
- [REST Message](https://docs.servicenow.com/bundle/tokyo-application-development/page/integrate/outbound-rest/concept/c_OutboundRESTMessage.html)

### AWS Documentation
- [Secrets Manager](https://docs.aws.amazon.com/secretsmanager/latest/userguide/)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)

### Source Code
- [GitHub Repository](https://github.com/your-username/aws-agentcore-tutorial)
- Branch: `step-03-servicenow-integration`

---

**Author:** Anthony PINTO
**Date:** December 2025
**Series:** Backoffice Support Agent with AWS AgentCore (3/5)

*This article is part of a series on AWS AgentCore.*
