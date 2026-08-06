import unittest

from asset_library.hardware_indexes import HardwareIndexPublisher, render_hardware_index_bundle
from tests.test_hardware_schema import valid_layout, valid_model, valid_unit


class FailingRest:
    def write_note(self, _path, _markdown):
        raise ConnectionError("rest unavailable")


class HardwareIndexesTests(unittest.TestCase):
    def test_index_bundle_renders_model_level_counts_and_links(self):
        model = valid_model()
        unit = valid_unit()
        unit["quantity_total"] = 2
        unit["quantity_available"] = 2
        records = [model, unit]

        bundle = render_hardware_index_bundle(records, generated_at="2026-08-06T12:00:00+08:00")

        home = bundle["02_Hardware/00_Index/Hardware Home.md"]
        inventory = bundle["02_Hardware/00_Index/Inventory.md"]
        self.assertIn("# Hardware Home", home)
        self.assertIn("硬件型号数 | 1", home)
        self.assertIn("可用 / 总数", home)
        self.assertIn("2 / 2", home)
        self.assertIn(
            "[[02_Hardware/10_Models/Controllers/HWM - ESP32-S3 Development Kit N16R8 - hwm_esp32-s3-dev-kit-n16r8|ESP32-S3 开发板]]",
            home,
        )
        self.assertIn("2 / 2", inventory)

    def test_index_bundle_lists_zero_inventory_and_needs_verification(self):
        model = valid_model()
        model["photo_refs"] = []
        model["last_verified_at"] = None

        bundle = render_hardware_index_bundle([model])

        self.assertIn("0 / 0", bundle["02_Hardware/00_Index/Hardware Home.md"])
        self.assertIn("ESP32-S3 开发板", bundle["02_Hardware/00_Index/Needs Verification.md"])

    def test_index_bundle_includes_layout_links_and_scope_sections(self):
        layout = valid_layout()
        bundle = render_hardware_index_bundle([valid_model(), valid_unit(), layout])

        self.assertIn("Layouts", bundle["02_Hardware/00_Index/Layouts.md"])
        self.assertIn("agent12", bundle["02_Hardware/00_Index/Inventory by Scope.md"])
        self.assertIn("lay_agent12-waterproof-box-v1", bundle["02_Hardware/00_Index/Layouts.md"])

    def test_index_bundle_has_fixed_plugin_free_paths(self):
        bundle = render_hardware_index_bundle([])

        self.assertEqual(
            set(bundle),
            {
                "02_Hardware/00_Index/Hardware Home.md",
                "02_Hardware/00_Index/Inventory.md",
                "02_Hardware/00_Index/Models by Category.md",
                "02_Hardware/00_Index/Inventory by Scope.md",
                "02_Hardware/00_Index/Layouts.md",
                "02_Hardware/00_Index/Needs Verification.md",
            },
        )
        self.assertNotIn("dataview", "".join(bundle.values()).lower())

    def test_index_publisher_reports_partial_failure_without_claiming_success(self):
        publisher = HardwareIndexPublisher(FailingRest(), None)

        result = publisher.publish([valid_model()])

        self.assertEqual(result.status, "partial")
        self.assertEqual(result.written, ())


if __name__ == "__main__":
    unittest.main()
