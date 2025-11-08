# Step 02: ServiceNow Integration (Webhook Receiver)

This branch implements a **webhook-based integration** between ServiceNow and AWS AgentCore.

## Architecture

```
ServiceNow Incident (New/Updated)
           ↓
ServiceNow Business Rule (triggers)
           ↓
POST Request → AWS API Gateway
           ↓
AWS Lambda (webhook_handler.py)
           ↓
AWS Bedrock AgentCore Agent
           ↓
HTTP Response (Agent Analysis)
```

**Note**: This is a **one-way integration**. ServiceNow sends incident data to AWS, and the agent analyzes it. The agent does **not** write back to ServiceNow in this step.

## What's Included

### Infrastructure (`infrastructure/cdk/`)
- **API Gateway**: REST API with `/webhook/servicenow` endpoint
- **Lambda Function**: Webhook handler that receives ServiceNow payloads
- **IAM Roles**: Permissions for Lambda to invoke Bedrock AgentCore
- **CloudWatch Logs**: Logging for debugging and monitoring

### Code (`src/webhook/`)
- **handler.py**: Lambda function that:
  - Parses ServiceNow incident payloads
  - Builds prompts for the agent
  - Invokes the AgentCore agent via Bedrock
  - Returns agent's analysis in HTTP response

### Tests (`tests/`)
- **test_webhook_handler.py**: Comprehensive unit tests (~15 tests)
- **pytest.ini**: PyTest configuration with coverage
- **requirements.txt**: Test dependencies

### Scripts (`scripts/`)
- **test_webhook.sh**: Bash script to test the webhook (local or deployed)

### Documentation (`docs/`)
- **WEBHOOK_SETUP.md**: Complete guide for:
  - Deploying AWS infrastructure
  - Configuring ServiceNow Business Rules
  - Testing the integration
  - Troubleshooting

## Quick Start

### 1. Prerequisites

- AWS AgentCore agent deployed (from step-01)
- AWS CLI configured
- Node.js 18+ and npm
- AWS CDK installed (`npm install -g aws-cdk`)

### 2. Deploy Infrastructure

```bash
# Install CDK dependencies
cd infrastructure/cdk
npm install

# Bootstrap CDK (first time only)
npm run cdk:bootstrap

# Deploy the stack
npm run cdk:deploy
```

**Note the outputs**:
- `WebhookURL`: The API Gateway endpoint URL
- `LambdaFunctionName`: Name of the Lambda function

### 3. Configure Agent ID

Set your AgentCore agent ID in the Lambda environment variables:

```bash
aws lambda update-function-configuration \
  --function-name <lambda-function-name> \
  --environment Variables='{
    "AGENT_ID":"<your-agent-id>",
    "AGENT_ALIAS_ID":"TSTALIASID",
    "LOG_LEVEL":"INFO"
  }'
```

### 4. Test the Webhook

```bash
# Test with sample incident data
./scripts/test_webhook.sh --url <webhook-url>
```

Expected output:
```
✓ Webhook responded successfully
✓ Agent analysis completed
Incident: INC0001234
```

### 5. Configure ServiceNow

See [docs/WEBHOOK_SETUP.md](docs/WEBHOOK_SETUP.md) for complete instructions on:
- Creating a ServiceNow Business Rule
- Configuring the webhook endpoint
- Testing the integration end-to-end

## Testing

### Run Unit Tests

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run tests with coverage
pytest tests/test_webhook_handler.py -v --cov=src/webhook
```

### Test Locally

```bash
# Set environment variables
export AGENT_ID="your-agent-id"
export AGENT_ALIAS_ID="TSTALIASID"

