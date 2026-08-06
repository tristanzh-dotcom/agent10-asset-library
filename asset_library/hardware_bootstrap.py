"""Idempotent bootstrap for the Agent10-owned 02_Hardware namespace."""

from dataclasses import dataclass
from pathlib import Path


HARDWARE_DIRECTORIES = (
    "02_Hardware/00_Index",
    "02_Hardware/00_Index/Templates",
    "02_Hardware/05_Inbox/codex",
    "02_Hardware/05_Inbox/web",
    "02_Hardware/05_Inbox/obsidian",
    "02_Hardware/10_Models/Controllers",
    "02_Hardware/10_Models/Sensors",
    "02_Hardware/10_Models/Power",
    "02_Hardware/10_Models/Wiring",
    "02_Hardware/10_Models/Connectors",
    "02_Hardware/10_Models/Enclosures",
    "02_Hardware/10_Models/Tools",
    "02_Hardware/10_Models/Consumables",
    "02_Hardware/10_Models/Other",
    "02_Hardware/20_Units/agent12",
    "02_Hardware/20_Units/agent13",
    "02_Hardware/20_Units/shared",
    "02_Hardware/30_Layouts/agent12",
    "02_Hardware/30_Layouts/agent13",
    "02_Hardware/30_Layouts/cross-agent",
    "02_Hardware/90_Evidence/photos",
    "02_Hardware/90_Evidence/vendor-docs",
)


HARDWARE_NOTES = {
    "02_Hardware/00_Index/Hardware Home.md": """---
record_type: hardware_index
namespace: 02_Hardware
---

# Hardware Home

Agent10 governs the cross-Agent hardware library. Obsidian is the human-readable
record surface; accepted model, unit, and layout records are published from one
immutable intake snapshot.

- [[Models by Category]]
- [[Inventory by Scope]]
- [[Assembly Layouts]]
- [[Needs Verification]]

Unknown values remain `null` or `unverified`. A published hardware record does
not prove installation, connectivity, or real-device acceptance.
""",
    "02_Hardware/00_Index/Models by Category.md": """---
record_type: hardware_index
index_kind: models_by_category
namespace: 02_Hardware
---

# Models by Category

This index is intentionally link-oriented. The SQLite projection and Web query
surface provide filtering; this page remains safe to regenerate without copying
model facts into a second source of truth.
""",
    "02_Hardware/00_Index/Inventory by Scope.md": """---
record_type: hardware_index
index_kind: inventory_by_scope
namespace: 02_Hardware
---

# Inventory by Scope

Inventory cards use stable `hardware_unit_id` values and distinguish available,
reserved, in-use, planned, and retired stock. They do not contain device IDs,
MAC addresses, credentials, or runtime configuration.
""",
    "02_Hardware/00_Index/Assembly Layouts.md": """---
record_type: hardware_index
index_kind: assembly_layouts
namespace: 02_Hardware
---

# Assembly Layouts

Layout records capture members, measured constraints, assumptions, and open
questions. They are not installation or commissioning acceptance records.
""",
    "02_Hardware/00_Index/Needs Verification.md": """---
record_type: hardware_index
index_kind: needs_verification
namespace: 02_Hardware
---

# Needs Verification

Use this view for records whose dimensions, interfaces, safety clearance, or
compatibility evidence is `reported`, `label_or_photo`, or `unverified` rather
than independently measured or supported by an official document.
""",
    "02_Hardware/00_Index/Templates/Hardware Model.md": """---
record_type: hardware_model
hardware_model_id: hwm_replace-me
canonical_name: ""
manufacturer: ""
model_or_sku: ""
category: controller
lifecycle_status: draft
status: active
nominal_dimensions: {}
interfaces: []
electrical: {}
installation_constraints: {}
compatibility: {}
technical_documents: []
photo_refs: []
scope_refs: []
relations: []
evidence_records: []
last_verified_at: null
---

# Hardware model

Create a new intake instead of editing a published record in place. Every
claim needs a traceable evidence record.
""",
    "02_Hardware/00_Index/Templates/Hardware Unit.md": """---
record_type: hardware_unit
hardware_unit_id: hwu_replace-me
model_ref: ""
inventory_kind: single
quantity_total: 0
quantity_available: 0
quantity_reserved: 0
ownership_scope: shared
condition: unknown
availability_status: planned
measured_dimensions: []
weight_g: null
photo_refs: []
layout_refs: []
relations: []
evidence_records: []
last_verified_at: null
status: active
---

# Hardware unit

Use an aggregate unit card for a batch or consumable. A unit card is inventory
metadata, not a device identity record.
""",
    "02_Hardware/00_Index/Templates/Assembly Layout.md": """---
record_type: assembly_layout
layout_id: lay_replace-me
title: ""
scope: cross-agent
target: waterproof_enclosure
status: draft
member_refs: []
constraints: {}
assumptions: []
open_questions: []
evidence_refs: []
last_reviewed_at: null
---

# Assembly layout

Keep layout constraints and open questions explicit. Do not copy project
configuration, credentials, runtime state, or commissioning claims here.
""",
}


@dataclass(frozen=True)
class HardwareBootstrapResult:
    actions: tuple
    written: tuple
    reused: tuple


class HardwareNamespaceBootstrapper:
    """Write fixed namespace notes through REST first, with safe fallback."""

    def __init__(self, vault_path, rest_client, fallback_writer=None, lock_factory=None):
        self.vault_path = Path(vault_path).resolve()
        self.rest_client = rest_client
        self.fallback_writer = fallback_writer
        self.lock_factory = lock_factory

    def bootstrap(self):
        actions = [f"mkdir:{directory}" for directory in HARDWARE_DIRECTORIES]
        for directory in HARDWARE_DIRECTORIES:
            (self.vault_path / directory).mkdir(parents=True, exist_ok=True)
        written = []
        reused = []
        for path, content in HARDWARE_NOTES.items():
            action = self._write_once(path, content)
            (written if action == "written" else reused).append(path)
        return HardwareBootstrapResult(tuple(actions), tuple(written), tuple(reused))

    def _write_once(self, path, content):
        lock = self.lock_factory(f"hardware-bootstrap:{path}") if self.lock_factory else _NoopLock()
        with lock:
            if self._read_existing(path):
                return "reused"
            try:
                self.rest_client.write_note(path, content)
            except Exception:
                if self.fallback_writer is None:
                    raise
                target = self.vault_path / path
                if target.exists():
                    return "reused"
                self.fallback_writer.write_note(path, content)
            return "written"

    def _read_existing(self, path):
        try:
            self.rest_client.read_note(path)
            return True
        except Exception as exc:
            # Obsidian REST exposes a 404 for a missing note. Other errors are
            # treated as unavailable and allow a local existence check only.
            if "404" in str(exc):
                return False
            return (self.vault_path / path).exists()


class _NoopLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False
