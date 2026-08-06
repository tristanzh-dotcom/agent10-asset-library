"""Stable, user-facing labels for the hardware projection.

These labels are presentation metadata only.  The canonical English name,
manufacturer, model/SKU, and source records remain unchanged in Obsidian.
"""


HARDWARE_DISPLAY_NAMES_ZH = {
    "hwm_dupont-wire-set": "杜邦线套装",
    "hwm_resistor-4k7-1-4w": "4.7k 金属膜电阻",
    "hwm_abs-waterproof-box-200x120x75": "ABS 防水盒",
    "hwm_aneng-616": "ANENG 616 万用表",
    "hwm_dfrobot-kit0021": "防水温度探头",
    "hwm_heat-shrink-tube": "热缩管套装",
    "hwm_m5stack-sticks3": "StickS3 开发板",
    "hwm_mb-102-830": "MB-102 面包板",
    "hwm_rvv-3c-0-3sqmm": "RVV 三芯电缆",
    "hwm_wago-221-413": "WAGO 221 接线端子",
    "hwm_esp32-s3-dev-kit-n16r8": "ESP32-S3 开发板",
}


def localized_hardware_name(record_id, record=None):
    """Return a safe UI label without changing the canonical hardware name."""

    record = record if isinstance(record, dict) else {}
    explicit = record.get("display_name_zh")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    model_id = record.get("hardware_model_id") or record.get("model_ref") or record_id
    return HARDWARE_DISPLAY_NAMES_ZH.get(model_id, "")
