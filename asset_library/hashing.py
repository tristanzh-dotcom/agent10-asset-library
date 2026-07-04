import hashlib
import json


NON_BODY_HASH_SOURCE = "metadata_v1_plus_identity_attachment_sha256_list"


def compute_body_hash(body_markdown):
    body = "" if body_markdown is None else str(body_markdown)
    if body.startswith("\ufeff"):
        body = body[1:]
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_non_body_hash(draft):
    metadata = {
        "asset_type": draft.get("asset_type", ""),
        "agent_id": draft.get("agent_id", ""),
        "source_asset_path": draft.get("source_asset_path", ""),
        "title": draft.get("title", ""),
        "workflow_id": draft.get("workflow_id", ""),
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    attachment_hashes = _identity_attachment_hashes(draft.get("file_refs", []))
    attachment_json = json.dumps(
        attachment_hashes,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    payload = metadata_json.encode("utf-8") + b"|" + attachment_json.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}", NON_BODY_HASH_SOURCE


def _identity_attachment_hashes(file_refs):
    selected = [ref for ref in file_refs if ref.get("primary") is True]
    if not selected:
        selected = [ref for ref in file_refs if ref.get("identity") is True]
    hashes = []
    for ref in sorted(selected, key=lambda item: str(item.get("path", ""))):
        hashes.append(
            {
                "path": str(ref.get("path", "")),
                "sha256": _bytes_sha256(ref.get("bytes", b"")),
            }
        )
    return hashes


def _bytes_sha256(value):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()
