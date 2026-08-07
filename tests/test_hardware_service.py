import base64
import os
import tempfile
import unittest
from pathlib import Path

from asset_library.hardware_service import HardwareService
from asset_library.hardware_intake import prepare_hardware_intake
from asset_library.hardware_store import HardwareStore
from tests.test_hardware_schema import valid_model, valid_unit


class FakeStore:
    def __init__(self):
        self.intakes = {}
        self.records = []
        self.drafts = {}

    def save_intake(self, intake):
        existing = self.intakes.get(intake["operation_key"])
        if existing:
            if existing["snapshot_hash"] != intake["snapshot_hash"]:
                raise ValueError("operation_key already exists with a different hardware snapshot")
            return existing, True
        self.intakes[intake["operation_key"]] = dict(intake)
        return dict(intake), False

    def get_intake(self, intake_id):
        return next((value for value in self.intakes.values() if value["intake_id"] == intake_id), None)

    def update_intake(self, intake):
        self.intakes[intake["operation_key"]] = dict(intake)
        return dict(intake)

    def list_records(self, **_filters):
        return list(self.records)

    def get_record(self, _record_id):
        return self.records[0] if self.records else None

    def save_draft(self, draft):
        self.drafts[draft["draft_id"]] = dict(draft)
        return dict(draft)

    def get_draft(self, draft_id):
        draft = self.drafts.get(draft_id)
        return dict(draft) if draft else None

    def update_draft(self, draft, expected_revision):
        current = self.drafts.get(draft["draft_id"])
        if current is None:
            raise ValueError("hardware draft not found")
        if current["revision"] != expected_revision:
            raise ValueError("stale draft revision")
        self.drafts[draft["draft_id"]] = dict(draft)
        return dict(draft)


class FakePublisher:
    def __init__(self):
        self.accepted = []

    def publish(self, intake):
        self.accepted.append(dict(intake))
        return type("Result", (), {"status": "published", "record_id": "hwm_demo", "path": "02_Hardware/demo.md", "mode": "rest", "mirror_status": "upserted"})()


class FakeMediaService:
    def manifest(self, record_id):
        return [{"photo_id": "p0", "content_type": "image/jpeg", "alt": f"photo for {record_id}"}]

    def read(self, record_id, photo_id):
        return "image/jpeg", f"{record_id}:{photo_id}".encode("utf-8")


class HardwareServiceTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.publisher = FakePublisher()
        self.service = HardwareService(
            self.store,
            self.publisher,
            intake_id_factory=lambda: f"hwi_{len(self.store.intakes) + 1}",
            clock=lambda: "2026-08-04T12:00:00+08:00",
            operator_id="server-operator",
        )

    def test_submit_persists_review_pending_intake_and_reuses_operation_key(self):
        payload = {"channel": "web", "submitted_by": "TZ", "operation_key": "op-demo", "draft": valid_model()}

        first = self.service.submit(payload)
        second = self.service.submit(payload)

        self.assertEqual(first["status"], "review_pending")
        self.assertEqual(second["outcome"], "idempotent_reuse")
        self.assertEqual(first["intake_id"], second["intake_id"])

    def test_accept_updates_intake_and_publishes_only_after_snapshot_check(self):
        submitted = self.service.submit({"channel": "codex", "submitted_by": "TZ", "operation_key": "op-accept", "draft": valid_model()})

        result = self.service.accept(submitted["intake_id"], "TZ", submitted["snapshot_hash"])

        self.assertEqual(result["status"], "published")
        self.assertEqual(len(self.publisher.accepted), 1)
        self.assertEqual(self.publisher.accepted[0]["intake_status"], "accepted")

    def test_accept_rejects_missing_intake(self):
        with self.assertRaises(ValueError):
            self.service.accept("hwi_missing", "TZ", "sha256:" + "a" * 64)

    def test_list_relations_projects_record_edges(self):
        record = valid_model()
        record["relations"] = [{"relation_type": "used_by", "ref": "agent12"}]
        self.store.records.append(record)

        edges = self.service.list_relations()

        self.assertEqual(
            edges,
            [{"source": record["hardware_model_id"], "relation_type": "used_by", "target": "agent12"}],
        )

    def test_record_projection_includes_safe_photo_manifest(self):
        record = valid_model()
        self.store.records.append(record)
        service = HardwareService(self.store, self.publisher, media_service=FakeMediaService())

        result = service.get_record(record["hardware_model_id"])

        self.assertEqual(result["photos"], [{"photo_id": "p0", "content_type": "image/jpeg", "alt": f"photo for {record['hardware_model_id']}"}])

    def test_record_projection_includes_user_facing_chinese_display_name(self):
        record = valid_model()
        self.store.records.append(record)

        result = self.service.get_record(record["hardware_model_id"])

        self.assertEqual(result["display_name_zh"], "ESP32-S3 开发板")

    def test_inventory_summary_reports_model_stock_and_verification_metrics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            model = valid_model()
            model["hardware_model_id"] = "hwm_metrics"
            model["last_verified_at"] = None
            unit = valid_unit()
            unit["hardware_unit_id"] = "hwu_metrics"
            unit["model_ref"] = "hwm_metrics"
            store.upsert_record(model, "02_Hardware/10_Models/Controllers/HWM - metrics.md")
            store.upsert_record(unit, "02_Hardware/20_Units/agent12/HWU - metrics.md")

            summary = HardwareService(store, self.publisher).list_inventory_summary()

            self.assertEqual(summary["metrics"]["item_count"], 1)
            self.assertEqual(summary["metrics"]["in_stock_model_count"], 1)
            self.assertEqual(summary["metrics"]["quantity_available"], 1)
            self.assertEqual(summary["metrics"]["needs_verification_count"], 1)
            self.assertEqual(summary["metrics"]["needs_info_count"], 1)

    def test_photo_read_is_delegated_without_exposing_internal_reference(self):
        service = HardwareService(self.store, self.publisher, media_service=FakeMediaService())

        content_type, payload = service.read_photo("hwm_demo", "p0")

        self.assertEqual((content_type, payload), ("image/jpeg", b"hwm_demo:p0"))

    def test_simple_draft_uses_versioned_single_confirmation_bundle(self):
        draft = self.service.create_draft(draft_id_factory=lambda: "hwd_demo")
        patched = self.service.patch_draft(
            draft["draft_id"],
            draft["revision"],
            {"display_name": "Demo board", "quantity": 2, "inventory_action": "new", "category": "controller"},
        )

        prepared = self.service.prepare_draft(patched["draft_id"], patched["revision"], "TZ")
        repeated = self.service.prepare_draft(patched["draft_id"], patched["revision"], "TZ")

        self.assertEqual(prepared["status"], "review_pending")
        self.assertEqual(repeated["bundle_hash"], prepared["bundle_hash"])
        self.assertEqual(len(prepared["intakes"]), 2)
        self.assertTrue(prepared["bundle_hash"].startswith("sha256:"))
        with self.assertRaisesRegex(ValueError, "stale draft revision"):
            self.service.patch_draft(draft["draft_id"], draft["revision"], {"quantity": 9})

    def test_draft_acceptance_uses_server_operator_not_browser_assertion(self):
        draft = self.service.create_draft(draft_id_factory=lambda: "hwd_accept")
        patched = self.service.patch_draft(
            draft["draft_id"],
            draft["revision"],
            {"display_name": "Demo board", "quantity": 1, "inventory_action": "new"},
        )
        prepared = self.service.prepare_draft(patched["draft_id"], patched["revision"], "TZ")

        self.service.accept_draft(prepared["draft_id"], prepared["bundle_hash"], "browser-assertion")

        self.assertEqual(
            {item["acceptance"]["accepted_by"] for item in self.publisher.accepted},
            {"server-operator"},
        )

    def test_attachment_is_private_hashed_and_does_not_return_a_filesystem_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            service = HardwareService(
                self.store,
                self.publisher,
                attachment_root=tmpdir,
                operator_id="server-operator",
            )
            draft = service.create_draft(draft_id_factory=lambda: "hwd_photo")
            payload = b"\x89PNG\r\n\x1a\n" + b"safe"

            result = service.attach_draft(
                draft["draft_id"],
                draft["revision"],
                "board.png",
                "image/png",
                base64.b64encode(payload).decode("ascii"),
            )

            self.assertNotIn("path", result["attachment"])
            stored = next(Path(tmpdir).joinpath("hwd_photo").iterdir())
            self.assertEqual(os.stat(stored).st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
