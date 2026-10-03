import base64
import unittest
import struct
import zlib
from asset_library.hardware_attachments import decode_image_payload, sanitize_image_payload, validate_image_payload


def png_chunk(kind, data=b""):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def valid_png(exif=False):
    return (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + (png_chunk(b"eXIf", b"private") if exif else b"")
            + png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + png_chunk(b"IEND"))


def valid_jpeg(exif=False):
    return (b"\xff\xd8" + (b"\xff\xe1\x00\x0eExif\x00\x00secret" if exif else b"")
            + b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00"
            + b"\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x01\xff\x00\x02\xff\xd9")


class HardwareAttachmentsTests(unittest.TestCase):
    def test_jpeg_rejects_impossible_sample_precision_for_each_sof_family(self):
        for marker, precision in ((0xC0, 0), (0xC0, 12), (0xC1, 9), (0xC2, 0), (0xC3, 1), (0xC7, 17), (0xC9, 0), (0xCF, 0)):
            payload = bytearray(valid_jpeg(True))
            sof = payload.index(b"\xff\xc0")
            payload[sof + 1] = marker
            payload[sof + 4] = precision
            with self.subTest(marker=marker, precision=precision), self.assertRaises(ValueError):
                sanitize_image_payload("image/jpeg", bytes(payload))

    def test_jpeg_keeps_allowed_sof_precision_and_original_pixel_bytes(self):
        for marker, precision in ((0xC0, 8), (0xC1, 12), (0xC2, 8), (0xC3, 2), (0xC3, 16), (0xC5, 12), (0xC6, 8), (0xC7, 8), (0xC9, 12), (0xCA, 8), (0xCB, 16), (0xCD, 12), (0xCE, 8), (0xCF, 2)):
            payload = bytearray(valid_jpeg(True))
            sof = payload.index(b"\xff\xc0")
            payload[sof + 1] = marker
            payload[sof + 4] = precision
            expected = bytes(payload).replace(b"\xff\xe1\x00\x0eExif\x00\x00secret", b"")
            with self.subTest(marker=marker, precision=precision):
                self.assertEqual(sanitize_image_payload("image/jpeg", bytes(payload)), expected)

    def test_webp_rejects_impossible_vp8_dimensions_and_frame_tag_bits(self):
        for width, height, tag in ((0, 1, 0x10), (1, 0, 0x10), (0x4000, 1, 0x10), (1, 1, 0x11), (1, 1, 0x18), (1, 1, 0)):
            data = bytes([tag, 0, 0]) + b"\x9d\x01\x2a" + struct.pack("<HH", width, height)
            chunk = b"VP8 " + struct.pack("<I", len(data)) + data
            payload = b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk
            with self.subTest(width=width, height=height, tag=tag), self.assertRaises(ValueError):
                sanitize_image_payload("image/webp", payload)

    def test_webp_keeps_valid_vp8_header_and_encoded_pixel_bytes(self):
        for tag in (0x10, 0x12, 0x14, 0x16):
            data = bytes([tag, 0, 0]) + b"\x9d\x01\x2a\x01\xc0\x02\x80" + b"pixel!"
            chunk = b"VP8 " + struct.pack("<I", len(data)) + data
            exif = b"EXIF\x08\x00\x00\x00private!"
            payload = b"RIFF" + struct.pack("<I", len(chunk + exif) + 4) + b"WEBP" + chunk + exif
            expected = b"RIFF" + struct.pack("<I", len(chunk) + 4) + b"WEBP" + chunk
            with self.subTest(tag=tag):
                self.assertEqual(sanitize_image_payload("image/webp", payload), expected)

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
        payload = valid_jpeg(True)

        sanitized = sanitize_image_payload("image/jpeg", payload)

        self.assertNotIn(b"Exif", sanitized)
        self.assertTrue(sanitized.startswith(b"\xff\xd8"))
        self.assertEqual(sanitized, valid_jpeg())

    def test_sanitizer_rejects_truncated_containers_instead_of_retaining_metadata(self):
        for kind, data in (
            ("image/png", valid_png(True)[:-12]),
            ("image/jpeg", b"\xff\xd8\xff\xe1\x00\x40Exif\x00\x00private"),
            ("image/webp", b"RIFF\x20\x00\x00\x00WEBPEXIF\x20\x00\x00\x00private"),
        ):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                sanitize_image_payload(kind, data)

    def test_png_and_webp_sanitizing_preserves_pixel_chunks(self):
        png = valid_png(True)
        self.assertEqual(sanitize_image_payload("image/png", png), valid_png())
        chunks = b"VP8L\x0a\x00\x00\x00\x2f\x00\x00\x00\x00pixel" + b"EXIF\x08\x00\x00\x00private!"
        webp = b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + chunks
        expected = b"RIFF\x16\x00\x00\x00WEBPVP8L\x0a\x00\x00\x00\x2f\x00\x00\x00\x00pixel"
        self.assertEqual(sanitize_image_payload("image/webp", webp), expected)

    def test_sanitizer_rejects_invalid_image_headers_even_with_complete_container(self):
        bad_png = (b"\x89PNG\r\n\x1a\n" + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 99, 0, 0, 0))
                   + png_chunk(b"IDAT", b"pixels") + png_chunk(b"IEND"))
        bad_webp = b"RIFF\x0e\x00\x00\x00WEBPVP8L\x02\x00\x00\x00xx"
        bad_jpeg = b"\xff\xd8\xff\xda\x00\x02pixels\xff\xd9"
        for kind, data in (("image/png", bad_png), ("image/webp", bad_webp), ("image/jpeg", bad_jpeg)):
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                sanitize_image_payload(kind, data)

    def test_webp_frame_cannot_hide_metadata_in_invalid_nested_chunks(self):
        frame = b"\x00" * 16 + b"VP8L\x0a\x00\x00\x00\x2f\x00\x00\x00\x00pixel" + b"EXIF\x08\x00\x00\x00private!"
        chunks = b"ANMF" + struct.pack("<I", len(frame)) + frame
        payload = b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WEBP" + chunks
        with self.assertRaises(ValueError):
            sanitize_image_payload("image/webp", payload)


if __name__ == "__main__":
    unittest.main()
