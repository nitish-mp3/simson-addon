"""Regression tests for bounded, actionable ingress proxy errors."""

import sys
import unittest
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from local_api import _safe_upstream_error  # noqa: E402


class LocalAPIErrorTests(unittest.TestCase):
    def test_cloudflare_html_is_not_returned_to_the_dashboard(self):
        result = _safe_upstream_error(
            502,
            "<!DOCTYPE html><html><title>Cloudflare Bad gateway</title>secret page</html>",
            "phone provisioning",
        )

        self.assertEqual(result["code"], "upstream_proxy_error")
        self.assertNotIn("<!DOCTYPE", result["error"])
        self.assertNotIn("secret page", result["error"])

    def test_old_vps_advanced_route_404_is_reported_as_version_mismatch(self):
        result = _safe_upstream_error(404, "404 page not found", "advanced routing")

        self.assertEqual(result["code"], "advanced_routes_unavailable")
        self.assertIn("matching Simson VPS build", result["error"])

    def test_json_upstream_error_is_bounded(self):
        result = _safe_upstream_error(422, '{"error":"bad route"}', "advanced routing")

        self.assertEqual(result["error"], "bad route")
        self.assertEqual(result["upstream_status"], 422)


if __name__ == "__main__":
    unittest.main()
