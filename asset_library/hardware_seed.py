"""Source-backed first records for the fish-tank and future StickS3 scopes."""

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


AGENT11_GUIDE_REF = "agent11-fishtank-monitor/docs/hardware-build-guide.md"
AGENT11_PHOTO_ROOT_REF = "agent11-fishtank-monitor/docs/hardware"
PHOTO_MANIFEST = {
    "hwm_esp32-s3-dev-kit-n16r8": ("ESP32-S3-Front.jpg", "ESP32-S3-Back.jpg"),
    "hwm_aneng-616": ("AHENG-616.jpg",),
    "hwm_heat-shrink-tube": ("热缩管.jpg",),
    "hwm_rvv-3c-0-3sqmm": ("RVV.jpg",),
    "hwm_mb-102-830": ("MB-102.jpg",),
    "hwm_abs-waterproof-box-200x120x75": ("防水盒.jpg",),
    "hwm_dfrobot-kit0021": ("KIT0021.jpg", "KIT0021-cover.jpg"),
    "hwm_resistor-4k7-1-4w": ("电阻4.7k.jpg",),
    "hwm_wago-221-413": ("WAGO.jpg",),
    "hwm_dupont-wire-set": ("杜邦线.jpg",),
}
PHOTO_TARGET_ROOT = "02_Hardware/90_Evidence/photos/agent11"


@dataclass(frozen=True)
class PhotoCopyResult:
    copied: tuple
    reused: tuple


def build_seed_records():
    return [*build_agent12_records(), build_agent13_model()]


def build_agent12_records():
    models = [
        _model(
            "hwm_esp32-s3-dev-kit-n16r8",
            "Waveshare ESP32-S3 Development Kit N16R8",
            "Waveshare",
            "ESP32-S3-DEV-KIT-N16R8-M",
            "controller",
            interfaces=["USB-C", "GPIO", "3.3V logic"],
            electrical={"project_role": "low-voltage controller", "logic_voltage": "3.3V", "mains_control": False},
            constraints={"placement": "dry enclosure; keep USB and wiring strain-relieved"},
        ),
        _model(
            "hwm_dfrobot-kit0021",
            "DFRobot KIT0021 DS18B20 waterproof probe",
            "DFRobot",
            "KIT0021",
            "sensor",
            interfaces=["3-wire OneWire probe"],
            electrical={"project_role": "low-voltage temperature sensing", "power_mode": "non-parasitic three-wire"},
            constraints={"probe_body": "water-contact component; keep cable junctions dry"},
        ),
        _model(
            "hwm_mb-102-830",
            "MB-102 830-point breadboard",
            "MB-102",
            "830-point breadboard",
            "connector",
            interfaces=["2.54mm breadboard rows", "split power rails"],
            constraints={"use": "low-voltage prototype only"},
        ),
        _model(
            "hwm_resistor-4k7-1-4w",
            "4.7k ohm 1/4W metal-film resistor",
            "Unknown",
            "4.7K 1% 1/4W",
            "consumable",
            interfaces=["through-hole"],
            electrical={"resistance_ohm": 4700, "power_rating_w": 0.25, "project_role": "single external DATA pull-up"},
        ),
        _model(
            "hwm_dupont-wire-set",
            "2.54mm 20cm 40P Dupont wire set",
            "Unknown",
            "2.54mm 20cm 40P",
            "wiring",
            interfaces=["male-male", "male-female", "female-female"],
            constraints={"use": "prototype interconnect; do not infer signal role from insulation color"},
        ),
        _model(
            "hwm_wago-221-413",
            "WAGO 221-413 lever connector",
            "WAGO",
            "221-413",
            "connector",
            interfaces=["3-conductor lever connector"],
            constraints={"use": "stripped copper conductors only; keep junction dry"},
        ),
        _model(
            "hwm_rvv-3c-0-3sqmm",
            "RVV three-core 0.3 square millimeter cable",
            "Unknown",
            "RVV 3C 0.3mm2",
            "wiring",
            interfaces=["three-core cable"],
            constraints={"routing": "measure both runs and leave service/drip-loop allowance"},
        ),
        _model(
            "hwm_abs-waterproof-box-200x120x75",
            "ABS waterproof enclosure approximately 200 x 120 x 75 mm",
            "Unknown",
            "ABS waterproof box (approx. 200x120x75mm)",
            "enclosure",
            dimensions={"length_mm": 200, "width_mm": 120, "height_mm": 75},
            interfaces=["screw lid", "cable-entry points pending measurement"],
            constraints={"waterproof_claim": "not established while USB/cable entries are open", "layout": "dry side separated from wet interfaces"},
        ),
        _model(
            "hwm_aneng-616",
            "ANENG 616 digital multimeter",
            "ANENG",
            "616",
            "tool",
            interfaces=["COM", "voltage", "resistance", "continuity"],
            constraints={"safety": "project use is unpowered continuity and low-voltage DC only; no mains"},
        ),
        _model(
            "hwm_heat-shrink-tube",
            "Heat-shrink tubing assortment",
            "Unknown",
            "heat-shrink tubing",
            "consumable",
            interfaces=["wire insulation"],
            constraints={"use": "not a substitute for a sealed underwater splice"},
        ),
    ]
    quantities = {
        "hwm_esp32-s3-dev-kit-n16r8": ("batch", 2, "available"),
        "hwm_dfrobot-kit0021": ("batch", 3, "available"),
        "hwm_mb-102-830": ("single", 1, "available"),
        "hwm_resistor-4k7-1-4w": ("package", 1, "available"),
        "hwm_dupont-wire-set": ("set", 1, "available"),
        "hwm_wago-221-413": ("batch", 10, "available"),
        "hwm_rvv-3c-0-3sqmm": ("length_m", 5, "available"),
        "hwm_abs-waterproof-box-200x120x75": ("batch", 2, "available"),
        "hwm_aneng-616": ("single", 1, "available"),
        "hwm_heat-shrink-tube": ("assortment", 1, "available"),
    }
    units = []
    for model in models:
        model_id = model["hardware_model_id"]
        inventory_kind, quantity, availability = quantities[model_id]
        units.append(
            {
                "record_type": "hardware_unit",
                "hardware_unit_id": f"hwu_agent12-{model_id[4:]}",
                "canonical_name": f"Agent12 stock - {model['canonical_name']}",
                "model_ref": model_id,
                "inventory_kind": inventory_kind,
                "quantity_total": quantity,
                "quantity_available": quantity,
                "quantity_reserved": 0,
                "quantity_unit": "m" if inventory_kind == "length_m" else "item_or_set",
                "ownership_scope": "agent12",
                "storage_location": None,
                "condition": "unknown",
                "availability_status": availability,
                "measured_dimensions": [],
                "weight_g": None,
                "photo_refs": _photo_refs(model_id),
                "layout_refs": [],
                "scope_refs": ["agent12"],
                "relations": [{"relation_type": "used_by", "ref": "agent12"}],
                "evidence_records": [
                    {
                        "claim": "quantity and intended stock role",
                        "level": "reported",
                        "source_ref": AGENT11_GUIDE_REF,
                    }
                ],
                "last_verified_at": None,
                "status": "active",
            }
        )
    return [*models, *units]


