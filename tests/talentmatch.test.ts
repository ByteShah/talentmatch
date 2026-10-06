import * as cdk from 'aws-cdk-lib/core';
import { Template } from 'aws-cdk-lib/assertions';
import { TalentmatchStack } from '../lib/talentmatch-stack';

const template = Template.fromStack(new TalentmatchStack(new cdk.App(), 'TestStack', { stage: 'dev' }));

test('API Lambda is Python 3.12 on arm64', () => {
  template.hasResourceProperties('AWS::Lambda::Function', { Runtime: 'python3.12', Architectures: ['arm64'] });
});

test('health route exists', () => {
  template.hasResourceProperties('AWS::ApiGatewayV2::Route', { RouteKey: 'GET /v1/health' });
});

test('logs kept for 7 days', () => {
  template.hasResourceProperties('AWS::Logs::LogGroup', { RetentionInDays: 7 });
});

test('web bucket blocks all public access', () => {
  template.hasResourceProperties('AWS::S3::Bucket', {
    PublicAccessBlockConfiguration: {
      BlockPublicAcls: true, BlockPublicPolicy: true, IgnorePublicAcls: true, RestrictPublicBuckets: true,
    },
  });
});
