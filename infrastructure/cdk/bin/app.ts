#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ServiceNowWebhookStack } from '../lib/servicenow-webhook-stack';

const app = new cdk.App();

// Get configuration from environment or use defaults
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID,
  region: process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'eu-central-1',
};

new ServiceNowWebhookStack(app, 'ServiceNowWebhookStack', {
  env,
  description: 'AWS AgentCore ServiceNow Webhook Integration',
  tags: {
    Project: 'AWS-AgentCore-Tutorial',
    Component: 'ServiceNow-Webhook',
    ManagedBy: 'CDK'
  }
});

app.synth();
