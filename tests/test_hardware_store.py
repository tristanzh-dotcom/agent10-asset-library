import tempfile
import unittest
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
