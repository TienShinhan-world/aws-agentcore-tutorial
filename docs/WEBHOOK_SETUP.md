# ServiceNow Webhook Setup Guide

This guide explains how to configure ServiceNow to send incident webhooks to your AWS AgentCore agent via API Gateway and Lambda.

## Architecture Overview

```
ServiceNow Incident Created/Updated
           ↓
ServiceNow Business Rule (triggers on incident)
           ↓
AWS API Gateway (/webhook/servicenow)
           ↓
AWS Lambda (webhook handler)
           ↓
AWS Bedrock AgentCore Agent
           ↓
Response back to ServiceNow/API Gateway
```

## Prerequisites

1. **AWS Resources Deployed**:
   - AgentCore agent deployed (from step-01)
   - Webhook infrastructure deployed (CDK stack)
   - Webhook URL from CDK outputs

2. **ServiceNow Instance**:
   - ServiceNow instance with admin access
   - Outbound HTTPS connectivity to AWS
   - Ability to create Business Rules and REST Messages

3. **Tools**:
   - AWS CLI configured
   - Access to ServiceNow Studio or Script Editor

## Step 1: Deploy AWS Infrastructure

### 1.1 Deploy the CDK Stack

```bash
cd infrastructure/cdk
npm install
npm run cdk:bootstrap  # First time only
npm run cdk:deploy
```

### 1.2 Note the Webhook URL

After deployment, save the `WebhookURL` output:

```
Outputs:
ServiceNowWebhookStack.WebhookURL = https://xxxxx.execute-api.eu-central-1.amazonaws.com/prod/webhook/servicenow
```

### 1.3 Configure Agent ID

Set your AgentCore agent ID in the Lambda function:

```bash
aws lambda update-function-configuration \
  --function-name <lambda-function-name> \
  --environment Variables='{
    "AGENT_ID":"<your-agent-id>",
    "AGENT_ALIAS_ID":"TSTALIASID",
    "LOG_LEVEL":"INFO"
  }'
```

Replace:
- `<lambda-function-name>`: From CDK output `LambdaFunctionName`
- `<your-agent-id>`: Your deployed AgentCore agent ID (from step-01)

### 1.4 Test the Webhook

```bash
./scripts/test_webhook.sh --url <webhook-url>
```

If successful, you'll see:
```
✓ Webhook responded successfully
✓ Agent analysis completed
```

## Step 2: Configure ServiceNow

### 2.1 Create REST Message (Optional but Recommended)

While Business Rules can make direct HTTP calls, creating a REST Message makes configuration cleaner and reusable.

1. Navigate to **System Web Services > Outbound > REST Message**
2. Click **New**
3. Configure:
   - **Name**: `AWS AgentCore Webhook`
   - **Endpoint**: Your webhook URL
   - **Authentication**: None (or use API key if configured)
   - **HTTP Methods**: POST

4. Click **Submit**

### 2.2 Create Business Rule to Trigger Webhook

This Business Rule will trigger when incidents are created or updated in a specific assignment group.

1. Navigate to **System Definition > Business Rules**
2. Click **New**
3. Configure the Business Rule:

#### When to Run Tab

- **Name**: `Send to AWS AgentCore`
- **Table**: `Incident [incident]`
- **Active**: ✓ (checked)
- **Advanced**: ✓ (checked)

#### When Section

- **When**: `after`
- **Insert**: ✓ (checked)
- **Update**: ☐ (unchecked initially - enable later if needed)

#### Filter Conditions

Add conditions to control when the webhook fires:

```
Assignment group | is | IT Support Level 1
AND
State | is | New
```

This ensures only new incidents assigned to "IT Support Level 1" trigger the agent.

#### Advanced Tab

Paste this script:

```javascript
(function executeRule(current, previous /*null when async*/) {

    try {
        // Build incident payload
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
            caller_id: current.getDisplayValue('caller_id'),
            sys_created_on: current.getValue('sys_created_on'),
            sys_updated_on: current.getValue('sys_updated_on')
        };

        // Configure HTTP request
        var request = new sn_ws.RESTMessageV2();
        request.setEndpoint('https://YOUR_API_GATEWAY_URL/prod/webhook/servicenow');
        request.setHttpMethod('POST');
        request.setRequestHeader('Content-Type', 'application/json');
        request.setRequestBody(JSON.stringify(payload));

        // Send request asynchronously
        var response = request.execute();
        var responseBody = response.getBody();
        var httpStatus = response.getStatusCode();

        // Log response
        gs.info('AWS AgentCore webhook response (HTTP ' + httpStatus + '): ' + responseBody);

        // Optionally parse response and add work notes
        if (httpStatus == 200) {
            try {
                var result = JSON.parse(responseBody);
                if (result.success && result.analysis) {
                    // Add agent's analysis as work notes
                    current.work_notes = 'AWS AgentCore Analysis:\n' + result.analysis;
                    current.update();
                }
            } catch (e) {
                gs.warn('Failed to parse AgentCore response: ' + e.message);
            }
        }

    } catch (e) {
        gs.error('AWS AgentCore webhook error: ' + e.message);
    }

})(current, previous);
```

**Important**: Replace `YOUR_API_GATEWAY_URL` with your actual webhook URL.

4. Click **Submit**

### 2.3 Alternative: Using REST Message

If you created the REST Message in step 2.1, use this simplified script:

```javascript
(function executeRule(current, previous) {

    try {
        // Build payload
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

        // Use REST Message
        var rm = new sn_ws.RESTMessageV2('AWS AgentCore Webhook', 'POST');
        rm.setRequestBody(JSON.stringify(payload));

        var response = rm.execute();
        var responseBody = response.getBody();
        var httpStatus = response.getStatusCode();

        gs.info('AgentCore response (' + httpStatus + '): ' + responseBody);

        if (httpStatus == 200) {
            var result = JSON.parse(responseBody);
            if (result.success && result.analysis) {
                current.work_notes = 'AWS AgentCore Analysis:\n' + result.analysis;
                current.update();
            }
        }

    } catch (e) {
        gs.error('AgentCore webhook error: ' + e.message);
    }

})(current, previous);
```

## Step 3: Test the Integration

### 3.1 Create a Test Incident

1. In ServiceNow, navigate to **Incident > Create New**
2. Fill in:
   - **Caller**: Any user
   - **Short Description**: "Test AWS AgentCore integration"
   - **Description**: "User cannot access shared drive"
   - **Assignment Group**: `IT Support Level 1` (or the group in your filter)
   - **Category**: Network
   - **Urgency**: 2 - Medium
   - **Impact**: 2 - Medium

3. Click **Submit**

### 3.2 Verify Webhook Execution

**In ServiceNow:**

1. Check **System Logs > System Log > All**
2. Look for log entries from your Business Rule
3. Verify HTTP 200 response

**In AWS CloudWatch:**

1. Go to **CloudWatch > Log Groups**
2. Find `/aws/lambda/ServiceNowWebhookStack-WebhookHandler-xxx`
3. Check recent log streams for:
   - "Received ServiceNow webhook request"
   - "Processing incident: INC0001234"
   - "Successfully processed incident"

**Check the Incident:**

1. Refresh the incident in ServiceNow
2. Check **Work Notes** tab
3. You should see agent's analysis added automatically

### 3.3 Troubleshooting

#### Webhook Not Triggered

- Verify Business Rule is **Active**
- Check filter conditions match your test incident
- Check ServiceNow system logs for errors

#### HTTP 4xx Errors

- **400 Bad Request**: Invalid payload format
  - Check Business Rule script syntax
  - Verify JSON structure in logs

- **403 Forbidden**: API Gateway auth issue
  - Check if API key is required but not sent
  - Verify CORS settings if needed

#### HTTP 500 Errors

- **500 Internal Server Error**: Lambda execution error
  - Check CloudWatch logs for Python errors
  - Verify AGENT_ID environment variable is set
  - Check Bedrock agent exists and is accessible

#### Agent Not Responding

- Verify `AGENT_ID` is correct:
  ```bash
  aws lambda get-function-configuration \
    --function-name <lambda-name> \
    --query 'Environment.Variables'
  ```

- Test agent directly:
  ```bash
  bedrock-agentcore invoke <agent-name> --prompt "Test"
  ```

