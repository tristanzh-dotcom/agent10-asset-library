import json
import stat
import tempfile
import unittest
from pathlib import Path

from asset_library.http_server import Agent10HttpApp, ensure_control_token


class FakeGovernanceService:
    def __init__(self):
        self.mutations = []

    def snapshot(self):
        return {"writer_health": {"mirror_asset_count": 2}}

    def run_mutation(self, action):
        self.mutations.append(action)
        return {"action": action, "status": "completed"}


class FakeProducerService:
    def ingest_draft(self, draft):
        return {"asset_id": "ast_20260712_deadbeef", "mode": "rest", "path": "note.md"}

    def ingest_producer_asset(self, producer_id, payload):
        return {"producer_id": producer_id, "asset_id": "ast_20260712_deadbeef", "mode": "rest", "path": "note.md"}

    def ingest_migration_draft(self, draft):
        return {"asset_id": draft["asset_id"], "mode": "rest", "path": "note.md"}


class FakeHardwareService:
    def __init__(self):
        self.calls = []

    def list_records(self, **filters):
        self.calls.append(("list", filters))
        return [{"record_type": "hardware_model", "hardware_model_id": "hwm_demo", "canonical_name": "Demo"}]

    def get_record(self, record_id):
        self.calls.append(("get", record_id))
        return {"record_type": "hardware_model", "hardware_model_id": record_id, "canonical_name": "Demo"}

    def read_photo(self, record_id, photo_id):
        self.calls.append(("photo", record_id, photo_id))
        return "image/jpeg", b"\xff\xd8\xffphoto"

    def submit(self, payload):
        self.calls.append(("submit", payload))
        return {"status": "review_pending", "intake_id": "hwi_demo", "snapshot_hash": "sha256:" + "a" * 64}

    def accept(self, intake_id, accepted_by, expected_snapshot_hash):
        self.calls.append(("accept", intake_id, accepted_by, expected_snapshot_hash))
        return {"status": "published", "record_id": "hwm_demo", "path": "02_Hardware/demo.md"}


class FakeRuntime:
    def __init__(self):
        self.governance_service = FakeGovernanceService()
        self.producer_service = FakeProducerService()
        self.hardware_service = FakeHardwareService()


class Agent10HttpAppTests(unittest.TestCase):
    def setUp(self):
        self.runtime = FakeRuntime()
        self.app = Agent10HttpApp(runtime=self.runtime, control_token="token-value")

    def test_governance_requires_loopback_bearer_token(self):
        status, _headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/governance",
            headers={},
            body=b"",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "control_authorization_required")

        status, _headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/governance",
            headers={"authorization": "Bearer token-value"},
            body=b"",
            client_host="192.168.1.7",
        )
        self.assertEqual(status, 403)
        self.assertEqual(json.loads(body)["error"], "loopback_required")

    def test_governance_returns_side_effect_free_snapshot_for_authorized_loopback(self):
        status, headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/governance",
            headers={"authorization": "Bearer token-value"},
            body=b"",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body)["writer_health"]["mirror_asset_count"], 2)

    def test_explicit_mutation_and_agent06_producer_are_authorized(self):
        headers = {"authorization": "Bearer token-value"}
        status, _headers, body = self.app.dispatch(
            method="POST",
            path="/api/agent10/governance/actions/recover-writer",
            headers=headers,
            body=b"{}",
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["action"], "recover-writer")
        self.assertEqual(self.runtime.governance_service.mutations, ["recover-writer"])

        status, _headers, body = self.app.dispatch(
            method="POST",
            path="/api/agent10/producers/agent06/assets",
            headers=headers,
            body=json.dumps({"source_asset_path": "/tmp/asset"}).encode("utf-8"),
            client_host="127.0.0.1",
        )
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["producer_id"], "agent06")

    def test_hardware_routes_use_authenticated_loopback_and_preserve_query_filters(self):
        headers = {"authorization": "Bearer token-value"}
        status, _headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/hardware?q=esp32&scope=agent12",
            headers=headers,
            body=b"",
            client_host="127.0.0.1",
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["records"][0]["hardware_model_id"], "hwm_demo")
        self.assertEqual(
            self.runtime.hardware_service.calls[0],
            ("list", {"query": "esp32", "record_type": "", "scope": "agent12"}),
        )

    def test_hardware_accept_route_requires_authenticated_loopback(self):
        body = json.dumps({"accepted_by": "TZ", "expected_snapshot_hash": "sha256:" + "a" * 64}).encode("utf-8")
        status, _headers, response_body = self.app.dispatch(
            method="POST",
            path="/api/agent10/hardware/intakes/hwi_demo/accept",
            headers={"authorization": "Bearer token-value"},
            body=body,
            client_host="127.0.0.1",
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(response_body)["status"], "published")
        self.assertEqual(
            self.runtime.hardware_service.calls[0],
            ("accept", "hwi_demo", "TZ", "sha256:" + "a" * 64),
        )

    def test_hardware_photo_route_returns_binary_from_authenticated_loopback(self):
        status, headers, body = self.app.dispatch(
            method="GET",
            path="/api/agent10/hardware/hwm_demo/photos/p0",
            headers={"authorization": "Bearer token-value"},
            body=b"",
            client_host="127.0.0.1",
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "image/jpeg")
        self.assertEqual(body, b"\xff\xd8\xffphoto")
        self.assertEqual(self.runtime.hardware_service.calls[0], ("photo", "hwm_demo", "p0"))

    def test_token_file_is_generated_with_owner_only_permissions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".agent10-control.token"
            first = ensure_control_token(path)
            second = ensure_control_token(path)

            self.assertEqual(first, second)
            self.assertRegex(first, r"^[0-9a-f]{64}$")
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()
