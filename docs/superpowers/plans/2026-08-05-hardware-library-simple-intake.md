# 简化硬件资料库 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 TZ 以“看库存、上传照片/链接、确认建议”的最少交互维护硬件资料，同时保留 Agent10 的 Obsidian-first、快照验收和证据边界。

**Architecture:** 保留现有 `hardware_model`、`hardware_unit` 和 `assembly_layout` 作为受治理事实；新增草稿、附件、资料和分析作业层，把它们编译成既有 intake 后才发布。`inventory_summary` 从已发布记录聚合生成，Web 只消费脱敏 summary/草稿状态；Web 代理继续在服务端注入 Agent10 token。

**Tech Stack:** Python 标准库（HTTP、SQLite、哈希、文件系统）、现有 Agent10 HTTP 服务/Obsidian writer、Node Web server 与原生浏览器模块、现有 Node/Python 测试。

## Global Constraints

- 不改变共享 Web 壳、侧栏、主题或全局 CSS；所有 Web 样式限定 `.agent10-page` 路由范围。
- 浏览器永不取得 Agent10 token、Obsidian REST key、原始网页正文、私有附件路径或敏感设备身份。
- 模型结果是候选；URL/附件验证、事实等级、去重、快照、验收、Obsidian 写入和镜像一致性必须是确定性逻辑。
- 公开 URL 只在用户点击后抓取，逐跳防 SSRF；不携带 Cookie、认证头或用户环境凭据。
- 未登记 `Agent10 / hardware_reference_analysis` 模型路线时，分析 API 必须明确不可用且 fail closed，禁止外发图片或网页正文。
- 发布仍只有现有 snapshot-hash 验收链可写入 Obsidian；局部写入不得报告成功。
- 现有 24 条硬件记录、关系 API 和 Obsidian 页面保持可读；不执行破坏性迁移。
- Git 最终提交与推送走 Agent08 manifest/prepare/confirm；本计划中的“提交”不授权直接 `git commit`。

---

## File Structure

| 路径 | 职责 |
|---|---|
| `asset_library/hardware_drafts.py` | 草稿状态、版本、可编辑字段与 legacy-intake 编译 |
| `asset_library/hardware_attachments.py` | 图片校验、哈希、私有存储与安全缩略图元数据 |
| `asset_library/hardware_sources.py` | 单 HTTPS URL 校验、受限抓取、内容哈希与资料元数据 |
| `asset_library/hardware_analysis.py` | 确定性候选合并、作业状态与受治理模型适配器接口 |
| `asset_library/hardware_store.py` | 草稿/附件/来源/作业表和库存 summary 查询 |
| `asset_library/hardware_service.py` | 草稿到 intake 的协调、幂等和发布前校验 |
| `asset_library/hardware_api.py` | 脱敏 API 路由与 mutation 校验 |
| `asset_library/hardware_notes.py` | 长期 Obsidian 页面中的资料/证据呈现，不写私有路径 |
| `asset_library/runtime.py` | 私有附件根与可选分析器的运行时组合 |
| `web/server.mjs` | `/agent10` HTML、Web allowlist、服务端代理 |
| `web/app/agent10.js` | 库存总览与引导录入/编辑状态机 |
| `web/app/agent10.css` | 路由专属响应式布局 |
| `web/config/agents/agent10.contract.json`、`web/docs/agents/agent10-publishing-config.md` | Web 接口、上传和模型边界 |
| `GLOBAL_MODEL_ROUTING_RECORD.md` | 仅在 TZ 明确选择并批准提供商/模型后登记运行时路线 |

### Task 1: 库存聚合投影与兼容性

**Files:**
- Modify: `asset_library/hardware_store.py`
- Modify: `asset_library/hardware_service.py`
- Modify: `asset_library/hardware_api.py`
- Test: `tests/test_hardware_store.py`
- Test: `tests/test_hardware_service.py`
- Test: `tests/test_hardware_api.py`

**Interfaces:**
- Produces `HardwareStore.inventory_summary(query="", category=None) -> list[dict]`.
- Produces `HardwareService.list_inventory_summary(query="", category=None) -> dict`.
- Produces `GET /api/agent10/hardware/summary` with only redacted aggregate fields.

- [ ] **Step 1: Write failing aggregate tests**

