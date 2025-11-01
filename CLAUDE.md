# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a tutorial repository for building an intelligent backoffice support agent using AWS AgentCore. The project demonstrates progressive integration with ServiceNow, knowledge bases, observability, and identity management across 5 tutorial steps, each on separate Git branches.

**Current Status**: Webhook-based ServiceNow integration - ServiceNow pushes ticket data to agent via API Gateway + Lambda

**Architecture**: ServiceNow → API Gateway → Lambda → AgentCore Agent → ServiceNow API (update ticket)

## Development Commands

### Local Testing

```bash
# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Run agent locally with Docker
docker build -t my-agent .
docker run -p 8000:8000 my-agent

# Test the agent locally
curl -X POST http://localhost:8000/invoke \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze ticket INC0001234"}'
```

### AWS Deployment

This project uses the Bedrock AgentCore CLI for deployment:

```bash
# Deploy agent to AWS (uses .bedrock_agentcore.yaml config)
bedrock-agentcore deploy my_agent

# Invoke deployed agent
bedrock-agentcore invoke my_agent --prompt "Your prompt here"

# Get deployment status
bedrock-agentcore status my_agent

# View logs
bedrock-agentcore logs my_agent
```

### Webhook Infrastructure Deployment

Deploy the API Gateway + Lambda webhook infrastructure:

```bash
# Install CDK dependencies
cd infrastructure/cdk
npm install

# Bootstrap CDK (first time only)
npm run cdk bootstrap

# Deploy webhook infrastructure
npm run cdk deploy

# Get webhook URL
aws cloudformation describe-stacks \
  --stack-name ServiceNowWebhookStack \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookURL`].OutputValue' \
  --output text

# Configure ServiceNow credentials
aws secretsmanager update-secret \
  --secret-id servicenow/credentials \
  --secret-string '{"instance_url":"https://YOUR_INSTANCE.service-now.com","username":"YOUR_USER","password":"YOUR_PASS"}'
```

### Testing Webhook Integration

```bash
# Test local webhook handler
./scripts/test_webhook.sh --local

# Test deployed webhook
./scripts/test_webhook.sh --url https://your-api-gateway-url/webhook/servicenow

# Test with custom ticket data
./scripts/test_webhook.sh --ticket my_ticket.json
```

### Navigation Between Tutorial Steps

```bash
# Interactive navigation
python scripts/navigate.py

# Direct navigation to specific step
python scripts/navigate.py --step 1

# List all available steps
python scripts/navigate.py --list

# With language preference (fr/en)
python scripts/navigate.py --step 1 --lang fr
```

## Code Architecture

### Webhook-Based Architecture

The system uses a **webhook-driven architecture** where ServiceNow initiates contact with the agent:

**Flow**:
1. **ServiceNow** creates/updates ticket → triggers Business Rule
2. **Business Rule** sends HTTP POST to AWS API Gateway webhook endpoint
3. **API Gateway** validates request → forwards to Lambda
4. **Lambda** (webhook_handler.py) parses ticket data → invokes agent
5. **Agent** analyzes ticket → searches knowledge base → calls ServiceNow API
6. **ServiceNow API** receives update with agent's resolution notes

### Agent System (src/agent/my_agent.py)

The core agent uses the **Strands** framework with AWS Bedrock AgentCore integration:

- **Model**: Amazon Nova Lite (`eu.amazon.nova-lite-v1:0`)
- **Framework**: Strands Agent with tool calling capabilities
- **Runtime**: BedrockAgentCoreApp provides HTTP server and AWS integration
- **Entry point**: `@app.entrypoint` decorator wraps the agent invocation handler

**Key components**:
1. `Agent` - Strands agent with system prompt and tool registration
2. `@tool` - Decorator for creating agent tools (must have descriptive docstrings)
3. `BedrockAgentCoreApp` - Runtime wrapper providing HTTP server and AWS integration
4. `invoke(payload)` - Entry point function that extracts prompt and returns agent response

**Tools** (modified for webhook architecture):
- `parse_ticket_data` - Parses ticket JSON received from webhook
- `search_knowledge_base` - Searches simulated KB (will be replaced with Bedrock KB in step 3)
- `update_servicenow_ticket` - Makes real API call to ServiceNow to update ticket with work notes

### Tool Development Pattern

Tools follow a specific pattern required by the Strands framework:

```python
@tool
def tool_name(param: str) -> str:
    """Clear description of what the tool does (used by LLM for tool selection)"""
    # Implementation
    result = {"key": "value"}
    return json.dumps(result, indent=2)  # Always return JSON string
