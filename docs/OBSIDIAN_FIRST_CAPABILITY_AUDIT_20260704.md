# Obsidian-first Capability Audit

Date: 2026-07-04

Status: Phase 1 prerequisite. This document supersedes direct implementation planning until Obsidian's native capabilities and plugin/tool options are validated.

## 1. First-principles Position

Agent10 is not building a standalone asset database with an Obsidian export adapter.

Agent10 is building an agent-oriented asset library on top of Obsidian's product model:

- Vault as the durable user-facing asset surface.
- Markdown notes as portable asset records.
- YAML properties as structured metadata.
- Tags, links, backlinks, search, and views as the primary human interaction layer.
- Agent10 code only fills gaps Obsidian does not own: agent draft normalization, safety validation, idempotency, cross-agent contracts, recovery journals, and optional machine query acceleration.

If an Obsidian native feature, core plugin, community plugin, MCP server, or existing skill safely satisfies a requirement with better stability, quality, or efficiency than custom code, it should be evaluated first and preferred when it wins the tradeoff.

## 2. Required Evaluation Criteria

Every Obsidian capability or external plugin/tool must be evaluated against:

- Functional fit: Does it satisfy the asset-library workflow directly?
- Stability: Is it maintained, documented, and suitable for a long-lived Vault?
- Safety: Can it mutate Vault content? Does it require network, API keys, or broad file access?
- Efficiency: Does it reduce custom code, operational burden, or sync risk?
- Output quality: Does it produce notes, properties, links, and views that are readable in Obsidian?
- Portability: Does data remain usable as plain Markdown/YAML if the plugin is removed?
- Agent fit: Can Codex and subagents interact with it reliably without manual UI dependence?

### 2.1 Validation Priority

Validation must proceed in dependency order, not by convenience.

Layer 1: Blocks Writer design.
- 3.1 Vault and Markdown Files.
- 3.2 Properties / YAML Frontmatter.
- 4.2 Local REST API / MCP Plugin.

Layer 2: Blocks UI and browsing design.
- 3.4 Internal Links and Backlinks.
- 3.3 Tags.
- 3.5 Search and Views.
- 4.1 Dataview.
- 3.6 Templates (core plugin).

Layer 3: Does not block Phase 1 implementation.
- 4.3 Obsidian Git.
- 4.4 Obsidian Linter.

### 2.2 General Acceptance Thresholds

Each candidate must end with one of four outcomes:

- `adopt`: Use in Phase 1.
- `restricted_adopt`: Use only under explicit constraints, such as local-only, read-only, or manual review.
- `defer`: Useful, but not required for Phase 1.
- `reject`: Do not use for this project.

Reject a candidate if any of the following is true:

- It requires network access for normal operation and has no offline fallback.
- It requires an API key or token that cannot be supplied from local configuration or environment variables.
- It silently modifies existing notes without preview, diff, journal, or undo path.
- It stores asset data outside the Vault in a non-portable format without a Markdown/YAML fallback.
- It requires broad remote sync or remote storage for Phase 1.
- It is a community plugin with no release or meaningful maintenance activity for more than 12 months and more than 50 open GitHub issues, unless the feature is read-only and has a complete fallback path.

Local REST or MCP candidates must additionally satisfy:

- Bind to localhost only by default or support localhost-only configuration.
- Require authentication for mutating operations.
- Demonstrate creation, read/open, and tag/metadata discovery in a test Vault before replacing direct file writing.
- Provide a fallback to direct filesystem writing governed by the 11.6 write safety strategy in the design contract.

### 2.3 Timebox and Termination Rule

The Obsidian-first validation phase is timeboxed to:

- No more than 3 calendar days, or
- No more than 2 complete validation rounds,

whichever comes first.

Layer 1 must be validated first. Layer 2 is validated only after Layer 1 has enough evidence to choose the Writer interface direction. Layer 3 is validated only if time remains; otherwise it is automatically marked `defer`.

At the end of round 2:

- Unverified Layer 1 items are blockers and must be escalated to TZ.
- Unverified Layer 2 items default to `defer` unless they block an already-chosen Phase 1 user workflow.
- Unverified Layer 3 items default to `defer-to-Phase-2`.

## 3. Native Obsidian Capabilities to Validate First

### 3.1 Vault and Markdown Files

Obsidian operates on local Markdown files in a Vault. This directly supports the portability goal and should remain the default storage surface.

Validation target:
- Create a test Vault.
- Generate asset notes as Markdown files.
- Confirm Obsidian indexes them without a custom plugin.

### 3.2 Properties / YAML Frontmatter

Obsidian Properties are stored as YAML at the top of Markdown files. Official docs state property names are unique within a note, support text/list/number/checkbox/date/date-time/tags types, and nested properties are not supported in the UI.

Implication:
- Agent10 schema should stay flat where possible.
- `tags` must be YAML list format.
- Complex objects should remain in note body, linked files, or JSON attachments rather than nested frontmatter.

Source:
- https://obsidian.md/help/properties

### 3.3 Tags

Obsidian tags can be defined in notes or the `tags` property. Tags cannot contain blank spaces; nested tags use `/`.

Implication:
- Existing `agent/agent06`, `workflow/ask`, `type/pka-answer` tags match Obsidian's nested tag model.
- Tag generation should enforce no spaces and stable casing.

Source:
- https://obsidian.md/help/tags

### 3.4 Internal Links and Backlinks

Obsidian supports Wikilinks and Markdown links, backlinks, heading links, block links, and attachment links. Official docs warn that some characters may not work well in links.