```python
def test_inventory_summary_groups_units_by_model_and_preserves_unknown_counts():
    store = HardwareStore(db_path)
    store.upsert_record(model("hwm_esp"), "02_Hardware/10_Models/ESP.md")
    store.upsert_record(unit("hwu_a", "hwm_esp", total=2, available=1), "02_Hardware/20_Units/A.md")
    store.upsert_record(unit("hwu_b", "hwm_esp", total=3, available=3), "02_Hardware/20_Units/B.md")
    assert store.inventory_summary() == [{
        "item_id": "hwm_esp", "display_name": "ESP", "quantity_total": 5,
        "quantity_available": 4, "status": "ready", "category": "开发板",
    }]
```

- [ ] **Step 2: Run the failing tests**

Run: `python3 -m unittest tests.test_hardware_store tests.test_hardware_service tests.test_hardware_api -q`  
Expected: FAIL because `inventory_summary` and `/summary` do not exist.

- [ ] **Step 3: Implement pure aggregation and redaction**

```python
def inventory_summary(self, query="", category=None):
    models, units = self._published_models_and_units()
    return [_summary_for(model, units.get(model["hardware_model_id"], []))
            for model in models if _matches_summary(model, query, category)]

def list_inventory_summary(self, query="", category=None):
    rows = self.store.inventory_summary(query, category)
    return {"items": rows, "metrics": _inventory_metrics(rows)}
```

`_summary_for` must derive `quantity_total`/`quantity_available` only from published `hardware_unit` records; models without units report `None`, not zero. `_redact` must remove evidence paths, technical document bodies and attachment references before response.

- [ ] **Step 4: Verify contract and backwards compatibility**

Run: `python3 -m unittest tests.test_hardware_store tests.test_hardware_service tests.test_hardware_api -q`  
Expected: PASS; existing `/hardware`, detail and relations tests remain green.

- [ ] **Step 5: Propose the scoped Agent08 commit**

Propose only the listed Agent10 files and tests through Agent08 after all tasks in this plan’s first release pass; do not create a direct Git commit.

### Task 2: Versioned simple drafts and legacy compilation

**Files:**
- Create: `asset_library/hardware_drafts.py`
- Modify: `asset_library/hardware_store.py`
- Modify: `asset_library/hardware_service.py`
- Modify: `asset_library/hardware_api.py`
- Test: `tests/test_hardware_drafts.py`
- Test: `tests/test_hardware_store.py`
- Test: `tests/test_hardware_service.py`
- Test: `tests/test_hardware_api.py`

**Interfaces:**
- Produces `create_draft(base_record_id=None) -> dict`, `patch_draft(draft_id, expected_revision, changes) -> dict`, `prepare_draft(draft_id, expected_revision, actor) -> dict`, and `accept_draft(draft_id, expected_bundle_hash, accepted_by) -> dict`.
- `prepare_draft` returns one immutable confirmation bundle containing existing per-record intakes; `accept_draft` coordinates their existing `HardwareService.submit`/`accept` publication paths and fails visibly on any partial result.

- [ ] **Step 1: Write failing state-machine tests**

```python
def test_prepare_requires_name_quantity_and_explicit_merge_choice():
    draft = service.create_draft()
    with self.assertRaisesRegex(ValueError, "display_name"):
        service.prepare_draft(draft["draft_id"], draft["revision"], "TZ")

def test_patch_rejects_stale_revision_without_overwriting_latest_values():
    first = service.patch_draft("hwd_x", 1, {"display_name": "ESP32", "quantity": 2})
    with self.assertRaisesRegex(ValueError, "stale draft revision"):
        service.patch_draft("hwd_x", 1, {"quantity": 9})
    self.assertEqual(first["revision"], 2)
```

- [ ] **Step 2: Run the failing draft tests**

Run: `python3 -m unittest tests.test_hardware_drafts tests.test_hardware_service tests.test_hardware_api -q`  
Expected: FAIL because the draft service and API do not exist.

- [ ] **Step 3: Implement draft persistence and compiler**

```python
EDITABLE_DRAFT_FIELDS = {"display_name", "quantity", "merge_target_id", "note", "category"}

def compile_draft_to_records(draft, model_id_factory, unit_id_factory):
    _require_confirmable_fields(draft)
    model = _model_record_from(draft, model_id_factory)
    unit = _inventory_batch_from(draft, model, unit_id_factory)
    return {"model": model, "unit": unit}
```

