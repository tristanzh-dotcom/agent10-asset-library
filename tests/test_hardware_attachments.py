import base64
import unittest
from asset_library.hardware_attachments import decode_image_payload, sanitize_image_payload, validate_image_payload


class HardwareAttachmentsTests(unittest.TestCase):
    def test_accepts_limited_image_and_rejects_non_image(self):
        data = b"\x89PNG\r\n\x1a\n" + b"x"
        self.assertEqual(validate_image_payload("image/png", data), "image/png")
        with self.assertRaises(ValueError):
            validate_image_payload("text/plain", data)

    def test_base64_decoder_has_size_limit(self):
        self.assertEqual(decode_image_payload(base64.b64encode(b"abc").decode()), b"abc")
        with self.assertRaises(ValueError):
            decode_image_payload("not-base64")

    def test_sanitizer_removes_jpeg_exif_segment_before_storage_or_egress(self):
        payload = b"\xff\xd8\xff\xe1\x00\x0cExif\x00\x00secret\xff\xd9"

        sanitized = sanitize_image_payload("image/jpeg", payload)

        self.assertNotIn(b"Exif", sanitized)
        self.assertTrue(sanitized.startswith(b"\xff\xd8"))


if __name__ == "__main__":
    unittest.main()