- Check Lambda IAM permissions:
  ```bash
  aws iam get-role-policy \
    --role-name ServiceNowWebhookStack-WebhookLambdaRole-xxx \
    --policy-name <policy-name>
  ```

## Step 4: Production Considerations

### 4.1 Security

**API Key Authentication:**

Modify CDK stack to require API keys:

```typescript
servicenowResource.addMethod('POST', lambdaIntegration, {
  apiKeyRequired: true,
});

const apiKey = api.addApiKey('ServiceNowApiKey');
const plan = api.addUsagePlan('ServiceNowUsagePlan', {
  apiStages: [{ stage: api.deploymentStage }],
});
plan.addApiKey(apiKey);
```

**IP Whitelisting:**

Add resource policy to API Gateway:

```typescript
const policy = new iam.PolicyDocument({
  statements: [
    new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      principals: [new iam.AnyPrincipal()],
      actions: ['execute-api:Invoke'],
      resources: ['execute-api:/*'],
      conditions: {
        IpAddress: {
          'aws:SourceIp': ['YOUR_SERVICENOW_IP/32'],
        },
      },
    }),
  ],
});
```

### 4.2 Monitoring

**CloudWatch Alarms:**

Create alarms for:
- Lambda errors
- Lambda throttling
- API Gateway 5xx errors
- High latency

**Dashboards:**

Create CloudWatch dashboard with:
- Request count
- Error rate
- Average latency
- Agent invocation success rate

### 4.3 Scaling

**Lambda Configuration:**

- Adjust timeout based on agent response time
- Increase memory if needed (affects CPU allocation)
- Configure reserved concurrency if needed

**API Gateway:**

- Enable caching if appropriate
- Configure throttling limits
- Set up usage plans per integration

## Step 5: Advanced Configuration

### 5.1 Selective Triggering

Modify Business Rule conditions to trigger only for specific scenarios:

```javascript
// Only trigger for high-priority incidents
Priority | is one of | 1 - Critical, 2 - High

// Only for specific categories
Category | is | Hardware
OR Category | is | Software

// Only during business hours
// Add script condition:
var now = new GlideDateTime();
var hour = now.getHourOfDayLocalTime();
answer = (hour >= 8 && hour < 18); // 8 AM to 6 PM
```

### 5.2 Bi-directional Integration

For future step-03, you can enable the agent to write back to ServiceNow by:

1. Storing ServiceNow credentials in AWS Secrets Manager
2. Modifying the Lambda to call ServiceNow API after agent analysis
3. Updating incident state, work notes, or assignment automatically

### 5.3 Session Management

The Lambda handler creates session IDs from incident numbers (`servicenow-INC0001234`). This ensures:

- Conversation continuity if incident is updated multiple times
- Agent remembers context from previous interactions
- Better multi-turn reasoning

## Appendix: Sample Payloads

### Minimal Payload

```json
{
  "number": "INC0001234",
  "short_description": "Cannot access email"
}
```

### Complete Payload

```json
{
  "number": "INC0001234",
  "short_description": "User cannot access shared drive",
  "description": "Detailed description of the issue...",
  "urgency": "2",
  "impact": "2",
  "priority": "2",
  "state": "1",
  "assigned_to": "John Doe",
  "assignment_group": "IT Support Level 1",
  "category": "Network",
  "subcategory": "File Share",
  "caller_id": "jane.smith@example.com",
  "sys_created_on": "2025-01-15 10:30:00",
  "sys_updated_on": "2025-01-15 10:30:00"
}
```

### Expected Response

```json
{
  "success": true,
  "incident_number": "INC0001234",
  "analysis": "Based on the incident description...",
  "message": "Incident analyzed successfully"
}
```

## Next Steps

- **Step 3**: Add Knowledge Base integration for better resolution suggestions
- **Step 4**: Add observability and monitoring
- **Step 5**: Add identity management and authorization

## Resources

- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [ServiceNow Business Rules](https://docs.servicenow.com/bundle/latest/page/script/business-rules/concept/c_BusinessRules.html)
- [ServiceNow REST API](https://docs.servicenow.com/bundle/latest/page/integrate/inbound-rest/concept/c_RESTAPI.html)