Persist `draft_id`, `revision`, `status`, source IDs, user-editable fields and content hashes in SQLite. A new item compiles to one model plus one inventory batch in one immutable confirmation bundle. A merge compiles only a new inventory batch referenced to the selected existing model. `accept_draft` accepts the matching bundle hash and coordinates its per-record existing intake publications; it returns `partial` if any record cannot publish. Do not mutate a published batch in place. Generate stable IDs server-side; reject arbitrary client IDs.

- [ ] **Step 4: Add API version checks**

Add `POST /hardware/drafts`, `PATCH /hardware/drafts/:id`, `POST /hardware/drafts/:id/prepare`, and `POST /hardware/drafts/:id/accept`. Each mutation requires `expected_revision`; `PATCH` returns 409 for stale revision, `prepare` returns the bundle hash and per-record intake IDs, and `accept` accepts only that bundle hash.

- [ ] **Step 5: Verify idempotency and snapshot behavior**

Run: `python3 -m unittest tests.test_hardware_drafts tests.test_hardware_store tests.test_hardware_service tests.test_hardware_api -q`  
Expected: PASS, including repeated prepare with the same operation key and stale-snapshot rejection through existing intake tests.

### Task 3: 安全图片附件与单链接资料

**Files:**
- Create: `asset_library/hardware_attachments.py`
- Create: `asset_library/hardware_sources.py`
- Modify: `asset_library/hardware_store.py`
- Modify: `asset_library/hardware_service.py`
- Modify: `asset_library/hardware_api.py`
- Modify: `asset_library/runtime.py`
- Test: `tests/test_hardware_attachments.py`
- Test: `tests/test_hardware_sources.py`
- Test: `tests/test_hardware_api.py`

**Interfaces:**
- Produces `AttachmentService.store_image(draft_id, filename, content_type, stream) -> dict`.
- Produces `ReferenceFetcher.fetch(url) -> ReferenceCapture`.
- Produces `POST /hardware/drafts/:id/attachments` and `POST /hardware/drafts/:id/reference`.

- [ ] **Step 1: Write failing safety tests**

```python
def test_reference_fetch_rejects_private_redirect_before_requesting_body():
    with self.assertRaisesRegex(ValueError, "private address"):
        fetcher.fetch("https://vendor.example/manual", resolver=redirect_to("127.0.0.1"))

def test_image_upload_stores_hashed_private_file_and_never_returns_path():
    result = attachments.store_image("hwd_x", "board.jpg", "image/jpeg", BytesIO(JPEG))
    self.assertEqual(result["sha256"], sha256(JPEG).hexdigest())
    self.assertNotIn("path", result)
```

- [ ] **Step 2: Run the failing safety tests**

Run: `python3 -m unittest tests.test_hardware_attachments tests.test_hardware_sources tests.test_hardware_api -q`  
Expected: FAIL because no attachment/source services exist.

- [ ] **Step 3: Implement bounded private attachment storage**

```python
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 12 * 1024 * 1024

def store_image(self, draft_id, filename, content_type, stream):
    payload = _read_limited(stream, MAX_IMAGE_BYTES)
    _validate_image(content_type, payload)
    digest = sha256(payload).hexdigest()
    return self.store.save_attachment(draft_id, digest, _sanitize_name(filename), content_type, payload)
```

Store files below the configured Agent10 private draft root with owner-only permissions and hash-derived names. Strip EXIF during derivative generation; store original-byte hashes and derivative metadata separately. Do not mount this directory in Web. Enforce one small bounded multipart parser; reject duplicate form fields and non-image parts.

- [ ] **Step 4: Implement controlled single-URL fetch**

```python
def fetch(self, raw_url):
    url = _validate_public_https_url(raw_url)
    response = self._request_with_validated_redirects(url, max_redirects=3)
    return _capture(response, max_bytes=512 * 1024, allowed_types={"text/html", "application/pdf"})
```

Resolve and validate every host before connect; reject credentials, non-HTTPS, loopback, link-local, private, multicast and reserved targets. Send only a fixed user agent and `Accept`; no cookies/authorization. Persist canonical URL, retrieval timestamp, response content type, SHA-256, bounded extracted text and safe title. HTML/PDF extraction failure creates a retained `link_only` capture, not a fake extraction.

