import json, sys, unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "api"))
import app  # noqa: E402

CONTEXT = SimpleNamespace(aws_request_id="test-request-id")


class HealthTest(unittest.TestCase):
    def test_health_returns_ok(self):
        res = app.handler({"routeKey": "GET /v1/health"}, CONTEXT)
        self.assertEqual(res["statusCode"], 200)
        self.assertEqual(json.loads(res["body"])["status"], "ok")

    def test_unknown_route_returns_404(self):
        res = app.handler({"routeKey": "GET /nope"}, CONTEXT)
        self.assertEqual(res["statusCode"], 404)