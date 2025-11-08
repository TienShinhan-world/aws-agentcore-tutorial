# Step 1: AWS AgentCore Runtime Deployment

> **Tutorial Series:** ServiceNow Backoffice Support Agent with AWS AgentCore
> **Part 1 of 5** | [Article FR](docs/fr/article-01-runtime.md) | [Article EN](docs/en/article-01-runtime.md)

## What You'll Build

In this step, you'll create a functional prototype with **AWS AgentCore Runtime**. This agent:
- Receives ticket data as input (via webhook in Step 2)
- Parses and extracts relevant ticket information
- Searches a simulated knowledge base
- Prepares ticket updates

**Important:** To validate the concept quickly, we use simulated data. In Step 2, we'll deploy the complete webhook infrastructure with API Gateway + Lambda and connect the agent to the real ServiceNow API.

## Prerequisites

- AWS account with Bedrock access in eu-central-1
- AWS CLI configured (`aws configure`)
- Python 3.9+ installed
- Git installed
- Docker installed (for local testing)

## Quick Start

### 1. Setup Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify AgentCore CLI is available
agentcore --help
```

### 2. Test Locally

```bash
# Launch agent locally
agentcore launch --local

# In another terminal, test the agent
agentcore invoke --local '{"prompt": "Hello! What can you help me with?"}'

# Test with ticket analysis
agentcore invoke --local '{
  "prompt": "Analyze this ticket data: {\"number\": \"INC0001234\", \"short_description\": \"VPN connection timeout\", \"description\": \"User cannot connect to VPN from home\", \"priority\": \"2\", \"state\": \"1\"}"
}'
```

### 3. Deploy to AWS

```bash
# Configure for deployment
agentcore configure --entrypoint src/agent/my_agent.py

# Answer the prompts:
# - Auto-create IAM execution role? Yes
# - Auto-create ECR repository? Yes
# - Use requirements.txt? Yes

# Deploy to AWS
agentcore launch

# Invoke the deployed agent
agentcore invoke '{"prompt": "Analyze ticket INC0001234"}'
```

## Agent Structure

The agent (`src/agent/my_agent.py`) includes:

### Three Custom Tools

1. **`parse_ticket_data`** - Parses JSON ticket data
2. **`search_knowledge_base`** - Searches simulated knowledge base
3. **`update_servicenow_ticket`** - Simulates ticket update (real API in Step 2)

### Key Features

- **Model:** Amazon Nova Lite (`eu.amazon.nova-lite-v1:0`)
- **Framework:** Strands Agents
- **Runtime:** AWS Bedrock AgentCore
- **Network Mode:** PUBLIC (for testing)
- **Observability:** CloudWatch Logs enabled

## Testing the Agent

### Example 1: VPN Issue

```bash
agentcore invoke --local '{
  "prompt": "Analyze this ticket: {\"number\": \"INC0001234\", \"short_description\": \"VPN connection timeout\", \"description\": \"User cannot connect to VPN from home\", \"priority\": \"2\", \"state\": \"1\"}. Find relevant KB articles and update the ticket."
}'
```

The agent will:
1. Parse the ticket data → extract key info
2. Search knowledge base → find KB0001 (VPN troubleshooting)
3. Prepare resolution notes
4. Simulate ticket update

### Example 2: Email Sync Issue

```bash
agentcore invoke --local '{
  "prompt": "How do I troubleshoot email sync issues on iPhone?"
}'
```

The agent will search the knowledge base and return KB0003 with mobile email sync solutions.

## What's Simulated in Step 1

- **Knowledge Base:** Hardcoded articles (replaced with Bedrock KB in Step 3)
- **ServiceNow Updates:** Returns JSON response (real API calls in Step 2)
- **Webhook Integration:** Manual JSON input (automated webhook in Step 2)

## Observability

View logs:

```bash
# Via CLI
agentcore logs --tail 50
agentcore logs --follow

# Via AWS Console
# Go to CloudWatch > Log Groups > [your-agent-log-group]
```

## Configuration Files

- **`.bedrock_agentcore.yaml`** - AgentCore deployment configuration
- **`Dockerfile`** - Container image definition
- **`requirements.txt`** - Python dependencies

## Troubleshooting

### Model Not Found

```bash
# Ensure Nova Lite is enabled in Bedrock console
# Check IAM permissions for bedrock:InvokeModel
```

### Port Already in Use

```bash
# Kill existing process
lsof -i :8080
kill -9 <PID>

# Or use different port
agentcore launch --local --port 8081
```

## Next Steps

🔜 **Step 2:** [Gateway & ServiceNow Integration](../step-02-gateway-servicenow/README_STEP02.md)

In the next step, we'll:
- Deploy API Gateway + Lambda webhook infrastructure
- Implement real ServiceNow API integration
- Configure ServiceNow Business Rules to trigger webhooks
- Create end-to-end ticket flow

## Resources

- [AWS Bedrock AgentCore Documentation](https://docs.aws.amazon.com/bedrock/latest/userguide/agents.html)
- [Strands Agents Documentation](https://docs.strands.ai/)
- [Amazon Nova Models](https://aws.amazon.com/bedrock/nova/)
- [Tutorial Article (French)](docs/fr/article-01-runtime.md)
- [Tutorial Article (English)](docs/en/article-01-runtime.md)

## Repository Structure

```
aws-agentcore-tutorial/
├── src/
│   └── agent/
│       └── my_agent.py          # Main agent implementation
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container definition
├── .bedrock_agentcore.yaml      # AgentCore config
├── docs/                         # Tutorial articles
└── README_STEP01.md             # This file
```

---

**Current Branch:** `step-01-runtime-deployment`
**Status:** ✅ Ready for deployment and testing