```

**Important**:
- Tool docstrings are critical - the LLM uses them to decide when to call the tool
- Always return JSON-serialized strings for structured data
- Type hints are required for all parameters
- Error handling should return JSON with "success": false and "error" fields

**Current tools**:
- `parse_ticket_data` - Extracts and formats ticket data from webhook payload
- `search_knowledge_base` - Searches simulated KB (currently hardcoded articles)
- `update_servicenow_ticket` - **Makes real API calls to ServiceNow** to update tickets with work notes and set state to "In Progress"

### Configuration (.bedrock_agentcore.yaml)

The `.bedrock_agentcore.yaml` file controls deployment behavior:

- `default_agent`: Specifies which agent to deploy by default
- `entrypoint`: Path to agent Python module (e.g., `src/agent/my_agent.py`)
- `platform`: Container platform architecture (`linux/arm64`)
- `aws.region`: Deployment region (currently `eu-central-1`)
- `aws.account`: AWS account ID for deployment
- `aws.ecr_auto_create`: Automatically creates ECR repository for container images
- `memory.mode`: Memory configuration (`STM_ONLY` for short-term memory only)
- `observability.enabled`: Enables CloudWatch logging and metrics

**When modifying**: Update AWS account ID and region to match your environment before deployment.

### Container Structure (Dockerfile)

Multi-stage Dockerfile using `uv` package manager:

1. **Base**: Uses Astral's uv Python 3.12 slim image
2. **Dependencies**: Installs from `requirements.txt` using uv
3. **Telemetry**: Adds AWS OpenTelemetry instrumentation
4. **Security**: Runs as non-root user `bedrock_agentcore` (uid 1000)
5. **Entry point**: Uses OpenTelemetry auto-instrumentation wrapper

**Exposed ports**: 8000 (HTTP server), 8080, 9000 (telemetry)

### ServiceNow Integration (src/servicenow/)

**Complete webhook-based ServiceNow integration**:

- `config.py` - Configuration management for ServiceNow credentials
  - Loads from environment variables or AWS Secrets Manager
  - Supports basic auth (username/password) or OAuth token
  - Provides URL builders for ServiceNow API endpoints

- `client.py` - ServiceNow REST API client
  - `ServiceNowClient` class with methods for ticket operations
  - `get_incident()` - Fetch incident by number
  - `update_incident()` - Update incident with arbitrary fields
  - `add_work_notes()` - Add work notes and optionally change state
  - `resolve_incident()` - Mark incident as resolved
  - Context manager support for automatic session cleanup

- `webhook_handler.py` - AWS Lambda function for webhook endpoint
  - Receives POST requests from ServiceNow via API Gateway
  - Parses ticket payload (handles various ServiceNow webhook formats)
  - Invokes agent with formatted prompt containing ticket data
  - Returns HTTP 200 with agent analysis result
  - Error handling with appropriate HTTP status codes

### Infrastructure (infrastructure/cdk/)

**AWS CDK stack for webhook infrastructure**:

- `bin/app.ts` - CDK application entry point
- `lib/servicenow-webhook-stack.ts` - Main infrastructure stack
  - **API Gateway**: REST API with `/webhook/servicenow` endpoint
  - **Lambda**: Python function running webhook_handler
  - **Secrets Manager**: Stores ServiceNow credentials
  - **IAM Roles**: Lambda execution role with Bedrock and Secrets Manager permissions
  - **CloudWatch**: Log groups for API Gateway and Lambda

**Deployment outputs**:
- `WebhookURL` - URL to configure in ServiceNow Business Rule
- `LambdaFunctionName` - Name of webhook handler function
- `SecretArn` - ARN of ServiceNow credentials secret

### Directory Structure

```
src/
├── agent/          # Agent implementations
│   └── my_agent.py # Main agent with webhook-aware tools
├── tools/          # Custom tools (ready for extensions)
├── servicenow/     # ServiceNow integration (complete)
│   ├── config.py   # Configuration management
│   ├── client.py   # REST API client
│   └── webhook_handler.py  # Lambda webhook handler
└── utils/          # Shared utilities

tests/              # Unit and integration tests (ready for tests)

scripts/            # Utility scripts
├── navigate.py     # Branch navigation helper
└── test_webhook.sh # Webhook testing script

docs/
├── fr/             # French tutorial articles
├── en/             # English tutorial articles
└── WEBHOOK_SETUP.md # ServiceNow webhook configuration guide

