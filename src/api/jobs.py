import base64
import json
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from errors import ApiError

_table = None

def table():
    global _table
    if _table is None:
        _table = boto3.resource("dynamodb").Table(os.environ["TABLE_NAME"])
    return _table

def to_public(item):
    return {k: v for k, v in item.items() if k not in ("PK", "SK", "GSI1PK", "GSI1SK", "type")}

def validate_new_job(body):
    errors = []
    for field, max_len in (("title", 200), ("description", 20000)):
        value = body.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append({"field": field, "message": f"{field} is required and must be a non-empty string."})
        elif len(value) > max_len:
            errors.append({"field": field, "message": f"{field} must not exceed {max_len} characters."})

    if errors:
        raise ApiError(status=400, code="VALIDATION_FAILED", message="Invalid input data.", details=errors)

def create_job(body):
    validate_new_job(body)
    now = datetime.now(timezone.utc).isoformat()
    job_id = uuid.uuid4().hex
    item = {
        "PK": f"JOB#{job_id}",
        "SK": "META",
        "GSI1PK": "JOB",
        "GSI1SK": f"{now}#{job_id}",  # time first, so the index sorts newest/oldest
        "type": "job",
        "id": job_id,
        "title": body["title"].strip(),
        "description": body["description"].strip(),
        "status": "open",
        "createdAt": now,
        "updatedAt": now,
    }
    table().put_item(Item=item, ConditionExpression="attribute_not_exists(PK)")
    return to_public(item)

def get_job(job_id):
    item = table().get_item(Key={"PK": f"JOB#{job_id}", "SK": "META"}).get("Item")
    return to_public(item) if item else None

def encode_token(key):
    if not key:
        return None
    return base64.urlsafe_b64encode(json.dumps(key).encode()).decode()

def decode_token(token):
    try:
        return json.loads(base64.urlsafe_b64decode(token.encode()).decode())
    except Exception:
        raise ApiError(status=400, code="BAD_REQUEST", message="The provided token is invalid.")

def list_jobs(limit, next_token=None):
    kwargs = {
        "IndexName": "GSI1",
        "KeyConditionExpression": Key("GSI1PK").eq("JOB"),
        "ScanIndexForward": False,
        "Limit": limit,
    }
    if next_token:
        kwargs["ExclusiveStartKey"] = decode_token(next_token)
    res = table().query(**kwargs)
    return {
        "items": [to_public(item) for item in res.get("Items", [])],
        "nextToken": encode_token(res.get("LastEvaluatedKey")),
    }
