import json
import unittest

from asset_library.hardware_api import hardware_response


class FakeHardwareService:
    def __init__(self):
        self.calls = []

    def list_records(self, query="", record_type=None, scope=None):
        self.calls.append(("list", query, record_type, scope))
        return [{"record_type": "hardware_model", "hardware_model_id": "hwm_demo", "canonical_name": "Demo"}]

    def get_record(self, record_id):
        self.calls.append(("get", record_id))
        return getattr(self, "records", {}).get(
            record_id,
            {"record_type": "hardware_model", "hardware_model_id": record_id, "canonical_name": "Demo"},
        )

    def read_photo(self, record_id, photo_id):
        self.calls.append(("photo", record_id, photo_id))
        return "image/png", b"\x89PNG\r\n\x1a\nphoto"

    def list_relations(self, query="", record_type=None, scope=None):
        self.calls.append(("relations", query, record_type, scope))
        return [{"source": "hwm_demo", "relation_type": "used_by", "target": "agent12"}]

    def list_inventory_summary(self, query="", category=None):
        self.calls.append(("summary", query, category))
        return {
            "items": [{"item_id": "hwm_demo", "display_name": "Demo", "quantity_total": 2, "quantity_available": 2}],
            "metrics": {"item_count": 1, "quantity_total": 2, "quantity_available": 2},
        }

    def submit(self, payload):
        self.calls.append(("submit", payload))
        return {"status": "review_pending", "intake_id": "hwi_demo", "snapshot_hash": "sha256:" + "a" * 64}

    def accept(self, intake_id, accepted_by, expected_snapshot_hash):
        self.calls.append(("accept", intake_id, accepted_by, expected_snapshot_hash))
        return {"status": "published", "record_id": "hwm_demo", "path": "02_Hardware/10_Models/Other/HWM - Demo - hwm_demo.md"}

    def create_draft(self, base_record_id=None):
        self.calls.append(("create_draft", base_record_id))
        return {"draft_id": "hwd_demo", "revision": 1, "status": "editing"}

    def patch_draft(self, draft_id, expected_revision, changes):
        self.calls.append(("patch_draft", draft_id, expected_revision, changes))
        return {"draft_id": draft_id, "revision": 2, "status": "editing", **changes}

    def prepare_draft(self, draft_id, expected_revision, submitted_by=None):
        self.calls.append(("prepare_draft", draft_id, expected_revision, submitted_by))
        return {"status": "review_pending", "draft_id": draft_id, "bundle_hash": "sha256:" + "b" * 64, "intakes": []}

    def accept_draft(self, draft_id, expected_bundle_hash):
        self.calls.append(("accept_draft", draft_id, expected_bundle_hash))
        return {"status": "published", "draft_id": draft_id, "results": []}

    def analyze_draft(self, draft_id, operation_key=None):
        self.calls.append(("analyze_draft", draft_id, operation_key))
        return {"job_id": "haj_demo", "draft_id": draft_id, "status": "unavailable", "candidates": []}

    def get_analysis_job(self, job_id):
        self.calls.append(("get_analysis_job", job_id))
        return {"job_id": job_id, "status": "completed", "candidates": []}


