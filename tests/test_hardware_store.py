import tempfile
import unittest
import sqlite3
import hashlib
from pathlib import Path

from asset_library.hardware_store import HardwareStore
from asset_library.hardware_intake import prepare_hardware_intake
from tests.test_hardware_schema import valid_model, valid_unit


def intake(operation_key="op-1", draft=None):
    return prepare_hardware_intake(
        draft or valid_model(),
        "codex",
        "TZ",
        operation_key,
        intake_id_factory=lambda: f"hwi_{operation_key}",
        clock=lambda: "2026-08-04T12:00:00+08:00",
    )


class HardwareStoreTests(unittest.TestCase):
    def test_all_readers_leave_absent_empty_and_partial_databases_unchanged(self):
        for state in ("absent", "empty", "partial"):
            with self.subTest(state=state), tempfile.TemporaryDirectory() as tmpdir:
                store = HardwareStore(Path(tmpdir) / "private" / "hardware.sqlite3")
                if state == "empty":
                    store.db_path.parent.mkdir()
                    sqlite3.connect(store.db_path).close()
                elif state == "partial":
                    store.save_intake(intake())
                    with sqlite3.connect(store.db_path) as conn:
                        for table in ("hardware_records", "hardware_drafts", "hardware_analysis_jobs", "hardware_mirror_gaps"):
                            conn.execute("drop table " + table)
                if state != "absent":
                    store.db_path.chmod(0o640)
                    before_hash = hashlib.sha256(store.db_path.read_bytes()).hexdigest()
                    with sqlite3.connect(store.db_path) as conn:
                        before_schema = conn.execute("select type, name, sql from sqlite_master order by type, name").fetchall()
                    before_files = set(store.db_path.parent.iterdir())
                readers = (
                    (lambda: store.get_intake("missing"), None),
                    (store.count_intakes, 1 if state == "partial" else 0),
                    (lambda: store.get_draft("missing"), None),
                    (lambda: store.get_analysis_job_by_operation("missing"), None),
                    (lambda: store.get_analysis_job("missing"), None),
                    (lambda: store.get_record("missing"), None),
                    (store.list_records, []),
                    (store.inventory_summary, []),
                    (store.count_records, 0),
                    (store.open_gap_count, 0),
                    (lambda: store.same_record_primary_intents(valid_model()["hardware_model_id"]), []),
                )
                for reader, expected in readers:
                    self.assertEqual(reader(), expected)
                if state == "absent":
                    self.assertFalse(store.db_path.parent.exists())
                else:
                    self.assertEqual(hashlib.sha256(store.db_path.read_bytes()).hexdigest(), before_hash)
                    self.assertEqual(store.db_path.stat().st_mode & 0o777, 0o640)
                    with sqlite3.connect(store.db_path) as conn:
                        self.assertEqual(conn.execute("select type, name, sql from sqlite_master order by type, name").fetchall(), before_schema)
                    self.assertEqual(set(store.db_path.parent.iterdir()), before_files)
                store.save_intake(intake("op-next"))
                self.assertEqual(store.count_intakes(), 2 if state == "partial" else 1)
                self.assertEqual(store.db_path.stat().st_mode & 0o777, 0o600)

    def test_private_hardware_db_permissions_are_tightened_only_by_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "private" / "hardware.sqlite3")
            self.assertIsNone(store.get_intake("missing"))
            self.assertFalse(store.db_path.parent.exists())
            store.save_intake(intake())
            self.assertEqual(store.db_path.stat().st_mode & 0o777, 0o600)
            store.db_path.chmod(0o644)
            store.get_intake("hwi_op-1")
            self.assertEqual(store.db_path.stat().st_mode & 0o777, 0o644)
            store.update_intake(intake())
            self.assertEqual(store.db_path.stat().st_mode & 0o777, 0o600)

    def test_save_intake_reuses_same_operation_key_without_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            first, reused = store.save_intake(intake())
            second, reused_again = store.save_intake(intake())

            self.assertFalse(reused)
            self.assertTrue(reused_again)
            self.assertEqual(first["intake_id"], second["intake_id"])
            self.assertEqual(store.count_intakes(), 1)

    def test_save_intake_rejects_changed_snapshot_for_same_operation_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            store.save_intake(intake())
            changed = valid_model()
            changed["canonical_name"] = "Changed model"

            with self.assertRaises(ValueError):
                store.save_intake(intake(draft=changed))

    def test_record_upsert_and_query_are_redacted_to_record_projection(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            record = valid_unit()
            record["hardware_unit_id"] = "hwu_agent12-board-001"
            record["submitted_by"] = "TZ"

            store.upsert_record(record, "02_Hardware/20_Units/agent12/HWU - board - hwu_agent12-board-001.md")
            rows = store.list_records(record_type="hardware_unit", scope="agent12")
            detail = store.get_record("hwu_agent12-board-001")

            self.assertEqual(len(rows), 1)
            self.assertEqual(detail["record_type"], "hardware_unit")
            self.assertNotIn("submitted_by", detail)
            self.assertEqual(store.count_records(), 1)

    def test_inventory_summary_groups_units_by_model_and_aggregates_counts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            model = valid_model()
            model["hardware_model_id"] = "hwm_demo"
            model["canonical_name"] = "Demo board"
            model["category"] = "controller"
            first = valid_unit()
            first["hardware_unit_id"] = "hwu_demo-a"
            first["model_ref"] = "hwm_demo"
            first["quantity_total"] = 2
            first["quantity_available"] = 1
            second = valid_unit()
            second["hardware_unit_id"] = "hwu_demo-b"
            second["model_ref"] = "hwm_demo"
            second["quantity_total"] = 3
            second["quantity_available"] = 3

            store.upsert_record(model, "02_Hardware/10_Models/Controllers/HWM - Demo.md")
            store.upsert_record(first, "02_Hardware/20_Units/agent12/HWU - demo-a.md")
            store.upsert_record(second, "02_Hardware/20_Units/agent12/HWU - demo-b.md")

            self.assertEqual(
                store.inventory_summary(),
                [
                    {
                        "item_id": "hwm_demo",
                        "display_name": "Demo board",
                        "manufacturer": "Waveshare",
                        "model_or_sku": "ESP32-S3-DEV-KIT-N16R8-M",
                        "category": "开发板",
                        "quantity_total": 5,
                        "quantity_available": 4,
                        "status": "ready",
                    }
                ],
            )

    def test_draft_store_preserves_revision_and_rejects_stale_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            original = store.save_draft({"draft_id": "hwd_demo", "revision": 1, "status": "editing"})
            updated = store.update_draft({**original, "revision": 2, "status": "prepared"}, 1)

            self.assertEqual(store.get_draft("hwd_demo"), updated)
            with self.assertRaisesRegex(ValueError, "stale draft revision"):
                store.update_draft({**updated, "revision": 3}, 1)


if __name__ == "__main__":
    unittest.main()
