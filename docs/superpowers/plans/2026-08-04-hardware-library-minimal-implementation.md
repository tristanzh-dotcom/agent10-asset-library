# Hardware Library Minimal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a small, testable Agent10 core for validating multi-entry hardware drafts and recording a single final-acceptance decision without writing to the real Vault or Web.

**Architecture:** Keep hardware records separate from the existing generic asset manifest because `HardwareModel`, `HardwareUnit`, and `AssemblyLayout` have different required fields and lifecycle semantics. A pure validation module accepts one normalized hardware draft; a pure intake module adds channel/provenance/snapshot metadata and performs fail-closed acceptance. A CLI validation command provides the first Codex/local entry check; future Web and Agent adapters can consume the same functions.

**Tech Stack:** Python 3 standard library, existing `unittest` suite, JSON CLI, SHA-256 canonical snapshots.

## Global Constraints

- Do not write to `/Users/tristanzh/agent/AgentAssetVault` or any real Obsidian Vault.
- Do not copy `/Users/tristanzh/agent/agent11-fishtank-monitor/docs/hardware` photos or fetch external vendor documents.
- Do not modify `/Users/tristanzh/agent/web`, Agent12, or Agent13 in this slice.
- Reject secrets and hardware identity data such as Token, MAC, serial number, Wi-Fi credentials, or private keys.
- Preserve the approved three-record model: `hardware_model`, `hardware_unit`, `assembly_layout`.
- Preserve multi-entry semantics: Codex, Web, Obsidian draft, and future Agent adapters share the same validation/intake contract.
- Final acceptance is a human-controlled state transition on an immutable snapshot; acceptance is not physical-device commissioning.
- Git commit/stage operations remain under Agent08 Git Control; do not commit directly from this repository.

---

### Task 1: Add hardware draft validation

**Files:**
- Create: `asset_library/hardware_schema.py`
- Test: `tests/test_hardware_schema.py`

**Interfaces:**
- Produces `validate_hardware_draft(draft: Mapping[str, Any]) -> list[str]`.
- Defines `HARDWARE_RECORD_TYPES`, `EVIDENCE_LEVELS`, relation/status constants, and `SENSITIVE_KEYS` for later intake/adapter code.

- [ ] **Step 1: Write failing tests for the three valid record types and core failures**

Add tests that assert:

```python
def test_valid_model_has_no_errors():
    self.assertEqual(validate_hardware_draft(valid_model()), [])

def test_valid_unit_requires_model_reference_and_counts():
    self.assertEqual(validate_hardware_draft(valid_unit()), [])

def test_valid_layout_requires_members_and_constraints():
    self.assertEqual(validate_hardware_draft(valid_layout()), [])

def test_unknown_record_type_is_rejected():
    errors = validate_hardware_draft({"record_type": "device"})
    self.assertIn("record_type must be one of hardware_model, hardware_unit, assembly_layout", errors)

def test_missing_evidence_is_rejected():
    draft = valid_model()
    draft["evidence_records"] = []
    self.assertIn("evidence_records must contain at least one record", validate_hardware_draft(draft))

def test_sensitive_hardware_identity_fields_are_rejected():
    draft = valid_unit()
    draft["mac_address"] = "AA:BB:CC:DD:EE:FF"
    self.assertIn("mac_address is not allowed in hardware records", validate_hardware_draft(draft))
```

Use small fixture helpers in the test file that construct one valid model, unit, and layout with `official` or `measured` evidence. Keep fixture IDs stable and non-device-derived.

- [ ] **Step 2: Run the focused test file and verify it fails**

Run:

```bash
python3 -m unittest tests.test_hardware_schema -v
```

Expected: collection or assertion failure because `asset_library.hardware_schema` and `validate_hardware_draft` do not yet exist.

- [ ] **Step 3: Implement minimal validation in `asset_library/hardware_schema.py`**

Implement these exact rules:

