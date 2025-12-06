import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

export interface ServiceNowWebhookStackProps extends cdk.StackProps {
  /**
   * The AgentCore agent runtime ARN to invoke
   * Example: arn:aws:bedrock-agentcore:eu-central-1:123456789012:runtime/my-agent-abc123
   * If not provided, must be set via environment variable at runtime
   */
  agentRuntimeArn?: string;

  /**
   * Lambda function timeout in seconds
   * @default 300 (5 minutes)
   */
  lambdaTimeout?: number;

  /**
   * Lambda function memory in MB
   * @default 512
   */
  lambdaMemory?: number;

  /**
   * CloudWatch log retention period
   * @default 7 days
   */
  logRetention?: logs.RetentionDays;
}

export class ServiceNowWebhookStack extends cdk.Stack {
  public readonly webhookUrl: string;
  public readonly lambdaFunction: lambda.Function;
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props?: ServiceNowWebhookStackProps) {
    super(scope, id, props);

    // Default configuration
    const lambdaTimeout = props?.lambdaTimeout || 300;
    const lambdaMemory = props?.lambdaMemory || 512;
    const logRetention = props?.logRetention || logs.RetentionDays.ONE_WEEK;

    // ========================================
    // IAM Role for Lambda
    // ========================================
    const lambdaRole = new iam.Role(this, 'WebhookLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for ServiceNow webhook Lambda function',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant permissions to invoke Bedrock AgentCore Runtime
    lambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock-agentcore:InvokeAgentRuntime',
        ],
        resources: ['arn:aws:bedrock-agentcore:eu-central-1:653783183133:runtime/*'],
      })
    );

    // ========================================
    // Lambda Function
    // ========================================
    const webhookHandler = new lambda.Function(this, 'WebhookHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../../src/webhook')),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(lambdaTimeout),
      memorySize: lambdaMemory,
      environment: {
        LOG_LEVEL: 'INFO',
        // AGENT_RUNTIME_ARN will be set via environment variable or parameter
      },
      description: 'Handles ServiceNow webhook requests and invokes AgentCore agent',
      logRetention: logRetention,
    });

    // Add AGENT_RUNTIME_ARN from props if provided
    if (props?.agentRuntimeArn) {
      webhookHandler.addEnvironment('AGENT_RUNTIME_ARN', props.agentRuntimeArn);
    }

    this.lambdaFunction = webhookHandler;

    // ========================================
    // API Gateway
    // ========================================
    const api = new apigateway.RestApi(this, 'ServiceNowWebhookApi', {
      restApiName: 'ServiceNow Webhook API',
      description: 'API Gateway for receiving ServiceNow incident webhooks',
      deployOptions: {
        stageName: 'prod',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: ['POST', 'OPTIONS'],
        allowHeaders: ['Content-Type', 'X-Amz-Date', 'Authorization', 'X-Api-Key'],
      },
    });

    this.api = api;

    // ========================================
    // API Key and Usage Plan
    // ========================================
    const apiKey = new apigateway.ApiKey(this, 'ServiceNowApiKey', {
      apiKeyName: 'servicenow-webhook-api-key',
      description: 'API Key for ServiceNow webhook integration',
      enabled: true,
    });

    const usagePlan = new apigateway.UsagePlan(this, 'ServiceNowUsagePlan', {
      name: 'ServiceNow Webhook Usage Plan',
      description: 'Usage plan for ServiceNow webhook integration',
      apiStages: [
        {
          api: api,
          stage: api.deploymentStage,
        },
      ],
      throttle: {
        rateLimit: 100,    // requests per second
        burstLimit: 200,   // maximum concurrent requests
      },
      quota: {
        limit: 10000,      // requests per month
        period: apigateway.Period.MONTH,
      },
    });

    usagePlan.addApiKey(apiKey);

    // Create /webhook resource
    const webhookResource = api.root.addResource('webhook');

    // Create /webhook/servicenow resource
    const servicenowResource = webhookResource.addResource('servicenow');

    // Add POST method to /webhook/servicenow
    const lambdaIntegration = new apigateway.LambdaIntegration(webhookHandler, {
      proxy: true,
      integrationResponses: [
        {
          statusCode: '200',
        },
      ],
    });

    servicenowResource.addMethod('POST', lambdaIntegration, {
      apiKeyRequired: true, // API Key is now required
      methodResponses: [
        {
          statusCode: '200',
          responseModels: {
            'application/json': apigateway.Model.EMPTY_MODEL,
          },
        },
      ],
    });

    // Store webhook URL
    this.webhookUrl = `${api.url}webhook/servicenow`;

    // ========================================
    // CloudWatch Log Groups
    // ========================================
    new logs.LogGroup(this, 'ApiGatewayAccessLogs', {
      logGroupName: `/aws/apigateway/servicenow-webhook-api`,
      retention: logRetention,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ========================================
    // Stack Outputs
    // ========================================
    new cdk.CfnOutput(this, 'WebhookURL', {
      value: this.webhookUrl,
      description: 'URL to configure in ServiceNow Business Rule',
      exportName: 'ServiceNowWebhookURL',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: webhookHandler.functionName,
      description: 'Name of the webhook Lambda function',
      exportName: 'ServiceNowWebhookLambdaName',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionArn', {
      value: webhookHandler.functionArn,
      description: 'ARN of the webhook Lambda function',
      exportName: 'ServiceNowWebhookLambdaArn',
    });

    new cdk.CfnOutput(this, 'ApiGatewayId', {
      value: api.restApiId,
      description: 'API Gateway REST API ID',
      exportName: 'ServiceNowWebhookApiId',
    });

    new cdk.CfnOutput(this, 'ApiKeyId', {
      value: apiKey.keyId,
      description: 'API Key ID (use AWS CLI to get the actual key value)',
      exportName: 'ServiceNowWebhookApiKeyId',
    });

    new cdk.CfnOutput(this, 'GetApiKeyCommand', {
      value: `aws apigateway get-api-key --api-key ${apiKey.keyId} --include-value --query 'value' --output text`,
      description: 'Command to retrieve the API Key value',
    });

    // Output instruction for setting AGENT_RUNTIME_ARN
    if (!props?.agentRuntimeArn) {
      new cdk.CfnOutput(this, 'SetAgentRuntimeArnCommand', {
        value: `aws lambda update-function-configuration --function-name ${webhookHandler.functionName} --environment "Variables={AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:eu-central-1:YOUR_ACCOUNT:runtime/YOUR_AGENT_ID,LOG_LEVEL=INFO}"`,
        description: 'Command to set AGENT_RUNTIME_ARN environment variable',
      });
    }
  }
}
