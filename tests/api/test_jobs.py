import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.update({
    "TABLE_NAME": "test-table",
    "AWS_DEFAULT_REGION": "ap-south-1",
    "AWS_ACCESS_KEY_ID": "test",
    "AWS_SECRET_ACCESS_KEY": "testing"
})
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "api"))

import boto3
from moto import mock_aws

import app
import jobs

CONTEXT = SimpleNamespace(aws_request_id="test-request-id")

def call(route, body=None, path=None, query=None):
    event = {"routeKey": route, "body": json.dumps(body) if body is not None else None,
             "pathParameters": path, "queryStringParameters": query}
    res = app.handler(event, CONTEXT)
    return res["statusCode"], json.loads(res["body"])

@mock_aws
class JobsTest(unittest.TestCase):
    def setUp(self):
        jobs._table = None
        boto3.client("dynamodb").create_table(
            TableName="test-table",
            AttributeDefinitions=[{"AttributeName": n, "AttributeType": "S"}
                                    for n in ("PK", "SK", "GSI1PK", "GSI1SK")],
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"},
                        {"AttributeName": "SK", "KeyType": "RANGE"}],
            GlobalSecondaryIndexes=[{
                "IndexName": "GSI1",
                "KeySchema": [{"AttributeName": "GSI1PK", "KeyType": "HASH"},
                              {"AttributeName": "GSI1SK", "KeyType": "RANGE"}],
                "Projection": {"ProjectionType": "ALL"},
            }],
            BillingMode="PAY_PER_REQUEST"
        )

    def test_create_then_get(self):
        status, body = call("POST /v1/jobs", {"title": "Odoo Developer", "description": "Python, Odoo"})
        self.assertEqual(status, 201)
        self.assertNotIn("PK", body)
        status, fetched = call("GET /v1/jobs/{jobId}", path={"jobId": body["id"]})
        self.assertEqual(status, 200)
        self.assertEqual(fetched["title"], "Odoo Developer")

    def test_missing_title_is_rejected(self):
        status, body = call("POST /v1/jobs", {"description": "Python, Odoo"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "VALIDATION_FAILED")
        self.assertIn("title", [e["field"] for e in body["error"]["details"]])

    def test_unknown_job_is_404(self):
        status, body = call("GET /v1/jobs/{jobId}", path={"jobId": "unknown"})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

    def test_list_pagination_newest_first(self):
        for title in ("A", "B", "C"):
            call("POST /v1/jobs", {"title": title, "description": f"Desc {title}"})
        _, page1 = call("GET /v1/jobs", query={"limit": "2"})
        self.assertEqual([j["title"] for j in page1["items"]], ["C", "B"])
        _, page2 = call("GET /v1/jobs", query={"limit": "2", "nextToken": page1["nextToken"]})
        self.assertEqual([j["title"] for j in page2["items"]], ["A"])
