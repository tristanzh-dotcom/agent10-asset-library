"""Validate and adapt an Agent14 immutable archive snapshot.

The adapter deliberately has no Vault or network side effects.  It only reads a
snapshot below an explicitly configured ``snapshots`` root and returns a normal
Agent10 producer draft; the Agent10 writer remains the owner of final asset IDs
and persistence.
"""

import hashlib
import json
import mimetypes
import re
import stat as stat_module
from datetime import datetime
from os.path import abspath
from pathlib import Path


CONTRACT_VERSION = "agent14-archive:v1"
SNAPSHOT_ID_PATTERN = re.compile(r"^snap-r[1-9][0-9]*-[0-9a-f]{12}$")
OPERATION_KEY_PATTERN = re.compile(r"^agent14:[a-z0-9_-]+:r[1-9][0-9]*:sha256:[0-9a-f]{64}$")
HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
SAFE_SOURCE_PATTERN = re.compile(r"^[^/\\\x00]+$")


def agent14_snapshot_to_draft(snapshot_dir, *, snapshot_root=None):
    snapshot, root = _safe_snapshot_path(snapshot_dir, snapshot_root)
    manifest = _read_manifest(snapshot)
    _validate_manifest_shape(manifest)
    files = _validate_payload(snapshot, manifest)
    _validate_identity(snapshot, manifest, files)

    content_path = snapshot / "payload" / "content.md"
    body = content_path.read_bytes().decode("utf-8")
    source = manifest["source"]
    document = manifest["document"]
    snapshot_id = manifest["snapshotId"]
    document_id = manifest["documentId"]
    source_file_name = source["fileName"]
    title = Path(source_file_name).stem or document_id
    warning_codes = document["warningCodes"]
    file_refs = [
        {
            "role": entry["role"],
            "path": entry["path"],
            "media_type": entry["mediaType"],
            "bytes": entry["bytes"],
            "sha256": entry["sha256"],
        }
        for entry in files
    ]
    attachment_lines = "\n".join(
        f"- `{entry['path']}` ({entry['role']}, {entry['bytes']} bytes)"
        for entry in files
    )
    body_markdown = (
        f"{body.rstrip()}\n\n"
        "## Archive Summary\n\n"
        f"- document_id: `{document_id}`\n"
        f"- snapshot_id: `{snapshot_id}`\n"
        f"- revision: `{manifest['snapshotRevision']}`\n"
        f"- page_count: `{document['pageCount']}`\n"
        f"- warning_codes: `{', '.join(warning_codes) if warning_codes else 'none'}`\n"
        f"- bundle_sha256: `{document['bundleSha256']}`\n\n"
        "## Attachments\n\n"
        f"{attachment_lines}\n"
    )
    return {
        "agent_id": "agent14",
        "workflow_id": "ppt2html_archive",
        "asset_type": "agent14_document_snapshot",
        "title": title,
        "status": "active",
        "knowledge_status": "not_indexed",
        "source_status": "uncertain" if warning_codes else "grounded",
        "sensitivity": "restricted",
        "created_at": manifest["createdAt"],
        "updated_at": manifest["createdAt"],
        "source_asset_path": f"agent14://{document_id}/{snapshot_id}",
        "source_content_hash": document["bundleSha256"],
        "source_refs": [
            {
                "type": "agent14_archive_snapshot",
                "document_id": document_id,
                "snapshot_id": snapshot_id,
                "operation_key": manifest["operationKey"],
                "bundle_sha256": document["bundleSha256"],
            }
        ],
        "input_refs": [{"type": "source_file", "file_name": source_file_name, "sha256": source["sha256"]}],
        "file_refs": file_refs,
        "export_refs": [],
        "model_route": "agent14_local",
        "subject_refs": [],
        "collection_refs": [],
        "tags": ["agent/agent14", "workflow/archive", "type/agent14-document-snapshot", "knowledge/not-indexed"],
        "body_markdown": body_markdown,
    }


def _safe_snapshot_path(snapshot_dir, snapshot_root):
    if snapshot_root is None:
        raise ValueError("snapshot root is required")
    root_input = Path(snapshot_root)
    snapshot_input = Path(snapshot_dir)
    if root_input.name != "snapshots":
        raise ValueError("snapshot root must be the snapshots root")
    root_absolute = Path(abspath(root_input))
    snapshot_absolute = Path(abspath(snapshot_input))
    if snapshot_absolute.parent != root_absolute:
        raise ValueError("source path must be inside the snapshots root")
    _reject_input_links(snapshot_absolute, stop=root_absolute)
    try:
        root = root_input.resolve(strict=True)
        snapshot = snapshot_input.resolve(strict=True)
    except OSError as exc:
        raise ValueError("snapshot path is unavailable") from exc
    if not root.is_dir() or not snapshot.is_dir() or snapshot.parent != root:
        raise ValueError("source path must be inside the snapshots root")
    if not SNAPSHOT_ID_PATTERN.fullmatch(snapshot.name):
        raise ValueError("snapshot id is invalid")
    _reject_links(root, snapshot)
    return snapshot, root


