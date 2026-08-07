# Agent10 Asset Library

Agent10 is the Obsidian-first asset publishing and governance layer for high-value Agent outputs. It supports the Agent06 generated-knowledge producer and the restricted `codex` development-capture producer. The latter can publish only local, audit-only development summaries through the same token-protected draft route; it does not bypass schema validation, safe writing, idempotency, the SQLite mirror, or operational governance. Obsidian is the human-facing asset UI; Agent10 owns publication and governance. See [the Codex capture design](docs/superpowers/specs/2026-07-16-codex-development-capture-design.md).

## Validate a Draft

Validation is local and does not require Obsidian credentials:

```bash
python3 -m asset_library validate-draft /absolute/path/to/draft.json
```

Hardware drafts use the same read-only local boundary and do not write the
Vault, copy attachments, or perform final acceptance:

```bash
python3 -m asset_library validate-hardware /absolute/path/to/hardware-draft.json
```

Hardware submissions from Codex use the same intake and final-acceptance
service as the Web entry point. The first command only creates a
`review_pending` snapshot; the second accepts that exact hash and publishes it
under `02_Hardware/`:

```bash
python3 -m asset_library prepare-hardware \
  /absolute/path/to/hardware-draft.json codex TZ operation-key
python3 -m asset_library accept-hardware \
  <intake_id> TZ <snapshot_hash>
```

The Web route proxies the corresponding allowlisted endpoints:

```text
GET  /api/agent10/hardware
GET  /api/agent10/hardware/summary
GET  /api/agent10/hardware/:id
GET  /api/agent10/hardware/relations
POST /api/agent10/hardware/drafts
PATCH /api/agent10/hardware/drafts/:id
POST /api/agent10/hardware/drafts/:id/reference
POST /api/agent10/hardware/drafts/:id/attachments
POST /api/agent10/hardware/drafts/:id/analyze
GET  /api/agent10/hardware/analysis-jobs/:id
POST /api/agent10/hardware/drafts/:id/prepare
POST /api/agent10/hardware/drafts/:id/accept
```

The `/agent10` page has two route-owned views: `我的硬件` is a read-only
inventory summary, and `录入 / 编辑` accepts multiple bounded images plus one
reference input containing an HTTPS URL and optional title/vendor/version
context. The server fetches the URL only after the explicit action, keeps the
reference even when it yields no hardware candidate, and requires the sequence
`识别 → 编辑 → 生成确认包 → 最终验收` before publishing to Obsidian.

Candidate analysis uses the registered `Agent10 / hardware_reference_analysis`
route only when its runtime is configured. Without the approved provider
credential, the deterministic upload/reference/draft workflow remains usable
and the analysis result is explicitly `unavailable`; no alternate provider is
used.

The accepted hardware namespace is:

```text
02_Hardware/00_Index/        fixed indexes and templates
02_Hardware/10_Models/       one model card per stable hardware model
02_Hardware/20_Units/        Agent/scoped stock and batch cards
02_Hardware/30_Layouts/      cross-Agent assembly layouts
02_Hardware/90_Evidence/     copied photos and future vendor evidence
```

Obsidian remains the human-facing primary record. Agent10's SQLite database is
a rebuildable query mirror; Web projections omit note bodies, local evidence
paths, credentials, and device identity fields. A published record is a
资料快照 acceptance, not proof of installation, connectivity, or physical
commissioning.

## Runtime Configuration

Commands that write assets require these environment variables:

```text
AGENT_ASSET_VAULT_PATH=/absolute/path/to/approved/vault
OBSIDIAN_REST_BASE_URL=https://127.0.0.1:27124
OBSIDIAN_REST_API_KEY=<runtime secret>
```

The REST URL must use HTTPS and a localhost host. Do not store the API key in source-controlled files.

For the Production Obsidian plugin, Agent10 reads the ignored runtime configuration by default from:

```text
AgentAssetVault/.obsidian/plugins/obsidian-local-rest-api/data.json
```

Agent10's separate Web control token is created at:

```text
AgentAssetVault/99_System/audit/.agent10-control.token
```

Both files must remain mode `0600` and must never be copied into Web HTML, JavaScript, logs, or Git.

## Ingestion

Normal drafts must not contain a final `asset_id`:

```bash
python3 -m asset_library ingest-draft /absolute/path/to/draft.json
```

Agent06 V0 assets use the Agent10-owned adapter:

```bash
python3 -m asset_library ingest-agent06 /absolute/path/to/agent06/answer-asset
```

In the Agent06 workflow, `POST /api/knowledge/add-generated` saves the local answer asset first and then calls the same local Agent10 producer route. If the local Agent10 control token is unavailable, the workflow returns a deferred state and does not claim that the asset reached Obsidian.

Historical migrations that preserve an existing valid `asset_id` use the separate local command:

```bash
python3 -m asset_library ingest-migration /absolute/path/to/migration-draft.json
```

The HTTP migration contract denies access by default. A host must explicitly authorize a request after applying its local authentication policy.

## Governance Boundary

`GET /api/asset-library/governance` is read-only. Writer recovery and mirror-gap compaction are explicit, default-denied mutation actions. Mirror retry and promotion reconciliation remain unavailable until their production resolvers are wired. The production Obsidian trust and shared Web wiring were live-verified on 2026-08-07; Agent10 must remain loopback-only and supervisor-managed.

## Verification

```bash
python3 -m unittest discover -s tests -v
PYTHONPYCACHEPREFIX=/tmp/agent10-asset-library-pycache python3 -m compileall -q asset_library tests
```
