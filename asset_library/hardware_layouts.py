"""Cross-Agent assembly layouts and relation projections."""

from .hardware_schema import validate_hardware_draft


def build_initial_layouts():
    return [
        {
            "record_type": "assembly_layout",
            "layout_id": "lay_agent12-dry-prototype-enclosure",
            "title": "Agent12 dry prototype enclosure layout",
            "scope": "agent12",
            "target": "waterproof_enclosure",
            "status": "draft",
            "member_refs": [
                "hwm_esp32-s3-dev-kit-n16r8",
                "hwm_mb-102-830",
                "hwm_dfrobot-kit0021",
                "hwm_wago-221-413",
                "hwm_rvv-3c-0-3sqmm",
                "hwm_abs-waterproof-box-200x120x75",
            ],
            "constraints": {
                "wet_dry_boundary": {"status": "required", "claim": "keep cable junctions and controller on dry side"},
                "usb_service_access": {"status": "open", "claim": "service access must remain possible without stressing the cable"},
                "cable_bend_radius": {"status": "unmeasured", "value_mm": None},
                "internal_clearance": {"status": "unmeasured", "value_mm": None},
                "thermal_spacing": {"status": "not_measured", "claim": "no thermal clearance acceptance recorded"},
            },
            "assumptions": ["low-voltage prototype only", "no mains switching", "enclosure water ingress is not yet accepted"],
            "open_questions": ["measure usable internal dimensions", "measure cable bend and strain-relief clearance", "confirm entry hardware before drilling"],
            "evidence_refs": ["agent11-fishtank-monitor/docs/hardware-build-guide.md"],
            "evidence_records": [{"claim": "prototype component roles and dry/wet boundary", "level": "reported", "source_ref": "agent11-fishtank-monitor/docs/hardware-build-guide.md"}],
            "scope_refs": ["agent12"],
            "relations": [{"relation_type": "used_by", "ref": "agent12"}],
            "last_reviewed_at": None,
        },
        {
            "record_type": "assembly_layout",
            "layout_id": "lay_agent13-dry-terminal-placement",
            "title": "Agent13 StickS3 dry terminal placement",
            "scope": "agent13",
            "target": "reminder_mount",
            "status": "draft",
            "member_refs": ["hwm_m5stack-sticks3"],
            "constraints": {
                "splash_separation": {"status": "required", "claim": "keep power and cable away from splash zones"},
                "viewing_distance": {"status": "reported", "value_cm": 50},
                "power_source": {"status": "reported", "claim": "independent USB wall power is preferred"},
                "mounting_clearance": {"status": "unmeasured", "value_mm": None},
            },
            "assumptions": ["physical reminder terminal is not an aquarium sensor node", "display and button acceptance remain separate gates"],
            "open_questions": ["confirm arrival condition and final mounting surface", "measure cable slack and service access"],
            "evidence_refs": ["agent13/docs/superpowers/specs/2026-07-29-agent13-sticks3-reminder-design.md"],
            "evidence_records": [{"claim": "dry placement and viewing-distance requirements", "level": "reported", "source_ref": "agent13/docs/superpowers/specs/2026-07-29-agent13-sticks3-reminder-design.md"}],
            "scope_refs": ["agent13"],
            "relations": [{"relation_type": "used_by", "ref": "agent13"}],
            "last_reviewed_at": None,
        },
        {
            "record_type": "assembly_layout",
            "layout_id": "lay_cross-agent-smart-home-hardware-index",
            "title": "Cross-Agent smart-home hardware compatibility index",
            "scope": "cross-agent",
            "target": "smart_home_node",
            "status": "draft",
            "member_refs": ["hwm_esp32-s3-dev-kit-n16r8", "hwm_m5stack-sticks3", "hwm_abs-waterproof-box-200x120x75"],
            "constraints": {
                "electrical_boundary": {"status": "required", "claim": "compatibility requires an explicit voltage and interface check"},
                "mechanical_boundary": {"status": "unmeasured", "claim": "no cross-project enclosure fit is accepted"},
                "runtime_boundary": {"status": "required", "claim": "hardware records do not carry project runtime configuration"},
            },
            "assumptions": ["model records are shared references, not duplicated per Agent"],
            "open_questions": ["define reusable connector and mounting profiles", "add measured interface/clearance evidence"],
            "evidence_refs": ["agent10/docs/superpowers/specs/2026-08-04-hardware-library-design.md"],
            "evidence_records": [{"claim": "cross-Agent model/reference boundary", "level": "reported", "source_ref": "agent10/docs/superpowers/specs/2026-08-04-hardware-library-design.md"}],
            "scope_refs": ["agent12", "agent13", "smart-home"],
            "relations": [{"relation_type": "used_by", "ref": "smart-home"}],
            "last_reviewed_at": None,
        },
    ]


def validate_layout_relations(layout, known_record_ids):
    errors = validate_hardware_draft(layout)
    known = set(known_record_ids)
    if not errors:
        for index, ref in enumerate(layout.get("member_refs", [])):
            if ref not in known:
                errors.append(f"member_refs[{index}] references unknown hardware record: {ref}")
    return errors


def relation_projection(records):
    """Return a redaction-ready edge list from public hardware projections."""

    edges = []
    for record in records:
        source = _record_id(record)
        if not source:
            continue
        for relation in record.get("relations", []) or []:
            if not isinstance(relation, dict) or not relation.get("ref"):
                continue
            edges.append(
                {
                    "source": source,
                    "relation_type": relation.get("relation_type", "related_to"),
                    "target": relation["ref"],
                }
            )
        for member in record.get("member_refs", []) or []:
            edges.append({"source": source, "relation_type": "contains", "target": member})
    return sorted(edges, key=lambda edge: (edge["source"], edge["relation_type"], edge["target"]))


def _record_id(record):
    for field in ("hardware_model_id", "hardware_unit_id", "layout_id"):
        if record.get(field):
            return record[field]
    return ""
