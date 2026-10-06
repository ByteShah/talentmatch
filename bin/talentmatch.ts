#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib/core';
import { TalentmatchStack } from '../lib/talentmatch-stack';

const app = new cdk.App();

const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: 'ap-south-1' };

for (const stage of ['dev', 'prod'] as const) {
  new TalentmatchStack(app, `TalentMatch-${stage}`, { env,  stage });
}