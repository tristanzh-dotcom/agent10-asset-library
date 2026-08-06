# Hardware Library Obsidian User Experience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将已接受的硬件记录渲染为中文优先、带图片和关系链接的 Obsidian 卡片，并生成无需 Dataview 的库存索引。

**Architecture:** 保留 `hardware_model`、`hardware_unit` 和 `assembly_layout` 作为唯一事实记录。新增纯函数式 Markdown 投影和索引发布器；`HardwareNotePublisher` 在成功写入卡片并更新 SQLite 镜像后，可选地重建固定索引页。旧记录没有新显示字段时使用稳定的本地中文标签和英文原名，不执行 Vault 迁移。

**Tech Stack:** Python 标准库、现有 Markdown/YAML 渲染器、Obsidian REST writer、SQLite `HardwareStore`、Python `unittest`。

## Global Constraints

- 索引必须是纯 Markdown，不依赖 Dataview、Bases 或其他插件。
- `display_name`、`aliases`、中文分类名、摘要和 Obsidian 链接是用户投影，不构成第四个事实源。
- Obsidian 是人类可读主记录；SQLite 是可重建查询镜像。
- 正式事实仍只能从已接受且 snapshot hash 匹配的 intake 发布。
- 不执行真实 AgentAssetVault 写入、照片复制、外部 URL 抓取或模型调用。
- 不覆盖当前工作树中已有的 `asset_library/hardware_service.py`、`tests/test_hardware_service.py` 和 `asset_library/hardware_labels.py` 改动；只在兼容边界内使用它们。
- 不直接执行 Git commit；后续 Git 变更走受治理 Git 路径。

---

## File Structure

| Path | Responsibility |
|---|---|
| `asset_library/hardware_notes.py` | 用户可读硬件卡片、显示名称、图片/关系链接和兼容发布器 |
| `asset_library/hardware_indexes.py` | 纯 Markdown 首页、库存、分类、范围、布局和待核验索引 |
| `asset_library/runtime.py` | 将可选索引发布器接入受控 runtime |
| `tests/test_hardware_notes.py` | 卡片正文、名称、图片、关系和敏感信息回归测试 |
| `tests/test_hardware_indexes.py` | 索引渲染、聚合、链接、空库存和部分失败测试 |
| `tests/test_runtime.py` | runtime 暴露索引发布器的兼容性测试 |

### Task 1: 用户可读硬件卡片

**Files:**
- Modify: `asset_library/hardware_notes.py`
- Test: `tests/test_hardware_notes.py`

**Interfaces:**
- Preserve `hardware_note_path(record) -> str` for records without an explicit `file_label` so existing Vault paths remain stable.
- Extend `render_hardware_note(record, related_paths=None) -> str` without mutating `record`.
- Add `index_publisher=None` to `HardwareNotePublisher(rest_client, fallback_writer, store, operation_lock_factory=None, index_publisher=None)`; existing callers without it keep the current result contract.

- [ ] **Step 1: Write the failing card-rendering tests**

```python
def test_render_note_uses_user_display_name_and_chinese_summary():
    draft = valid_model()
    draft["display_name"] = "ESP32-S3 开发板 N16R8"
    markdown = render_hardware_note(draft)

    self.assertIn("# ESP32-S3 开发板 N16R8", markdown)
    self.assertIn("## 快速信息", markdown)
    self.assertIn("| 分类 | 开发板 |", markdown)
    self.assertIn("| 型号 | ESP32-S3-DEV-KIT-N16R8-M |", markdown)

def test_render_note_embeds_vault_photos_and_links_known_related_records():
    draft = valid_model()
    draft["photo_refs"] = ["02_Hardware/90_Evidence/photos/agent11/front.jpg"]
    draft["relations"] = [{"relation_type": "part_of_layout", "ref": "lay_demo"}]
    markdown = render_hardware_note(
        draft,
        {"lay_demo": "02_Hardware/30_Layouts/agent12/LAY - demo - lay_demo"},
    )

    self.assertIn("![[02_Hardware/90_Evidence/photos/agent11/front.jpg]]", markdown)
    self.assertIn("[[02_Hardware/30_Layouts/agent12/LAY - demo - lay_demo|装配布局]]", markdown)

def test_render_note_does_not_expose_private_attachment_paths():
    draft = valid_model()
    draft["photo_refs"] = ["/private/drafts/hwd_demo/front.jpg", "attachment:att_1"]
    markdown = render_hardware_note(draft)

    self.assertNotIn("/private/drafts/", markdown)
    self.assertNotIn("attachment:att_1", markdown)
```