- [ ] **Step 5: Verify no sensitive projection leaks**

Run: `python3 -m unittest tests.test_hardware_attachments tests.test_hardware_sources tests.test_hardware_api tests.test_http_server -q`  
Expected: PASS; response JSON contains neither attachment filesystem paths nor captured source body.

### Task 4: 候选分析作业与证据比较

**Files:**
- Create: `asset_library/hardware_analysis.py`
- Modify: `asset_library/hardware_store.py`
- Modify: `asset_library/hardware_service.py`
- Modify: `asset_library/hardware_api.py`
- Test: `tests/test_hardware_analysis.py`
- Test: `tests/test_hardware_service.py`
- Test: `tests/test_hardware_api.py`

**Interfaces:**
- Produces `AnalysisEngine.start(draft_id, operation_key) -> dict` and `AnalysisEngine.status(job_id) -> dict`.
- Produces `compare_candidates(draft, capture, image_candidates) -> list[dict]`.

- [ ] **Step 1: Write failing candidate-boundary tests**

```python
def test_photo_dimension_candidate_remains_label_or_photo_not_measured():
    comparison = compare_candidates(draft, None, [{"field": "length_mm", "value": 200, "origin": "image"}])
    self.assertEqual(comparison[0]["evidence_level"], "label_or_photo")
    self.assertNotEqual(comparison[0]["evidence_level"], "measured")

def test_unconfigured_model_marks_job_unavailable_without_egress():
    job = engine.start("hwd_x", "op_x")
    self.assertEqual(job["status"], "unavailable")
    self.assertEqual(fake_model.calls, [])
```

- [ ] **Step 2: Run the failing analysis tests**

Run: `python3 -m unittest tests.test_hardware_analysis tests.test_hardware_service tests.test_hardware_api -q`  
Expected: FAIL because analysis job/state functions do not exist.

- [ ] **Step 3: Implement deterministic job state and comparison**

```python
JOB_STATUSES = {"queued", "running", "completed", "unavailable", "failed"}

def compare_candidates(draft, capture, image_candidates):
    candidates = _normalize_candidates(capture, image_candidates)
    return [_comparison_row(candidate, draft) for candidate in candidates]
```

Jobs are idempotent on draft revision plus operation key. Store only structured candidates, source locators, bounded error codes and model execution receipt; never model chain-of-thought. A capture with no hardware candidates returns `completed` and `reference_status: "retained_without_hardware_candidates"`.

- [ ] **Step 4: Expose the narrow job API**

Add `POST /hardware/drafts/:id/analyze` and `GET /hardware/analysis-jobs/:id`. Redact attachment paths, raw source text, raw model messages and all credentials. Return `unavailable` when no approved adapter has been injected.

- [ ] **Step 5: Verify semantic and security boundaries**

Run: `python3 -m unittest tests.test_hardware_analysis tests.test_hardware_service tests.test_hardware_api -q`  
Expected: PASS, including conflict display, source-without-hardware result, no silent fallback and candidate-not-fact assertions.

### Task 5: 受批准模型路线的受控适配器

**Files:**
- Modify: `/Users/tristanzh/agent/GLOBAL_MODEL_ROUTING_RECORD.md`
- Modify: `asset_library/hardware_analysis.py`
- Modify: `asset_library/runtime.py`
- Modify: `README.md`
- Test: `tests/test_hardware_analysis.py`
- Test: `tests/test_runtime.py`

**Interfaces:**
- Consumes a route-specific `HardwareCandidateAnalyzer.analyze(images, reference_text, receipt_context) -> list[dict]` injected by runtime.
- Produces one machine-auditable receipt containing route key, provider, resolved model, bounded input classes, content hashes, timestamps, status and output schema version.

- [ ] **Step 1: Establish the explicit routing precondition**

Before writing an external adapter or sending any content, require a current Global Model Routing entry named `Agent10 / hardware_reference_analysis` that states an exact provider and resolved model, allowed image/text categories, input bounds, retention/receipt policy, availability and fail-closed fallback. If this entry is absent, retain the Task 4 unavailable adapter and do not modify provider credentials or invoke a network model.