class HardwareApiTests(unittest.TestCase):
    def setUp(self):
        self.service = FakeHardwareService()

    def test_get_hardware_list_supports_query_filters(self):
        status, headers, body = hardware_response(
            "GET",
            "/api/asset-library/hardware",
            b"",
            self.service,
            "q=esp32&record_type=hardware_model&scope=agent12",
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "application/json; charset=utf-8")
        self.assertEqual(json.loads(body)["records"][0]["hardware_model_id"], "hwm_demo")
        self.assertEqual(self.service.calls[0], ("list", "esp32", "hardware_model", "agent12"))

    def test_get_inventory_summary_returns_aggregate_only(self):
        status, _headers, body = hardware_response(
            "GET",
            "/api/asset-library/hardware/summary",
            b"",
            self.service,
            "q=esp32&category=%E5%BC%80%E5%8F%91%E6%9D%BF",
        )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["metrics"]["quantity_available"], 2)
        self.assertEqual(payload["items"][0]["item_id"], "hwm_demo")
        self.assertEqual(self.service.calls[0], ("summary", "esp32", "开发板"))

    def test_get_photo_returns_binary_content_without_json_redaction(self):
        status, headers, body = hardware_response(
            "GET",
            "/api/asset-library/hardware/hwm_demo/photos/p0",
            b"",
            self.service,
            "",
        )

        self.assertEqual(status, 200)
        self.assertEqual(headers["content-type"], "image/png")
        self.assertEqual(headers["x-content-type-options"], "nosniff")
        self.assertTrue(body.startswith(b"\x89PNG"))
        self.assertEqual(self.service.calls[0], ("photo", "hwm_demo", "p0"))

    def test_post_request_uses_single_intake_payload(self):
        payload = {"channel": "codex", "submitted_by": "TZ", "operation_key": "op-1", "draft": {"record_type": "hardware_model"}}

        status, _headers, body = hardware_response(
            "POST",
            "/api/asset-library/hardware/requests",
            json.dumps(payload).encode("utf-8"),
            self.service,
            "",
        )

        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["intake_id"], "hwi_demo")
        self.assertEqual(self.service.calls[0][0], "submit")

    def test_draft_routes_create_patch_and_prepare_a_confirmation_bundle(self):
        create_status, _headers, create_body = hardware_response(
            "POST", "/api/asset-library/hardware/drafts", b"{}", self.service, ""
        )
        draft_id = json.loads(create_body)["draft_id"]
        patch_status, _headers, patch_body = hardware_response(
            "PATCH", f"/api/asset-library/hardware/drafts/{draft_id}",
            json.dumps({"expected_revision": 1, "changes": {"quantity": 2}}).encode("utf-8"), self.service, ""
        )
        prepare_status, _headers, prepare_body = hardware_response(
            "POST", f"/api/asset-library/hardware/drafts/{draft_id}/prepare",
            json.dumps({"expected_revision": 2, "submitted_by": "TZ"}).encode("utf-8"), self.service, ""
        )

        self.assertEqual((create_status, patch_status, prepare_status), (201, 200, 200))
        self.assertEqual(json.loads(patch_body)["revision"], 2)
        self.assertTrue(json.loads(prepare_body)["bundle_hash"].startswith("sha256:"))

    def test_post_acceptance_uses_intake_id_and_snapshot_hash(self):
        payload = {"accepted_by": "TZ", "expected_snapshot_hash": "sha256:" + "a" * 64}

        status, _headers, body = hardware_response(
            "POST",
            "/api/asset-library/hardware/intakes/hwi_demo/accept",
            json.dumps(payload).encode("utf-8"),
            self.service,
            "",
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "published")
        self.assertEqual(
            self.service.calls[0],
            ("accept", "hwi_demo", "TZ", "sha256:" + "a" * 64),
        )

    def test_draft_acceptance_does_not_forward_browser_operator_assertion(self):
        status, _headers, body = hardware_response(
            "POST",
            "/api/asset-library/hardware/drafts/hwd_demo/accept",
            json.dumps({"accepted_by": "browser-assertion", "expected_bundle_hash": "sha256:" + "b" * 64}).encode("utf-8"),
            self.service,
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "published")
        self.assertEqual(
            self.service.calls[0],
            ("accept_draft", "hwd_demo", "sha256:" + "b" * 64),
        )

    def test_analysis_routes_start_and_read_a_redacted_job(self):
        status, _headers, body = hardware_response(
            "POST",
            "/api/asset-library/hardware/drafts/hwd_demo/analyze",
            json.dumps({"operation_key": "op-analysis"}).encode("utf-8"),
            self.service,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["job_id"], "haj_demo")
        self.assertEqual(self.service.calls[0], ("analyze_draft", "hwd_demo", "op-analysis"))

        status, _headers, body = hardware_response(
            "GET",
            "/api/asset-library/hardware/analysis-jobs/haj_demo",
            b"",
            self.service,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "completed")

    def test_unknown_hardware_route_is_not_found(self):
        status, _headers, body = hardware_response("GET", "/api/asset-library/hardware/nope/x", b"", self.service, "")

        self.assertEqual(status, 404)
        self.assertEqual(json.loads(body)["error"], "not_found")

    def test_get_relations_returns_explicit_edges(self):
        status, _headers, body = hardware_response(
            "GET",
            "/api/asset-library/hardware/relations",
            b"",
            self.service,
            "scope=agent12",
        )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["relations"][0]["target"], "agent12")
        self.assertEqual(self.service.calls[0], ("relations", "", "", "agent12"))

    def test_projection_redacts_local_evidence_references_but_keeps_claim_level(self):
        self.service.records = {
            "hwm_demo": {
                "record_type": "hardware_model",
                "hardware_model_id": "hwm_demo",
                "evidence_records": [{"claim": "appearance", "level": "label_or_photo", "source_ref": "agent11/private.jpg"}],
                "photo_refs": ["02_Hardware/90_Evidence/photos/private.jpg"],
            }
        }

        status, _headers, body = hardware_response(
            "GET",
            "/api/asset-library/hardware/hwm_demo",
            b"",
            self.service,
        )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["evidence_records"][0]["claim"], "appearance")
        self.assertNotIn("source_ref", payload["evidence_records"][0])
        self.assertNotIn("private.jpg", body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
