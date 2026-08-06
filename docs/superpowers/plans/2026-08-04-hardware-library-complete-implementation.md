# Hardware Library Complete Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the approved cross-Agent hardware library from validated intake through governed Obsidian publication, accepted records/layouts, and a theme-compliant Agent10 Web workspace.

**Architecture:** Agent10 remains the single domain publication authority. Hardware drafts from Codex, Web, Obsidian draft space, and future Agent adapters enter one SQLite-backed intake store, use the existing loopback bearer boundary, and publish accepted records through a REST-first/fallback writer under the existing Vault lock. The shared Web only proxies allowlisted, redacted hardware projections and renders a route-scoped `上下分区` workspace inside the existing `/agent10` shell.

**Tech Stack:** Python 3 standard library, SQLite, existing Obsidian REST/fallback writer and lock, Node `server.mjs`, route-scoped Agent10 CSS/JS, Node test runner, Puppeteer browser tests.

## Global Constraints

- Preserve `02_Hardware` namespace, three record types, evidence levels, stable IDs, and final snapshot acceptance from the approved design.
- Keep secrets, device identifiers, private asset content, raw Vault note bodies, absolute paths, and runtime tokens out of Web/browser output.
- Real Vault writes, attachment migration, and external document retrieval are authorized for this task but remain explicit, auditable operations; never fabricate unknown measurements.
- Web changes are a route-specific Agent10 Delta: do not modify `.tz-sidebar`, `.tz-nav`, `.tz-frame`, `body`, `:root`, shared theme tokens, or unrelated Agent routes.
- Retain `上下分区`, shared shell/header/footer, `data-web-theme`, and active site theme inheritance (`light-tech` is current but both registered themes must remain valid).
- Web page loads, reads, probes, and proxies must not start/restart/stop a backend.
- Every persistence path must be idempotent, fail closed on changed snapshots, use atomic note/mirror semantics, and record partial failure rather than claiming success.
- Git mutations remain under Agent08 Git Control.

---

### Task 1: Add persistent hardware intake and publication services

**Files:**
- Create: `asset_library/hardware_store.py`
- Create: `asset_library/hardware_notes.py`
- Create: `tests/test_hardware_store.py`
- Create: `tests/test_hardware_notes.py`
- Modify: `asset_library/runtime.py`
- Modify: `asset_library/http_server.py`

**Deliverable:** A tested SQLite-backed intake/record store and a REST-first hardware note publisher that writes only accepted snapshots into the `02_Hardware` namespace.

Required behaviors:

- operation-key reuse returns the same intake without a second write;
- a changed draft under an existing operation key is rejected;
- model/unit/layout note paths are confined to `02_Hardware`;
- accepted records use safe YAML rendering and default readable sections;
- REST failure may use the existing filesystem fallback; mirror failure records a gap and is not reported as full success;
- no record is published unless `intake_status == "accepted"` and snapshot hash matches.

### Task 2: Expose Agent10 hardware API and local Codex operations

**Files:**
- Create: `asset_library/hardware_service.py`
- Modify: `asset_library/http_server.py`
- Modify: `asset_library/runtime.py`
- Modify: `asset_library/cli.py`
- Modify: `asset_library/__main__.py`
- Create/modify: `tests/test_hardware_api.py`, `tests/test_cli.py`

**Deliverable:** Local authenticated endpoints and CLI paths for submit, list/detail, and final accept.

Proposed endpoints:

```text
GET  /api/agent10/hardware
GET  /api/agent10/hardware/:id
POST /api/agent10/hardware/requests
POST /api/agent10/hardware/intakes/:id/accept
GET  /api/agent10/hardware/relations
```

The API returns redacted projections, never note bodies or runtime secrets. Codex commands use the same `prepare_hardware_intake`/`accept_hardware_intake` contract and never bypass the acceptance snapshot.

### Task 3: Create the governed Obsidian namespace and publish the first records

**Files:**
- Create: `asset_library/hardware_bootstrap.py`
- Create: `asset_library/hardware_seed.py`
- Create: `tests/test_hardware_bootstrap.py`, `tests/test_hardware_seed.py`
- Modify: `README.md`

**Deliverable:** Idempotent namespace/template/index bootstrap and a source-backed first batch.

Seed rules:

- create model/unit/layout templates and index pages only through the approved Agent10 writer path;
- register the 12 Agent11 hardware photos as evidence references, excluding `.DS_Store`;
- create only source-backed Agent12/Agent13 records from local project documents and explicit physical observations;
- leave unknown dimensions as `null`/`unverified`;
- do not infer real-device readiness from project code or a photo;
- every created record is accepted through the same final acceptance operation.

### Task 4: Add Agent10 Web hardware workspace as a route Delta

**Files in `/Users/tristanzh/agent/web`:**
- Modify: `server.mjs`
- Modify: `app/agent10.js`
- Modify: `app/agent10.css`
- Modify: `config/agents/agent10.contract.json`
- Modify: `docs/agents/agent10-publishing-config.md`
- Modify: `tests/agent10-service.test.mjs`
- Create: `tests/agent10-hardware-browser.test.mjs`

**Deliverable:** Existing `/agent10` page gains a hardware tab/workspace with search, filters, detail projection, draft request, and explicit final-accept action.

Theme/layout rules:

- keep shared sidebar/shell/header/footer untouched;
- retain `上下分区` with governance status above and hardware workspace below;
- use `data-web-theme` and `var(--tz-*)` tokens for all structural surfaces/borders/text;
- route CSS remains under `.agent10-*` selectors;
- test both `jlr` and `light-tech` inheritance and narrow/desktop geometry;
- proxy only the new allowlisted hardware endpoints with the server-injected Agent10 token.

### Task 5: Add cross-Agent relationships and assembly layouts

**Files:**
- Create: `asset_library/hardware_layouts.py`
- Create: `tests/test_hardware_layouts.py`
- Modify: `asset_library/hardware_service.py`
- Modify: `README.md` and the design/implementation handoff docs

**Deliverable:** Accepted layout records for Agent12/Agent13/shared/Smart-Home scopes, with member references, measured constraints, open questions, and relation projections. Layout facts remain separate from project runtime/commissioning facts.

### Task 6: End-to-end verification and final acceptance report

**Files:**
- Create: `docs/hardware/HANDOVER_hardware-library-acceptance-20260804.md`
- Modify: durable Agent10/Web publishing docs if the final API or route contract changed

**Verification:**

```bash
# Agent10
python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/agent10-hardware-pycache python3 -m compileall -q asset_library tests

# Web
node --check server.mjs
node --test tests/agent10-service.test.mjs tests/agent10-hardware-browser.test.mjs \
  tests/new-agent-publishing-contract.test.mjs tests/platform-region-contract-browser.test.mjs \
  tests/platform-visible-text-contract-browser.test.mjs tests/platform-theme.test.mjs
```

The final report must distinguish: schema/code, native/unit tests, target/runtime API, Obsidian write evidence, Web/browser evidence, and physical measurement/commissioning evidence. It must list unresolved hardware measurements and any mirror gaps; it must not claim real-device acceptance from software-only evidence.
