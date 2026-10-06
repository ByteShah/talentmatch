import * as path from 'path';
import * as cdk from 'aws-cdk-lib/core';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
// import * as sqs from 'aws-cdk-lib/aws-sqs';

export interface TalentmatchStackProps extends cdk.StackProps {
  stage: 'dev' | 'prod';
}

export class TalentmatchStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: TalentmatchStackProps) {
    super(scope, id, props);

    cdk.Tags.of(this).add('stage', props.stage);

    // 7-day retention keeps logs inside the free tier.
    const apiLogs = new logs.LogGroup(this, 'ApiLogs', {
      logGroupName: `/talentmatch/${props.stage}/api`,
      retention: logs.RetentionDays.ONE_WEEK,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // ADR-004: one table, on-demand billing, keys designed for known access patterns.
    const table = new dynamodb.TableV2(this, 'Table', {
      partitionKey: { name: 'PK', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'SK', type: dynamodb.AttributeType.STRING },
      billing: dynamodb.Billing.onDemand(),
      globalSecondaryIndexes: [{
        indexName: 'GSI1',
        partitionKey: { name: 'GSI1PK', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'GSI1SK', type: dynamodb.AttributeType.STRING },
      }],
      // Dev data is disposable; prod data must survive a stack delete.
      removalPolicy: props.stage === 'prod' ? cdk.RemovalPolicy.RETAIN : cdk.RemovalPolicy.DESTROY,
    });

    const apiFn = new lambda.Function(this, 'ApiFunction', {
      runtime: lambda.Runtime.PYTHON_3_12,
      architecture: lambda.Architecture.ARM_64,
      handler: 'app.handler',                 // file app.py, function handler
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'src', 'api')),
      memorySize: 256,
      timeout: cdk.Duration.seconds(10),
      logGroup: apiLogs,
      environment: { STAGE: props.stage, APP_VERSION: '0.1.0', TABLE_NAME: table.tableName },
    });
    // Least privilege: read/write on this table and its indexes only.
    table.grantReadWriteData(apiFn);

    const webBucket = new s3.Bucket(this, 'WebBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    const web = new cloudfront.Distribution(this, 'WebDistribution', {
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(webBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      },
      defaultRootObject: 'index.html',
      // SPA fallback: unknown paths like /jobs return index.html so React can route them.
      errorResponses: [
        { httpStatus: 403, responseHttpStatus: 200, responsePagePath: '/index.html' },
        { httpStatus: 404, responseHttpStatus: 200, responsePagePath: '/index.html' },
      ],
    });
    const webUrl = `https://${web.distributionDomainName}`;

    const api = new apigw.HttpApi(this, 'HttpApi', { 
      apiName: `talentmatch-${props.stage}`, 
      corsPreflight: {
        allowOrigins: props.stage === 'dev' ? [webUrl, 'http://localhost:5173'] : [webUrl],
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST],
        allowHeaders: ['content-type'],
      },
    });
    // Every route goes to the same Lambda; app.py's ROUTES picks the function.
    const integration = new HttpLambdaIntegration('ApiIntegration', apiFn);
    api.addRoutes({ path: '/v1/health', methods: [apigw.HttpMethod.GET], integration });
    api.addRoutes({ path: '/v1/jobs', methods: [apigw.HttpMethod.GET, apigw.HttpMethod.POST], integration });
    api.addRoutes({ path: '/v1/jobs/{jobId}', methods: [apigw.HttpMethod.GET], integration });

    new s3deploy.BucketDeployment(this, 'WebDeployment', {
      destinationBucket: webBucket,
      sources: [
        s3deploy.Source.asset(path.join(__dirname, '..', 'frontend', 'dist'), { exclude: ['config.json'] }),
        s3deploy.Source.jsonData('config.json', { apiUrl: api.apiEndpoint, stage: props.stage }),
      ],
      distribution: web,
      distributionPaths: ['/*'],
    });

    new cdk.CfnOutput(this, 'ApiUrl', { value: api.apiEndpoint });
    new cdk.CfnOutput(this, 'ApiFunctionName', { value: apiFn.functionName });
    new cdk.CfnOutput(this, 'WebUrl', { value: webUrl });
    new cdk.CfnOutput(this, 'ApiLogGroup', { value: apiLogs.logGroupName });
    new cdk.CfnOutput(this, 'TableName', { value: table.tableName });
  }
}