# Agent10 Production Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `test-driven-development` for each code task. Do not commit or push from this business repository.

**Goal:** Run the Agent10 governance service locally, proxy it through the shared Web publish service, and activate the existing Production Obsidian Vault.

**Architecture:** A localhost Python HTTP service authenticates Web-originated requests with a file-backed local token and reads the Obsidian Local REST key only from ignored runtime configuration. Web injects the token only while proxying governance APIs and renders governance-only content.

**Tech Stack:** Python 3 standard library HTTP server, Node.js shared Web server, Obsidian Local REST API plugin, unittest, node:test.

## Global Constraints

- Bind Agent10 only to `127.0.0.1:8010`.
- Keep Obsidian Local REST on localhost HTTPS only.
- Never commit or render control tokens, API keys, raw Vault notes, or note bodies.
- Agent06 is the only enabled producer; Agent05 is retired.
- `GET` governance remains side-effect free.
- Git write operations remain owned by Agent08.

### Task 1: Agent10 HTTP server and local control token

**Files:** Create `asset_library/http_server.py`, modify `asset_library/runtime.py`, `asset_library/vault_bootstrap.py`; create `tests/test_http_server.py`, modify `tests/test_runtime.py`.

- [x] Write failing tests for loopback rejection, missing/invalid token rejection, valid governance response, side-effect-free GET, and token-file mode.
- [x] Run `python3 -m unittest tests.test_http_server tests.test_runtime -v` and verify failure because the server/token loader does not exist.
- [x] Implement file-backed token loading, constant-time bearer verification, localhost HTTP dispatch, and runtime key-file loading without logging secrets.
- [x] Run the focused tests and the full Agent10 suite.

### Task 2: Shared Web proxy and Agent10 governance page

**Files:** Modify `/Users/tristanzh/agent/web/server.mjs`, `config/platform-backend-processes.json`, `config/agents/agent10.contract.json`, `docs/agents/agent10-publishing-config.md`; modify or create focused Web tests.

- [x] Write failing `node:test` cases proving `/agent10` renders governance-only data, `/api/agent10/governance` proxies without secret leakage, and unauthenticated/unknown mutation routes are rejected.
- [x] Run the focused Node tests and verify the placeholder contract fails for the new API expectations.
- [x] Implement server-side proxying with a file-backed token, route-owned Agent10 markup, and the supervised Agent10 backend entry.
- [x] Run focused Node tests plus affected platform contracts.

### Task 3: Obsidian activation and live verification

**Files:** Modify production Vault ignored runtime configuration only through Obsidian; update `docs/OBSIDIAN_PHASE1_IMPLEMENTATION_STATUS_20260704.md` and `README.md`.

- [x] Open the Production Vault and inspect the Local REST API plugin settings.
- [x] Immediately before creating/saving the persistent Local REST key, obtain the Computer Use confirmation required for persistent access creation.
- [x] Generate the runtime configuration and Agent10 control token without printing either value.
- [x] Start Agent10, verify authenticated Obsidian REST status, Agent10 health, Web proxy, explicit mutation, and browser-visible governance page.