- [ ] **Step 2: Write a failing registered-route test using a fake transport**

```python
def test_registered_adapter_sends_only_bounded_selected_inputs_and_records_receipt():
    result = adapter.analyze([safe_image], bounded_reference_text, receipt_context)
    self.assertEqual(transport.payload["route_key"], "hardware_reference_analysis")
    self.assertLessEqual(len(transport.payload["reference_text"]), MAX_REFERENCE_CHARS)
    self.assertEqual(result.receipt["status"], "completed")
```

- [ ] **Step 3: Run the failing adapter test**

Run: `python3 -m unittest tests.test_hardware_analysis tests.test_runtime -q`  
Expected: FAIL until the registered adapter exists; when the routing precondition is absent this step is intentionally not run against a real provider.

- [ ] **Step 4: Implement only the approved adapter contract**

```python
class HardwareCandidateAnalyzer:
    def analyze(self, images, reference_text, receipt_context):
        response = self.transport.call(_bounded_request(images, reference_text))
        return _validated_candidate_result(response, receipt_context)
```

Use a route-specific environment/config key only after the global record authorizes it; do not reuse another project’s model client or credentials. Enforce size/count limits before transport, validate structured output, record the receipt, and return `failed`/`unavailable` without fallback on transport/schema errors.

- [ ] **Step 5: Verify registered-route behavior without live provider content**

Run: `python3 -m unittest tests.test_hardware_analysis tests.test_runtime -q`  
Expected: PASS with fake transport; a live smoke call is a separate explicit TZ-authorized external-evidence action after credentials and route availability are verified.

### Task 6: Agent10 Web 双页面与受控确认

**Files:**
- Modify: `/Users/tristanzh/agent/web/server.mjs`
- Modify: `/Users/tristanzh/agent/web/app/agent10.js`
- Modify: `/Users/tristanzh/agent/web/app/agent10.css`
- Modify: `/Users/tristanzh/agent/web/config/agents/agent10.contract.json`
- Modify: `/Users/tristanzh/agent/web/docs/agents/agent10-publishing-config.md`
- Test: `/Users/tristanzh/agent/web/tests/agent10-service.test.mjs`
- Test: `/Users/tristanzh/agent/web/tests/agent10-hardware-browser.test.mjs`
- Test: `/Users/tristanzh/agent/web/tests/new-agent-publishing-contract.test.mjs`

**Interfaces:**
- Consumes the Task 1–4 APIs through `/api/agent10/*` only.
- Produces route state `browse | intake`, held in the URL query but no draft content in browser storage.

- [ ] **Step 1: Write failing service and browser tests**

```js
test('Agent10 publishes only simplified inventory and draft APIs', () => {
  assert.equal(isPublishedAgent10Api('/api/agent10/hardware/summary', 'GET'), true);
  assert.equal(isPublishedAgent10Api('/api/agent10/hardware/drafts', 'POST'), true);
  assert.equal(isPublishedAgent10Api('/api/agent10/hardware/drafts/x/attachments', 'POST'), true);
});

test('Agent10 shows inventory metrics and a guided intake without JSON textarea', async () => {
  await page.goto(`${baseUrl}/agent10?hardware=intake`);
  assert.equal(await page.locator('[data-agent10-request-draft]').count(), 0);
  await expect(page.locator('[data-agent10-intake-form]')).toBeVisible();
});
```

- [ ] **Step 2: Run the failing Web tests**

Run: `node --test tests/agent10-service.test.mjs tests/agent10-hardware-browser.test.mjs`  
Expected: FAIL because the new route allowlist, inventory metrics and guided form do not exist.

- [ ] **Step 3: Implement route-owned markup, state and CSS**

Replace the raw JSON `<details>` panel with a browse view and a guided intake view. Browse fetches summary plus selected detail; intake creates a draft, uploads selected files through `FormData`, saves the one URL only when requested, polls a job while visible, and renders a minimal editable suggestion card. Use query `?hardware=browse`/`?hardware=intake&draft=<id>`; on refresh reload server data and never recreate an acceptance claim.

Add only route-scoped selectors such as `.agent10-inventory-metrics`, `.agent10-intake-form`, `.agent10-suggestion-card` and responsive grid rules inside `.agent10-page`. Keep shared shell selectors untouched.

