# Obsidian Phase 1 Layer 1 Validation

Date: 2026-07-04

Scope: Layer 1 only, per `OBSIDIAN_FIRST_CAPABILITY_AUDIT_20260704.md`.

Layer 1 items:

- 3.1 Vault and Markdown Files.
- 3.2 Properties / YAML Frontmatter.
- 4.2 Local REST API / MCP Plugin.

## 1. Environment Probe

Commands executed:

```text
ls -ld /Applications/Obsidian.app
find /Applications "$HOME/Applications" -maxdepth 2 -iname 'Obsidian.app' -print
curl -sS -m 2 http://127.0.0.1:27123/
curl -k -sS -m 2 https://127.0.0.1:27124/
```

Observed results:

- Initial probe: `/Applications/Obsidian.app` did not exist and no Local REST API service responded on `127.0.0.1:27123` or `127.0.0.1:27124`.
- After TZ authorization, Obsidian `1.12.7` was installed from the official `obsidianmd/obsidian-releases` GitHub release.
- Downloaded DMG SHA-256 matched official release metadata: `3b85c13b4ce55512e86e170a7cd2a494e2db695ac888c0601e153cb85b77881b`.
- Obsidian App version confirmed from `/Applications/Obsidian.app/Contents/Info.plist`: `1.12.7`.
- Local REST API with MCP plugin `4.1.3` was installed only in the test Vault.
- Plugin release asset hashes matched GitHub release metadata:
  - `main.js`: `93588cbb6cf0214479c069a36f670acd0eb11b72072caa45a13a777a595b4389`
  - `manifest.json`: `05d304daffef1b8095bad7b1602dfe22cd340f30bfd35610784ac2ba5e2deab2`
  - `styles.css`: `1180db8e819c757a858e5591eb0a2f9b1fbe2e5db7fa642da576360c4b6c2c3b`

Implication:

- Runtime validation can proceed against the test Vault.
- Plugin runtime secrets are generated in `validation/obsidian-test-vault/.obsidian/plugins/obsidian-local-rest-api/data.json`; this path is ignored by `.gitignore`.

## 2. Test Vault Artifact

Created local test Vault artifact under:

```text
validation/obsidian-test-vault/
```

Included files:

- `01_Agents/Agent06/2026-07-04 - agent06 - PKA Answer Smoke - ast_20260704_a1b2c3d4.md`
- `03_Subjects/Mantou.md`
- `99_System/templates/asset-note-template.md`

This artifact validates the intended file layout, flat YAML property schema, nested tags, subject links, and template skeleton at the filesystem/Markdown level.

## 3. Decision Matrix

| Candidate | Priority | Evidence | Decision | Reason |
|---|---:|---|---|---|
| Vault + Markdown files | Layer 1 | Test Vault opened successfully in Obsidian. File tree shows `01_Agents`, `03_Subjects`, and `99_System`. | `adopt` | Vault + Markdown is confirmed as the baseline product/storage surface. |
| Properties / YAML Frontmatter | Layer 1 | Sample asset note is readable through Local REST API with flat YAML frontmatter intact. Tags from YAML properties are indexed by Obsidian and returned by `/tags/`. | `adopt` | Flat YAML properties and list-form tags work for V1 asset notes. Obsidian Properties UI still deserves visual QA, but it no longer blocks Writer interface choice. |
| Local REST API / MCP Plugin | Layer 1 | HTTPS service responds on `https://127.0.0.1:27124/`; HTTP on `27123` is disabled. Authenticated request returns `authenticated: true`. `/vault/{path}` reads notes. `PUT /vault/{path}` creates a note and parent folder in test Vault. `/tags/` returns indexed tags. `/mcp/` initializes with MCP `2025-06-18`, returning tools/resources capabilities. | `restricted_adopt` | Suitable as primary Obsidian-live interface for Phase 1, restricted to localhost HTTPS, Bearer auth, test/approved Vaults only, and direct filesystem writer fallback under 11.6. |

## 4. Layer 1 Result

Current Writer direction can now be narrowed.

What can be decided now:

- Vault Markdown remains the portable fallback and baseline.
- Frontmatter must remain flat and Obsidian-compatible.
- Direct filesystem writing remains required as an offline fallback path.
- Local REST API with MCP is viable as the primary live-Obsidian interface for Phase 1 under restrictions.
- MCP is viable for agent-oriented tooling discovery/invocation, but implementation should start with REST endpoints first because they are simpler to test and reason about.

What remains open:

- Whether Obsidian live metadata should replace or reduce SQLite Mirror responsibilities.
- Exact endpoint set for search/open behavior. A guessed `/search/simple/?query=PKA` returned `404`; endpoint names must be taken from plugin docs or MCP tool list, not guessed.

## 5. Next Validation Steps

Layer 1 is complete enough to rewrite Phase 1 planning. Remaining follow-up:

1. Use plugin docs or MCP `tools/list` to enumerate supported endpoints/tools before coding.
2. Perform visual QA in Obsidian Properties UI for the sample asset note.
3. Decide SQLite Mirror scope after checking whether Local REST API/MCP metadata/query support is sufficient for Agent10 API needs.
4. Rewrite Phase 1 implementation plan around REST-first Writer with direct filesystem fallback.

## 6. Phase 1 Planning Impact

The previous code-first plan remains superseded.

A rewritten Phase 1 implementation plan should use this interface decision:

- Primary path: Obsidian Local REST API with MCP, localhost HTTPS, Bearer auth, approved Vaults only.
- Fallback path: direct filesystem writer governed by the design contract's 11.6 write safety strategy.
- Agent10 code should implement draft validation, schema/idempotency, endpoint client, fallback writer, and recovery journals only where Obsidian/plugins do not provide the capability.