# Test the handler locally
./scripts/test_webhook.sh --local
```

### Test Deployed Webhook

```bash
./scripts/test_webhook.sh --url https://xxxxx.execute-api.eu-central-1.amazonaws.com/prod/webhook/servicenow
```

## ServiceNow Configuration

### Business Rule Script

Create a Business Rule in ServiceNow with:

**When to run:**
- Table: `Incident [incident]`
- When: `after`
- Insert: ✓

**Filter Conditions:**
```
Assignment group | is | IT Support Level 1
AND
State | is | New
```

**Script:**
```javascript
(function executeRule(current, previous) {
    try {
        var payload = {
            number: current.getValue('number'),
            short_description: current.getValue('short_description'),
            description: current.getValue('description'),
            urgency: current.getValue('urgency'),
            impact: current.getValue('impact'),
            priority: current.getValue('priority'),
            state: current.getValue('state'),
            assigned_to: current.getDisplayValue('assigned_to'),
            assignment_group: current.getDisplayValue('assignment_group'),
            category: current.getValue('category'),
            subcategory: current.getValue('subcategory'),
            caller_id: current.getDisplayValue('caller_id')
        };

        var request = new sn_ws.RESTMessageV2();
        request.setEndpoint('YOUR_WEBHOOK_URL');
        request.setHttpMethod('POST');
        request.setRequestHeader('Content-Type', 'application/json');
        request.setRequestBody(JSON.stringify(payload));

        var response = request.execute();
        var httpStatus = response.getStatusCode();

        gs.info('AgentCore webhook response: HTTP ' + httpStatus);

    } catch (e) {
        gs.error('AgentCore webhook error: ' + e.message);
    }
})(current, previous);
```

## What's Different from step-02-gateway-servicenow?

This branch (`step-02-servicenow-integration`) is a **simplified version** compared to the existing `step-02-gateway-servicenow` branch:

| Feature | step-02-servicenow-integration (this branch) | step-02-gateway-servicenow |
|---------|---------------------------------------------|----------------------------|
| **Webhook receiver** | ✅ Yes | ✅ Yes |
| **ServiceNow API client** | ❌ No | ✅ Yes |
| **Write back to ServiceNow** | ❌ No | ✅ Yes |
| **Secrets Manager** | ❌ Not needed | ✅ Yes (for credentials) |
| **Test suite** | ~15 tests | ~81 tests |
| **Complexity** | Simple | Complete |

**Use this branch if:**
- You want to start simple (receive-only)
- You don't need bi-directional integration yet
- You're learning the basics of webhook integration

**Use step-02-gateway-servicenow if:**
- You need complete integration
- You want the agent to update ServiceNow tickets
- You need production-ready code with comprehensive tests

## Troubleshooting

### Webhook not triggered
- Check ServiceNow Business Rule is active
- Verify filter conditions match your test incident
- Check ServiceNow System Logs

### HTTP 400 errors
- Verify JSON payload structure
- Check Lambda CloudWatch logs for parsing errors

### HTTP 500 errors
- Check `AGENT_ID` environment variable is set
- Verify Lambda has permissions to invoke Bedrock
- Check CloudWatch logs for detailed error messages

### Agent not responding
- Test agent directly: `bedrock-agentcore invoke <agent-name> --prompt "Test"`
- Verify agent ID is correct
- Check IAM permissions on Lambda role

## Next Steps

### Option 1: Add ServiceNow Write-Back (Future Step)
Add capability for agent to update ServiceNow tickets:
- Add ServiceNow REST API client
- Store credentials in Secrets Manager
- Modify handler to call ServiceNow API after agent analysis

### Option 2: Switch to Full Implementation
Checkout the complete implementation:
```bash
git checkout step-02-gateway-servicenow
```

### Option 3: Continue to Step 3
Add Knowledge Base integration:
```bash
git checkout step-03-knowledge-base
```

## Resources

- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS Bedrock Agent Runtime](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent-runtime_InvokeAgent.html)
- [ServiceNow Business Rules](https://docs.servicenow.com/bundle/latest/page/script/business-rules/concept/c_BusinessRules.html)
- [Complete Setup Guide](docs/WEBHOOK_SETUP.md)

## Cleanup

To remove all AWS resources:

```bash
cd infrastructure/cdk
npm run cdk:destroy
```

This will delete:
- API Gateway
- Lambda function
- IAM roles
- CloudWatch log groups
