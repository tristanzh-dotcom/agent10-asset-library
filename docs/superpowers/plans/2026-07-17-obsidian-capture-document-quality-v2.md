# Obsidian Capture 文档质量 V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Obsidian Capture task documents evidence-grounded, non-duplicated, task-bounded, manually editable, and correctly queryable in Obsidian Base.

**Architecture:** Keep the append-only session ledger immutable, add an append-only event-to-task assignment ledger, and treat Markdown cards/daily reports/Base as reversible materialized views. Separate evidence completeness, readability, and publication eligibility. Semantic enrichment remains disabled unless the approved product route is registered and available.

**Tech Stack:** Python 3 standard library, `unittest`, JSON/JSONL, Markdown/YAML, existing Agent10 draft contract, Obsidian Bases.

## Global Constraints

- Authority: `docs/superpowers/specs/2026-07-17-obsidian-capture-document-quality-v2-design.md`.
- Preserve raw ledger, existing Agent10 asset IDs/bodies, archived legacy notes, and unrelated dirty worktree changes.
- All state and rendering behavior is strict TDD; every deterministic behavior starts with an observed failing test.
- Default runtime stays deterministic and makes zero external model calls until `obsidian_capture_terminal_enrichment` is registered in `GLOBAL_MODEL_ROUTING_RECORD.md`.
- Never store commands, patches, tool-output bodies, credentials, account data, or raw transcripts in task cards or model input.
- Git writes remain Agent08-only. `Codex-Ops` is not a Git worktree; record test evidence and hashes instead.

---

### Task 1: Event-to-task attribution and terminal boundary

**Files:**
- Modify: `Codex-Ops/codex-capture/codex_capture/storage.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/tasks.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/runtime.py`
- Modify: `Codex-Ops/codex-capture/tests/test_storage.py`
- Modify: `Codex-Ops/codex-capture/tests/test_tasks.py`
- Modify: `Codex-Ops/codex-capture/tests/test_runtime.py`

**Interfaces:**
- `CaptureStorage.assign_event(session_key, sequence, task_id, reason, now) -> dict`
- `CaptureStorage.event_refs_for_task(task_id) -> list[str]`
- `CaptureStorage.events_for_task(task_id) -> list[dict]`
- `CaptureStorage.bind_session(session_key, task_id, history=True) -> None`
- `TaskEngine.resolve(...) -> TaskResolution(task, assignment_reason)`

- [ ] Write failing tests proving two tasks in one session read disjoint events, terminal candidate plus a non-continuation prompt creates a new task, and `继续/补充/当前任务` preserve the prior task.
- [ ] Run `python3 -m unittest tests.test_storage tests.test_tasks tests.test_runtime -v`; confirm the failure is missing attribution or wrong task identity.
- [ ] Add append-only `indexes/event-assignments/<session>.jsonl`, `current_task_id`, and `task_history`; retain compatibility with old `task_id` thread indexes.
- [ ] Assign each meaningful/confirmation/material event only after task resolution; use the assignment index rather than all session events for task reads.
- [ ] Re-run focused tests and full Capture suite.

### Task 2: Structured source items and three-dimensional quality

**Files:**
- Create: `Codex-Ops/codex-capture/codex_capture/extraction.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/tasks.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/quality.py`
- Modify: `Codex-Ops/codex-capture/tests/test_quality_rendering.py`
- Modify: `Codex-Ops/codex-capture/tests/test_tasks.py`

**Interfaces:**
- `extract_source_items(event, event_ref) -> list[dict]`
- `deduplicate_source_items(items) -> list[dict]`
- `evaluate_document(task) -> DocumentQuality`
- `DocumentQuality(evidence_score, evidence_state, readability_state, publication_eligibility, blockers)`

- [ ] Write red tests for non-duplicated result/work/verification items, Markdown-safe title extraction, active task `not_terminal`, and conflicting/verbose content detection.
- [ ] Run the targeted tests; observe failures against current single score and repeated results renderer.
- [ ] Implement deterministic heading/list/sentence extraction with stable source-item IDs and no free-text inference.
- [ ] Replace the old public quality decision with evidence, readability, and eligibility fields while retaining backward-compatible legacy fields during migration.
- [ ] Re-run focused and full Capture tests.

### Task 3: Managed Markdown cards, manual preservation, daily reports, and Base

**Files:**
- Modify: `Codex-Ops/codex-capture/codex_capture/rendering.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/runtime.py`
- Modify: `Codex-Ops/codex-capture/config/obsidian-capture.base`
- Modify: `Codex-Ops/codex-capture/tests/test_quality_rendering.py`
- Modify: `Codex-Ops/codex-capture/tests/test_runtime.py`
- Modify: `Codex-Ops/codex-capture/tests/test_migration.py`

**Interfaces:**
- `render_task_card(task, quality, existing_text="") -> str`
- `render_daily_report(report_date, project, tasks, automation, existing_text="") -> str`
- `extract_manual_block(text) -> str | None`
- `validate_managed_block(text, expected_digest) -> bool`

