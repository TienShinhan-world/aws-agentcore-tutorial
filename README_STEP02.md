# Step 2: Gateway & ServiceNow Integration

> **Tutorial Series:** ServiceNow Backoffice Support Agent with AWS AgentCore
> **Part 2 of 5** | [Article FR](docs/fr/article-02-gateway.md) | [Article EN](docs/en/article-02-gateway.md)

## What You'll Build

In this step, you'll implement the complete webhook-based ServiceNow integration:

- ✅ Deploy API Gateway + Lambda webhook infrastructure
- ✅ Implement real ServiceNow REST API client
- ✅ Configure ServiceNow Business Rules to trigger webhooks
- ✅ Create end-to-end ticket flow with real updates

**Architecture:**
```
ServiceNow (new ticket created)
    ↓ Triggers Business Rule
    ↓ HTTP POST with complete ticket data
API Gateway (/webhook/servicenow)
    ↓ Invokes
Lambda Function (webhook_handler)
    ↓ Calls
Agent (parse + analyze + update)
    ↓ Updates
ServiceNow API (add work notes, set In Progress)
```

## Prerequisites

- Completed Step 1 (or checkout `step-01-runtime-deployment` branch)
- ServiceNow instance (developer instance or production)
- ServiceNow credentials (username/password or OAuth token)
- AWS CDK installed (`npm install -g aws-cdk`)
- Node.js 18+ installed

## Quick Start

### 1. Setup ServiceNow Credentials

```bash
# Store credentials in AWS Secrets Manager
aws secretsmanager create-secret \
  --name servicenow/credentials \
  --secret-string '{
    "instance_url": "https://YOUR_INSTANCE.service-now.com",
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }'
```

### 2. Deploy Webhook Infrastructure

```bash
# Install CDK dependencies
cd infrastructure/cdk
npm install

# Bootstrap CDK (first time only)
npm run cdk bootstrap

# Deploy the stack
npm run cdk deploy

# Save the WebhookURL from outputs
```

### 3. Configure ServiceNow Business Rule

See [Webhook Setup Guide](docs/WEBHOOK_SETUP.md) for detailed instructions on:
- Creating a Business Rule in ServiceNow
- Configuring REST Message to call the webhook
- Testing the integration

### 4. Test the Integration

```bash
# Test locally with simulated webhook payload
./scripts/test_webhook.sh --local

# Test deployed webhook
./scripts/test_webhook.sh --url https://YOUR_API_GATEWAY_URL/webhook/servicenow

# Test with custom ticket data
./scripts/test_webhook.sh --ticket test_data/sample_ticket.json
```

## New Components in Step 2

### ServiceNow Client (`src/servicenow/client.py`)

Real ServiceNow REST API client with methods:
- `get_incident(ticket_number)` - Fetch incident details
- `update_incident(ticket_number, fields)` - Update any incident fields
- `add_work_notes(ticket_number, notes, set_in_progress)` - Add notes and change state
- `resolve_incident(ticket_number, resolution)` - Mark incident as resolved

### Webhook Handler (`src/servicenow/webhook_handler.py`)

AWS Lambda function that:
- Receives POST requests from ServiceNow
- Validates and parses ticket payload
- Invokes the agent with formatted prompt
- Returns analysis result to ServiceNow

### Infrastructure Stack (`infrastructure/cdk/lib/servicenow-webhook-stack.ts`)

AWS CDK stack deploying:
- **API Gateway:** REST API with `/webhook/servicenow` endpoint
- **Lambda:** Python function running webhook_handler
- **Secrets Manager:** ServiceNow credentials storage
- **IAM Roles:** Permissions for Bedrock and Secrets Manager
- **CloudWatch:** Logging for debugging

## Updated Agent

The agent (`src/agent/my_agent.py`) now:
- Uses real ServiceNow client for ticket updates
- Handles ServiceNowError exceptions
- Logs all operations to CloudWatch
- Makes actual API calls to update tickets

## Environment Variables

### Local Testing

```bash
export SERVICENOW_INSTANCE_URL=https://YOUR_INSTANCE.service-now.com
export SERVICENOW_USERNAME=your_username
export SERVICENOW_PASSWORD=your_password
```

### AWS Deployment

