# Article 1: Deploy a Support Agent with AWS AgentCore Runtime

> **Series: Backoffice Support Agent with AWS AgentCore**
> **Step 1**

## Table of Contents

1. [Introduction](#introduction)
2. [What is AWS AgentCore Runtime?](#what-is-aws-agentcore-runtime)
3. [Prerequisites](#prerequisites)
4. [Environment Setup](#environment-setup)
5. [Creating the Agent](#creating-the-agent)
6. [Local Testing](#local-testing)
7. [Deploying to AWS](#deploying-to-aws)
8. [Invoking the Agent](#invoking-the-agent)
9. [Observability](#observability)
10. [Next Steps](#next-steps)

---

## Introduction

When a ticket arrives in ServiceNow, the support team must analyze the problem, search the knowledge base, and prepare a response. This manual process takes time and delays resolution.

In this article series, we will build an **intelligent backoffice support agent** that:
- ✅ Automatically receives ServiceNow tickets via webhook
- ✅ Analyzes received ticket data
- ✅ Searches for solutions in a knowledge base
- ✅ Directly updates tickets in ServiceNow
- ✅ Helps the support team process tickets faster

### What You Will Build in This Article

In this first article, we will create a functional prototype with **AWS AgentCore Runtime**. This agent:
- Receives ticket data as input (via webhook in Article 2)
- Parses and extracts relevant ticket information
- Searches a simulated knowledge base
- Prepares ticket updates

**Important:** To quickly validate the concept, we use simulated (hard-coded) data. In Article 2, we will deploy the complete webhook infrastructure with API Gateway + Lambda and connect the agent to the real ServiceNow API.

### Estimated Time
⏱️ **30-45 minutes** to complete this tutorial.

---

## What is AWS AgentCore Runtime?

**AWS AgentCore Runtime** is a service that allows you to securely deploy, run, and scale AI agents. It offers:

### Session Isolation
Each user session runs in its own protected environment, preventing data leaks - a critical requirement for applications handling sensitive data.

### Serverless Environment
- No servers to manage
- Automatic scaling
- Pay-per-use billing

### Compatibility with All Frameworks
AgentCore Runtime works with:
- ✅ **Strands Agents** (which we use in this series)
- ✅ CrewAI
- ✅ LangGraph
- ✅ LlamaIndex
- ✅ Any custom framework or agent

### Network Configurations

AgentCore Runtime supports different network configurations:

**Public** (which we use in this article)
- Execution with managed Internet access
- Perfect for prototypes and testing

**VPC-only** (available soon)
- Access to resources hosted in your VPC
- Connection via AWS PrivateLink
- Ideal for production with strict security requirements

---

## Prerequisites

### AWS Account and Tools

1. **Active AWS Account**
   - Access to Amazon Bedrock in your region (eu-central-1)
   - IAM permissions to create roles and ECR repositories

2. **Configured AWS CLI**
   ```bash
   aws configure
   # Verify configuration
   aws sts get-caller-identity
   ```

3. **Python 3.9 or higher**
   ```bash
   python --version
   # Should display Python 3.9.x or higher
   ```

4. **Git**
   ```bash
   git --version
   ```

### Recommended Knowledge

- Python basics
- Understanding of AI agent concepts
- Familiarity with AWS (IAM, basic services)

---

## Environment Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/aws-agentcore-tutorial.git
cd aws-agentcore-tutorial

# Switch to step-01 branch (if available)
git checkout step-01-runtime-deployment
```

### 2. Create and Activate a Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate environment
# On Linux/Mac:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

Your prompt should now start with `(.venv)`.

### 3. Install Dependencies

The `requirements.txt` file contains all necessary dependencies:

```txt
strands-agents
strands-agents-tools
bedrock-agentcore
bedrock-agentcore-starter-toolkit
```

Install them with:

```bash
pip install -r requirements.txt
```

**Verification:**
```bash
# Verify packages are installed
pip list | grep -E "strands|bedrock"
```

You should see:
```
bedrock-agentcore              x.x.x
bedrock-agentcore-starter-toolkit x.x.x
strands-agents                 x.x.x
strands-agents-tools          x.x.x
```

### 4. Verify AgentCore CLI Access

Installing the `bedrock-agentcore-starter-toolkit` package gives you access to the AgentCore CLI:

```bash
agentcore --help
```

You should see the CLI help with available commands.

### 5. Configure Your AWS Account

The `.bedrock_agentcore.yaml` configuration file contains information specific to your AWS account. For security reasons, this file is not included in the Git repository.

**Configuration steps:**

1. **Copy the configuration template**
    ```bash
    cp .bedrock_agentcore.yaml.template .bedrock_agentcore.yaml
    ```

2. **Retrieve your AWS account number**
```bash
aws sts get-caller-identity --query Account --output text
```

Or via the AWS console: click on your username in the top right → the account number is displayed.

3. **Edit the configuration file**

Open `.bedrock_agentcore.yaml` and replace all occurrences of `AWS_ACCOUNT_NUMBER` with your AWS account number:
```bash
# Before
account: 'AWS_ACCOUNT_NUMBER'
ecr_repository: AWS_ACCOUNT_NUMBER.dkr.ecr.eu-central-1.amazonaws.com/...

# After (example with account 123456789012)
account: '123456789012'
ecr_repository: 123456789012.dkr.ecr.eu-central-1.amazonaws.com/...
```

4. **Verify configuration**
```bash
grep "AWS_ACCOUNT_NUMBER" .bedrock_agentcore.yaml
```

This command should return nothing. If it displays results, you haven't replaced all occurrences.

**Note:** The `.bedrock_agentcore.yaml` file is ignored by Git (via `.gitignore`) to protect your sensitive information. Never commit this file to your repository.


---

## Creating the Agent

### Project Structure

Here is our project structure:

```
aws-agentcore-tutorial/
├── src/
│   └── agent/
│       └── agent_level_one_triage.py          # Our main agent
├── requirements.txt
└── .bedrock_agentcore.yaml      # Configuration (automatically generated)
```

### Agent Code

Let's open `src/agent/agent_level_one_triage.py` to understand the structure.

#### Module Imports

```python
import json
from strands import Agent, tool
from strands_tools import calculator, current_time
from bedrock_agentcore.runtime import BedrockAgentCoreApp
```

**Explanations:**
- `strands`: Framework for creating AI agents
- `@tool`: Decorator to define tools the agent can use
- `BedrockAgentCoreApp`: Main class for creating an AgentCore application

#### Agent Configuration

```python
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
```

The **System Prompt** defines:
- The agent's personality
- Its role and responsibilities
- How it should behave

This is the key element that guides the agent's behavior.

#### Tool Definition

Tools allow the agent to interact with external systems. Let's define three tools for our support agent.

**Tool 1: Parse Received Ticket Data**

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

**What this tool does:**
- Receives complete ticket data in JSON format
- Extracts and formats key ticket information
- Handles parsing errors gracefully
- In Article 2, will receive data directly via ServiceNow webhook

**Webhook architecture (Article 2):**
```
ServiceNow (new ticket created)
    ↓ Triggers Business Rule
    ↓ HTTP POST with complete ticket data
API Gateway (/webhook/servicenow)
    ↓ Invokes
Lambda Function (webhook_handler)
    ↓ Calls
Agent (parse_ticket_data + analysis + update)
```

**Tool 2: Search Knowledge Base**

```python
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
                "1. Check if user's home network allows VPN traffic...",
                "2. Verify VPN client version is up to date",
                # ... other steps
            ],
            "category": "Network Access"
        })

    # ... other articles

    return json.dumps(response, indent=2)
```

**What this tool does:**
- Searches for relevant knowledge base articles
- Returns corresponding solutions
- In this article, uses simple keyword-based logic
- In Article 3, will use AWS Bedrock Knowledge Bases with semantic search

**Tool 3: ServiceNow Ticket Update**

```python
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
```

**What this tool does:**
- Prepares a ticket update with resolution notes
- Simulates the update in this article
- In Article 2, will make a real REST API call to ServiceNow
- Returns a structured result indicating success or failure

#### AgentCore Application Initialization

```python
# Create AgentCore application
app = BedrockAgentCoreApp()

# Create agent with Nova Lite model
agent = Agent(
    model="eu.amazon.nova-lite-v1:0",
    system_prompt=SYSTEM_PROMPT,
    tools=[
        calculator,
        current_time,
        parse_ticket_data,      # Parse received ticket data
        search_knowledge_base,
        update_servicenow_ticket  # Update ServiceNow
    ]
)
```

**Explanations:**
- `BedrockAgentCoreApp()`: Creates the AgentCore application
- `Agent()`: Initializes the Strands agent with:
  - **model**: Amazon Nova Lite (fast and economical)
  - **system_prompt**: The system prompt defined above
  - **tools**: List of available tools for the agent

#### Application Entry Point

```python
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
```

**Explanations:**
- `@app.entrypoint`: Defines the function called during invocation
- `payload.get("prompt")`: Extracts the user message from JSON payload
- `agent(user_message)`: Invokes the agent with the message
- `response.message['content'][0]['text']`: Extracts the response text

---

## Local Testing

Before deploying to AWS, let's test the agent locally.

### 1. Launch Agent in Local Mode

```bash
# From the project root directory
agentcore launch --local
```

### 2. Test with AgentCore CLI

Open a new terminal (keep the server running) and test:

**Test 1: Simple Greeting**
```bash
agentcore invoke --local '{"prompt": "Hello! What can you help me with?"}'
```

The agent should respond explaining its support role for ServiceNow.

**Test 2: VPN Ticket Data Analysis**
```bash
agentcore invoke --local '{"prompt": "Analyze this ticket data: {\"number\": \"INC0001234\", \"short_description\": \"VPN connection timeout\", \"description\": \"User cannot connect to VPN from home\", \"priority\": \"2\", \"state\": \"1\"}"}'
```

The agent should:
1. Call `parse_ticket_data()` with the ticket JSON data
2. Extract key information (number, description, priority)
3. Call `search_knowledge_base` with "VPN"
4. Find article KB0001
5. Propose a solution based on the article
6. Call `update_servicenow_ticket()` to update the ticket

**Test 3: General Search**
```bash
agentcore invoke --local '{"prompt": "How do I troubleshoot email sync issues on iPhone?"}'
```

The agent should search the knowledge base and return article KB0003 about mobile email sync issues.

### 3. Test with curl (Optional)

You can also test directly with curl:

```bash
curl -X POST http://localhost:8080/invoke \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Analyze ticket INC0001235"
  }'
```

### 4. Observe Agent Behavior

When you invoke the agent, observe how it:
- **Reasons**: Plans necessary steps
- **Acts**: Calls appropriate tools
- **Synthesizes**: Combines information to give a complete response

This is the **Reasoning → Acting → Observing** cycle of AI agents.

---

## Deploying to AWS

Now that the agent works locally, let's deploy it to AWS with AgentCore Runtime.

### 1. Configure Agent for Deployment

Stop the local server (Ctrl+C) and run:

```bash
agentcore configure --entrypoint src/agent/agent_level_one_triage.py
```

**Questions asked by the CLI:**

1. **Auto-create IAM execution role?** → Press Enter (Yes)
   - Automatically creates an IAM role with necessary permissions

2. **Auto-create ECR repository?** → Press Enter (Yes)
   - Creates an Amazon ECR repository to store the Docker image

3. **Dependency file detected** → Press Enter (Confirm)
   - Uses requirements.txt to install dependencies

This command creates a `.bedrock_agentcore.yaml` file with the configuration:

```yaml
default_agent: agent_level_one_triage
agents:
  agent_level_one_triage:
    name: agent_level_one_triage
    entrypoint: src/agent/agent_level_one_triage.py
    platform: linux/arm64
    container_runtime: docker
    aws:
      account: 'YOUR-ACCOUNT-ID'
      region: eu-central-1
      ecr_auto_create: true
      execution_role_auto_create: true
      network_configuration:
        network_mode: PUBLIC
      observability:
        enabled: true
```

### 2. Enable Observability with CloudWatch

To enable trace delivery, configure Transaction Search in CloudWatch:

```bash
# Enable CloudWatch Logs for traces
aws xray update-trace-segment-destination --destination CloudWatchLogs

# Configure sampling rate (1% here)
aws xray update-indexing-rule --name "Default" --rule '{"Probabilistic": {"DesiredSamplingPercentage": 1}}'
```

Verify configuration:

```bash
aws xray get-trace-segment-destination
aws xray get-indexing-rules
```

### 3. Deploy the Agent

Launch deployment:

```bash
agentcore launch
```

**What this command does:**
1. **Build**: Builds your agent's Docker image
2. **Push**: Pushes the image to Amazon ECR
3. **Deploy**: Creates AgentCore Runtime infrastructure:
   - Isolated serverless environment
   - Network configuration (PUBLIC mode)
   - IAM roles with Bedrock permissions
   - Invocation endpoints

Deployment typically takes **2-3 minutes**.

You'll see:
```
Building agent...
Pushing to ECR...
Deploying to AgentCore Runtime...
✓ Agent deployed successfully!

Endpoint: https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/invoke
```

---

## Invoking the Agent

Once deployed, invoke the agent from anywhere.

### 1. Check Status

```bash
agentcore status
```

Should display:
```
Agent: agent_level_one_triage
Status: ACTIVE
Endpoint: https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/invoke
Region: eu-central-1
```

### 2. Invoke the Deployed Agent

**Without the `--local` flag, commands use the AWS endpoint:**

```bash
agentcore invoke '{"prompt": "Analyze ticket INC0001234 and provide a resolution"}'
```

The agent now runs on AWS AgentCore Runtime!

### 3. Complete Usage Example

Let's test a complete scenario:

```bash
agentcore invoke '{
  "prompt": "Analyze this ticket: {\"number\": \"INC0001236\", \"short_description\": \"Email sync issues on iPhone\", \"description\": \"User cannot sync email on iPhone 14\", \"priority\": \"3\", \"state\": \"1\"}. Find relevant KB articles and update the ticket with the solution."
}'
```

The agent will:
1. ✅ Parse ticket INC0001236 data with `parse_ticket_data()`
2. ✅ Identify the problem (email sync on iPhone)
3. ✅ Search KB with `search_knowledge_base()` → finds KB0003
4. ✅ Update ServiceNow with `update_servicenow_ticket()` with resolution steps
5. ✅ Return a professional and structured response

---

## Observability

### Viewing Logs

AgentCore Runtime automatically integrates with CloudWatch Logs.

**Via AWS CLI:**
```bash
# Find the log group name
agentcore status

# View recent logs (replace LOG_GROUP_ID with ID shown in status)
aws logs tail /aws/lambda/bedrock-agentcore-agent_level_one_triage-LOG_GROUP_ID --follow

# Or list all log groups to find your agent's
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/bedrock-agentcore
```

**Via AWS Console:**
1. Open CloudWatch in the AWS console
2. Go to **Logs > Log groups**
3. Search for log group: `/aws/lambda/bedrock-agentcore-agent_level_one_triage`
4. Explore execution logs

### X-Ray Traces (if configured)

If you enabled X-Ray Transaction Search, you can:
- Visualize execution traces
- See tool calls
- Analyze performance
- Debug errors

We will explore observability in depth in Article 4.

---

## Summary and Best Practices

### What We Accomplished 🎉

✅ Created an intelligent support agent for ServiceNow
✅ Defined 3 custom tools:
   - `parse_ticket_data`: Parses received ticket data
   - `search_knowledge_base`: Searches KB
   - `update_servicenow_ticket`: Updates tickets
✅ Tested agent locally with `agentcore launch --local`
✅ Deployed agent to AWS with `agentcore launch`
✅ Invoked agent via CLI
✅ Configured basic observability

### Best Practices

#### 1. Iterative Development

Always follow this cycle:
```
Develop locally → Test locally → Deploy → Test in prod
```

#### 2. System Prompt

- Be specific about the agent's role
- Give examples of expected behavior
- Iterate on the prompt based on results

#### 3. Tools

- Keep tools simple and focused
- Always return structured JSON
- Include robust error handling

#### 4. Testing

Test different scenarios:
- Nominal cases (ticket exists, KB finds solution)
- Error cases (ticket doesn't exist, no solution)
- Edge cases (ambiguous queries, multiple possible solutions)

---

## Troubleshooting

### Agent Cannot Find Model

**Error:** `Model eu.amazon.nova-lite-v1:0 not found`

**Solution:**
- Verify you have access to Amazon Bedrock in eu-central-1
- Enable Nova Lite model in Bedrock console
- Check IAM permissions to invoke the model

### IAM Permission Error

**Error:** `AccessDeniedException`

**Solution:**
The automatically created IAM role must have:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:eu-central-1::foundation-model/amazon.nova-lite-v1:0"
    }
  ]
}
```
---

## Next Steps

In the **next article (Article 2)**, we will:

🔜 **Implement complete webhook architecture** (ServiceNow → API Gateway → Lambda → Agent)
🔜 **Create a ServiceNow API client** for real-time updates
🔜 **Deploy infrastructure** with AWS CDK (API Gateway + Lambda + Secrets Manager)
🔜 **Configure ServiceNow Business Rules** to trigger webhooks
🔜 **Implement end-to-end ticket flow**:
   - ServiceNow sends ticket data via webhook
   - Lambda invokes agent with data
   - Agent analyzes and updates ServiceNow directly
🔜 **Create comprehensive test suite**

**Git Branch:** `step-02-gateway-servicenow`

---

## Resources

### Documentation
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Strands Agents Documentation](https://docs.strands.ai/)
- [Amazon Nova Models](https://aws.amazon.com/bedrock/nova/)

### Source Code
- [GitHub Repository](https://github.com/TienShinhan-world/aws-agentcore-tutorial)
- Branch: `step-01-runtime-deployment`

### Support
- Open an [issue on GitHub](https://github.com/TienShinhan-world/aws-agentcore-tutorial/issues)
- [ServiceNow Developer Portal](https://developer.servicenow.com/)

---

## Conclusion

Congratulations! 🎉 You deployed your first intelligent agent with AWS AgentCore Runtime.

**Recap:**
- You understood AgentCore Runtime concepts
- Created an agent with 3 ServiceNow tools:
  - `parse_ticket_data`: Parses ticket data
  - `search_knowledge_base`: Solution search
  - `update_servicenow_ticket`: Ticket updates
- Tested locally then deployed to AWS
- Invoked the agent in production

**The progressive approach:**
- **Article 1** (this tutorial): Functional agent with data parsing
- **Article 2**: Complete webhook architecture + Real ServiceNow API + AWS CDK Infrastructure
- **Articles 3-X**: Advanced features (Memory, KB, Observability, Identity)

This approach allows you to quickly validate the concept before investing in complete infrastructure. The agent is already designed to receive ticket data as input, which facilitates webhook integration in Article 2.

---

**Author:** Anthony PINTO
**Date:** October 2025
**Series:** Backoffice Support Agent with AWS AgentCore (1/X)

*This article is part of a series on AWS AgentCore.*
