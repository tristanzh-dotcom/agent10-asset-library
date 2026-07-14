# Agent06 Obsidian Integration Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `executing-plans` to execute this plan in the current session. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record Agent06 as the sole enabled Agent10 producer with an active Obsidian workflow, then prove its local write and governance trail without altering Agent06 business behavior.

**Architecture:** Agent06 remains the source workflow. Agent10 owns validated producer ingestion, the local Obsidian REST write, the rebuildable SQLite mirror, and governance snapshots. The shared Web remains a governance-only proxy and never receives an Obsidian key or producer credential.

**Tech Stack:** Python standard library HTTP service and unittest, Obsidian Local REST on loopback HTTPS, SQLite mirror, Node shared Web proxy.

## Global Constraints

- Agent06 is the only enabled V1 producer.
- Agent05 remains retired and excluded.
- A repeated idempotent submission fully reuses the original asset; it does not update a note or create a version.
- Producer submissions cannot provide a final `asset_id`; migrations use a separate, default-denied path.
- Governance GET is strictly read-only; mutations are explicit POST actions.
- No API key, control token, raw Vault note, or asset body is written to documentation, logs, source, or Web responses.
- This acceptance does not change Agent06 workflow behavior or publish new Web capabilities.

---

### Task 1: Record the authoritative onboarding state

**Files:**
- Modify: `docs/OBSIDIAN_PHASE1_IMPLEMENTATION_STATUS_20260704.md`
- Modify: `README.md`

**Consumes:** TZ confirmation that Agent06's workflow is connected to Obsidian.

**Produces:** A two-layer state record: the live Agent06-to-Obsidian workflow is active; the Agent10 producer path is the sole V1 governed intake and is independently verified by Task 2.

- [x] **Step 1: Add the confirmed state without overstating the transport.**

  Record that Agent06 is live with Obsidian, is the only enabled producer, and that Agent05 is excluded. Explicitly distinguish the workflow fact from the governed producer acceptance evidence.

- [x] **Step 2: Check the documentation contains no secrets.**

  Run: `rg -o '\\b[0-9a-fA-F]{64}\\b' README.md docs/OBSIDIAN_PHASE1_IMPLEMENTATION_STATUS_20260704.md`

  Expected: no control-token or Obsidian-key value. Literal environment-variable names and the redacted `<runtime secret>` placeholder are allowed where the security contract explains that values are not exposed.

### Task 2: Run the Agent06 producer acceptance

**Files:**
- Read: `asset_library/http_server.py`
- Read: `asset_library/producer_api.py`
- Read: `asset_library/governance.py`
- Read: `/Users/tristanzh/agent/AgentAssetVault/01_Agents/Agent06/`

**Consumes:** Agent10 localhost service, local control-token file, active Obsidian Local REST plugin, and a non-sensitive Agent06 source asset.

**Produces:** One successful governed Agent06 write or a precise blocked-state report; a fresh governance snapshot; evidence that direct unauthenticated access is refused.

- [x] **Step 1: Find an existing non-sensitive Agent06 answer asset.**

  Run a read-only search below the configured Agent06 `data_dir` for one saved answer directory. Do not inspect or print its answer body.

- [x] **Step 2: Submit that source path through the local Agent10 Agent06 producer route.**

  Read the token only into a shell variable, send it in the request header, and print only the response status plus non-secret fields (`producer_id`, `asset_id`, `mode`, `mirror_status`, `outcome`).

- [x] **Step 3: Repeat the identical submission.**

  Verify that it returns the same asset identifier with `idempotent_reuse`, and does not change the note or create a new mirror row.

- [x] **Step 4: Verify governance and access boundaries.**

  Verify the Web governance proxy returns 200 without exposing secret-marker fields. Verify direct Agent10 governance without the control token returns 403.

### Task 3: Verify regression coverage and document the result

**Files:**
- Test: `tests/test_agent06_adapter.py`
- Test: `tests/test_producer_api.py`
- Test: `tests/test_http_server.py`
- Test: `tests/test_governance.py`
- Test: `/Users/tristanzh/agent/agent06-pka/tests/test_answer_result_operations.py`
- Read: `docs/superpowers/plans/2026-07-13-agent06-obsidian-acceptance.md`

**Consumes:** Tasks 1 and 2.

**Produces:** Current test evidence, clean patch validation, and checkboxes that show either verified completion or the exact blocked task.

- [x] **Step 1: Run focused current-contract tests.**

  Run: `python3 -m unittest tests.test_agent06_adapter tests.test_producer_api tests.test_http_server tests.test_governance -q && cd /Users/tristanzh/agent/agent06-pka && python3 -m pytest tests/test_answer_result_operations.py -q`

  Expected: all selected tests pass.

- [x] **Step 2: Run the complete Agent10 suite and syntax compilation.**

  Run: `python3 -m unittest discover -s tests -q && python3 -m compileall -q asset_library && git diff --check`

  Expected: exit 0 with no failures and no whitespace errors.

- [x] **Step 3: Mark completed steps with evidence only.**

  Update the checkboxes after commands and live probes run. If no safe source asset exists, leave Task 2 unchecked and document the precise missing prerequisite instead of fabricating a write.