```python
HARDWARE_RECORD_TYPES = ("hardware_model", "hardware_unit", "assembly_layout")
EVIDENCE_LEVELS = ("official", "measured", "label_or_photo", "reported", "unverified")
RELATION_TYPES = (
    "used_by", "owned_by", "part_of_layout", "compatible_with",
    "incompatible_with", "replacement_for", "reserved_for",
)
SENSITIVE_KEYS = {
    "token", "api_key", "secret", "private_key", "password", "wifi_password",
    "mac", "mac_address", "serial", "serial_number", "device_id",
}
```

Validate:

- `record_type` and stable ID prefix/pattern (`hwm_`, `hwu_`, `lay_` plus lowercase slug);
- required identity fields per record type;
- model `lifecycle_status` and `status`, unit `availability_status`/`condition`, and layout `status` enums;
- non-negative integer counts and numeric dimensions/weight;
- `evidence_records` is a non-empty list, each evidence level is valid, and `measured` evidence has `tool`, `method`, and `measured_at`;
- `relations` is a list of objects with an allowed `relation_type` and non-empty `ref`;
- `scope_refs`/`ownership_scope` use lowercase scoped IDs and no whitespace;
- recursively reject sensitive key names, while leaving unknown non-sensitive extension fields available for future versions.

Return deterministic human-readable error strings; do not mutate the input draft or make any IO calls.

- [ ] **Step 4: Run the focused test file and verify it passes**

Run:

```bash
python3 -m unittest tests.test_hardware_schema -v
```

Expected: all hardware schema tests pass.

### Task 2: Add multi-entry intake and final acceptance

**Files:**
- Create: `asset_library/hardware_intake.py`
- Test: `tests/test_hardware_intake.py`

**Interfaces:**
- `prepare_hardware_intake(draft: Mapping[str, Any], channel: str, submitted_by: str, operation_key: str, intake_id_factory: Callable[[], str] | None = None, clock: Callable[[], str] | None = None) -> dict`.
- `accept_hardware_intake(intake: Mapping[str, Any], accepted_by: str, expected_snapshot_hash: str, accepted_at: str | None = None) -> dict`.
- `snapshot_hash(payload: Mapping[str, Any]) -> str`.

- [ ] **Step 1: Write failing tests for provenance, idempotent preparation, and fail-closed acceptance**

Add tests that assert:

```python
def test_prepare_adds_channel_provenance_revision_and_snapshot():
    result = prepare_hardware_intake(valid_model(), "codex", "TZ", "op-model-1", intake_id_factory=lambda: "hwi_1", clock=lambda: "2026-08-04T12:00:00+08:00")
    self.assertEqual(result["intake_channel"], "codex")
    self.assertEqual(result["intake_status"], "review_pending")
    self.assertEqual(result["draft_revision"], 1)
    self.assertTrue(result["snapshot_hash"].startswith("sha256:"))

def test_prepare_rejects_unknown_channel_and_invalid_draft():
    with self.assertRaises(ValueError):
        prepare_hardware_intake(valid_model(), "unknown", "TZ", "op-1")

def test_accept_requires_matching_snapshot_and_review_pending_state():
    intake = prepared_intake()
    accepted = accept_hardware_intake(intake, "TZ", intake["snapshot_hash"], "2026-08-04T12:05:00+08:00")
    self.assertEqual(accepted["intake_status"], "accepted")
    self.assertEqual(accepted["acceptance"]["accepted_by"], "TZ")

    with self.assertRaises(ValueError):
        accept_hardware_intake(intake, "TZ", "sha256:" + "0" * 64)

def test_accept_does_not_mutate_original_intake():
    intake = prepared_intake()
    accept_hardware_intake(intake, "TZ", intake["snapshot_hash"])
    self.assertNotIn("acceptance", intake)
    self.assertEqual(intake["intake_status"], "review_pending")
```

- [ ] **Step 2: Run the focused test file and verify it fails**

Run:

```bash
python3 -m unittest tests.test_hardware_intake -v
```

Expected: import or assertion failure because the intake module does not yet exist.

- [ ] **Step 3: Implement pure intake functions**

Implement these rules:

