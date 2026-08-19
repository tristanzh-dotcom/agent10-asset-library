# Hardware Library User Experience Fixes Implementation Plan

> **For agentic workers:** Use the existing governed Agent10 publication path for the final Vault refresh. Do not write the production Vault directly from ad-hoc scripts.

**Goal:** Close the remaining Obsidian browsing gaps identified in the final-user audit while preserving stable hardware facts and IDs.

**Architecture:** Keep the accepted SQLite records as the source for all projections. Extend the note renderer with a complete record context so model, unit, and layout cards can render human titles, aggregate inventory, member/related links, inherited categories, and readable source summaries. Render index-table links as Markdown links because Obsidian's wikilink alias pipe conflicts with Markdown table separators.

**Tech Stack:** Python standard library, existing Agent10 renderers/publisher, SQLite mirror, Obsidian Local REST, Python unittest.

## Global Constraints

- Obsidian indexes remain pure Markdown and plugin-free.
- Stable IDs remain in frontmatter and link targets; user-facing body text uses display names.
- Published facts continue to come only from accepted records and existing operation/lock boundaries.
- The production Vault is refreshed only through the existing REST-first/fallback publisher.
- No secrets, absolute local paths, device identifiers, or raw private references enter user-facing Markdown.

### Task 1: Add failing projection tests

Modify tests/test_hardware_notes.py and tests/test_hardware_indexes.py to cover:

- Markdown links in every index table.
- Home's explicit all-record verification metric.
- Model cards showing aggregate inventory and related unit/layout links.
- Unit cards inheriting the linked model category and linking back to the model.
- Layout cards showing readable titles and member links.
- Readable source labels without exposing private paths.

Run the focused tests and confirm the new assertions fail before implementation.

### Task 2: Implement pure renderers

Modify asset_library/hardware_indexes.py and asset_library/hardware_notes.py:

- Build a record context keyed by stable ID and derive model/unit/layout relationships.
- Use Markdown links in tables and human labels for relation links.
- Aggregate inventory in model cards and count all records in the verification metric.
- Render layout members and source labels in the body.
- Keep existing safety redaction and acceptance semantics.

Run focused tests to green, then refactor only within the affected helpers.

### Task 3: Preserve governed publication behavior

Extend the note publication context so accepted records and their affected related cards are rendered from the same accepted mirror snapshot. Keep REST-first/fallback behavior, partial-result reporting, and index publication unchanged.

Run the full hardware-focused test set and compile checks.

### Task 4: Refresh the production Vault

Use the existing local runtime configuration and publisher to regenerate the accepted hardware cards and six indexes in /Users/tristanzh/agent/AgentAssetVault. Verify the publication result, file counts, link syntax, and Obsidian reading views without printing credentials.

### Task 5: Final verification

Run:

    PYTHONPYCACHEPREFIX=/tmp/agent10-hardware-pycache python3 -m unittest tests.test_hardware_notes tests.test_hardware_indexes tests.test_hardware_service tests.test_hardware_seed
    PYTHONPYCACHEPREFIX=/tmp/agent10-hardware-pycache python3 -m compileall -q asset_library tests

Then verify the real Obsidian Home, Inventory, Needs Verification, one model, one unit, and one layout in reading view.
