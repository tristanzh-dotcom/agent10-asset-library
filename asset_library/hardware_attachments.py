"""Bounded image payload validation for private hardware drafts."""

import base64
import binascii
import struct
import zlib

MAX_IMAGE_BYTES = 12 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_image_payload(content_type, payload):
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("only JPEG, PNG, or WebP images are accepted")
    if not isinstance(payload, bytes) or not payload or len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("image payload exceeds the size limit")
    signatures = {"image/png": b"\x89PNG\r\n\x1a\n", "image/jpeg": b"\xff\xd8\xff", "image/webp": b"RIFF"}
    if not payload.startswith(signatures[content_type]):
        raise ValueError("image payload signature does not match its content type")
    return content_type


def decode_image_payload(value):
    if not isinstance(value, str):
        raise ValueError("image payload must be base64 text")
    try:
        payload = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("image payload is not valid base64") from exc
    if len(payload) > MAX_IMAGE_BYTES:
        raise ValueError("image payload exceeds the size limit")
    return payload


def sanitize_image_payload(content_type, payload):
    """Remove EXIF container chunks without decoding or rewriting pixels."""

    validate_image_payload(content_type, payload)
    if content_type == "image/jpeg":
        return _strip_jpeg_exif(payload)
    if content_type == "image/png":
        return _strip_png_exif(payload)
    if content_type == "image/webp":
        return _strip_webp_exif(payload)
    return payload


def _strip_jpeg_exif(payload):
    output = bytearray(payload[:2])
    index = 2
    saw_scan = False
    saw_frame = False
    while index + 1 < len(payload):
        if payload[index] != 0xFF:
            raise ValueError("malformed JPEG container")
        if payload[index + 1] == 0xFF:
            output.append(0xFF)
            index += 1
            continue
        marker = payload[index + 1]
        if marker == 0xD9:
            if not saw_scan or index + 2 != len(payload):
                raise ValueError("malformed JPEG end marker")
            return bytes(output) + payload[index:]
        if marker in {0x00, 0xD8} or 0xD0 <= marker <= 0xD7:
            raise ValueError("malformed JPEG marker")
        if marker == 0x01:
            output.extend(payload[index:index + 2])
            index += 2
            continue
        if index + 4 > len(payload):
            raise ValueError("truncated JPEG segment")
        length = int.from_bytes(payload[index + 2:index + 4], "big")
        end = index + 2 + length
        if end > len(payload) or length < 2:
            raise ValueError("truncated JPEG segment")
        segment = payload[index:end]
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if length < 8 or not segment[9] or length != 8 + 3 * segment[9] or not all(struct.unpack(">HH", segment[5:9])):
                raise ValueError("invalid JPEG frame header")
            precision = segment[4]
            allowed_precision = {8} if marker == 0xC0 else range(2, 17) if marker in {0xC3, 0xC7, 0xCB, 0xCF} else {8, 12}
            if precision not in allowed_precision:
                raise ValueError("invalid JPEG sample precision")
            saw_frame = True
        if not (marker == 0xE1 and segment[4:10] == b"Exif\x00\x00"):
            output.extend(segment)
        index = end
        if marker == 0xDA:
            if not saw_frame or length < 6 or not segment[4] or length != 6 + 2 * segment[4]:
                raise ValueError("invalid JPEG scan header")
            saw_scan = True
            start = index
            while index < len(payload):
                if payload[index] != 0xFF:
                    index += 1
                elif index + 1 < len(payload) and (payload[index + 1] == 0x00 or 0xD0 <= payload[index + 1] <= 0xD7):
                    index += 2
                else:
                    break
            output.extend(payload[start:index])
    raise ValueError("truncated JPEG container")


def _strip_png_exif(payload):
    signature = b"\x89PNG\r\n\x1a\n"
    output = bytearray(signature)
    index = len(signature)
    saw_header = saw_pixels = False
    while index + 12 <= len(payload):
        length = struct.unpack(">I", payload[index:index + 4])[0]
        end = index + 12 + length
        if end > len(payload):
            raise ValueError("truncated PNG chunk")
        chunk_type = payload[index + 4:index + 8]
        data = payload[index + 8:end - 4]
        if zlib.crc32(chunk_type + data) != struct.unpack(">I", payload[end - 4:end])[0]:
            raise ValueError("invalid PNG chunk checksum")
        if not saw_header:
            if chunk_type != b"IHDR" or length != 13 or not all(struct.unpack(">II", data[:8])):
                raise ValueError("invalid PNG header")
            saw_header = True
            depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if data[8] not in depths.get(data[9], set()) or data[10:12] != b"\x00\x00" or data[12] not in {0, 1}:
                raise ValueError("invalid PNG image format")
        elif chunk_type == b"IHDR":
            raise ValueError("duplicate PNG header")
        if chunk_type == b"IDAT":
            saw_pixels = True
        if chunk_type != b"eXIf":
            output.extend(payload[index:end])
        index = end
        if chunk_type == b"IEND":
            if length or not saw_pixels or index != len(payload):
                raise ValueError("invalid PNG end chunk")
            return bytes(output)
    raise ValueError("truncated PNG container")


def _strip_webp_exif(payload, frame=False):
    if len(payload) < 12 or payload[8:12] != b"WEBP" or struct.unpack("<I", payload[4:8])[0] != len(payload) - 8:
        raise ValueError("invalid WebP container")
    output = bytearray(payload[:12])
    index = 12
    saw_pixels = False
    while index + 8 <= len(payload):
        chunk_type = payload[index:index + 4]
        if frame and chunk_type not in {b"ALPH", b"VP8 ", b"VP8L"}:
            raise ValueError("invalid WebP frame subchunk")
        length = struct.unpack("<I", payload[index + 4:index + 8])[0]
        end = index + 8 + length + (length % 2)
        if end > len(payload):
            raise ValueError("truncated WebP chunk")
        if chunk_type in {b"VP8 ", b"VP8L", b"ANMF"}:
            data = payload[index + 8:index + 8 + length]
            if chunk_type == b"VP8L" and (length < 5 or data[0] != 0x2F or data[4] & 0xE0):
                raise ValueError("invalid WebP lossless header")
            if chunk_type == b"VP8 " and (length < 10 or data[3:6] != b"\x9d\x01\x2a"):
                raise ValueError("invalid WebP lossy header")
            if chunk_type == b"VP8 ":
                width, height = struct.unpack("<HH", data[6:10])
                if data[0] & 1 or ((data[0] >> 1) & 7) > 3 or not data[0] & 0x10 or not width & 0x3FFF or not height & 0x3FFF:
                    raise ValueError("invalid WebP lossy frame header")
            if chunk_type == b"ANMF":
                if length < 24:
                    raise ValueError("invalid WebP animation frame")
                frame_bytes = data[16:]
                _strip_webp_exif(b"RIFF" + struct.pack("<I", len(frame_bytes) + 4) + b"WEBP" + frame_bytes, frame=True)
            saw_pixels = True
        if chunk_type != b"EXIF":
            chunk = bytearray(payload[index:end])
            if chunk_type == b"VP8X":
                if length != 10:
                    raise ValueError("invalid WebP extended header")
                chunk[8] &= ~0x08
            output.extend(chunk)
        index = end
    if index != len(payload) or not saw_pixels:
        raise ValueError("truncated WebP container")
    output[4:8] = struct.pack("<I", len(output) - 8)
    return bytes(output)
