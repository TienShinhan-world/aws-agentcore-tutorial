# ServiceNow Webhook Infrastructure

AWS CDK infrastructure for ServiceNow webhook integration with AWS AgentCore.

## Architecture

```
ServiceNow → API Gateway → Lambda → Bedrock AgentCore → Response
```

## Prerequisites

- Node.js 18+ and npm
- AWS CLI configured with credentials
- AWS CDK CLI (`npm install -g aws-cdk`)
- Deployed AgentCore agent (from step-01)

## Installation

```bash
cd infrastructure/cdk
npm install
```

## Deployment

### 1. Bootstrap CDK (first time only)

```bash
npm run cdk:bootstrap
```

### 2. Deploy the stack

```bash
npm run cdk:deploy
```

This will create:
- API Gateway REST API with `/webhook/servicenow` endpoint
- Lambda function to handle webhook requests
- IAM roles with Bedrock permissions
- CloudWatch log groups

### 3. Configure AGENT_ID

After deployment, set your AgentCore agent ID:

```bash
aws lambda update-function-configuration \
  --function-name <lambda-function-name> \
  --environment Variables='{AGENT_ID=<your-agent-id>,AGENT_ALIAS_ID=TSTALIASID,LOG_LEVEL=INFO}'
```

Replace:
- `<lambda-function-name>` with the output from `LambdaFunctionName`
- `<your-agent-id>` with your deployed AgentCore agent ID

### 4. Get the webhook URL

The webhook URL will be in the stack outputs as `WebhookURL`. Use this URL in your ServiceNow Business Rule configuration.

## Development Commands

```bash
# Build TypeScript
npm run build

# Watch for changes
npm run watch

# Synthesize CloudFormation template
npm run cdk:synth

# Show stack diff
npm run cdk:diff

# Deploy stack
npm run cdk:deploy

# Destroy stack
npm run cdk:destroy
```

## Stack Outputs

After deployment, you'll get:

- **WebhookURL**: The URL to configure in ServiceNow
- **LambdaFunctionName**: Name of the webhook handler function
- **LambdaFunctionArn**: ARN of the Lambda function
- **ApiGatewayId**: API Gateway REST API ID

## Testing

See `../../scripts/test_webhook.sh` for testing the deployed webhook.

## Customization

Edit `lib/servicenow-webhook-stack.ts` to:
- Adjust Lambda timeout or memory
- Add API key authentication
- Configure custom domains
- Add additional endpoints
- Modify IAM permissions

## Cleanup

To remove all resources:

```bash
npm run cdk:destroy
```