Credentials are automatically loaded from AWS Secrets Manager (`servicenow/credentials`).

## Testing Scenarios

### Scenario 1: VPN Timeout Issue

```bash
# Create a ticket in ServiceNow with:
# Short description: "VPN connection timeout"
# Description: "User cannot connect to VPN from home network"

# The agent should:
# 1. Receive webhook from ServiceNow
# 2. Parse ticket data
# 3. Search KB → find KB0001
# 4. Update ticket with VPN troubleshooting steps
# 5. Set state to "In Progress"
```

### Scenario 2: Email Sync Issue

```bash
# Create a ticket in ServiceNow with:
# Short description: "Email sync issues on iPhone"
# Description: "User cannot sync email on iPhone 14"

# The agent should:
# 1. Receive webhook
# 2. Search KB → find KB0003
# 3. Update ticket with mobile email sync solutions
# 4. Add work notes to ServiceNow
```

## Monitoring & Debugging

### View Lambda Logs

```bash
# Get log group name from CDK outputs
aws logs tail /aws/lambda/ServiceNowWebhookHandler --follow

# Or use the AWS Console
# CloudWatch > Log Groups > /aws/lambda/ServiceNowWebhookHandler
```

### View Agent Logs

```bash
# Using AgentCore CLI
agentcore logs --follow

# Or via AWS Console
# CloudWatch > Log Groups > [agent-log-group]
```

### Test Webhook Locally

```bash
# Start webhook handler locally
python src/servicenow/webhook_handler.py

# In another terminal, send test request
curl -X POST http://localhost:8001/webhook \
  -H "Content-Type: application/json" \
  -d @test_data/sample_ticket.json
```

## Troubleshooting

### ServiceNow Authentication Failed

```bash
# Verify credentials
aws secretsmanager get-secret-value --secret-id servicenow/credentials

# Update credentials
aws secretsmanager update-secret \
  --secret-id servicenow/credentials \
  --secret-string '{"instance_url":"...","username":"...","password":"..."}'
```

### Webhook Not Triggered

1. Check ServiceNow Business Rule is active
2. Verify REST Message endpoint URL matches API Gateway URL
3. Check ServiceNow outbound HTTP logs
4. Verify API Gateway has public access

### Agent Can't Update Tickets

1. Check ServiceNow credentials have write permissions
2. Verify ticket number exists in ServiceNow
3. Check CloudWatch logs for detailed error messages
4. Ensure IAM role has `secretsmanager:GetSecretValue` permission

## Configuration Files

- **`infrastructure/cdk/lib/servicenow-webhook-stack.ts`** - CDK infrastructure
- **`src/servicenow/config.py`** - ServiceNow configuration management
- **`src/servicenow/client.py`** - ServiceNow REST API client
- **`src/servicenow/webhook_handler.py`** - Lambda webhook handler
- **`scripts/test_webhook.sh`** - Webhook testing script

## Cost Estimation

Step 2 introduces these AWS services:
- **API Gateway:** ~$3.50 per million requests
- **Lambda:** First 1M requests free, then $0.20 per 1M
- **Secrets Manager:** $0.40 per secret per month
- **CloudWatch Logs:** $0.50 per GB ingested

Estimated cost for testing: **< $5/month**

## Security Best Practices

1. **Credentials:** Never commit ServiceNow credentials to Git
2. **Secrets Manager:** Rotate credentials regularly
3. **API Gateway:** Consider adding API key authentication
4. **VPC:** For production, use VPC mode (Step 5)
5. **IAM:** Follow least privilege principle

## Next Steps

🔜 **Step 3:** [Knowledge Base & RAG](../step-03-knowledge-base/README_STEP03.md)

In the next step, we'll:
- Replace simulated KB with AWS Bedrock Knowledge Bases
- Implement semantic search with embeddings
- Add document ingestion pipeline
- Improve resolution quality with RAG

## Resources

- [ServiceNow REST API Documentation](https://developer.servicenow.com/dev.do#!/reference/api/latest/rest/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Webhook Setup Guide](docs/WEBHOOK_SETUP.md)

---

**Current Branch:** `step-02-gateway-servicenow`
**Status:** ✅ Ready for deployment with real ServiceNow integration
