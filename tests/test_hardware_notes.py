import tempfile
import unittest
from pathlib import Path

from asset_library.hardware_intake import snapshot_hash
from asset_library.hardware_notes import HardwareNotePublisher, hardware_note_path, render_hardware_note
from asset_library.hardware_store import HardwareStore
from tests.test_hardware_schema import valid_model


class HardwareNotesTests(unittest.TestCase):
    def test_model_note_path_is_confined_to_hardware_namespace(self):
        draft = valid_model()

        path = hardware_note_path(draft)

        self.assertEqual(
            path,
            "02_Hardware/10_Models/Controllers/HWM - ESP32-S3 Development Kit N16R8 - hwm_esp32-s3-dev-kit-n16r8.md",
        )
        self.assertTrue(path.startswith("02_Hardware/"))

    def test_render_note_contains_safe_frontmatter_and_readable_sections(self):
        draft = valid_model()
        draft["acceptance"] = {
            "status": "accepted",
            "accepted_by": "TZ",
            "snapshot_hash": "sha256:" + "a" * 64,
        }

        markdown = render_hardware_note(draft)

        self.assertTrue(markdown.startswith("---\n"))
        self.assertIn('record_type: "hardware_model"', markdown)
        self.assertIn('hardware_model_id: "hwm_esp32-s3-dev-kit-n16r8"', markdown)
        self.assertIn("# ESP32-S3 Development Kit N16R8", markdown)
        self.assertIn("## Summary", markdown)
        self.assertIn("## Sources", markdown)
        self.assertIn("## Related", markdown)
        self.assertIn("## Acceptance", markdown)
        self.assertNotIn("mac_address", markdown)

    def test_render_note_explains_link_only_reference_and_unknown_physical_fields(self):
        draft = valid_model()
        draft["technical_documents"] = [{
            "title": "Official SDK reference",
            "url": "https://vendor.example/sdk",
            "status": "link_only",
            "content_sha256": "sha256:" + "a" * 64,
        }]
        draft["nominal_dimensions"] = {}
        draft["installation_constraints"] = {}
        markdown = render_hardware_note(draft)

        self.assertIn("资料已保存，未形成硬件候选", markdown)
        self.assertIn("## 待补物理信息", markdown)
        self.assertIn("孔位", markdown)
        self.assertNotIn("/private/drafts/", markdown)

    def _accepted(self):
        draft = valid_model()
        digest = snapshot_hash(draft)
        draft.update(
            {
                "intake_status": "accepted",
                "snapshot_hash": digest,
                "acceptance": {
                    "status": "accepted",
                    "accepted_by": "TZ",
                    "snapshot_hash": digest,
                },
            }
        )
        return draft

    def test_publisher_uses_rest_and_upserts_public_record(self):
        class Rest:
            def __init__(self):
                self.calls = []

            def write_note(self, path, markdown):
                self.calls.append((path, markdown))

        with tempfile.TemporaryDirectory() as tmpdir:
            rest = Rest()
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            result = HardwareNotePublisher(rest, None, store).publish(self._accepted())

            self.assertEqual(result.status, "published")
            self.assertEqual(result.mode, "rest")
            self.assertEqual(result.mirror_status, "upserted")
            self.assertEqual(len(rest.calls), 1)
            self.assertIsNotNone(store.get_record("hwm_esp32-s3-dev-kit-n16r8"))

    def test_publisher_falls_back_when_rest_write_fails(self):
        class Rest:
            def write_note(self, _path, _markdown):
                raise ConnectionError("rest unavailable")

        class Fallback:
            def __init__(self):
                self.calls = []

            def write_note(self, path, markdown):
                self.calls.append((path, markdown))

        with tempfile.TemporaryDirectory() as tmpdir:
            fallback = Fallback()
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            result = HardwareNotePublisher(Rest(), fallback, store).publish(self._accepted())

            self.assertEqual(result.status, "published")
            self.assertEqual(result.mode, "fallback")
            self.assertEqual(len(fallback.calls), 1)

    def test_publisher_records_gap_when_local_mirror_upsert_fails(self):
        class Rest:
            def write_note(self, _path, _markdown):
                return None

        class FailingStore:
            def __init__(self):
                self.gaps = []

            def upsert_record(self, _record, _path):
                raise OSError("sqlite unavailable")

            def record_gap(self, record_id, path, reason):
                self.gaps.append((record_id, path, reason))

        store = FailingStore()
        result = HardwareNotePublisher(Rest(), None, store).publish(self._accepted())

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.mirror_status, "gap_recorded")
        self.assertEqual(len(store.gaps), 1)

    def test_publisher_rejects_unaccepted_or_changed_snapshot(self):
        accepted = self._accepted()
        with self.assertRaises(ValueError):
            HardwareNotePublisher(None, None, None).publish({**accepted, "intake_status": "review_pending"})
        with self.assertRaises(ValueError):
            HardwareNotePublisher(None, None, None).publish(
                {
                    **accepted,
                    "acceptance": {"snapshot_hash": "sha256:" + "b" * 64},
                }
            )


if __name__ == "__main__":
    unittest.main()
