# Agent10 V1 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` task-by-task. Git write operations remain owned by Agent08.

**Goal:** Harden and assemble Agent10 V1 for safe Agent06-only operation.

**Architecture:** Keep existing focused components, enforce the approved behavior in the writer and API boundaries, add a small runtime composition root, and preserve Obsidian as the asset UI. All mutations are explicit and all governance reads are side-effect free.

**Tech Stack:** Python 3 standard library, PyYAML already available in the local runtime, SQLite, unittest, Obsidian Local REST API.

## Global Constraints

- Same idempotent key means reuse without update.
- Normal producers cannot provide final asset IDs.
- Governance GET is strictly read-only.
- V1 supports Agent06 only; Agent05 is excluded.
- No Git commit, push, pull, stash, or rebase from this repository.

### Task 1: Contract and YAML hardening

**Files:** Modify `asset_library/schema.py`, `asset_library/frontmatter.py`, `asset_library/writer.py`; test `tests/test_contract_rendering.py`, `tests/test_writer.py`.

- [x] Add failing tests for invalid agent IDs, paths, hashes, timestamps, schema versions, malformed refs, and YAML-sensitive strings.
- [x] Run the focused tests and confirm the expected failures.
- [x] Implement strict validation and safe YAML rendering.
- [x] Run focused and full tests.

### Task 2: Asset ID and collision policy

**Files:** Modify `asset_library/writer.py`, `asset_library/collision.py`, `asset_library/producer_api.py`; test `tests/test_writer.py`, `tests/test_collision.py`, `tests/test_producer_api.py`.

- [x] Add failing tests proving normal drafts reject supplied IDs, controlled migration accepts valid IDs, reuse performs no update, and generated collisions retry five times.
- [x] Run the focused tests and confirm failure for the missing behavior.
- [x] Implement separate normal/migration methods and mandatory collision handling.
- [x] Run focused and full tests.

### Task 3: Concurrency, journals, and read-only governance

**Files:** Modify `asset_library/locking.py`, `asset_library/writer.py`, `asset_library/sqlite_mirror.py`, `asset_library/knowledge_bridge.py`, `asset_library/governance.py`; test matching test modules.

- [x] Add failing tests for shared REST locking, atomic Mirror Gap replacement, and side-effect-free governance snapshots.
- [x] Run focused tests and confirm expected failures.
- [x] Implement read-only inspection separately from explicit recovery.
- [ ] Complete component-level shared locking for Mirror Gap Scanner and Promotion Journal when the production retry/reconciliation adapters are wired.
- [x] Run focused and full tests.

### Task 4: Agent06 and runtime composition

**Files:** Modify `asset_library/adapters/agent06.py`, `asset_library/cli.py`; create `asset_library/runtime.py`, `asset_library/__main__.py`; test `tests/test_agent06_adapter.py`, `tests/test_cli.py`, `tests/test_runtime.py`.

- [x] Add failing tests for status-aligned Agent06 tags, runtime construction, safe localhost configuration, side-effect-free startup, and separate migration commands.
- [x] Run focused tests and confirm expected failures.
- [x] Implement the minimal runtime and CLI entrypoint.
- [x] Run focused and full tests.

### Task 5: Documentation and release verification

**Files:** Modify `docs/OBSIDIAN_ASSET_LIBRARY_USER_AUDIT_20260704.md`, `docs/OBSIDIAN_PHASE1_IMPLEMENTATION_STATUS_20260704.md`; create or update operational instructions if required.

- [x] Mark the four TZ decisions as authoritative and remove Agent05 from active V1 scope.
- [x] Record actual runtime and production activation status without claiming unverified live integration.
- [ ] Run unit tests, compile checks, diff checks, and live read-only probes.
- [ ] Report any remaining action that requires Obsidian trust flow, shared Web publication, or another repository owner.
