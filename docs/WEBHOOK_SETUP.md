# ServiceNow Webhook Setup Guide

This guide explains how to configure ServiceNow to send webhook notifications to your AWS AgentCore agent when new tickets are created.

## Architecture Overview

```
ServiceNow (New Ticket Created)
    ↓
Business Rule Triggered
    ↓
REST Message (Webhook)
    ↓
AWS API Gateway
    ↓
AWS Lambda (webhook_handler)
    ↓
AgentCore Agent (Analysis)
    ↓
ServiceNow API (Update Ticket)
```

## Prerequisites

1. **AWS Infrastructure Deployed**
   - CDK stack deployed successfully
   - Webhook URL from CDK output
   - ServiceNow credentials stored in AWS Secrets Manager

2. **ServiceNow Access**
   - Admin or developer access to ServiceNow instance
   - Permissions to create Business Rules and REST Messages

3. **Network Configuration**
   - ServiceNow instance can reach AWS API Gateway (outbound HTTPS)
   - No firewall blocking outbound connections to AWS

## Part 1: Deploy AWS Infrastructure

### 1. Install CDK Dependencies

```bash
cd infrastructure/cdk
npm install
```

### 2. Configure AWS Credentials

Ensure your AWS credentials are configured:

```bash
aws configure
# OR
export AWS_PROFILE=your-profile
```

### 3. Bootstrap CDK (First Time Only)

```bash
npm run cdk bootstrap
```

### 4. Deploy the Stack

```bash
npm run cdk deploy
```

**Important**: Save the outputs from the deployment:
- `WebhookURL`: The URL to configure in ServiceNow
- `SecretArn`: ARN of the Secrets Manager secret for ServiceNow credentials
- `LambdaFunctionName`: Name of the Lambda function

### 5. Configure ServiceNow Credentials

Update the Secrets Manager secret with your actual ServiceNow credentials:

```bash
aws secretsmanager update-secret \
  --secret-id servicenow/credentials \
  --secret-string '{
    "instance_url": "https://YOUR_INSTANCE.service-now.com",
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }'
```

**Alternative: Using OAuth Token**

```bash
aws secretsmanager update-secret \
  --secret-id servicenow/credentials \
  --secret-string '{
    "instance_url": "https://YOUR_INSTANCE.service-now.com",
    "oauth_token": "YOUR_OAUTH_TOKEN"
  }'
```

## Part 2: Configure ServiceNow

### 1. Create REST Message

1. Navigate to **System Web Services → Outbound → REST Message**
2. Click **New**
3. Fill in the details:
   - **Name**: `AWS AgentCore Webhook`
   - **Endpoint**: `${WebhookURL}` (from CDK output)
   - **Authentication**: None (or configure API key if added)

4. Click **Submit**

### 2. Create HTTP Method

1. Open the REST Message you just created
2. In the **HTTP Methods** related list, click **New**
3. Fill in:
   - **Name**: `Send Ticket to Agent`
   - **HTTP Method**: `POST`
   - **Endpoint**: Use the parent endpoint (already configured)
   - **HTTP Headers**:
     - Name: `Content-Type`, Value: `application/json`

4. In the **Content** field, add the following template:

```javascript
{
  "record": {
    "number": "${number}",
    "sys_id": "${sys_id}",
    "short_description": "${short_description}",
    "description": "${description}",
    "priority": "${priority}",
    "state": "${state}",
    "caller_id": "${caller_id}",
    "assigned_to": "${assigned_to}",
    "sys_created_on": "${sys_created_on}",
    "category": "${category}",
    "subcategory": "${subcategory}"
  }
}
```

5. Click **Submit**

### 3. Create Business Rule

1. Navigate to **System Definition → Business Rules**
2. Click **New**
3. Fill in the **When to run** section:
   - **Name**: `Notify Agent on New Incident`
   - **Table**: `Incident [incident]`
   - **Active**: ✓ (checked)
   - **Advanced**: ✓ (checked)
   - **When**: `after`
   - **Insert**: ✓ (checked)
   - **Update**: □ (unchecked - only trigger on new tickets)
   - **Filter Conditions**: (Optional) Add conditions if you only want to trigger for specific priorities or categories

4. In the **Advanced** tab, add this script:

```javascript
(function executeRule(current, previous /*null when async*/) {

    try {
        // Log that we're sending webhook
        gs.info('Sending incident ' + current.number + ' to AWS AgentCore webhook');

        // Get the REST Message
        var r = new sn_ws.RESTMessageV2('AWS AgentCore Webhook', 'Send Ticket to Agent');

        // Set variable substitutions
        r.setStringParameterNoEscape('number', current.number);
        r.setStringParameterNoEscape('sys_id', current.sys_id);
        r.setStringParameterNoEscape('short_description', current.short_description);
        r.setStringParameterNoEscape('description', current.description);
        r.setStringParameterNoEscape('priority', current.priority);
        r.setStringParameterNoEscape('state', current.state);
        r.setStringParameterNoEscape('caller_id', current.caller_id.getDisplayValue());
        r.setStringParameterNoEscape('assigned_to', current.assigned_to.getDisplayValue());
        r.setStringParameterNoEscape('sys_created_on', current.sys_created_on);
        r.setStringParameterNoEscape('category', current.category);
        r.setStringParameterNoEscape('subcategory', current.subcategory);

        // Execute the REST call
        var response = r.execute();
        var httpStatus = response.getStatusCode();
        var responseBody = response.getBody();

        // Log the response
        gs.info('Webhook response status: ' + httpStatus);
        gs.debug('Webhook response body: ' + responseBody);

        if (httpStatus != 200) {
            gs.error('Failed to send incident to webhook. Status: ' + httpStatus + ', Response: ' + responseBody);
        }

    } catch (ex) {
        gs.error('Error sending webhook for incident ' + current.number + ': ' + ex.message);
    }

})(current, previous);
```

