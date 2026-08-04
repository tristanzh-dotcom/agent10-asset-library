import copy
import unittest

from asset_library.hardware_intake import (
    accept_hardware_intake,
    prepare_hardware_intake,
    snapshot_hash,
)
from tests.test_hardware_schema import valid_model


def prepared_intake():
    return prepare_hardware_intake(
        valid_model(),
        "codex",
        "TZ",
        "op-model-1",
        intake_id_factory=lambda: "hwi_1",
        clock=lambda: "2026-08-04T12:00:00+08:00",
    )


class HardwareIntakeTests(unittest.TestCase):
    def test_prepare_adds_channel_provenance_revision_and_snapshot(self):
        result = prepared_intake()

        self.assertEqual(result["intake_channel"], "codex")
        self.assertEqual(result["submitted_by"], "TZ")
        self.assertEqual(result["intake_status"], "review_pending")
        self.assertEqual(result["draft_revision"], 1)
        self.assertTrue(result["snapshot_hash"].startswith("sha256:"))

    def test_prepare_rejects_unknown_channel_and_invalid_draft(self):
        with self.assertRaises(ValueError):
            prepare_hardware_intake(valid_model(), "unknown", "TZ", "op-1")

        invalid = valid_model()
        invalid["evidence_records"] = []
        with self.assertRaises(ValueError):
            prepare_hardware_intake(invalid, "web", "TZ", "op-2")

    def test_accept_requires_matching_snapshot_and_review_pending_state(self):
        intake = prepared_intake()

        accepted = accept_hardware_intake(
            intake,
            "TZ",
            intake["snapshot_hash"],
            "2026-08-04T12:05:00+08:00",
        )

        self.assertEqual(accepted["intake_status"], "accepted")
        self.assertEqual(accepted["acceptance"]["accepted_by"], "TZ")
        self.assertEqual(accepted["acceptance"]["accepted_revision"], 1)

        with self.assertRaises(ValueError):
            accept_hardware_intake(intake, "TZ", "sha256:" + "0" * 64)

    def test_accept_rejects_changed_snapshot(self):
        intake = prepared_intake()
        changed = copy.deepcopy(intake)
        changed["canonical_name"] = "Changed after review"

        with self.assertRaises(ValueError):
            accept_hardware_intake(changed, "TZ", intake["snapshot_hash"])

    def test_accept_does_not_mutate_original_intake(self):
        intake = prepared_intake()

        accept_hardware_intake(intake, "TZ", intake["snapshot_hash"])

        self.assertNotIn("acceptance", intake)
        self.assertEqual(intake["intake_status"], "review_pending")

    def test_snapshot_hash_is_stable_for_mapping_order(self):
        first = {"b": 2, "a": {"d": 4, "c": 3}}
        second = {"a": {"c": 3, "d": 4}, "b": 2}

        self.assertEqual(snapshot_hash(first), snapshot_hash(second))


if __name__ == "__main__":
    unittest.main()
