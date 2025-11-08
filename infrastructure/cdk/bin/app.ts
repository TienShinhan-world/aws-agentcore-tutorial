#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { ServiceNowWebhookStack } from '../lib/servicenow-webhook-stack';

const app = new cdk.App();

// Get environment configuration
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'eu-central-1',
};

// Create the webhook stack
new ServiceNowWebhookStack(app, 'ServiceNowWebhookStack', {
  env,
  description: 'Infrastructure for ServiceNow webhook integration with AWS AgentCore',

  // Stack tags
  tags: {
    Project: 'aws-agentcore-tutorial',
    Component: 'servicenow-webhook',
    Step: 'step-02',
  },
});

app.synth();
