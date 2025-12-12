import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
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
  public readonly servicenowApiLambda: lambda.Function;
  public readonly api: apigateway.RestApi;
  public readonly servicenowSecret: secretsmanager.Secret;
  public readonly cognitoUserPool: cognito.UserPool;
  public readonly gatewayRole: iam.Role;

  constructor(scope: Construct, id: string, props?: ServiceNowWebhookStackProps) {
    super(scope, id, props);

    // Default configuration
    const lambdaTimeout = props?.lambdaTimeout || 300;
    const lambdaMemory = props?.lambdaMemory || 512;
    const logRetention = props?.logRetention || logs.RetentionDays.ONE_WEEK;

    // ========================================
    // Secrets Manager - ServiceNow Credentials
    // ========================================
    const servicenowSecret = new secretsmanager.Secret(this, 'ServiceNowCredentials', {
      secretName: 'servicenow/credentials',
      description: 'ServiceNow API credentials for AgentCore integration',
      secretObjectValue: {
        instance_url: cdk.SecretValue.unsafePlainText('https://YOUR_INSTANCE.service-now.com'),
        username: cdk.SecretValue.unsafePlainText('PLACEHOLDER_USERNAME'),
        password: cdk.SecretValue.unsafePlainText('PLACEHOLDER_PASSWORD'),
      },
    });
    this.servicenowSecret = servicenowSecret;

    // ========================================
    // Cognito User Pool for Gateway OAuth
    // ========================================
    const userPool = new cognito.UserPool(this, 'AgentCoreGatewayUserPool', {
      userPoolName: 'agentcore-gateway-servicenow-pool',
      selfSignUpEnabled: false,
      signInAliases: {
        email: true,
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    this.cognitoUserPool = userPool;

    // Add domain for OAuth endpoints
    const userPoolDomain = userPool.addDomain('GatewayDomain', {
      cognitoDomain: {
        domainPrefix: `agentcore-gateway-${this.account}`,
      },
    });

    // Resource server for Gateway scopes
    const resourceServer = userPool.addResourceServer('GatewayResourceServer', {
      identifier: 'agentcore-gateway',
      scopes: [
        {
          scopeName: 'tools.invoke',
          scopeDescription: 'Invoke Gateway tools',
        },
      ],
    });

    // App client for M2M (machine-to-machine) auth
    const appClient = userPool.addClient('GatewayM2MClient', {
      userPoolClientName: 'agentcore-gateway-m2m-client',
      generateSecret: true,
      oAuth: {
        flows: {
          clientCredentials: true,
        },
        scopes: [
          cognito.OAuthScope.custom('agentcore-gateway/tools.invoke'),
        ],
      },
    });

    // Ensure Resource Server is created before App Client
    appClient.node.addDependency(resourceServer);

    // ========================================
    // IAM Role for Lambda (Webhook Handler)
    // ========================================
    const webhookLambdaRole = new iam.Role(this, 'WebhookLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for ServiceNow webhook Lambda function',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant permissions to invoke Bedrock AgentCore Runtime
    webhookLambdaRole.addToPolicy(
      new iam.PolicyStatement({
        effect: iam.Effect.ALLOW,
        actions: [
          'bedrock-agentcore:InvokeAgentRuntime',
        ],
        resources: [`arn:aws:bedrock-agentcore:${this.region}:${this.account}:runtime/*`],
      })
    );

    // ========================================
    // IAM Role for ServiceNow API Lambda
    // ========================================
    const servicenowApiLambdaRole = new iam.Role(this, 'ServiceNowApiLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Execution role for ServiceNow API Lambda function',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Grant access to read ServiceNow credentials from Secrets Manager
    servicenowSecret.grantRead(servicenowApiLambdaRole);

    // ========================================
    // IAM Role for AgentCore Gateway
    // ========================================
    const gatewayRole = new iam.Role(this, 'AgentCoreGatewayRole', {
      roleName: 'AgentCoreGatewayServiceNowRole',
      assumedBy: new iam.ServicePrincipal('bedrock-agentcore.amazonaws.com'),
      description: 'Role for AgentCore Gateway to invoke ServiceNow Lambda functions',
    });
    this.gatewayRole = gatewayRole;

    // ========================================
    // Lambda Function - Webhook Handler
    // ========================================
    const webhookHandler = new lambda.Function(this, 'WebhookHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../../src/webhook')),
      role: webhookLambdaRole,
      timeout: cdk.Duration.seconds(lambdaTimeout),
      memorySize: lambdaMemory,
      environment: {
        LOG_LEVEL: 'INFO',
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
    // Lambda Function - ServiceNow API Handler
    // ========================================
    const servicenowApiHandler = new lambda.Function(this, 'ServiceNowApiHandler', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'lambda_handler.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../../src/servicenow'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_12.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -r . /asset-output'
          ],
        },
      }),
      role: servicenowApiLambdaRole,
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
      environment: {
        LOG_LEVEL: 'INFO',
        SERVICENOW_SECRET_NAME: servicenowSecret.secretName,
        // Note: AWS_REGION is automatically set by Lambda runtime
      },
      description: 'Handles ServiceNow API operations for AgentCore Gateway tools',
      logRetention: logRetention,
    });

    this.servicenowApiLambda = servicenowApiHandler;

    // Grant Gateway role permission to invoke ServiceNow API Lambda
    servicenowApiHandler.grantInvoke(gatewayRole);

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
        rateLimit: 100,
        burstLimit: 200,
      },
      quota: {
        limit: 10000,
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
      apiKeyRequired: true,
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

    new cdk.CfnOutput(this, 'ServiceNowApiLambdaArn', {
      value: servicenowApiHandler.functionArn,
      description: 'ARN of the ServiceNow API Lambda function (for Gateway targets)',
      exportName: 'ServiceNowApiLambdaArn',
    });

    new cdk.CfnOutput(this, 'ServiceNowApiLambdaName', {
      value: servicenowApiHandler.functionName,
      description: 'Name of the ServiceNow API Lambda function',
      exportName: 'ServiceNowApiLambdaName',
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

    new cdk.CfnOutput(this, 'ServiceNowSecretArn', {
      value: servicenowSecret.secretArn,
      description: 'ARN of the ServiceNow credentials secret',
      exportName: 'ServiceNowSecretArn',
    });

    new cdk.CfnOutput(this, 'UpdateServiceNowSecretCommand', {
      value: `aws secretsmanager update-secret --secret-id ${servicenowSecret.secretName} --secret-string '{"instance_url":"https://YOUR_INSTANCE.service-now.com","username":"YOUR_USERNAME","password":"YOUR_PASSWORD"}'`,
      description: 'Command to update ServiceNow credentials',
    });

    new cdk.CfnOutput(this, 'CognitoUserPoolId', {
      value: userPool.userPoolId,
      description: 'Cognito User Pool ID for Gateway OAuth',
      exportName: 'AgentCoreGatewayCognitoUserPoolId',
    });

    new cdk.CfnOutput(this, 'CognitoAppClientId', {
      value: appClient.userPoolClientId,
      description: 'Cognito App Client ID for Gateway M2M auth',
      exportName: 'AgentCoreGatewayCognitoAppClientId',
    });

    new cdk.CfnOutput(this, 'CognitoTokenEndpoint', {
      value: `https://${userPoolDomain.domainName}.auth.${this.region}.amazoncognito.com/oauth2/token`,
      description: 'Cognito token endpoint for OAuth',
      exportName: 'AgentCoreGatewayCognitoTokenEndpoint',
    });

    new cdk.CfnOutput(this, 'GatewayRoleArn', {
      value: gatewayRole.roleArn,
      description: 'IAM Role ARN for AgentCore Gateway',
      exportName: 'AgentCoreGatewayRoleArn',
    });

    // Output instruction for setting AGENT_RUNTIME_ARN
    if (!props?.agentRuntimeArn) {
      new cdk.CfnOutput(this, 'SetAgentRuntimeArnCommand', {
        value: `aws lambda update-function-configuration --function-name ${webhookHandler.functionName} --environment "Variables={AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:${this.region}:${this.account}:runtime/YOUR_AGENT_ID,LOG_LEVEL=INFO}"`,
        description: 'Command to set AGENT_RUNTIME_ARN environment variable',
      });
    }

    // Gateway setup command
    new cdk.CfnOutput(this, 'GatewaySetupCommand', {
      value: `python scripts/setup_gateway.py --lambda-arn ${servicenowApiHandler.functionArn} --role-arn ${gatewayRole.roleArn} --user-pool-id ${userPool.userPoolId} --client-id ${appClient.userPoolClientId} --region ${this.region}`,
      description: 'Command to setup AgentCore Gateway with ServiceNow tools',
    });
  }
}
