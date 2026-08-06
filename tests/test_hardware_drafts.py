import unittest

from asset_library.hardware_drafts import compile_draft_to_records
from asset_library.hardware_schema import validate_hardware_draft


class HardwareDraftTests(unittest.TestCase):
    def test_new_simple_draft_compiles_to_valid_model_and_inventory_batch(self):
        records = compile_draft_to_records(
            {
                "draft_id": "hwd_demo",
                "display_name": "ESP32-S3 development board",
                "quantity": 2,
                "inventory_action": "new",
                "category": "controller",
                "note": "new boards for the next controller build",
            },
            model_id_factory=lambda _draft: "hwm_esp32-s3-development-board",
            unit_id_factory=lambda _draft, _model: "hwu_shared-esp32-s3-development-board-batch-1",
        )

        self.assertEqual(records["model"]["hardware_model_id"], "hwm_esp32-s3-development-board")
        self.assertEqual(records["unit"]["model_ref"], "hwm_esp32-s3-development-board")
        self.assertEqual(records["unit"]["quantity_total"], 2)
        self.assertEqual(records["unit"]["quantity_available"], 2)
        self.assertEqual(validate_hardware_draft(records["model"]), [])
        self.assertEqual(validate_hardware_draft(records["unit"]), [])

    def test_merge_simple_draft_creates_only_a_new_inventory_batch(self):
        records = compile_draft_to_records(
            {
                "draft_id": "hwd_more",
                "display_name": "ignored when merging",
                "quantity": 3,
                "inventory_action": "merge",
                "merge_target_id": "hwm_existing",
            },
            model_id_factory=lambda _draft: self.fail("merge must not create a model"),
            unit_id_factory=lambda _draft, model: f"hwu_shared-{model}-batch-2",
        )

        self.assertIsNone(records["model"])
        self.assertEqual(records["unit"]["model_ref"], "hwm_existing")
        self.assertEqual(records["unit"]["quantity_total"], 3)

    def test_compiled_records_retain_reference_and_private_attachment_ids(self):
        records = compile_draft_to_records(
            {
                "draft_id": "hwd_demo",
                "inventory_action": "new",
                "display_name": "Demo board",
                "quantity": 1,
                "category": "controller",
                "reference": {
                    "url": "https://vendor.example/manual",
                    "content_sha256": "sha256:" + "a" * 64,
                },
                "attachments": [{"attachment_id": "hat_abc", "sha256": "sha256:" + "b" * 64}],
            },
            model_id_factory=lambda _draft: "hwm_demo",
            unit_id_factory=lambda _draft, _model: "hwu_demo",
        )

        document = records["model"]["technical_documents"][0]
        self.assertEqual(document["url"], "https://vendor.example/manual")
        self.assertEqual(document["content_sha256"], "sha256:" + "a" * 64)
        self.assertEqual(records["model"]["photo_refs"], ["hat_abc"])

    def test_simple_draft_requires_name_quantity_and_explicit_inventory_action(self):
        with self.assertRaisesRegex(ValueError, "display_name"):
            compile_draft_to_records(
                {"draft_id": "hwd_missing", "quantity": 1, "inventory_action": "new"},
                model_id_factory=lambda _draft: "hwm_x",
                unit_id_factory=lambda _draft, _model: "hwu_x",
            )
        with self.assertRaisesRegex(ValueError, "quantity"):
            compile_draft_to_records(
                {"draft_id": "hwd_missing", "display_name": "Demo", "inventory_action": "new"},
                model_id_factory=lambda _draft: "hwm_x",
                unit_id_factory=lambda _draft, _model: "hwu_x",
            )
        with self.assertRaisesRegex(ValueError, "inventory_action"):
            compile_draft_to_records(
                {"draft_id": "hwd_missing", "display_name": "Demo", "quantity": 1},
                model_id_factory=lambda _draft: "hwm_x",
                unit_id_factory=lambda _draft, _model: "hwu_x",
            )


if __name__ == "__main__":
    unittest.main()