infrastructure/
└── cdk/            # AWS CDK infrastructure
    ├── bin/app.ts
    ├── lib/servicenow-webhook-stack.ts
    ├── package.json
    ├── tsconfig.json
    └── cdk.json
```

## Tutorial Series Structure

The repository is organized around **5 progressive tutorial steps**, each on a separate Git branch:

| Step | Branch | Topic | Status |
|------|--------|-------|--------|
| 1 | `main` (or `step-01-runtime-deployment`) | AWS AgentRuntime Deployment | ✅ Complete |
| 2 | `step-02-gateway-ticketing` | Gateway & ServiceNow Integration | 🚧 Planned |
| 3 | `step-03-knowledge-base` | Knowledge Base & RAG | 🚧 Planned |
| 4 | `step-04-observability` | Observability & Monitoring | 🚧 Planned |
| 5 | `step-05-identity` | Identity & Authorization | 🚧 Planned |

**Important**: When making changes, ensure they are appropriate for the current tutorial step. Step 1 uses simulated external services - real integrations come in later steps.

## Key Dependencies

From `requirements.txt`:

- `strands-agents` - Core agent framework with tool calling
- `strands-agents-tools` - Pre-built tools (calculator, current_time, etc.)
- `bedrock-agentcore` - AWS Bedrock AgentCore runtime and SDK
- `bedrock-agentcore-starter-toolkit` - Starter toolkit and utilities

These are AWS-specific packages for building agents with Amazon Bedrock.

## Testing Strategy

**Current state**: Tests directory is empty (step 1 focuses on basic deployment)

**For future work**:
- Add unit tests for individual tools in `tests/test_tools.py`
- Add integration tests for agent responses in `tests/test_agent.py`
- Use pytest as the test runner
- Mock external services (ServiceNow, AWS services) using unittest.mock or pytest-mock

## Development Workflow

1. **Make changes** to agent code in `src/agent/my_agent.py`
2. **Test locally** using Docker or direct Python execution
3. **Deploy to AWS** using `bedrock-agentcore deploy my_agent`
4. **Invoke and test** using `bedrock-agentcore invoke my_agent`
5. **Check logs** with `bedrock-agentcore logs my_agent` if issues occur

## Important Notes

- This is a **bilingual tutorial project** (French/English) - both language versions of articles should be maintained
- The agent now uses **real ServiceNow API integration** - credentials must be configured in AWS Secrets Manager
- **Knowledge base is still simulated** - will be replaced with AWS Bedrock Knowledge Bases in step 3
- **AWS region** is set to `eu-central-1` - update in `.bedrock_agentcore.yaml` and CDK if deploying elsewhere
- The **navigation script** (`scripts/navigate.py`) is essential for users moving between tutorial steps
- **Documentation is excluded** from Docker builds via `.dockerignore` to reduce image size
- The project uses **Amazon Nova Lite** model - ensure Bedrock access is enabled in your AWS account for this model
- **ServiceNow webhook** requires outbound HTTPS connectivity from ServiceNow instance to AWS API Gateway

## ServiceNow Configuration

### Required Environment Variables

When running locally or in Lambda, set these environment variables:

```bash
SERVICENOW_INSTANCE_URL=https://YOUR_INSTANCE.service-now.com
SERVICENOW_USERNAME=your_username
SERVICENOW_PASSWORD=your_password
# OR use OAuth:
# SERVICENOW_OAUTH_TOKEN=your_oauth_token
```

**For AWS deployment**, credentials are stored in Secrets Manager (secret: `servicenow/credentials`).

### ServiceNow Webhook Setup

See `docs/WEBHOOK_SETUP.md` for complete instructions on:
1. Deploying AWS infrastructure (API Gateway + Lambda)
2. Configuring ServiceNow Business Rules to trigger webhook
3. Creating REST Message in ServiceNow
4. Testing the integration
5. Troubleshooting common issues

## Agent Runtime Details

The agent uses **BedrockAgentCoreApp** which:
- Provides an HTTP server listening on port 8000 (configurable via DOCKER_CONTAINER env var)
- Expects POST requests to `/invoke` endpoint with JSON payload containing a "prompt" field
- Returns agent responses as plain text (extracted from the first content block)
- Automatically handles AWS integration, logging, and telemetry when deployed
- Supports local testing without AWS credentials when run via `app.run()`

**Invocation flow**:
1. HTTP POST to `/invoke` with `{"prompt": "user message"}`
2. `invoke(payload)` extracts the prompt
3. Agent processes with system prompt and available tools
4. Tools are called as needed by the LLM
5. Final response text is returned to caller
