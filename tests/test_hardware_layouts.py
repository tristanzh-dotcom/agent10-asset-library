import unittest

from asset_library.hardware_layouts import build_initial_layouts, relation_projection, validate_layout_relations
from asset_library.hardware_seed import build_seed_records
from asset_library.hardware_schema import validate_hardware_draft


class HardwareLayoutsTests(unittest.TestCase):
    def test_initial_layouts_validate_against_seeded_models(self):
        records = build_seed_records()
        known_ids = [
            record.get("hardware_model_id") or record.get("hardware_unit_id")
            for record in records
        ]
        known_ids.extend(layout["layout_id"] for layout in build_initial_layouts())

        for layout in build_initial_layouts():
            self.assertEqual(validate_hardware_draft(layout), [])
            self.assertEqual(validate_layout_relations(layout, known_ids), [])
            self.assertTrue(all("password" not in str(value).lower() for value in layout.values()))

    def test_layout_relation_projection_is_stable_and_explicit(self):
        edges = relation_projection(build_initial_layouts())

        self.assertIn(
            {
                "source": "lay_agent12-dry-prototype-enclosure",
                "relation_type": "contains",
                "target": "hwm_esp32-s3-dev-kit-n16r8",
            },
            edges,
        )
        self.assertEqual(edges, sorted(edges, key=lambda edge: (edge["source"], edge["relation_type"], edge["target"])))

    def test_unknown_layout_member_is_rejected(self):
        layout = build_initial_layouts()[0]
        layout["member_refs"] = ["hwm_missing"]

        errors = validate_layout_relations(layout, set())

        self.assertIn("unknown hardware record", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