- [ ] **Step 2: Run the failing card tests**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest tests.test_hardware_notes -v`

Expected: FAIL because the renderer currently emits the generic summary, English-only sections, and no photo/relationship projection.

- [ ] **Step 3: Implement the minimal card projection**

Add presentation-only helpers in `asset_library/hardware_notes.py`:

```python
def _display_name(record):
    explicit = record.get("display_name") or record.get("display_name_zh")
    if explicit:
        return str(explicit).strip()
    return localized_hardware_name(record_id_for(record), record) or record.get("canonical_name") or record_id_for(record)

def _related_link(record_id, label, related_paths):
    path = (related_paths or {}).get(record_id)
    return f"[[{path}|{label}]]" if path else f"`{record_id}`"
```

Render frontmatter fields `display_name` and `aliases` when supplied or derived, retain all safety redaction, and render the body in this order: title, original English name, first safe Vault photo, `## 一句话说明`, `## 快速信息`, `## 已知规格`, `## 适用与限制`, `## 相关库存`, `## 来源与核验`, `## 待补资料`, and the existing acceptance section. Preserve `## Summary`, `## Sources`, `## Related`, and `## Acceptance` headings in the generated output for backwards-compatible tests and readers. Render only non-absolute `02_Hardware/` photo references as embeds; ignore private attachment locators.

The quick-information table must show Chinese category, manufacturer, SKU, aggregate quantity when present, scope, user-facing record status, and evidence state. Missing values are written as `未提供` or `待核验`, never guessed. Relations use `related_paths` when known and otherwise remain visibly non-clickable IDs.

- [ ] **Step 4: Run the focused card tests**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest tests.test_hardware_notes -v`

Expected: PASS, including the existing safety, fallback, mirror-gap, and snapshot tests.

### Task 2: Pure Markdown index bundle

**Files:**
- Create: `asset_library/hardware_indexes.py`
- Create: `tests/test_hardware_indexes.py`

**Interfaces:**
- Produce `render_hardware_index_bundle(records, generated_at=None) -> dict[str, str]`.
- Bundle keys must be exactly `02_Hardware/00_Index/Hardware Home.md`, `Inventory.md`, `Models by Category.md`, `Inventory by Scope.md`, `Layouts.md`, and `Needs Verification.md`.
- Define `HardwareIndexPublishResult(status: str, written: tuple, mode: str, error: str = "")` and produce it from `HardwareIndexPublisher.publish(records, generated_at=None)` using the existing REST-first/fallback writer shape. Pure rendering has no external side effects.

- [ ] **Step 1: Write the failing index tests**

```python
def test_index_bundle_renders_model_level_counts_and_links():
    model = valid_model()
    unit = valid_unit()
    unit["quantity_total"] = 2
    unit["quantity_available"] = 2
    records = [model, unit]
    bundle = render_hardware_index_bundle(records, generated_at="2026-08-06T12:00:00+08:00")

    home = bundle["02_Hardware/00_Index/Hardware Home.md"]
    inventory = bundle["02_Hardware/00_Index/Inventory.md"]
    self.assertIn("# Hardware Home", home)
    self.assertIn("硬件型号数 | 1", home)
    self.assertIn("可用 / 总数", home)
    self.assertIn("2 / 2", home)
    self.assertIn("[[02_Hardware/10_Models/Controllers/HWM - ESP32-S3 Development Kit N16R8 - hwm_esp32-s3-dev-kit-n16r8|ESP32-S3 开发板]]", home)
    self.assertIn("2 / 2", inventory)

def test_index_bundle_lists_zero_inventory_and_needs_verification():
    model = valid_model()
    model["photo_refs"] = []
    records = [model]
    bundle = render_hardware_index_bundle(records)

    self.assertIn("0 / 0", bundle["02_Hardware/00_Index/Hardware Home.md"])
    self.assertIn("ESP32-S3 开发板", bundle["02_Hardware/00_Index/Needs Verification.md"])

def test_index_publisher_reports_partial_failure_without_claiming_success():
    class FailingRest:
        def write_note(self, _path, _markdown):
            raise ConnectionError("rest unavailable")

    publisher = HardwareIndexPublisher(FailingRest(), None)
    result = publisher.publish([valid_model()])
    self.assertEqual(result.status, "partial")
    self.assertEqual(result.written, ())
```

- [ ] **Step 2: Run the failing index tests**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest tests.test_hardware_indexes -v`

Expected: FAIL because `asset_library.hardware_indexes` does not exist.

- [ ] **Step 3: Implement deterministic bundle rendering**

Group `hardware_unit` records by `model_ref`; aggregate `quantity_total` and `quantity_available` only when units exist, otherwise render `0 / 0`. Sort models by user display name and stable ID. Use the existing category mapping and `hardware_note_path` to produce Obsidian links without copying note facts into the index.