- allowed channels are `codex`, `web`, `obsidian`, and `agent_adapter`;
- call `validate_hardware_draft` before adding metadata;
- return a deep copy containing `intake_id`, `intake_channel`, `submitted_by`, `operation_key`, `intake_status="review_pending"`, `draft_revision=1`, `captured_at`, and canonical `snapshot_hash`;
- canonical snapshot excludes no user fields and uses sorted JSON keys, UTF-8, compact separators, and SHA-256 formatted as `sha256:<64hex>`;
- acceptance requires `intake_status == "review_pending"` and exact snapshot hash equality;
- acceptance returns a deep copy with `intake_status="accepted"` and an `acceptance` object containing `accepted_revision`, `accepted_by`, `accepted_at`, `snapshot_hash`, and empty/default `evidence_refs` if absent;
- reject missing/blank `submitted_by`, `operation_key`, `accepted_by`, or invalid ISO timestamps;
- never write files, call Vault/Obsidian, or silently refresh a changed snapshot.

- [ ] **Step 4: Run the focused intake tests and the schema tests**

Run:

```bash
python3 -m unittest tests.test_hardware_schema tests.test_hardware_intake -v
```

Expected: all focused tests pass.

### Task 3: Expose local/Codex validation through the CLI

**Files:**
- Modify: `asset_library/cli.py`
- Modify: `asset_library/__main__.py` only if command dispatch requires it after inspection
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- Add `validate-hardware <draft.json>` to `run_cli`; it returns `(0, "OK")` for a valid hardware draft and `(1, <newline-separated errors>)` for invalid input.
- Keep `validate-draft` behavior unchanged.

- [ ] **Step 1: Write failing CLI tests**

Add tests that write a valid and invalid JSON draft to a temporary directory and assert:

```python
status, output = run_cli(["validate-hardware", str(draft_path)], service=FakeProducerService())
self.assertEqual(status, 0)
self.assertEqual(output, "OK")

status, output = run_cli(["validate-hardware", str(invalid_path)], service=FakeProducerService())
self.assertEqual(status, 1)
self.assertIn("record_type", output)
```

- [ ] **Step 2: Run the focused CLI tests and verify the new tests fail**

Run:

```bash
python3 -m unittest tests.test_cli -v
```

Expected: the new command returns usage/error instead of validating the hardware draft.

- [ ] **Step 3: Implement the command and document the read-only boundary**

Import `validate_hardware_draft` in `asset_library/cli.py`, add a command branch before service-dependent commands, and update usage text to:

```text
usage: validate-draft <draft.json> | validate-hardware <draft.json> | ingest-draft <draft.json> | ingest-migration <draft.json> | ingest-agent06 <source_asset_path>
```

Add a short README section showing:

```bash
python3 -m asset_library validate-hardware /absolute/path/to/hardware-draft.json
```

State that this command is read-only validation; it does not write the Vault, copy attachments, or perform final acceptance.

- [ ] **Step 4: Run CLI and focused hardware tests**

Run:

```bash
python3 -m unittest tests.test_cli tests.test_hardware_schema tests.test_hardware_intake -v
```

Expected: all tests pass.

### Task 4: Minimum verification and handoff

**Files:**
- No new implementation files.

- [ ] **Step 1: Run package compile and focused regression checks**

Run from `/Users/tristanzh/agent/agent10-asset-library`:

```bash
PYTHONPYCACHEPREFIX=/tmp/agent10-hardware-pycache python3 -m compileall -q asset_library tests
python3 -m unittest tests.test_hardware_schema tests.test_hardware_intake tests.test_cli -v
git diff --check
```

Expected: compile succeeds, all focused tests pass, and `git diff --check` prints no errors.

- [ ] **Step 2: Inspect the final diff and report scope**

Confirm that only Agent10 source/tests/README and the plan file changed; confirm no Vault, Web, Agent12, Agent13, photos, credentials, or external data were touched. Report any pre-existing dirty files separately.

- [ ] **Step 3: Hand off Git mutation through Agent08**

Do not run `git add`, `git commit`, branch, push, or remote operations in this repository. Provide the exact changed paths and verification results for the governed Agent08 Git Control flow.
