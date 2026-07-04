SUPPORTED_SCHEMA_VERSION = 1

DEFAULTS = {
    "asset_schema_version": 1,
    "status": "active",
    "knowledge_status": "not_indexed",
    "source_status": "unverified",
    "sensitivity": "normal",
    "source_refs": [],
    "input_refs": [],
    "file_refs": [],
    "export_refs": [],
    "subject_refs": [],
    "collection_refs": [],
    "tags": [],
    "hash_source": "",
}


def normalize_asset_frontmatter(frontmatter):
    normalized = dict(frontmatter)
    changes = []
    version = normalized.get("asset_schema_version", 1)
    if int(version) != SUPPORTED_SCHEMA_VERSION:
        raise ValueError(f"unsupported asset_schema_version: {version}")

    if "knowledge_status" not in normalized and "rag_status" in normalized:
        normalized["knowledge_status"] = normalized["rag_status"]
        changes.append("mapped rag_status to knowledge_status")

    for field, default in DEFAULTS.items():
        if field not in normalized or normalized[field] in (None, ""):
            normalized[field] = _copy_default(default)
            changes.append(f"added default {field}={default}")

    return normalized, changes


def _copy_default(value):
    if isinstance(value, list):
        return list(value)
    return value
