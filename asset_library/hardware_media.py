"""Fail-closed projection and delivery of hardware photos.

The hardware API must never expose the vault path, attachment path, or the
stored ``photo_refs`` values.  This module turns those internal references into
short public photo IDs and only serves bounded, validated image bytes.
"""

import re
from pathlib import Path


PUBLIC_ROOT = Path("02_Hardware") / "90_Evidence" / "photos"
MAX_PHOTOS_PER_RECORD = 12
MAX_BYTES = 12 * 1024 * 1024
_PRIVATE_ATTACHMENT = re.compile(r"^hat_[0-9a-f]{64}$")
_PHOTO_ID = re.compile(r"^p[0-9]{1,2}$")


class HardwareMediaService:
    """Resolve approved hardware photo references without leaking local paths."""

    def __init__(self, store, vault_path, attachment_root):
        self.store = store
        self.vault_path = Path(vault_path).resolve()
        self.attachment_root = Path(attachment_root).resolve() if attachment_root else None

    def manifest(self, record_id):
        return [
            {
                "photo_id": photo_id,
                "content_type": content_type,
                "alt": f"硬件实物照片 {int(photo_id[1:]) + 1}",
            }
            for photo_id, content_type, _target in self._entries(record_id)
        ]

    def read(self, record_id, photo_id):
        if not isinstance(photo_id, str) or not _PHOTO_ID.fullmatch(photo_id):
            raise ValueError("hardware photo is not available")
        for current_id, content_type, target in self._entries(record_id):
            if current_id != photo_id:
                continue
            try:
                payload = target.read_bytes()
            except OSError as exc:
                raise ValueError("hardware photo is not available") from exc
            if len(payload) > MAX_BYTES or _content_type_from_bytes(payload) != content_type:
                raise ValueError("hardware photo is not available")
            return content_type, payload
        raise ValueError("hardware photo is not available")

    def _references(self, record_id):
        record = self.store.get_record(record_id)
        if not isinstance(record, dict):
            return []
        references = record.get("photo_refs")
        return [value for value in references if isinstance(value, str)] if isinstance(references, list) else []

    def _entries(self, record_id):
        entries = []
        for reference in self._references(record_id):
            target = self._resolve(reference)
            if target is None or _content_type(target) is None:
                continue
            entries.append((f"p{len(entries)}", _content_type(target), target))
            if len(entries) >= MAX_PHOTOS_PER_RECORD:
                break
        return entries

    def _resolve(self, reference):
        if _PRIVATE_ATTACHMENT.fullmatch(reference):
            return self._resolve_private(reference)
        return self._resolve_public(reference)

    def _resolve_public(self, reference):
        reference_path = Path(reference)
        if reference_path.is_absolute() or reference_path.parts[: len(PUBLIC_ROOT.parts)] != PUBLIC_ROOT.parts:
            return None
        root = (self.vault_path / PUBLIC_ROOT).resolve()
        candidate = (self.vault_path / reference_path).resolve()
        if not _inside(candidate, root) or not candidate.is_file():
            return None
        return candidate

    def _resolve_private(self, reference):
        if self.attachment_root is None or not self.attachment_root.is_dir():
            return None
        digest = reference[4:]
        try:
            candidates = self.attachment_root.rglob(digest)
        except OSError:
            return None
        for candidate in candidates:
            try:
                resolved = candidate.resolve()
            except OSError:
                continue
            if _inside(resolved, self.attachment_root) and resolved.is_file() and resolved.name == digest:
                return resolved
        return None


def _inside(candidate, root):
    return candidate == root or root in candidate.parents


def _content_type(path):
    if path is None:
        return None
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        with path.open("rb") as handle:
            header = handle.read(12)
    except OSError:
        return None
    return _content_type_from_bytes(header)


def _content_type_from_bytes(payload):
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "image/webp"
    return None

