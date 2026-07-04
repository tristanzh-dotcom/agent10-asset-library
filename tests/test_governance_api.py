import json
import unittest

from asset_library.governance_api import governance_response


class FakeGovernanceService:
    def snapshot(self):
        return {"writer_health": {"mirror_asset_count": 1}, "mirror_gaps": {"open_count": 0}}


class GovernanceApiTests(unittest.TestCase):
    def test_governance_endpoint_returns_snapshot_json(self):
        status, headers, body = governance_response("/api/asset-library/governance", FakeGovernanceService())

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body), {"writer_health": {"mirror_asset_count": 1}, "mirror_gaps": {"open_count": 0}})

    def test_unknown_endpoint_returns_404(self):
        status, headers, body = governance_response("/api/asset-library/assets", FakeGovernanceService())

        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