- [ ] Write failing golden tests proving manual blocks are byte-preserved, duplicate prose is absent, daily Frontmatter is queryable, and malformed managed markers fail closed.
- [ ] Run those tests and verify the current renderer fails due to duplicated result sections and missing daily properties.
- [ ] Implement revisioned managed/manual markers, render digests, title cleanup, concise sections, and task/daily frontmatter.
- [ ] Update Base views to restrict folders, query daily reports, distinguish eligibility/readability, and include both formal asset types.
- [ ] Run the rendering, runtime, migration, and full Capture suites.

### Task 4: Safe refresh and historical state repartition

**Files:**
- Create: `Codex-Ops/codex-capture/codex_capture/refresh.py`
- Create: `Codex-Ops/codex-capture/bin/codex_capture_refresh.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/migration.py`
- Modify: `Codex-Ops/codex-capture/tests/test_migration.py`
- Create: `Codex-Ops/codex-capture/tests/test_refresh.py`

**Interfaces:**
- `RenderRefresher.scan(now) -> dict`
- `RenderRefresher.apply(report, now) -> dict`
- `RenderRefresher.rollback(digest, now) -> dict`
- `TaskRepartitioner.scan(now) -> dict`
- `TaskRepartitioner.apply(report, now) -> dict`

- [ ] Write red tests for dry-run/no-write, source-digest mismatch, managed-card backup, manual-conflict refusal, same-session terminal split, and rollback.
- [ ] Run `python3 -m unittest tests.test_refresh tests.test_migration -v`; confirm each fails for absent operations.
- [ ] Implement timestamped backup paths, report pointers, collision checks, task-state/thread-index re-partition, and legacy index cards without touching legacy asset bodies.
- [ ] Add CLI with explicit `--dry-run`, `--apply`, and `--rollback`; expected failures return nonzero safe JSON.
- [ ] Run temporary-Vault E2E: old mixed state -> dry-run -> apply -> semantic-free readable cards/reports -> rollback.

### Task 5: Agent10 contract and dormant semantic-enhancement boundary

**Files:**
- Modify: `agent10-asset-library/asset_library/schema.py`
- Modify: `agent10-asset-library/asset_library/frontmatter.py`
- Modify: `agent10-asset-library/tests/test_codex_capture_producer.py`
- Modify: `agent10-asset-library/tests/test_contract_rendering.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/publishing.py`
- Create: `Codex-Ops/codex-capture/codex_capture/enrichment.py`
- Create: `Codex-Ops/codex-capture/tests/test_enrichment.py`

**Interfaces:**
- Agent10 accepts flat V2 evidence/readability/eligibility properties while retaining V1 compatibility.
- `build_enrichment_request(task, source_items) -> dict | None`
- `validate_enrichment_response(response, source_items) -> dict | None`

- [ ] Write red tests for V2 frontmatter preservation, stale V1 asset compatibility, disabled enrichment producing no request, and invalid/unknown-source output rejection.
- [ ] Implement only local request construction and strict response validation; no network client or route activation in this task.
- [ ] Keep `semantic_enhancement_enabled=false` until a separately reviewed model-routing change supplies provider and credentials.
- [ ] Run Capture tests, all Agent10 tests, and the affected Web supervisor contract tests.

### Task 6: Live rollout and evidence

**Files:**
- Modify: `Codex-Ops/codex-capture/config/obsidian-capture.base` only through Task 3
- Create: migration/refresh reports under the existing Vault ledger paths only after temporary-Vault acceptance

- [ ] Run all Capture tests, Agent10 tests, Web supervisor tests, Python compilation, and `git diff --check`.
- [ ] Run live `codex_capture_refresh.py --dry-run`; inspect counts and conflicts without exposing note bodies.
- [ ] Apply only if dry-run reports zero manual conflicts and expected source digests; validate task cards, daily reports, Base views, and preserved backups.
- [ ] Do not activate semantic enrichment: report the separate model-route registration prerequisite rather than silently selecting a provider.
- [ ] Record final file hashes, test counts, live command results, remaining risks, and no-Git-write status.

## V2 Implementation Token Forecast

| Work | Input tokens | Output tokens |
|---|---:|---:|
| Attribution/state migration and tests | 34,000–48,000 | 8,000–12,000 |
| Extraction, quality, rendering, Base | 42,000–60,000 | 10,000–15,000 |
| Refresh/repartition and temporary-Vault E2E | 35,000–52,000 | 8,000–13,000 |
| Agent10 compatibility, regressions, live rollout | 30,000–45,000 | 6,000–10,000 |
| **Total** | **141,000–205,000** | **32,000–50,000** |

Recommended reserve: 190,000 input and 44,000 output tokens. Stop and report before exceeding 235,000 input or 55,000 output tokens. This forecast excludes any optional external-model calls; the default implementation performs zero such calls.

## Plan Self-Review

- Spec coverage: Tasks 1–6 cover task boundaries, event attribution, structured extraction, quality, manual ownership, daily/Base, historical refresh, V1 compatibility, disabled enrichment, and live acceptance.
- Placeholder review: every production change has a named file, interface, red test, verification command, and expected result.
- Type review: Task 1 produces attributed events consumed by Task 2; Task 2 produces `DocumentQuality` consumed by Task 3 and Task 5; Task 4 operates only on Task 1–3 persisted forms.
- Scope review: semantic runtime activation is intentionally excluded until a provider/data-egress route is explicitly registered; no unrelated Web or Agent10 supervisor behavior changes.