def build_agent13_model():
    return {
        "record_type": "hardware_model",
        "hardware_model_id": "hwm_m5stack-sticks3",
        "canonical_name": "M5Stack StickS3",
        "manufacturer": "M5Stack",
        "model_or_sku": "StickS3",
        "category": "controller",
        "lifecycle_status": "candidate",
        "status": "active",
        "nominal_dimensions": {},
        "interfaces": ["USB", "display", "buttons", "audio"],
        "electrical": {"project_role": "offline reminder terminal"},
        "installation_constraints": {"placement": "dry placement; keep cable and power away from splash zones"},
        "compatibility": {},
        "technical_documents": [
            {"title": "Agent13 hardware design", "source_ref": "agent13/docs/superpowers/specs/2026-07-29-agent13-sticks3-reminder-design.md"}
        ],
        "photo_refs": [],
        "scope_refs": ["agent13"],
        "relations": [{"relation_type": "used_by", "ref": "agent13"}],
        "evidence_records": [
            {
                "claim": "StickS3 physical model and project role",
                "level": "reported",
                "source_ref": "agent13/docs/evidence/hardware-device-record.md",
            }
        ],
        "last_verified_at": None,
    }


def copy_hardware_photos(source_dir, vault_path):
    source_dir = Path(source_dir).resolve()
    if not source_dir.is_dir():
        raise ValueError("hardware photo source directory does not exist")
    target_root = (Path(vault_path).resolve() / PHOTO_TARGET_ROOT).resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    copied = []
    reused = []
    for filename in _photo_files():
        source = source_dir / filename
        if not source.is_file() or source.is_symlink():
            raise ValueError(f"hardware photo is missing or not a regular file: {filename}")
        target = (target_root / filename).resolve()
        target.relative_to(target_root)
        if target.exists():
            if _sha256(source) != _sha256(target):
                raise ValueError(f"existing hardware photo differs: {filename}")
            reused.append(_target_ref(filename))
            continue
        temporary = target.with_name(f".{target.name}.tmp")
        shutil.copy2(source, temporary)
        os.replace(temporary, target)
        copied.append(_target_ref(filename))
    return PhotoCopyResult(tuple(copied), tuple(reused))


def _model(model_id, canonical_name, manufacturer, sku, category, interfaces=None, electrical=None, constraints=None, dimensions=None):
    return {
        "record_type": "hardware_model",
        "hardware_model_id": model_id,
        "canonical_name": canonical_name,
        "manufacturer": manufacturer,
        "model_or_sku": sku,
        "category": category,
        "lifecycle_status": "candidate",
        "status": "active",
        "nominal_dimensions": dimensions or {},
        "interfaces": interfaces or [],
        "electrical": electrical or {},
        "installation_constraints": constraints or {},
        "compatibility": {},
        "technical_documents": [{"title": "Agent11 hardware build guide", "source_ref": AGENT11_GUIDE_REF}],
        "photo_refs": _photo_refs(model_id),
        "scope_refs": ["agent12"],
        "relations": [{"relation_type": "used_by", "ref": "agent12"}],
        "evidence_records": [
            {"claim": "appearance or label", "level": "label_or_photo", "source_ref": _photo_source(model_id)},
            {"claim": "project hardware role", "level": "reported", "source_ref": AGENT11_GUIDE_REF},
        ],
        "last_verified_at": None,
    }


def _photo_files():
    return tuple(filename for filenames in PHOTO_MANIFEST.values() for filename in filenames)


def _photo_refs(model_id):
    return [_target_ref(filename) for filename in PHOTO_MANIFEST.get(model_id, ())]


def _photo_source(model_id):
    filenames = PHOTO_MANIFEST.get(model_id, ())
    filename = filenames[0] if filenames else ""
    return f"{AGENT11_PHOTO_ROOT_REF}/{filename}" if filename else AGENT11_GUIDE_REF


def _target_ref(filename):
    return f"{PHOTO_TARGET_ROOT}/{filename}"


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
