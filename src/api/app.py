import base64
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import jobs
from errors import ApiError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

STAGE = os.environ.get("STAGE", "local")
VERSION = os.environ.get("APP_VERSION", "0.1.0")


def log(level, message, context, **fields):
    entry = {"level": level, "message": message, "request_id": context.aws_request_id, **fields}
    logger.log(getattr(logging, level), json.dumps(entry))


def response(status, body):
    return {
        "statusCode": status, 
        "headers": {"content-type": "application/json"}, 
        "body": json.dumps(body, default=json_default)
    }

def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    raise TypeError(f"Cannot serialize {type(value)} to JSON")

def handler(event, context):
    route = event.get("routeKey", "")
    log("INFO", "request", context, route=route)

    try:
        route_fn = ROUTES.get(route)
        if route_fn is None:
            raise ApiError(status=404, code="NOT_FOUND", message=f"No route {route}")
        status, body = route_fn(event)
        return response(status, body)
    except ApiError as e:
        log("WARNING", "Request failed", context, route=route, status=e.status, code=e.code, error=e.message, details=e.details)
        error = {"code": e.code, "message": e.message}
        if e.details is not None:
            error["details"] = e.details
        return response(e.status, {"error": error})
    except Exception:
        logger.exception(json.dumps({"level": "ERROR", "message": "Unhandled exception", "request_id": context.aws_request_id, "route": route}))
        return response(500, {"error": {"code": "INTERNAL", "message": "Something went wrong"}})

def parse_body(event):
    raw = event.get("body", "")
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")
    try:
        body = json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        raise ApiError(status=400, code="BAD_REQUEST", message="Request body is not valid JSON.")
    if not isinstance(body, dict):
        raise ApiError(status=400, code="BAD_REQUEST", message="Request body must be a JSON object.")
    return body

def health(event):
    return 200, {"status": "ok", "stage": STAGE, "version": VERSION,
                 "time": datetime.now(timezone.utc).isoformat()}

def list_jobs(event):
    params = event.get("queryStringParameters") or {}
    try:
        limit = int(params.get("limit", 20))
    except ValueError:
        raise ApiError(status=400, code="BAD_REQUEST", message="Limit must be an integer.")
    if limit < 1 or limit > 100:
        raise ApiError(status=400, code="BAD_REQUEST", message="Limit must be between 1 and 100.")
    return 200, jobs.list_jobs(limit, next_token=params.get("nextToken"))

def create_job(event):
    return 201, jobs.create_job(parse_body(event))

def get_job(event):
    job = jobs.get_job((event.get("pathParameters") or {}).get("jobId"))
    if job is None:
        raise ApiError(status=404, code="NOT_FOUND", message="Job not found.")
    return 200, job

ROUTES = {
    "GET /v1/health": health,
    "GET /v1/jobs": list_jobs,
    "POST /v1/jobs": create_job,
    "GET /v1/jobs/{jobId}": get_job,
}
