"""Bounded image payload validation for private hardware drafts."""

import base64
import binascii
import struct

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
    if not payload.startswith(b"\xff\xd8"):
        return payload
    output = bytearray(payload[:2])
    index = 2
    while index + 1 < len(payload):
        if payload[index] != 0xFF:
            output.extend(payload[index:])
            break
        marker = payload[index + 1]
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            output.extend(payload[index:index + 2])
            index += 2
            continue
        if index + 4 > len(payload):
            output.extend(payload[index:])
            break
        length = int.from_bytes(payload[index + 2:index + 4], "big")
        end = index + 2 + length
        if end > len(payload) or length < 2:
            output.extend(payload[index:])
            break
        segment = payload[index:end]
        if not (marker == 0xE1 and segment[4:10] == b"Exif\x00\x00"):
            output.extend(segment)
        index = end
        if marker == 0xDA:
            output.extend(payload[index:])
            break
    return bytes(output)


def _strip_png_exif(payload):
    signature = b"\x89PNG\r\n\x1a\n"
    if not payload.startswith(signature):
        return payload
    output = bytearray(signature)
    index = len(signature)
    while index + 12 <= len(payload):
        length = struct.unpack(">I", payload[index:index + 4])[0]
        end = index + 12 + length
        if end > len(payload):
            return payload
        chunk_type = payload[index + 4:index + 8]
        if chunk_type != b"eXIf":
            output.extend(payload[index:end])
        index = end
        if chunk_type == b"IEND":
            output.extend(payload[index:])
            return bytes(output)
    return payload


def _strip_webp_exif(payload):
    if not payload.startswith(b"RIFF") or payload[8:12] != b"WEBP":
        return payload
    output = bytearray(payload[:12])
    index = 12
    while index + 8 <= len(payload):
        chunk_type = payload[index:index + 4]
        length = struct.unpack("<I", payload[index + 4:index + 8])[0]
        end = index + 8 + length + (length % 2)
        if end > len(payload):
            return payload
        if chunk_type != b"EXIF":
            output.extend(payload[index:end])
        index = end
    output[4:8] = struct.pack("<I", len(output) - 8)
    return bytes(output)