`Hardware Home.md` must contain generated time, four metrics, and one model-level table. `Inventory.md` contains the same aggregation with scopes. `Models by Category.md` groups links by Chinese category. `Inventory by Scope.md` groups model links and `可用 / 总数` by scope. `Layouts.md` lists layout links and member links. `Needs Verification.md` includes records whose evidence level is `reported`, `label_or_photo`, or `unverified`, or whose verification timestamp is absent.

- [ ] **Step 4: Implement REST-first index publication**

`HardwareIndexPublisher.publish` writes the fixed six paths in sorted order. It uses REST first, falls back only when REST fails before a write, returns `published` only when every path is written, and returns `partial` with the written paths when any later write fails. It must not log Markdown bodies, credentials, or private paths.

- [ ] **Step 5: Run index tests**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest tests.test_hardware_indexes -v`

Expected: PASS, with stable output and no plugin-specific syntax.

### Task 3: Optional publication wiring

**Files:**
- Modify: `asset_library/hardware_notes.py`
- Modify: `asset_library/runtime.py`
- Test: `tests/test_hardware_notes.py`
- Test: `tests/test_runtime.py`

**Interfaces:**
- `HardwareNotePublisher` accepts an optional `index_publisher` without changing existing callers.
- `AssetLibraryRuntime` exposes `hardware_index_publisher`.

- [ ] **Step 1: Write the failing wiring tests**

```python
def test_note_publisher_rebuilds_indexes_after_mirror_upsert():
    class RecordingIndexPublisher:
        def __init__(self):
            self.records = []

        def publish(self, records):
            self.records.append(list(records))
            return type("Result", (), {"status": "published"})()

    class RecordingRest:
        def __init__(self):
            self.calls = []

        def write_note(self, path, markdown):
            self.calls.append((path, markdown))

    accepted = self._accepted()
    store = HardwareStore(Path(tempfile.mkdtemp()) / "hardware.sqlite3")
    rest = RecordingRest()
    publisher = RecordingIndexPublisher()
    note_publisher = HardwareNotePublisher(rest, None, store, index_publisher=publisher)
    result = note_publisher.publish(accepted)
    self.assertEqual(result.status, "published")
    self.assertEqual(len(publisher.records), 1)

def test_runtime_assembles_index_publisher_with_same_rest_and_fallback_clients():
    runtime = build_runtime(env={
        "AGENT_ASSET_VAULT_PATH": tempfile.mkdtemp(),
        "OBSIDIAN_REST_API_KEY": "secret",
        "OBSIDIAN_REST_BASE_URL": "https://127.0.0.1:27124",
    })
    self.assertIsNotNone(runtime.hardware_index_publisher)
```

The wiring test reuses the existing `HardwareNotesTests._accepted` fixture and defines `RecordingRest.write_note` as the same in-memory recorder used by the existing publisher tests. `tempfile`, `Path`, `HardwareStore`, and `build_runtime` are imported in the test module.

- [ ] **Step 2: Run wiring tests to verify red**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest tests.test_hardware_notes tests.test_runtime -v`

Expected: FAIL because the optional publisher and runtime field do not exist.

- [ ] **Step 3: Wire publication after the accepted record is mirrored**

After `HardwareNotePublisher` successfully writes the card and calls `store.upsert_record`, collect `store.list_records()` and invoke the optional index publisher. If index publication is partial, record a `hardware-indexes` mirror gap and return the existing `HardwarePublishResult` with `status="partial"`; never claim the whole publication succeeded. Existing callers without `index_publisher` retain `mirror_status="upserted"`.

Instantiate `HardwareIndexPublisher` in `build_runtime` with the same REST client, fallback writer, and operation lock factory used by hardware notes. Do not perform bootstrap or real Vault writes during runtime construction.

- [ ] **Step 4: Run wiring tests**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest tests.test_hardware_notes tests.test_runtime -v`

Expected: PASS, including existing runtime credential and lock-boundary tests.

## Minimal Verification Gate

Run only the affected test modules after implementation:

```bash
PYTHONPYCACHEPREFIX=/tmp/agent10-obsidian-pycache python3 -m unittest \
  tests.test_hardware_notes \
  tests.test_hardware_indexes \
  tests.test_runtime -v
```

Expected result: all selected tests pass with zero failures and no warnings. Do not claim actual Obsidian acceptance; that requires a separately authorized controlled Vault write and refresh/reopen check.

## Self-Review Checklist

- [ ] Existing note paths remain stable when no explicit `file_label` is present.
- [ ] User display labels never overwrite canonical names or stable IDs.
- [ ] Home and index pages contain only aggregate/user-facing data and Obsidian links.
- [ ] Private attachments, absolute paths, tokens, and raw source bodies do not enter Markdown.
- [ ] Index failure is visibly partial and leaves a retryable gap.
- [ ] No actual AgentAssetVault write is performed by unit tests.
