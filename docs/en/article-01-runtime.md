# Article 1: Deploy a Support Agent with AWS AgentCore Runtime

> **Series: Backoffice Support Agent with AWS AgentCore**
> **Step 1 of 5** | [Version française](../fr/article-01-runtime.md)

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

In this article series, we'll build an **intelligent backoffice support agent** that:
- ✅ Automatically analyzes ServiceNow tickets
- ✅ Searches for solutions in a knowledge base
- ✅ Prepares ticket updates with proposed resolutions
- ✅ Helps the support team process tickets faster

### What You'll Build in This Article

In this first article, we'll create a functional prototype with **AWS AgentCore Runtime**. This agent will:
- Retrieve ticket information
- Search a simulated knowledge base
- Prepare ticket updates

**Important:** To validate the concept quickly, we use simulated (hard-coded) data. In Article 2, we'll connect the agent to the real ServiceNow API and add production infrastructure.

### Estimated Time
⏱️ **30-45 minutes** to complete this tutorial.

---

## What is AWS AgentCore Runtime?

**AWS AgentCore Runtime** is a service that allows you to deploy, run, and scale AI agents securely. It offers:

### Session Isolation
Each user session runs in its own protected environment, preventing data leaks—a critical requirement for applications handling sensitive data.

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

**Public** (what we use in this article)
- Execution with managed Internet access
- Perfect for prototypes and testing

**VPC-only** (coming soon)
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
   # Should show Python 3.9.x or higher
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

# Activate the environment
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
# Check that packages are installed
pip list | grep -E "strands|bedrock"
```

You should see:
```
bedrock-agentcore              x.x.x
bedrock-agentcore-starter-toolkit x.x.x
strands-agents                 x.x.x
strands-agents-tools          x.x.x
```

### 4. Verify Access to AgentCore CLI

Installing the `bedrock-agentcore-starter-toolkit` package gives you access to the AgentCore CLI:

```bash
agentcore --help
```

You should see the CLI help with available commands.

---

## Creating the Agent

### Project Structure

Here's our project structure:

```
aws-agentcore-tutorial/
├── src/
│   └── agent/
│       └── my_agent.py          # Our main agent
├── requirements.txt
└── .bedrock_agentcore.yaml      # Configuration (auto-generated)
```

### Agent Code

Let's open `src/agent/my_agent.py` to understand the structure.

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
- `BedrockAgentCoreApp`: Main class to create an AgentCore application

#### Agent Configuration

```python
SYSTEM_PROMPT = """
You are a helpful backoffice support assistant for ServiceNow ticket management.
Your role is to:
1. Analyze incoming support tickets
2. Search the knowledge base for relevant solutions
3. Prepare detailed ticket updates with proposed resolutions
4. Provide clear, professional responses to support staff

When analyzing a ticket:
- Extract key information (ticket ID, description, priority)
- Search the knowledge base for similar issues
- Propose a resolution based on available information
- Prepare a professional update for the ticket

Always be concise and professional in your responses.
"""
```

The **System Prompt** defines:
- The agent's personality
- Its role and responsibilities
- How it should behave

This is the key element that guides the agent's behavior.

#### Tool Definitions

Tools allow the agent to interact with external systems. Let's define three tools for our support agent.

**Tool 1: Ticket Information Retrieval**

```python
@tool
def get_ticket_info(ticket_id: str) -> str:
    """Get detailed information about a ServiceNow ticket"""
    # Simulated ticket data - will be replaced with real ServiceNow API in Article 2
    tickets = {
        "INC0001234": {
            "ticket_id": "INC0001234",
            "short_description": "Unable to access VPN from home",
            "description": "User reports that VPN client shows 'Connection timeout' error...",
            "priority": "2 - High",
            "state": "New",
            # ... other fields
        },
        # ... other tickets
    }

    if ticket_id in tickets:
        response = tickets[ticket_id]
    else:
        response = {"error": f"Ticket {ticket_id} not found"}

    return json.dumps(response, indent=2)
