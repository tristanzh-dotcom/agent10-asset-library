import hashlib
import tempfile
import unittest
from pathlib import Path

from asset_library.hardware_media import HardwareMediaService


class FakeHardwareStore:
    def __init__(self, records):
        self.records = records

    def get_record(self, record_id):
        return self.records.get(record_id)


class HardwareMediaServiceTests(unittest.TestCase):
    def test_manifest_exposes_safe_photo_ids_without_source_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            photo = root / "02_Hardware" / "90_Evidence" / "photos" / "agent11" / "board.jpg"
            photo.parent.mkdir(parents=True)
            photo.write_bytes(b"\xff\xd8\xff" + b"jpeg-data")
            service = HardwareMediaService(
                FakeHardwareStore({"hwm_demo": {"hardware_model_id": "hwm_demo", "photo_refs": ["02_Hardware/90_Evidence/photos/agent11/board.jpg"]}}),
                root,
                root / "99_System" / "audit" / "hardware-drafts",
            )

            manifest = service.manifest("hwm_demo")

            self.assertEqual(manifest, [{"photo_id": "p0", "content_type": "image/jpeg", "alt": "硬件实物照片 1"}])
            self.assertNotIn("board.jpg", str(manifest))
            self.assertNotIn(str(root), str(manifest))

    def test_read_accepts_public_photo_and_private_sanitized_attachment(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            public_photo = root / "02_Hardware" / "90_Evidence" / "photos" / "board.png"
            public_photo.parent.mkdir(parents=True)
            public_photo.write_bytes(b"\x89PNG\r\n\x1a\n" + b"png-data")
            private_bytes = b"RIFFxxxxWEBPprivate"
            digest = hashlib.sha256(private_bytes).hexdigest()
            private_photo = root / "99_System" / "audit" / "hardware-drafts" / "hwd_demo" / digest
            private_photo.parent.mkdir(parents=True)
            private_photo.write_bytes(private_bytes)
            service = HardwareMediaService(
                FakeHardwareStore({"hwm_demo": {"hardware_model_id": "hwm_demo", "photo_refs": [
                    "02_Hardware/90_Evidence/photos/board.png",
                    f"hat_{digest}",
                ]}}),
                root,
                root / "99_System" / "audit" / "hardware-drafts",
            )

            self.assertEqual(service.read("hwm_demo", "p0"), ("image/png", b"\x89PNG\r\n\x1a\n" + b"png-data"))
            self.assertEqual(service.read("hwm_demo", "p1"), ("image/webp", private_bytes))

    def test_read_fails_closed_for_unknown_ids_traversal_and_non_images(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            safe_dir = root / "02_Hardware" / "90_Evidence" / "photos"
            safe_dir.mkdir(parents=True)
            safe = safe_dir / "safe.jpg"
            safe.write_bytes(b"not-an-image")
            service = HardwareMediaService(
                FakeHardwareStore({"hwm_demo": {"hardware_model_id": "hwm_demo", "photo_refs": [
                    "02_Hardware/90_Evidence/photos/safe.jpg",
                    "02_Hardware/90_Evidence/photos/../safe.jpg",
                ]}}),
                root,
                root / "99_System" / "audit" / "hardware-drafts",
            )

            self.assertEqual(service.manifest("missing"), [])
            self.assertEqual(service.manifest("hwm_demo"), [])
            with self.assertRaises(ValueError):
                service.read("hwm_demo", "p0")
            with self.assertRaises(ValueError):
                service.read("hwm_demo", "../p0")


if __name__ == "__main__":
    unittest.main()
