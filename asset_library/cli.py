import json
from pathlib import Path

from .hardware_schema import validate_hardware_draft
from .schema import validate_draft


def run_cli(argv, service):
    if not argv:
        return 1, _usage()
    command = argv[0]
    try:
        if command == "validate-draft":
            draft = _read_json_arg(argv, 1)
            errors = validate_draft(draft)
            if errors:
                return 1, "\n".join(errors)
            return 0, "OK"
        if command == "validate-hardware":
            draft = _read_json_arg(argv, 1)
            errors = validate_hardware_draft(draft)
            if errors:
                return 1, "\n".join(errors)
            return 0, "OK"
        if command == "prepare-hardware":
            draft = _read_json_arg(argv, 1)
            if len(argv) < 5:
                raise ValueError("channel, submitted_by, and operation_key are required")
            result = _require_method(service, "submit")(
                {
                    "channel": argv[2],
                    "submitted_by": argv[3],
                    "operation_key": argv[4],
                    "draft": draft,
                }
            )
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
        if command == "accept-hardware":
            if len(argv) < 4:
                raise ValueError("intake_id, accepted_by, and expected_snapshot_hash are required")
            result = _require_method(service, "accept")(
                argv[1],
                argv[2],
                argv[3],
            )
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
        if command == "ingest-draft":
            result = service.ingest_draft(_read_json_arg(argv, 1))
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
        if command == "ingest-migration":
            result = service.ingest_migration_draft(_read_json_arg(argv, 1))
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
        if command == "ingest-agent06":
            if len(argv) < 2:
                return 1, "source_asset_path is required"
            result = service.ingest_producer_asset("agent06", {"source_asset_path": argv[1]})
            return 0, json.dumps(result, ensure_ascii=False, sort_keys=True)
    except Exception as exc:
        return 1, str(exc)
    return 1, _usage()


def _read_json_arg(argv, index):
    if len(argv) <= index:
        raise ValueError("json path is required")
    return json.loads(Path(argv[index]).read_text(encoding="utf-8"))


def _usage():
    return (
        "usage: validate-draft <draft.json> | validate-hardware <draft.json> | "
        "prepare-hardware <draft.json> <channel> <submitted_by> <operation_key> | "
        "accept-hardware <intake_id> <accepted_by> <expected_snapshot_hash> | "
        "ingest-draft <draft.json> | ingest-migration <draft.json> | "
        "ingest-agent06 <source_asset_path>"
    )


def _require_method(service, method_name):
    method = getattr(service, method_name, None)
    if method is None:
        raise ValueError(f"configured service does not support {method_name}")
    return method
