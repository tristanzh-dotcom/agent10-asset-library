import tempfile
import unittest
import sqlite3
from pathlib import Path

from asset_library.hardware_intake import snapshot_hash
from asset_library.hardware_notes import HardwareNotePublisher, hardware_note_path, render_hardware_note
from asset_library.hardware_store import HardwareStore
from tests.test_hardware_schema import valid_layout, valid_model, valid_unit


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
        self.assertIn("# ESP32-S3 开发板", markdown)
        self.assertIn("> ESP32-S3 Development Kit N16R8", markdown)
        self.assertIn("## Summary", markdown)
        self.assertIn("## Sources", markdown)
        self.assertIn("## Related", markdown)
        self.assertIn("## Acceptance", markdown)
        self.assertNotIn("mac_address", markdown)

    def test_render_note_uses_user_display_name_and_chinese_summary(self):
        draft = valid_model()
        draft["display_name"] = "ESP32-S3 开发板 N16R8"

        markdown = render_hardware_note(draft)

        self.assertIn("# ESP32-S3 开发板 N16R8", markdown)
        self.assertIn("## 快速信息", markdown)
        self.assertIn("| 分类 | 开发板 |", markdown)
        self.assertIn("| 型号 | ESP32-S3-DEV-KIT-N16R8-M |", markdown)

    def test_model_note_aggregates_inventory_and_links_related_records(self):
        model = valid_model()
        unit = valid_unit()
        layout = valid_layout()
        layout["title"] = "Agent12 dry prototype enclosure layout"
        layout["member_refs"] = [model["hardware_model_id"]]

        markdown = render_hardware_note(model, related_records=[model, unit, layout])

        self.assertIn("| 当前库存 | 1 / 1 |", markdown)
        self.assertIn("## 相关库存", markdown)
        self.assertIn("Agent12 库存", markdown)
        self.assertIn("## 关联布局", markdown)
        self.assertIn("Agent12 dry prototype enclosure layout", markdown)

    def test_unit_note_inherits_model_category_and_links_model(self):
        model = valid_model()
        unit = valid_unit()
        unit["scope_refs"] = ["agent12"]

        markdown = render_hardware_note(unit, related_records=[model, unit])

        self.assertIn("| 分类 | 开发板 |", markdown)
        self.assertIn("| 使用范围 | Agent12 |", markdown)
        self.assertNotIn("| 使用范围 | Agent12、Agent12 |", markdown)
        self.assertIn(
            "[ESP32-S3 开发板](<02_Hardware/10_Models/Controllers/HWM - ESP32-S3 Development Kit N16R8 - hwm_esp32-s3-dev-kit-n16r8>)",
            markdown,
        )

    def test_layout_note_uses_human_title_and_lists_member_links(self):
        model = valid_model()
        layout = valid_layout()
        layout["title"] = "Agent12 dry prototype enclosure layout"
        layout["member_refs"] = [model["hardware_model_id"]]

        markdown = render_hardware_note(layout, related_records=[model, layout])

        self.assertIn("# Agent12 dry prototype enclosure layout", markdown)
        self.assertNotIn("# lay_agent12-dry-prototype-enclosure", markdown)
        self.assertIn("## 布局成员", markdown)
        self.assertIn("ESP32-S3 开发板", markdown)

    def test_note_specs_and_sources_are_readable_without_raw_source_paths(self):
        draft = valid_model()
        draft["electrical"]["project_role"] = "low-voltage controller"
        draft["installation_constraints"] = {
            "placement": "dry enclosure; keep USB and wiring strain-relieved",
            "use": "low-voltage prototype only",
        }
        draft["technical_documents"] = [{
            "title": "Agent11 hardware build guide",
            "source_ref": "agent11-fishtank-monitor/docs/hardware-build-guide.md",
        }]

        markdown = render_hardware_note(draft)

        self.assertIn("逻辑电平：3.3V", markdown)
        self.assertIn("低压控制器", markdown)
        self.assertIn("放在干燥盒内；USB 与线缆需做应力释放", markdown)
        self.assertIn("仅限低压原型", markdown)
        self.assertIn("接口：USB-C（供电与数据）", markdown)
        self.assertNotIn('{"logic_voltage"', markdown)
        self.assertIn("## 来源与核验", markdown)
        self.assertIn("Agent11 hardware build guide", markdown)
        self.assertNotIn("link_only", markdown)
        body = markdown.split("---\n", 2)[-1]
        self.assertNotIn("agent11-fishtank-monitor/docs/hardware-build-guide.md", body)

    def test_render_note_embeds_vault_photos_and_links_known_related_records(self):
        draft = valid_model()
        draft["photo_refs"] = ["02_Hardware/90_Evidence/photos/agent11/front.jpg"]
        draft["relations"] = [{"relation_type": "part_of_layout", "ref": "lay_demo"}]

        markdown = render_hardware_note(
            draft,
            {"lay_demo": "02_Hardware/30_Layouts/agent12/LAY - demo - lay_demo"},
        )

        self.assertIn("![[02_Hardware/90_Evidence/photos/agent11/front.jpg]]", markdown)
        self.assertIn(
            "[[02_Hardware/30_Layouts/agent12/LAY - demo - lay_demo|装配布局]]",
            markdown,
        )

    def test_render_note_does_not_expose_private_attachment_paths(self):
        draft = valid_model()
        draft["photo_refs"] = ["/private/drafts/hwd_demo/front.jpg", "attachment:att_1"]

        markdown = render_hardware_note(draft)

        self.assertNotIn("/private/drafts/", markdown)
        self.assertNotIn("attachment:att_1", markdown)

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

    def test_publisher_rebuilds_indexes_after_mirror_upsert(self):
        class Rest:
            def __init__(self):
                self.calls = []

            def write_note(self, path, markdown):
                self.calls.append((path, markdown))

        class IndexPublisher:
            def __init__(self):
                self.records = []

            def publish(self, records):
                self.records.append(list(records))
                return type("Result", (), {"status": "published"})()

        with tempfile.TemporaryDirectory() as tmpdir:
            rest = Rest()
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            indexes = IndexPublisher()
            result = HardwareNotePublisher(rest, None, store, index_publisher=indexes).publish(self._accepted())

            self.assertEqual(result.status, "published")
            self.assertEqual(len(indexes.records), 1)
            self.assertEqual(len(indexes.records[0]), 1)

    def test_publisher_refreshes_related_model_card_from_mirror_context(self):
        class Rest:
            def __init__(self):
                self.calls = []

            def write_note(self, path, markdown):
                self.calls.append((path, markdown))

        class IndexPublisher:
            def publish(self, _records):
                return type("Result", (), {"status": "published"})()

        with tempfile.TemporaryDirectory() as tmpdir:
            rest = Rest()
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            model = self._accepted()
            store.upsert_record(model, hardware_note_path(model))
            unit = valid_unit()
            digest = snapshot_hash(unit)
            unit.update(
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

            result = HardwareNotePublisher(
                rest,
                None,
                store,
                index_publisher=IndexPublisher(),
            ).publish(unit)

            self.assertEqual(result.status, "published")
            writes = dict(rest.calls)
            self.assertIn(hardware_note_path(model), writes)
            self.assertIn("| 当前库存 | 1 / 1 |", writes[hardware_note_path(model)])

    def test_publisher_reports_partial_when_index_rebuild_fails(self):
        class Rest:
            def write_note(self, _path, _markdown):
                return None

        class FailingIndexes:
            def publish(self, _records):
                return type("Result", (), {"status": "partial", "error": "index unavailable"})()

        with tempfile.TemporaryDirectory() as tmpdir:
            store = HardwareStore(Path(tmpdir) / "hardware.sqlite3")
            result = HardwareNotePublisher(Rest(), None, store, index_publisher=FailingIndexes()).publish(self._accepted())

            self.assertEqual(result.status, "partial")
            self.assertEqual(result.index_status, "partial")
            self.assertEqual(result.mirror_status, "index_gap")
            self.assertEqual(store.open_gap_count(), 1)
            with sqlite3.connect(store.db_path) as connection:
                gap = connection.execute(
                    "select record_id, vault_path from hardware_mirror_gaps"
                ).fetchone()
            self.assertEqual(gap, ("hardware-indexes", "02_Hardware/00_Index"))

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