Implication:
- Asset note filenames and generated links must avoid unsafe characters.
- Subject pages such as `[[Mantou]]` and workflow pages should be used before building custom navigation UI.

Sources:
- https://obsidian.md/help/links
- https://obsidian.md/help/Plugins/Backlinks

### 3.5 Search and Views

Obsidian Search, Properties, Tags view, Backlinks, and newer view capabilities should be validated before building a custom `/assets` UI.

Validation target:
- Can a user answer "show all Agent06 indexed answers" from native search/tags/properties?
- Can a user browse by subject, workflow, and status without Agent10 Web UI?

### 3.6 Templates (core plugin)

Obsidian Templates is a core plugin that inserts predefined Markdown snippets and supports template variables. It directly overlaps with the planned `99_System/templates/` folder and subject-note skeletons.

Validation target:
- Confirm whether Agent10 should store template files in `99_System/templates/` and let Obsidian Templates insert them.
- Confirm generated template notes can include YAML frontmatter, tags, and double-link skeletons without Obsidian rewriting them incorrectly.
- Confirm whether Templates can cover human-created subject notes and collection notes, while machine-generated asset notes remain produced by the Writer/API path.

V1 stance:
- Prefer Obsidian Templates for human-invoked note skeletons.
- Do not build a custom template engine unless Templates cannot preserve the required frontmatter and link structure.

## 4. Plugin / Tool Candidates

### 4.1 Dataview

Fit:
- Strong candidate for asset tables and filtered lists over frontmatter.
- Reads Markdown frontmatter and inline fields, and provides DQL and DataviewJS query modes.

Safety:
- Regular Dataview queries are read-oriented and safer.
- DataviewJS is powerful and can run with plugin-level access; avoid arbitrary DataviewJS in V1 unless manually reviewed.

Current signal:
- GitHub project describes it as a data index and query language over Markdown files.
- It has a large user base and active ecosystem, but should still be validated in a test Vault.

Source:
- https://github.com/blacksmithgu/obsidian-dataview

V1 stance:
- Prefer Dataview or native views for human asset browsing before writing custom asset list UI.

### 4.2 Local REST API / MCP Plugin

Fit:
- Strong candidate for agent-to-Obsidian interaction.
- Provides endpoints for files, commands, tags, open-file behavior, and ships an MCP server for AI agents.

Safety:
- Requires API key authentication.
- Runs inside Obsidian with live Vault access, which is powerful but requires strict local-only configuration.

Current signal:
- Project describes itself as a secure REST API and MCP server for the Vault.
- It exposes `/commands/`, `/tags/`, `/open/{path}`, status/auth checks, and `/mcp/`.

Source:
- https://github.com/coddingtonbear/obsidian-local-rest-api

V1 stance:
- Must be evaluated before custom external file writer becomes the default interface.
- If accepted, Agent10 Writer may become a thin client around Obsidian's live API plus offline fallback.

### 4.3 Obsidian Git

Fit:
- Candidate for Vault backup/versioning and manual review of changes.
- Offers automatic commit/sync, auto-pull on startup, source control view, history view, and diff view.

Safety:
- Automatic push/pull can conflict with TZ's git sovereignty rules and sensitive asset policy.
- V1 should not enable auto-push or remote sync by default.

Source:
- https://github.com/Vinzent03/obsidian-git

V1 stance:
- Consider for local-only Vault history and visual diff, but do not enable automated remote sync in Phase 1.

### 4.4 Obsidian Linter

Fit:
- Candidate for note formatting consistency.

Safety:
- It mutates note content, so rules must be reviewed carefully before applying to machine-generated asset notes.

Source:
- https://github.com/platers/obsidian-linter

V1 stance:
- Optional later; not required before core asset flow. Avoid auto-formatting until schema and generated note layout stabilize.

## 5. Revised Phase 1 Gate

No Agent10 asset writer implementation should proceed until these questions are answered with a test Vault:

1. Can native Obsidian Properties, Tags, Links, Backlinks, and Search satisfy the primary user browsing workflows?
2. Does Dataview or a native view mechanism remove the need for a custom `/assets` browser in V1?
3. Does Local REST API / MCP provide a safer and more Obsidian-native write/open/query interface than direct filesystem writes?
4. What minimum custom code remains after adopting Obsidian-native capabilities?
5. What plugin set is acceptable under TZ's privacy, stability, and migration constraints?

## 6. Expected Output of the Audit

The audit must produce:

- A plugin decision matrix: adopt / reject / defer, with reason.
- A validated test Vault layout.
- Example notes that render correctly in Obsidian.
- A revised Phase 1 implementation plan that starts from Obsidian interfaces, not from an isolated internal library.
- A fallback policy for running without community plugins.

### 6.1 Fallback Policy Requirements

The fallback policy must cover at least:

- If Dataview is unavailable: asset browsing falls back to Obsidian Search, Tags view, Properties view, and curated index notes.
- If Local REST API / MCP is unavailable: asset creation falls back to direct filesystem writing under the design contract's 11.6 write safety strategy.
- If Obsidian Templates is unavailable: human-created skeleton notes fall back to checked-in Markdown template files under `99_System/templates/`.
- If Obsidian Git is unavailable or rejected: backup falls back to local-only filesystem snapshots and/or Agent08-mediated review, not automatic remote sync.
- If Linter is unavailable or rejected: machine-generated notes remain formatted by Agent10's deterministic renderer.
- For every fallback mode: list lost capabilities, user-visible behavior changes, and whether existing Vault notes remain readable without the plugin.