def _reject_input_links(path, *, stop=None):
    current = Path(abspath(path))
    stop_path = Path(abspath(stop)) if stop is not None else None
    while True:
        try:
            info = current.lstat()
        except OSError:
            break
        if stat_module.S_ISLNK(info.st_mode):
            raise ValueError("symlink in snapshot path")
        if stop_path is not None and current == stop_path:
            break
        if current.parent == current:
            break
        current = current.parent


def _reject_links(root, snapshot):
    current = snapshot
    while True:
        try:
            info = current.lstat()
        except OSError as exc:
            raise ValueError("snapshot path is unavailable") from exc
        if stat_module.S_ISLNK(info.st_mode):
            raise ValueError("symlink in snapshot path")
        if current == root:
            break
        current = current.parent


def _read_manifest(snapshot):
    path = snapshot / "archive-manifest.json"
    try:
        info = path.lstat()
        if stat_module.S_ISLNK(info.st_mode) or not stat_module.S_ISREG(info.st_mode) or info.st_nlink > 1:
            raise ValueError("manifest file is not a regular file")
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        raise
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("archive manifest is invalid") from exc


def _validate_manifest_shape(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("archive manifest is invalid")
    if manifest.get("contractVersion") != CONTRACT_VERSION:
        raise ValueError("unsupported contract version")
    snapshot_id = manifest.get("snapshotId")
    if not isinstance(snapshot_id, str) or not SNAPSHOT_ID_PATTERN.fullmatch(snapshot_id):
        raise ValueError("snapshot id is invalid")
    document_id = manifest.get("documentId")
    if not isinstance(document_id, str) or not re.fullmatch(r"doc-[a-z0-9_-]+", document_id):
        raise ValueError("document id is invalid")
    revision = manifest.get("snapshotRevision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        raise ValueError("snapshot revision is invalid")
    operation_key = manifest.get("operationKey")
    expected_prefix = f"agent14:{document_id}:r{revision}:sha256:"
    if not isinstance(operation_key, str) or not OPERATION_KEY_PATTERN.fullmatch(operation_key) or not operation_key.startswith(expected_prefix):
        raise ValueError("operation key is invalid")
    created_at = manifest.get("createdAt")
    if not isinstance(created_at, str):
        raise ValueError("createdAt is invalid")
    try:
        datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("createdAt is invalid") from exc

    source = manifest.get("source")
    if not isinstance(source, dict):
        raise ValueError("source metadata is invalid")
    file_name = source.get("fileName")
    if not isinstance(file_name, str) or not SAFE_SOURCE_PATTERN.fullmatch(file_name):
        raise ValueError("source file name is invalid")
    if not isinstance(source.get("mediaType"), str) or not HASH_PATTERN.fullmatch(str(source.get("sha256"))):
        raise ValueError("source metadata is invalid")
    if not isinstance(source.get("originalIncluded"), bool):
        raise ValueError("source metadata is invalid")

    document = manifest.get("document")
    if not isinstance(document, dict):
        raise ValueError("document metadata is invalid")
    if not isinstance(document.get("pageCount"), int) or isinstance(document.get("pageCount"), bool) or document["pageCount"] < 0:
        raise ValueError("document metadata is invalid")
    warning_codes = document.get("warningCodes")
    if not isinstance(warning_codes, list) or any(not isinstance(item, str) or not item for item in warning_codes):
        raise ValueError("warning codes are invalid")
    if warning_codes != sorted(set(warning_codes), key=lambda item: item.encode("utf-8")):
        raise ValueError("warning codes are not canonical")
    if not HASH_PATTERN.fullmatch(str(document.get("contentSha256"))) or not HASH_PATTERN.fullmatch(str(document.get("bundleSha256"))):
        raise ValueError("document hashes are invalid")


def _validate_payload(snapshot, manifest):
    payload = snapshot / "payload"
    if not payload.is_dir():
        raise ValueError("payload is missing")
    actual = []
    for path in sorted(payload.rglob("*"), key=lambda item: item.relative_to(snapshot).as_posix().encode("utf-8")):
        relative = path.relative_to(snapshot).as_posix()
        if path.is_symlink():
            raise ValueError("symlink in payload")
        info = path.lstat()
        if path.is_dir():
            continue
        if not path.is_file() or info.st_nlink > 1:
            raise ValueError("payload contains a non-regular file")
        _validate_relative_path(relative)
        actual.append(relative)
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise ValueError("manifest file list is invalid")
    paths = [entry.get("path") if isinstance(entry, dict) else None for entry in entries]
    if any(not isinstance(path, str) for path in paths) or paths != sorted(paths, key=lambda item: item.encode("utf-8")):
        raise ValueError("manifest file list is not canonical")
    if len(paths) != len(set(paths)) or set(paths) != set(actual):
        raise ValueError("manifest file list does not match payload")
    required = {"payload/index.html", "payload/content.md", "payload/manifest.json"}
    if not required.issubset(set(paths)):
        raise ValueError("required payload file is missing")
    source = manifest["source"]
    source_paths = [path for path in paths if path.startswith("payload/source/")]
    expected_source_path = f"payload/source/{source['fileName']}"
    if source.get("originalIncluded"):
        if source_paths != [expected_source_path]:
            raise ValueError("original source file is invalid")
    elif source_paths:
        raise ValueError("original source is not allowed")

    verified = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("manifest file entry is invalid")
        path = entry["path"]
        _validate_relative_path(path)
        expected_role = _role_for(path)
        expected_media_type = _media_type_for(path)
        if entry.get("role") != expected_role or entry.get("mediaType") != expected_media_type:
            raise ValueError("manifest file metadata is invalid")
        file_path = snapshot / path
        data = file_path.read_bytes()
        if entry.get("bytes") != len(data) or entry.get("sha256") != _hash(data):
            if path == "payload/content.md":
                raise ValueError("content hash mismatch")
            raise ValueError("file hash or size mismatch")
        if path == "payload/content.md" and _normalize_markdown(data) != data:
            raise ValueError("content hash normalization mismatch")
        verified.append(entry)
    content_entry = next(entry for entry in verified if entry["path"] == "payload/content.md")
    if manifest["document"]["contentSha256"] != content_entry["sha256"]:
        raise ValueError("content hash mismatch")
    return verified


def _validate_identity(snapshot, manifest, files):
    core = {
        "contractVersion": manifest["contractVersion"],
        "documentId": manifest["documentId"],
        "snapshotRevision": manifest["snapshotRevision"],
        "source": manifest["source"],
        "document": {
            "pageCount": manifest["document"]["pageCount"],
            "warningCodes": manifest["document"]["warningCodes"],
            "contentSha256": manifest["document"]["contentSha256"],
        },
        "files": files,
    }
    bundle_hash = _hash(_canonical(core))
    if manifest["document"]["bundleSha256"] != bundle_hash:
        raise ValueError("bundle hash mismatch")
    bundle_hex = bundle_hash.split(":", 1)[1]
    expected_snapshot_id = f"snap-r{manifest['snapshotRevision']}-{bundle_hex[:12]}"
    expected_operation_key = f"agent14:{manifest['documentId']}:r{manifest['snapshotRevision']}:sha256:{bundle_hex}"
    if snapshot.name != expected_snapshot_id or manifest["snapshotId"] != expected_snapshot_id:
        raise ValueError("snapshot identity mismatch")
    if manifest["operationKey"] != expected_operation_key:
        raise ValueError("operation key mismatch")


def _validate_relative_path(path):
    if not path.startswith("payload/") or "\\" in path or path.startswith("/"):
        raise ValueError("payload path is invalid")
    parts = path.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError("payload path is invalid")


def _role_for(path):
    if path == "payload/index.html":
        return "editable_html"
    if path == "payload/content.md":
        return "content_markdown"
    if path == "payload/manifest.json":
        return "document_manifest"
    if path.startswith("payload/source/"):
        return "original_source"
    return "asset"


def _media_type_for(path):
    suffix = Path(path).suffix.lower()
    known = {
        ".html": "text/html",
        ".json": "application/json",
        ".md": "text/markdown",
        ".pdf": "application/pdf",
        ".ppt": "application/vnd.ms-powerpoint",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    return known.get(suffix, mimetypes.guess_type(path)[0] or "application/octet-stream")


def _normalize_markdown(data):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("content is not valid UTF-8") from exc
    text = text.removeprefix("\ufeff").replace("\r\n", "\n").replace("\r", "\n").rstrip("\n")
    return (text + "\n").encode("utf-8")


def _hash(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _canonical(value):
    if isinstance(value, list):
        return b"[" + b",".join(_canonical(item) for item in value) + b"]"
    if isinstance(value, dict):
        pairs = []
        for key in sorted(value, key=lambda item: str(item).encode("utf-8")):
            encoded_key = json.dumps(str(key), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            pairs.append(encoded_key + b":" + _canonical(value[key]))
        return b"{" + b",".join(pairs) + b"}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
