import json
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

STAGE = os.environ.get("STAGE", "local")
VERSION = os.environ.get("APP_VERSION", "0.1.0")


def log(level, message, context, **fields):
    entry = {"level": level, "message": message, "request_id": context.aws_request_id, **fields}
    logger.log(getattr(logging, level), json.dumps(entry))


def response(status, body):
    return {"statusCode": status, "headers": {"content-type": "application/json"}, "body": json.dumps(body)}


def handler(event, context):
    route = event.get("routeKey", "")
    log("INFO", "request", context, route=route)

    if route == "GET /v1/health":
        return response(200, {"status": "ok", "stage": STAGE, "version": VERSION,
                              "time": datetime.now(timezone.utc).isoformat()})

    return response(404, {"error": {"code" f"No route {route}"}})