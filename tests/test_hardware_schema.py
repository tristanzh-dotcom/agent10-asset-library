import copy
import unittest

from asset_library.hardware_schema import validate_hardware_draft


def valid_evidence(level="label_or_photo"):
    evidence = {
        "claim": "identity",
        "level": level,
        "source_ref": "photo:front",
    }
    if level == "measured":
        evidence.update(
            {
                "tool": "digital_caliper",
                "method": "body edges, excluding cables",
                "measured_at": "2026-08-04T12:00:00+08:00",
            }
        )
    return evidence


def valid_model():
    return {
        "record_type": "hardware_model",
        "hardware_model_id": "hwm_esp32-s3-dev-kit-n16r8",
        "canonical_name": "ESP32-S3 Development Kit N16R8",
        "manufacturer": "Waveshare",
        "model_or_sku": "ESP32-S3-DEV-KIT-N16R8-M",
        "category": "controller",
        "lifecycle_status": "candidate",
        "status": "active",
        "nominal_dimensions": {
            "length_mm": 90,
            "width_mm": 25,
            "height_mm": 5,
            "measurement_scope": "body",
            "source_ref": "vendor:manual",
        },
        "interfaces": [{"name": "USB-C", "kind": "power_and_data"}],
        "electrical": {"logic_voltage": "3.3V"},
        "installation_constraints": {},
        "compatibility": {},
        "technical_documents": [],
        "photo_refs": [],
        "scope_refs": ["agent12"],
        "relations": [],
        "evidence_records": [valid_evidence()],
        "last_verified_at": "2026-08-04T12:00:00+08:00",
    }


def valid_unit():
    return {
        "record_type": "hardware_unit",
        "hardware_unit_id": "hwu_agent12-esp32-s3-001",
        "model_ref": "hwm_esp32-s3-dev-kit-n16r8",
        "inventory_kind": "single",
        "quantity_total": 1,
        "quantity_available": 1,
        "quantity_reserved": 0,
        "ownership_scope": "agent12",
        "storage_location": "dry_storage",
        "condition": "new",
        "availability_status": "available",
        "measured_dimensions": [],
        "weight_g": None,
        "photo_refs": [],
        "layout_refs": [],
        "relations": [],
        "evidence_records": [valid_evidence()],
        "last_verified_at": "2026-08-04T12:00:00+08:00",
        "status": "active",
    }


def valid_layout():
    return {
        "record_type": "assembly_layout",
        "layout_id": "lay_agent12-waterproof-box-v1",
        "title": "Agent12 Waterproof Box V1",
        "scope": "agent12",
        "target": "waterproof_enclosure",
        "status": "draft",
        "member_refs": ["hwu_agent12-esp32-s3-001"],
        "constraints": {"dry_zone": True, "drip_loop_required": True},
        "assumptions": [],
        "open_questions": ["measure internal clearances"],
        "evidence_refs": ["photo:box"],
        "evidence_records": [valid_evidence("measured")],
        "last_reviewed_at": "2026-08-04T12:00:00+08:00",
    }


class HardwareSchemaTests(unittest.TestCase):
    def test_valid_model_has_no_errors(self):
        self.assertEqual(validate_hardware_draft(valid_model()), [])

    def test_valid_unit_requires_model_reference_and_counts(self):
        self.assertEqual(validate_hardware_draft(valid_unit()), [])

    def test_valid_layout_requires_members_and_constraints(self):
        self.assertEqual(validate_hardware_draft(valid_layout()), [])

    def test_unknown_record_type_is_rejected(self):
        errors = validate_hardware_draft({"record_type": "device"})
        self.assertIn(
            "record_type must be one of hardware_model, hardware_unit, assembly_layout",
            errors,
        )

    def test_missing_evidence_is_rejected(self):
        draft = valid_model()
        draft["evidence_records"] = []
        self.assertIn(
            "evidence_records must contain at least one record",
            validate_hardware_draft(draft),
        )

    def test_sensitive_hardware_identity_fields_are_rejected(self):
        draft = valid_unit()
        draft["identity"] = {"mac_address": "AA:BB:CC:DD:EE:FF"}
        self.assertIn(
            "mac_address is not allowed in hardware records",
            validate_hardware_draft(draft),
        )

    def test_validation_does_not_mutate_input(self):
        draft = valid_model()
        original = copy.deepcopy(draft)

        validate_hardware_draft(draft)

        self.assertEqual(draft, original)


if __name__ == "__main__":
    unittest.main()
