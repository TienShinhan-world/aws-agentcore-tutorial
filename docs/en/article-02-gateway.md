# Article 2: Expose Your Agent via REST API with AWS AgentCore

> **Series: Backoffice Support Agent with AWS AgentCore**
> **Step 2** | [Version française](../fr/article-02-gateway.md)

## Table of Contents

1. [Introduction](#introduction)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Direct Agent Invocation](#direct-agent-invocation)
5. [Webhook Infrastructure with CDK](#webhook-infrastructure-with-cdk)
6. [Infrastructure Deployment](#infrastructure-deployment)
7. [Post-Deployment Configuration](#post-deployment-configuration)
8. [Testing and Validation](#testing-and-validation)
9. [Troubleshooting](#troubleshooting)
10. [Next Steps](#next-steps)

---

## Introduction

In [Article 1](article-01-runtime.md), we deployed our support agent with AWS AgentCore Runtime. The agent works and can be invoked via the `agentcore invoke` CLI.

But how do we allow external systems (like ServiceNow) to call our agent? That's what we'll solve in this article.

### What You Will Build

In this article, we will:
- ✅ Understand how to invoke the agent via the AWS `bedrock-agentcore` API
- ✅ Deploy a complete webhook infrastructure with AWS CDK
- ✅ Create a secure REST API with API Gateway
- ✅ Configure a Lambda that bridges the API and the agent
- ✅ Test everything with curl

### Estimated Time
⏱️ **30-45 minutes** to complete this tutorial.

---

## Architecture

### Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│  HTTP Client    │────▶│  API Gateway    │────▶│     Lambda      │────▶│  AgentCore      │
│  (curl, app)    │     │  + API Key      │     │  (handler.py)   │     │  Runtime        │
│                 │◀────│                 │◀────│                 │◀────│                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                              │                        │
                              │                        │
                              ▼                        ▼
                        CloudWatch              Secrets Manager
                          Logs                  (credentials)
```

### Why This Architecture?

1. **API Gateway**: Secure entry point with API Key authentication, throttling, and logging
2. **Lambda**: Transformation logic between HTTP request format and AgentCore expected format
3. **AgentCore Runtime**: Our agent deployed in Article 1
4. **Secrets Manager**: Secure credential storage (used in Article 3)

### Data Flow

1. A client sends a POST request to `/webhook/servicenow` with ticket data
2. API Gateway validates the API Key and forwards to Lambda
3. Lambda parses the payload, builds the prompt, and calls AgentCore
4. AgentCore executes the agent which analyzes the ticket
5. The response flows back to the client

---

## Prerequisites

### From Article 1

- ✅ Agent deployed with `agentcore launch`
- ✅ Agent ARN available in `.bedrock_agentcore.yaml`

### New Prerequisites

1. **Node.js and npm** (for AWS CDK)
   ```bash
   node --version  # v18.x or higher recommended
   npm --version
   ```

2. **AWS CDK CLI**
   ```bash
   npm install -g aws-cdk
   cdk --version
   ```

3. **Docker** (for Lambda build)
   ```bash
   docker --version
   ```

---

## Direct Agent Invocation

Before building the infrastructure, let's understand how to invoke the agent programmatically.

### The `bedrock-agentcore` Client

AWS provides a specific boto3 client for AgentCore:

```python
import boto3
import json

# Create the bedrock-agentcore client
client = boto3.client('bedrock-agentcore', region_name='eu-central-1')

# Prepare the payload
payload = json.dumps({
    "prompt": "Analyze this ticket: INC0001234 - VPN connection issues"
})

# Invoke the agent
response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:eu-central-1:ACCOUNT_ID:runtime/AGENT_ID',
    runtimeSessionId='unique-session-id-minimum-33-characters',
    payload=payload,
    qualifier="DEFAULT"
)

# Read the response
response_body = response['response'].read()
response_data = json.loads(response_body)
print("Agent Response:", response_data)
```

### Important Parameters

| Parameter | Description | Constraints |
|-----------|-------------|-------------|
| `agentRuntimeArn` | Full ARN of the deployed agent | Format: `arn:aws:bedrock-agentcore:REGION:ACCOUNT:runtime/AGENT_ID` |
| `runtimeSessionId` | Unique session identifier | **Minimum 33 characters** |
| `payload` | Data to send to the agent | Stringified JSON with `prompt` key |
| `qualifier` | Agent version | `DEFAULT` for active version |

### Retrieve Your Agent ARN

The ARN is found in the `.bedrock_agentcore.yaml` file generated during deployment:

```bash
grep "agent_arn" .bedrock_agentcore.yaml
```

Example output:
```
agent_arn: arn:aws:bedrock-agentcore:eu-central-1:653783183133:runtime/agent_level_one_triage-9rGFpG5ZFx
```

---

## Webhook Infrastructure with CDK

Now, let's create the infrastructure that will expose our agent via a REST API.

### CDK Project Structure

```
infrastructure/
└── cdk/
    ├── bin/
    │   └── app.ts              # CDK entry point
    ├── lib/
    │   └── servicenow-webhook-stack.ts  # Stack definition
    ├── package.json
    ├── tsconfig.json
    └── cdk.json
```

### The CDK Stack

Here are the main components of our stack (`lib/servicenow-webhook-stack.ts`):

#### 1. IAM Role for Lambda

```typescript
const lambdaRole = new iam.Role(this, 'WebhookLambdaRole', {
  assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
  managedPolicies: [
    iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
  ],
});

// Permission to invoke AgentCore
lambdaRole.addToPolicy(
  new iam.PolicyStatement({
    effect: iam.Effect.ALLOW,
    actions: ['bedrock-agentcore:InvokeAgentRuntime'],
    resources: ['arn:aws:bedrock-agentcore:eu-central-1:ACCOUNT_ID:runtime/*'],
  })
);
```

**Important:** The `bedrock-agentcore:InvokeAgentRuntime` permission is specific to AgentCore. Don't confuse it with `bedrock:InvokeAgent` which is for classic Bedrock Agents.

#### 2. Lambda Function

```typescript
const webhookHandler = new lambda.Function(this, 'WebhookHandler', {
  runtime: lambda.Runtime.PYTHON_3_12,
  handler: 'handler.lambda_handler',
  code: lambda.Code.fromAsset(path.join(__dirname, '../../../src/webhook')),
  role: lambdaRole,
  timeout: cdk.Duration.seconds(300),  // 5 minutes to give the agent time
  memorySize: 512,
  environment: {
    LOG_LEVEL: 'INFO',
  },
});
```

#### 3. API Gateway with API Key

```typescript
const api = new apigateway.RestApi(this, 'ServiceNowWebhookApi', {
  restApiName: 'ServiceNow Webhook API',
  deployOptions: {
    stageName: 'prod',
    loggingLevel: apigateway.MethodLoggingLevel.INFO,
  },
});

// API Key to secure access
const apiKey = new apigateway.ApiKey(this, 'ServiceNowApiKey', {
  apiKeyName: 'servicenow-webhook-api-key',
  enabled: true,
});

// POST route /webhook/servicenow
const webhookResource = api.root.addResource('webhook');
const servicenowResource = webhookResource.addResource('servicenow');
servicenowResource.addMethod('POST', new apigateway.LambdaIntegration(webhookHandler), {
  apiKeyRequired: true,
});
```

### The Lambda Handler

The `src/webhook/handler.py` file bridges the API and AgentCore:

```python
import boto3
import json
import os
import uuid

# AgentCore client
bedrock_agentcore = boto3.client("bedrock-agentcore", region_name="eu-central-1")
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN")

def generate_session_id(incident_number: str) -> str:
    """Generate a session ID of 33+ characters"""
    base = f"servicenow-{incident_number}-{uuid.uuid4().hex}"
    return base[:50]

def lambda_handler(event, context):
    # Parse request body
    body = json.loads(event.get("body", "{}"))

    # Extract ticket data
    incident_number = body.get("number", "UNKNOWN")

    # Build the prompt
    prompt = f"""Analyze the following ServiceNow incident:
    Ticket Number: {incident_number}
    Description: {body.get("description", "")}
    Priority: {body.get("priority", "")}
    """

    # Invoke the agent
    response = bedrock_agentcore.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=generate_session_id(incident_number),
        payload=json.dumps({"prompt": prompt}),
        qualifier="DEFAULT"
    )

    # Return the response
    response_body = response["response"].read()
    return {
        "statusCode": 200,
        "body": json.dumps({
            "success": True,
            "analysis": json.loads(response_body)
        })
    }
```

---

## Infrastructure Deployment

### 1. Install CDK Dependencies

```bash
cd infrastructure/cdk
npm install
```

### 2. Bootstrap CDK (First Time Only)

```bash
npm run cdk bootstrap
```

This command creates the necessary CDK resources in your AWS account.

### 3. Deploy the Stack

```bash
npm run cdk deploy
```

Deployment takes about 2-3 minutes. At the end, you'll see the outputs:

```
Outputs:
ServiceNowWebhookStack.WebhookURL = https://xxxxxx.execute-api.eu-central-1.amazonaws.com/prod/webhook/servicenow
ServiceNowWebhookStack.ApiKeyId = xxxxxxxxxx
ServiceNowWebhookStack.LambdaFunctionName = ServiceNowWebhookStack-WebhookHandler-xxxxx
ServiceNowWebhookStack.GetApiKeyCommand = aws apigateway get-api-key --api-key xxxxxxxxxx --include-value --query 'value' --output text
```

### 4. Retrieve the API Key

```bash
aws apigateway get-api-key --api-key <API_KEY_ID> --include-value --query 'value' --output text
```

Note this value, you'll need it for testing.

---

## Post-Deployment Configuration

### Configure the Agent ARN

The Lambda needs to know your agent's ARN. Configure the environment variable:

```bash
aws lambda update-function-configuration \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --environment "Variables={AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-central-1:ACCOUNT_ID:runtime/AGENT_ID,LOG_LEVEL=INFO}"
```

**Replace:**
- `<LAMBDA_FUNCTION_NAME>`: The Lambda function name (see CDK output)
- `ACCOUNT_ID`: Your AWS account ID
- `AGENT_ID`: Your agent ID (from `.bedrock_agentcore.yaml`)

### Verify the Configuration

```bash
aws lambda get-function-configuration \
  --function-name <LAMBDA_FUNCTION_NAME> \
  --query 'Environment.Variables'
```

---

## Testing and Validation

### Test with curl

```bash
curl --location 'https://YOUR_API_GATEWAY_URL/prod/webhook/servicenow' \
  --header 'x-api-key: YOUR_API_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "number": "INC0001234",
    "short_description": "Cannot access email",
    "description": "User cannot send or receive emails since this morning",
    "urgency": "2",
    "impact": "2",
    "priority": "2",
    "category": "Email",
    "assignment_group": "IT Support Level 1"
}'
```

### Expected Response

```json
{
  "success": true,
  "incident_number": "INC0001234",
  "analysis": "**Summary of the issue:**\nUser cannot send or receive emails since this morning...",
  "message": "Incident analyzed successfully"
}
```

### Check CloudWatch Logs

```bash
# Find the log group
aws logs describe-log-groups --log-group-name-prefix /aws/lambda/ServiceNowWebhookStack

# View latest logs
aws logs tail /aws/lambda/ServiceNowWebhookStack-WebhookHandler-xxxxx --follow
```

---

## Troubleshooting

### Error: "not authorized to perform bedrock-agentcore:InvokeAgentRuntime"

**Cause:** The Lambda IAM role doesn't have the permission.

**Solution:** Verify that the CDK stack includes:
```typescript
actions: ['bedrock-agentcore:InvokeAgentRuntime'],
```

And redeploy with `npm run cdk deploy`.

### Error: "AGENT_RUNTIME_ARN environment variable not set"

**Cause:** The environment variable is not configured.

**Solution:** Run the `aws lambda update-function-configuration` command from the Configuration section.

### Error: "runtimeSessionId must be at least 33 characters"

**Cause:** The session ID is too short.

**Solution:** The handler automatically generates a 50-character ID. If testing manually, ensure you use a long enough ID.

### Error: "Response ended prematurely"

**Cause:** Connection issue with Bedrock (usually temporary).

**Solution:** Retry after a few seconds. If the problem persists, check:
- Agent region
- Bedrock quotas
- Bedrock service status

### Error 403 Forbidden

**Cause:** Missing or invalid API Key.

**Solution:** Verify that you include the `x-api-key` header with the correct value.

---

## Next Steps

Congratulations! 🎉 Your agent is now accessible via a secure REST API.

In the **next article (Article 3)**, we will:

🔜 **Connect ServiceNow to our API** via Business Rules and REST Messages
🔜 **Modify the agent to update ServiceNow** with real API calls
🔜 **Configure credentials** in AWS Secrets Manager
🔜 **Test the complete flow**: ticket creation → automatic analysis → update

**Git Branch:** `step-03-servicenow-integration`

---

## Resources

### Documentation
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/latest/guide/)
- [API Gateway Developer Guide](https://docs.aws.amazon.com/apigateway/latest/developerguide/)
- [Lambda Developer Guide](https://docs.aws.amazon.com/lambda/latest/dg/)

### Source Code
- [GitHub Repository](https://github.com/your-username/aws-agentcore-tutorial)
- Branch: `step-02-servicenow-integration`

---

**Author:** Anthony PINTO
**Date:** December 2025
**Series:** Backoffice Support Agent with AWS AgentCore (2/5)

*This article is part of a series on AWS AgentCore.*