- [ ] **Step 4: Implement server-only proxy and confirmation identity**

Extend `isPublishedAgent10Api` with exact draft/attachment/reference/job paths and methods; reject all other Agent10 paths. Preserve server-side token injection. Remove browser-supplied `accepted_by`; final acceptance uses the Web’s controlled local operator identity and disables the button when no identity is configured.

- [ ] **Step 5: Verify the direct consumer boundary**

Run: `node --check server.mjs && node --check app/agent10.js && node --test tests/agent10-service.test.mjs tests/agent10-hardware-browser.test.mjs tests/new-agent-publishing-contract.test.mjs`  
Expected: PASS, with desktop and narrow browser assertions for no JSON form, no horizontal overflow, upload state, unavailable-analysis state, and no token/raw-path leakage.

### Task 7: Obsidian presentation, documentation and release evidence

**Files:**
- Modify: `asset_library/hardware_notes.py`
- Modify: `README.md`
- Modify: `docs/hardware/HANDOVER_hardware-library-acceptance-20260804.md`
- Test: `tests/test_hardware_notes.py`
- Test: `tests/test_hardware_service.py`

**Interfaces:**
- Consumes accepted compiled model/unit records with reference and evidence summaries.
- Produces readable `02_Hardware` notes with source URL, evidence level, reference state and unknown physical constraints.

- [ ] **Step 1: Write failing note-rendering tests**

```python
def test_note_preserves_reference_without_hardware_claim_and_hides_private_paths():
    markdown = render_hardware_note(accepted_record_with_link_only_reference())
    self.assertIn("资料已保存，未形成硬件候选", markdown)
    self.assertNotIn("/private/drafts/", markdown)
```

- [ ] **Step 2: Run the failing note tests**

Run: `python3 -m unittest tests.test_hardware_notes tests.test_hardware_service -q`  
Expected: FAIL until source/reference sections are rendered safely.

- [ ] **Step 3: Render concise source and unknown-state sections**

Render a stable “参考资料” section with safe URL, retrieved date, capture hash and `link_only`/candidate state. Render “待补物理信息” for null dimensions, hole patterns, bend radius, thermal spacing and clearance. Never include original attachments, raw captured body, source filesystem path, tokens or device identity.

- [ ] **Step 4: Run release-proportional Agent10 verification**

Run: `PYTHONPYCACHEPREFIX=/tmp/agent10-simple-intake-pycache python3 -m compileall -q asset_library tests && python3 -m unittest tests.test_hardware_store tests.test_hardware_drafts tests.test_hardware_attachments tests.test_hardware_sources tests.test_hardware_analysis tests.test_hardware_service tests.test_hardware_api tests.test_hardware_notes tests.test_runtime -q && git diff --check`  
Expected: PASS. This is Level 2/3 direct-contract verification; do not run full unittest discovery unless an actual migration, shared-auth change, or TZ release request triggers Level 4.

- [ ] **Step 5: Perform safe runtime and Web evidence checks**

Use a local authenticated read-only GET for `/api/agent10/hardware/summary`, inspect the returned redacted keys, and open `/agent10` at desktop and narrow widths through the governed local service. Do not submit a real hardware record, invoke an external model, or write a real Vault record during verification.

- [ ] **Step 6: Prepare final Git control request**

Report exact changed paths, tests, the model-route state, skipped live external/Vault checks and any unrelated dirty files. Supply Agent08 with the scoped manifest, proposed commit message and push intent; do not stage, commit or push unrelated changes.

## Plan Self-Review

- Spec coverage: Tasks 1–2 implement simple aggregate inventory and confirmable drafts; Task 3 implements private photos and one safe URL; Task 4 keeps candidates non-factual; Task 5 isolates the explicit model-route gate; Task 6 implements the two Web pages and server-only proxy; Task 7 preserves Obsidian, documents evidence and verifies direct consumers.
- Placeholder scan: no incomplete implementation markers are present. The model provider is an explicit external-authority precondition, not an implicit fallback or unspecified implementation detail.
- Type consistency: Task 2 owns `draft_id`/`revision`; Task 3 attaches sources to that ID; Task 4 returns a job for that ID; Task 6 consumes those exact paths; Task 2 compiles only to the existing intake/accept contract.
