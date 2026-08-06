import tempfile
import unittest
from pathlib import Path

from asset_library.hardware_schema import validate_hardware_draft
from asset_library.hardware_seed import (
    PHOTO_MANIFEST,
    PHOTO_TARGET_ROOT,
    build_agent12_records,
    build_seed_records,
    copy_hardware_photos,
)


class HardwareSeedTests(unittest.TestCase):
    def test_seed_records_validate_and_keep_unknown_measurements_explicit(self):
        records = build_seed_records()

        self.assertEqual(len([r for r in records if r["record_type"] == "hardware_model"]), 11)
        self.assertEqual(len([r for r in records if r["record_type"] == "hardware_unit"]), 10)
        for record in records:
            self.assertEqual(validate_hardware_draft(record), [], record.get("hardware_model_id") or record.get("hardware_unit_id"))
            for ref in record.get("photo_refs", []):
                self.assertFalse(ref.startswith("/"))
        enclosure = next(r for r in records if r.get("hardware_model_id") == "hwm_abs-waterproof-box-200x120x75")
        self.assertEqual(enclosure["nominal_dimensions"]["length_mm"], 200)
        self.assertIsNone(enclosure["last_verified_at"])

    def test_photo_manifest_has_twelve_files_and_excludes_ds_store(self):
        files = [filename for filenames in PHOTO_MANIFEST.values() for filename in filenames]

        self.assertEqual(len(files), 12)
        self.assertNotIn(".DS_Store", files)
        self.assertEqual(len(set(files)), 12)

    def test_photo_copy_is_idempotent_and_rejects_changed_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "source"
            vault = Path(tmpdir) / "vault"
            source.mkdir()
            for filename in [name for names in PHOTO_MANIFEST.values() for name in names]:
                (source / filename).write_bytes(filename.encode("utf-8"))
            (source / ".DS_Store").write_bytes(b"ignore")

            first = copy_hardware_photos(source, vault)
            second = copy_hardware_photos(source, vault)

            self.assertEqual(len(first.copied), 12)
            self.assertEqual(first.reused, ())
            self.assertEqual(len(second.reused), 12)
            self.assertEqual(second.copied, ())
            self.assertTrue((vault / PHOTO_TARGET_ROOT / "ESP32-S3-Front.jpg").exists())

            (vault / PHOTO_TARGET_ROOT / "WAGO.jpg").write_bytes(b"changed")
            with self.assertRaises(ValueError):
                copy_hardware_photos(source, vault)


if __name__ == "__main__":
    unittest.main()