```

**What this tool does:**
- Takes a ticket ID as input
- Returns complete ticket details
- In this article, uses simulated data
- In Article 2, will call the real ServiceNow API

**Tool 2: Knowledge Base Search**

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
- Returns matching solutions
- In this article, uses simple keyword-based logic
- In Article 3, will use AWS Bedrock Knowledge Bases with semantic search

**Tool 3: Ticket Update Preparation**

```python
@tool
def prepare_ticket_update(ticket_id: str, resolution_notes: str,
                         proposed_state: str = "In Progress") -> str:
    """Prepare a ticket update with resolution notes and state change"""
    # Simulated ticket update preparation
    update_payload = {
        "ticket_id": ticket_id,
        "work_notes": resolution_notes,
        "state": proposed_state,
        "updated_by": "AI Agent",
        "note": "This is a simulated update. In production, this would update the actual ServiceNow ticket."
    }

    return json.dumps(update_payload, indent=2)
```

**What this tool does:**
- Prepares a ticket update
- Formats resolution notes
- In Article 2, will actually send the update to ServiceNow

#### AgentCore Application Initialization

```python
# Create the AgentCore app
app = BedrockAgentCoreApp()

# Create the agent with Nova Lite model
agent = Agent(
    model="eu.amazon.nova-lite-v1:0",
    system_prompt=SYSTEM_PROMPT,
    tools=[
        calculator,
        current_time,
        get_ticket_info,
        search_knowledge_base,
        prepare_ticket_update
    ]
)
```

**Explanations:**
- `BedrockAgentCoreApp()`: Creates the AgentCore application
- `Agent()`: Initializes the Strands agent with:
  - **model**: Amazon Nova Lite (fast and economical)
  - **system_prompt**: The system prompt defined above
  - **tools**: List of tools available to the agent

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
- `payload.get("prompt")`: Extracts the user message from the JSON payload
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

**What this command does:**
- Launches the agent in a local server
- Listens on `http://localhost:8080`
- Allows testing the agent without AWS deployment
- Uses your local AWS credentials to access Bedrock

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

### 2. Test with AgentCore CLI

Open a new terminal (keep the server running) and test:

**Test 1: Simple Greeting**
```bash
agentcore invoke --local '{"prompt": "Hello! What can you help me with?"}'
```

The agent should respond by explaining its role in ServiceNow support.

**Test 2: VPN Ticket Analysis**
```bash
agentcore invoke --local '{"prompt": "Analyze ticket INC0001234 and propose a solution"}'
```

The agent should:
1. Call `get_ticket_info("INC0001234")`
2. Read the ticket details (VPN problem)
3. Call `search_knowledge_base` with "VPN"
4. Find article KB0001
5. Propose a solution based on the article

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
- **Reasons**: Plans the necessary steps
- **Acts**: Calls appropriate tools
- **Synthesizes**: Combines information to give a complete response

This is the **Reasoning → Acting → Observing** cycle of AI agents.

---

## Deploying to AWS

Now that the agent works locally, let's deploy it to AWS with AgentCore Runtime.

### 1. Configure Agent for Deployment

Stop the local server (Ctrl+C) and run:

```bash
agentcore configure --entrypoint src/agent/my_agent.py
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
default_agent: my_agent
agents:
  my_agent:
    name: my_agent
    entrypoint: src/agent/my_agent.py
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
   - Endpoints for invocation

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
Agent: my_agent
Status: ACTIVE
Endpoint: https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/invoke
Region: eu-central-1
```

### 2. Invoke Deployed Agent

**Without the `--local` flag, commands use the AWS endpoint:**

```bash
agentcore invoke '{"prompt": "Analyze ticket INC0001234 and provide a resolution"}'
```

The agent is now running on AWS AgentCore Runtime!

### 3. Complete Usage Example

Let's test a complete scenario:

```bash
agentcore invoke '{
  "prompt": "I have a new ticket INC0001236 about email sync issues on iPhone. Please analyze it, find relevant KB articles, and prepare a ticket update with the solution."
}'
```

The agent will:
1. ✅ Retrieve ticket INC0001236 details
2. ✅ Identify the problem (email sync on iPhone)
3. ✅ Search KB → finds KB0003
4. ✅ Prepare an update with resolution steps
5. ✅ Return a professional, structured response