5. Click **Submit**

### 4. Test the Integration

1. Create a new test incident in ServiceNow
2. Check the **System Logs → System Log → All** for webhook execution logs
3. Verify in AWS CloudWatch Logs:
   - Lambda function logs: `/aws/lambda/ServiceNowWebhookHandler`
   - API Gateway logs: `/aws/apigateway/ServiceNow Webhook API`
4. Check that the incident was updated with agent analysis

## Part 3: Verify and Monitor

### Check Lambda Logs

```bash
# Get recent logs
aws logs tail /aws/lambda/$(aws cloudformation describe-stacks \
  --stack-name ServiceNowWebhookStack \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
  --output text) --follow
```

### Test Webhook Manually

```bash
# Get webhook URL from CDK output
WEBHOOK_URL=$(aws cloudformation describe-stacks \
  --stack-name ServiceNowWebhookStack \
  --query 'Stacks[0].Outputs[?OutputKey==`WebhookURL`].OutputValue' \
  --output text)

# Send test request
curl -X POST $WEBHOOK_URL \
  -H "Content-Type: application/json" \
  -d '{
    "record": {
      "number": "INC0001234",
      "sys_id": "test123",
      "short_description": "Test ticket",
      "description": "This is a test ticket to verify webhook integration",
      "priority": "3",
      "state": "1",
      "caller_id": "test.user@example.com",
      "assigned_to": "Support Team",
      "sys_created_on": "2025-10-31 10:00:00",
      "category": "Software",
      "subcategory": "Email"
    }
  }'
```

### Monitor API Gateway

```bash
# View API Gateway metrics in CloudWatch
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApiGateway \
  --metric-name Count \
  --dimensions Name=ApiName,Value="ServiceNow Webhook API" \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum
```

## Troubleshooting

### Webhook Not Triggering

1. **Check Business Rule**
   - Verify it's set to **Active**
   - Check filter conditions aren't too restrictive
   - Review System Logs for errors

2. **Check REST Message Configuration**
   - Verify endpoint URL is correct
   - Test REST Message manually in ServiceNow
   - Check authentication settings

### Lambda Errors

1. **Check CloudWatch Logs**
   ```bash
   aws logs tail /aws/lambda/ServiceNowWebhookHandler --follow
   ```

2. **Common Issues**
   - ServiceNow credentials not configured correctly
   - Network timeout (increase Lambda timeout)
   - Missing IAM permissions

### ServiceNow Update Failures

1. **Verify Credentials**
   ```bash
   # Test ServiceNow API access
   curl -u USERNAME:PASSWORD \
     https://YOUR_INSTANCE.service-now.com/api/now/table/incident?sysparm_limit=1
   ```

2. **Check Secret Configuration**
   ```bash
   aws secretsmanager get-secret-value \
     --secret-id servicenow/credentials \
     --query SecretString \
     --output text
   ```

### Network Issues

1. **API Gateway Timeout**
   - Check if ServiceNow can reach AWS endpoint
   - Verify no firewall rules blocking outbound HTTPS
   - Check VPC configuration if using private API

2. **ServiceNow API Timeout**
   - Increase Lambda timeout
   - Check ServiceNow instance availability
   - Verify network connectivity from Lambda to ServiceNow

## Security Considerations

### Current Setup (Development)

- No authentication on webhook endpoint
- Credentials stored in Secrets Manager
- CloudWatch logging enabled

### Production Recommendations

1. **Add API Key Authentication**
   - Configure API Gateway API key
   - Add X-API-Key header validation
   - Update ServiceNow REST Message with API key

2. **Enable AWS WAF**
   - Rate limiting
   - IP allowlisting for ServiceNow IPs
   - Block malicious requests

3. **Use VPC Endpoints**
   - Deploy Lambda in VPC
   - Use VPC endpoints for AWS services
   - Restrict internet access

4. **Rotate Credentials**
   - Set up automatic credential rotation in Secrets Manager
   - Use temporary credentials where possible
   - Implement least-privilege IAM policies

5. **Enable Encryption**
   - Encrypt Secrets Manager secrets with KMS
   - Enable encryption at rest for CloudWatch Logs
   - Use HTTPS only

## Next Steps

1. **Add Authentication**: Implement API key or AWS IAM authentication
2. **Set Up Monitoring**: Create CloudWatch dashboards and alarms
3. **Implement Retry Logic**: Handle transient failures gracefully
4. **Add More Ticket Types**: Extend to handle other ServiceNow tables
5. **Enhance Agent**: Improve knowledge base and resolution capabilities

## References

- [ServiceNow REST Message Documentation](https://docs.servicenow.com/bundle/vancouver-application-development/page/integrate/outbound-rest/concept/c_OutboundREST.html)
- [ServiceNow Business Rules](https://docs.servicenow.com/bundle/vancouver-application-development/page/script/business-rules/concept/c_BusinessRules.html)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [AWS API Gateway Documentation](https://docs.aws.amazon.com/apigateway/)
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