---

## Observability

### View Logs

AgentCore Runtime automatically integrates with CloudWatch Logs.

**Via CLI:**
```bash
# View recent logs
agentcore logs --tail 50

# Follow logs in real-time
agentcore logs --follow
```

**Via AWS Console:**
1. Open CloudWatch in AWS console
2. Go to **Logs > Log groups**
3. Search for your agent's log group
4. Explore execution logs

### X-Ray Traces (if configured)

If you enabled X-Ray Transaction Search, you can:
- Visualize execution traces
- See tool calls
- Analyze performance
- Debug errors

We'll dive deeper into observability in Article 4.

---

## Summary and Best Practices

### What We Accomplished 🎉

✅ Created an intelligent support agent for ServiceNow
✅ Defined 3 custom tools (ticket info, KB search, ticket update)
✅ Tested the agent locally with `agentcore launch --local`
✅ Deployed the agent to AWS with `agentcore launch`
✅ Invoked the agent via CLI
✅ Configured basic observability

### Best Practices

#### 1. Iterative Development

Always follow this cycle:
```
Develop locally → Test locally → Deploy → Test in prod
```

#### 2. System Prompt

- Be specific about the agent's role
- Provide examples of expected behavior
- Iterate on the prompt based on results

#### 3. Tools

- Keep tools simple and focused
- Always return structured JSON
- Include robust error handling

#### 4. Testing

Test different scenarios:
- Nominal cases (ticket exists, KB finds solution)
- Error cases (ticket not found, no solution)
- Edge cases (ambiguous queries, multiple solutions)

---

## Troubleshooting

### Agent Can't Find Model

**Error:** `Model eu.amazon.nova-lite-v1:0 not found`

**Solution:**
- Verify you have access to Amazon Bedrock in eu-central-1
- Enable Nova Lite model in Bedrock console
- Check IAM permissions to invoke the model

### IAM Permission Error

**Error:** `AccessDeniedException`

**Solution:**
The auto-created IAM role must have:
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

### Local Agent Won't Start

**Error:** `Port 8080 already in use`

**Solution:**
```bash
# Find process using the port
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or use a different port
agentcore launch --local --port 8081
```

---

## Next Steps

In the **next article (Article 2)**, we will:

🔜 **Connect the agent to ServiceNow** via REST API
🔜 **Integrate AWS AgentCore Gateway** to expose the agent
🔜 **Configure webhooks** to automatically receive new tickets
🔜 **Deploy production infrastructure** with AWS CDK
🔜 **Implement end-to-end ticket flow**

**Git Branch:** `step-02-gateway-servicenow`

---

## Resources

### Documentation
- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Strands Agents Documentation](https://docs.strands.ai/)
- [Amazon Nova Models](https://aws.amazon.com/bedrock/nova/)

### Source Code
- [GitHub Repository](https://github.com/your-username/aws-agentcore-tutorial)
- Branch: `step-01-runtime-deployment`

### Support
- Open a [GitHub issue](https://github.com/your-username/aws-agentcore-tutorial/issues)
- [ServiceNow Developer Portal](https://developer.servicenow.com/)

---

## Conclusion

Congratulations! 🎉 You've deployed your first intelligent agent with AWS AgentCore Runtime.

**Recap:**
- You understood AgentCore Runtime concepts
- Created an agent with 3 ServiceNow tools
- Tested locally then deployed to AWS
- Invoked the agent in production

**The Progressive Approach:**
- **Article 1** (this tutorial): Functional agent with simulated data
- **Article 2**: Connection to real ServiceNow + Infrastructure
- **Articles 3-5**: Advanced features (KB, Observability, Identity)

This approach allows you to quickly validate the concept before investing in complete infrastructure.

**Ready for more?** → [Article 2: Gateway and ServiceNow Integration](article-02-gateway.md)

---

**Author:** Your Name
**Date:** October 2025
**Series:** Backoffice Support Agent with AWS AgentCore (1/5)

*This article is part of a 5-article series on AWS AgentCore.*
