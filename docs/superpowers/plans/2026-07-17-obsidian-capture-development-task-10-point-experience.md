# Obsidian Capture 开发任务 10 分体验 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Use superpowers:test-driven-development for every lifecycle, quality, migration, and public-contract change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Obsidian Capture 的开发任务升级为目标稳定、跨日连续、状态可信、首屏高密度且可在“开发任务中心”快速浏览的单卡双层体验，同时保持日常运行零模型调用和历史迁移可逆。

**Architecture:** 继续以本地 append-only Ledger 和结构化来源为事实层；增加明确的任务生命周期契约与只读任务投影；渲染器只消费投影和质量结果，生成面向人首屏与折叠审计层；独立的 Obsidian Base 只聚合任务卡属性。既有项目日报、正式 Agent10 资产正文和共享监督器行为保持不变。

**Tech Stack:** Python 3、`unittest`、JSON/JSONL、Markdown/YAML、Obsidian Bases、Obsidian CSS snippets、现有 Agent10 草稿契约。

## Global Constraints

- 权威规格：`agent10-asset-library/docs/superpowers/specs/2026-07-17-obsidian-capture-development-task-10-point-experience-design.md`。
- 本计划仅处理“开发任务”；不得改变项目日报的正文、汇总指标、生成频率或跨日冻结规则。
- 本计划在开发任务生命周期、渲染和浏览入口范围内取代旧的 V1/V2 计划；已验证的并发安全、事件归属、出站队列和迁移安全能力继续复用。
- 任务事实、状态判断、质量门、Markdown 和 Base 全部本地确定性执行。未注册语义路由时，产品运行时模型调用必须为零。
- 不保存原始聊天、命令、补丁、完整工具输出、凭据、令牌、环境变量值或无关个人数据。
- 不改写既有正式 Agent10 资产正文；只允许扩展新草稿的兼容枚举和验证。
- 用户区域逐字节归用户所有。系统区域摘要不匹配、来源变化或人工冲突时必须失败关闭。
- 保留无关未提交修改。Git 状态只读；所有 Git 写操作只可由 `/agent08` 执行。
- `Codex-Ops/codex-capture` 不是 Git worktree；该目录通过测试证据、文件摘要和受控安装记录交付。
- 当前回归底线：Capture `65 passed`，Agent10 `107 passed`。任何旧测试与批准规格冲突时，先把测试标记为 `needs update`，再用新规格断言替换，不保留过时业务行为。

## Canonical Contracts

### Internal lifecycle

```python
TASK_STATES = (
    "in_progress",
    "blocked",
    "pending_acceptance",
    "completed",
    "handed_off",
    "cancelled",
    "paused",
)

HUMAN_STATUS = {
    "in_progress": "进行中",
    "blocked": "阻塞",
    "pending_acceptance": "待验收",
    "completed": "已完成",
    "handed_off": "已交接",
    "cancelled": "已取消",
    "paused": "暂停",
}

TERMINAL_STATES = {"completed", "handed_off", "cancelled"}
PUBLISHABLE_TERMINAL_STATES = {"completed", "handed_off", "cancelled"}
```

`checkpoint` 只保存在 `checkpoint_at`，不再是生命周期状态。旧状态读取映射固定为：

```python
LEGACY_STATE_MAP = {
    "active": "in_progress",
    "checkpoint": "in_progress",
    "dormant": "paused",
    "completed": "completed",
    "handed_off": "handed_off",
}
```

### Task projection

```python
@dataclass(frozen=True)
class TaskProjection:
    title: str
    objective: str
    status: str
    status_label: str
    is_cross_day: bool
    current_progress: tuple[str, ...]
    current_result: tuple[str, ...]
    verification: tuple[str, ...]
    blockers: tuple[str, ...]
    unblock_conditions: tuple[str, ...]
    next_actions: tuple[str, ...]
    acceptance_items: tuple[str, ...]
    outputs: tuple[str, ...]
    timeline: tuple[dict, ...]
    decisions: tuple[str, ...]
    conflicts: tuple[dict, ...]
    source_refs: tuple[str, ...]
```

`TaskProjection` 是渲染器唯一的业务输入。它只能整理已有结构化事实，不得决定生命周期状态。

### Quality result

```python
@dataclass(frozen=True)
class QualityAssessment:
    completeness_state: str
    readability_state: str
    trust_state: str
    consistency_state: str
    publication_eligibility: str
    needs_enrichment: bool
    issues: tuple[str, ...]
```

允许值固定为：

- `completeness_state`: `complete | needs_evidence`
- `readability_state`: `clear | needs_rewrite`
- `trust_state`: `grounded | source_conflict | missing_source`
- `consistency_state`: `consistent | contradictory`
- `publication_eligibility`: `not_terminal | blocked | ready | publish_pending | published`

### Human-facing task properties

任务卡属性只写：

```yaml
项目: agent
状态: 进行中
开始日期: 2026-07-17
最后更新: 2026-07-18 15:40
今日活跃: 2026-07-18
跨日: true
当前进展: 正在实施任务投影
下一步: 完成双层渲染
验证: 生命周期回归已通过
cssclasses:
  - obsidian-capture-task
```

`task_id`、continuity key、Ledger、渲染版本和质量内部状态只进入本地状态或折叠审计层。

---

### Task 1: Lock the new lifecycle and task-boundary contract

**Files:**

- Create: `Codex-Ops/codex-capture/codex_capture/task_contract.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/tasks.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/events.py`
- Modify: `Codex-Ops/codex-capture/tests/test_tasks.py`
- Modify: `Codex-Ops/codex-capture/tests/test_events.py`
- Modify: `Codex-Ops/codex-capture/tests/test_hook_config.py`

**Interfaces:**

- `normalize_task_state(value: str) -> str`
- `human_status(value: str) -> str`
- `validate_transition(previous: str, current: str, reason: str = "", evidence: tuple[str, ...] = ()) -> None`
- `is_cross_day(task: dict, now: datetime) -> bool`
- `classify_prompt_role(text: str) -> str`
- `TaskEngine.resolve(event: dict, source_class: str, project: dict, now: datetime) -> dict | None`
- `TaskEngine.apply_handoff(task, handoff_path, now, successor_event=None) -> dict`

- [ ] Replace the obsolete dormant regression with failing tests proving 24 hours of inactivity produces `paused`, does not set `ended_at`, and same-goal recovery keeps the original `task_id` and continuity key.
- [ ] Add failing tests proving 15 minutes only sets `checkpoint_at`; `PreCompact`, restart, account switch, model switch, and a new session do not alter the human lifecycle.
- [ ] Add a table-driven failing test for `确认/开始/继续/执行/授权/状态怎么样/继续测试/继续修复/验收当前任务`, proving each is `task_control` or `task_continuation` and never creates a card.
- [ ] Add failing tests for the only observable new-task boundaries: explicit new-task marker, different resolved project, substantive input after a terminal task, or handoff with an explicit successor objective.
- [ ] Add a failing test proving an active task with an uncertain boundary remains the current task and records `boundary_uncertain` in the audit state instead of guessing a new task.
- [ ] Add state-transition tests for every allowed arrow in the approved state diagram and reject direct `blocked -> completed`, `paused -> completed`, and `pending_acceptance -> cancelled` transitions unless an explicit terminal reason is recorded.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_events tests.test_tasks tests.test_hook_config -v
```

Expected red result: failures mention legacy `checkpoint/dormant`, new successor creation after inactivity, missing `task_control`, or absent transition validation.

- [ ] Implement `task_contract.py` as the only lifecycle enum and transition owner. Remove duplicate status sets from `tasks.py` and publishing code.
- [ ] Change maintenance so 15 minutes updates only `checkpoint_at`; 24 hours changes an unfinished task to `paused` without `ended_at`.
- [ ] Change continuity selection to accept exactly one `in_progress | blocked | pending_acceptance | paused` task for the exact project path; consuming a marker resumes the same task only when the project and continuity key still match.
- [ ] Keep new-task resolution conservative: never infer a boundary from generic prose alone. Store uncertain boundary evidence for audit and wait for a deterministic boundary event.
- [ ] Change handoff behavior so it never manufactures a successor with the old title. Create and link a successor only when `successor_event` contains a new independent objective.
- [ ] Re-run the focused command. Expected result: all lifecycle, event, and continuity tests pass.

**Agent08 candidate:** `feat(obsidian-capture): adopt human task lifecycle and continuity contract`

---

### Task 2: Preserve a stable objective and structure material task facts

**Files:**

- Modify: `Codex-Ops/codex-capture/codex_capture/extraction.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/tasks.py`
- Create: `Codex-Ops/codex-capture/codex_capture/task_projection.py`
- Modify: `Codex-Ops/codex-capture/tests/test_extraction.py`
- Create: `Codex-Ops/codex-capture/tests/test_task_projection.py`
- Modify: `Codex-Ops/codex-capture/tests/test_runtime.py`

**Interfaces:**

- `extract_source_items(event, event_ref) -> list[dict]`
- `deduplicate_source_items(items) -> list[dict]`
- `derive_task_identity(prompt: str) -> tuple[str, str]`
- `project_task(task: dict, source_items: list[dict], now: datetime) -> TaskProjection`

Each source item has this exact persisted shape:

```python
{
    "item_id": "src_" + digest,
    "kind": "progress",
    "text": "已完成生命周期回归",
    "source_ref": "sessionhash#12",
    "observed_at": "2026-07-18T08:00:00+00:00",
    "material": True,
}
```

Allowed `kind` values are `objective`, `progress`, `result`, `verification`, `blocker`, `unblock_condition`, `next_action`, `acceptance`, `decision`, `handoff`, `output`, and `conflict`.

- [ ] Write failing extraction tests for headings and list labels in Chinese and English; verify only allowlisted kinds survive and no command, patch, tool body, secret, or transcript field enters a source item.
- [ ] Write failing tests proving the first independent goal becomes immutable `objective`; confirmation, authorization, added constraints, and progress prompts do not append to `goals` or replace it.
- [ ] Write failing title tests proving `开始执行/确认/继续/授权确认` are stripped, the title differs from the objective, the fallback is `待整理任务` rather than `未命名任务`, and filenames remain filesystem-safe.
- [ ] Write projection tests for every human state. Each projection must select only current facts and put superseded facts into the date-grouped timeline.
- [ ] Add tests proving routine automation and repeated status reports do not enter the timeline; one day’s small material updates merge into one date node.
- [ ] Add tests for current-result conflicts: preserve both source refs, expose one conflict notice, and never silently choose a factual winner.
- [ ] Add a cross-day projection test: same task ID, `is_cross_day=True`, two date nodes, and only the current day’s live progress on the first screen.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_extraction tests.test_task_projection tests.test_runtime -v
```

Expected red result: missing `TaskProjection`, mutable goals, untyped source items, or old results remaining in the current layer.

- [ ] Extend extraction with deterministic labels only; do not add a model, natural-language classifier, or broad assistant-message summarizer.
- [ ] Persist one immutable `objective`, retain `goals` only as a read-compatibility alias during migration, and store later constraints as decisions or next actions.
- [ ] Implement projection as a pure function. Cap each returned current section at five items, keep stable order, and move older material facts to `timeline`.
- [ ] Mark an item material only when it changes objective, status, result, verification, blocker, decision, handoff, output, or next action.
- [ ] Re-run the focused command. Expected result: all extraction, projection, and affected runtime tests pass.

**Agent08 candidate:** `feat(obsidian-capture): project stable tasks from structured facts`

---

### Task 3: Replace the legacy score with a deterministic four-dimension quality gate

**Files:**

- Modify: `Codex-Ops/codex-capture/codex_capture/quality.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/publishing.py`
- Modify: `Codex-Ops/codex-capture/tests/test_quality_rendering.py`
- Create: `Codex-Ops/codex-capture/tests/test_quality_gate.py`
- Modify: `Codex-Ops/codex-capture/tests/test_publishing.py`

**Interfaces:**

- `evaluate_projection(task: dict, projection: TaskProjection) -> QualityAssessment`
- `legacy_quality_view(assessment: QualityAssessment) -> object`
- `TaskEngine.reconcile_status(task: dict, projection: TaskProjection, now: datetime) -> dict`
- `OutboxPublisher.enqueue_terminal(task, quality, now) -> bool`

- [ ] Write failing completeness tests: unfinished tasks require either a next action or blocker; completed tasks require result plus deterministic or human acceptance evidence; handed-off tasks require a handoff entry; cancelled tasks require a reason.
- [ ] Write failing readability tests for an empty section, placeholder phrase, repeated item, low-quality title, item over 120 characters, more than five items per section, and a first screen over 500 Chinese characters.
- [ ] Write failing trust tests proving every displayed fact has a source ref and conflicts produce `source_conflict`.
- [ ] Write failing consistency tests for contradictory status/ended time/verification/publication combinations.
- [ ] Write completion tests:
  - deterministic test/build/migration/run evidence with no blocker or next action can become `completed`;
  - visual, content, business, or device acceptance becomes `pending_acceptance`;
  - assistant prose alone never completes a task.
- [ ] Update publishing tests so only `completed | handed_off | cancelled` plus `publication_eligibility=ready` can enter the Agent10 outbox. `paused`, `blocked`, and `pending_acceptance` never publish.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_quality_gate tests.test_quality_rendering tests.test_publishing -v
```

Expected red result: legacy score allows contradictory or incomplete tasks, or `dormant` still qualifies as terminal.

- [ ] Implement `QualityAssessment` without a weighted score. Keep legacy `state/score/blockers` only through `legacy_quality_view` for V1/V2 consumers during rollout.
- [ ] Implement `TaskEngine.reconcile_status` as the state-layer consumer of deterministic acceptance evidence. It may apply an allowed transition, but the quality gate itself remains read-only.
- [ ] Make the quality gate read-only: it reports issues but never changes facts, lifecycle, evidence, or publication state.
- [ ] Add stable issue codes such as `missing_objective`, `missing_next_action`, `terminal_without_evidence`, `first_screen_too_long`, `source_conflict`, `manual_region_conflict`, and `state_verification_conflict`.
- [ ] Keep `待补充证据` as a rendered quality hint, not a lifecycle state and not an empty-section placeholder.
- [ ] Re-run the focused command. Expected result: all quality and publishing tests pass.

**Agent08 candidate:** `feat(obsidian-capture): add deterministic task quality gate`

---

### Task 4: Render the single-card dual-layer note and scoped Obsidian CSS

**Files:**

- Modify: `Codex-Ops/codex-capture/codex_capture/rendering.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/runtime.py`
- Create: `Codex-Ops/codex-capture/config/obsidian-capture-task.css`
- Modify: `Codex-Ops/codex-capture/tests/test_quality_rendering.py`
- Create: `Codex-Ops/codex-capture/tests/test_task_card_golden.py`
- Modify: `Codex-Ops/codex-capture/tests/test_runtime.py`

**Interfaces:**

- `render_task_card(task, projection, quality, formal_link="", existing_text="") -> str`
- `render_managed_task_block(task, projection, quality, formal_link="") -> str`
- `extract_manual_block(text) -> bytes | None`
- `validate_managed_block(text) -> None`
- `task_filename(task, existing) -> str`

Managed markers advance to revision 3:

```markdown
<!-- obsidian-capture:managed:start revision=3 digest=sha256:0000000000000000000000000000000000000000000000000000000000000000 -->
managed task content
<!-- obsidian-capture:managed:end -->
```

- [ ] Create one golden fixture per human state and write failing tests for the state-specific first-screen section order from the approved specification.
- [ ] Add failing tests proving:
  - no empty section and no `无/未形成结论/未记录验证/未命名任务`;
  - the first screen contains at most 500 Chinese characters;
  - each section contains three to five items at most;
  - H1 omits date and project;
  - the manual section is absent when empty;
  - internal IDs and machine paths appear only in the folded audit layer;
  - old conclusions appear only under their historical date.
- [ ] Add a byte-level manual-region test using mixed line endings, whitespace, Unicode, links, and HTML comments. Repeat rendering three times and compare exact bytes.
- [ ] Add a managed-digest test: changing one system-owned byte causes a conflict, writes a backup, and refuses the card rewrite.
- [ ] Add CSS tests proving every selector is rooted at `.obsidian-capture-task` and no global `.metadata-container`, `.markdown-preview-view`, or callout selector can affect unrelated notes.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_quality_rendering tests.test_task_card_golden tests.test_runtime -v
```

Expected red result: fixed nine-section output, placeholder text, English machine frontmatter, empty manual region, or unmanaged checksum.

- [ ] Render only the approved Chinese properties and `cssclasses`.
- [ ] Render the status callout, objective, and state-specific current sections before the folded audit callout. Do not render a section whose item list is empty.
- [ ] Render source conflicts as a concise first-screen warning and list the source refs in audit history.
- [ ] Render clickable task relations, Ledger references, and formal asset link only in the bottom of the folded audit layer.
- [ ] Preserve the current daily-report renderer and all calls to it byte-for-byte except for necessary signature adaptation; add a regression fixture proving unchanged output.
- [ ] Add scoped CSS that hides the property panel only in reading view for notes with `obsidian-capture-task`; editing and source modes remain unaffected.
- [ ] Re-run the focused command. Expected result: all golden, ownership, CSS, and runtime tests pass.

**Agent08 candidate:** `feat(obsidian-capture): render concise dual-layer task cards`

---

### Task 5: Add the dedicated Obsidian Development Task Center

**Files:**

- Create: `Codex-Ops/codex-capture/config/development-task-center.base`
- Modify: `Codex-Ops/codex-capture/codex_capture/runtime.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/refresh.py`
- Modify: `Codex-Ops/codex-capture/tests/test_refresh.py`
- Create: `Codex-Ops/codex-capture/tests/test_task_center.py`
- Modify: `Codex-Ops/codex-capture/tests/test_migration.py`

**Interfaces:**

- `CaptureConfig.task_center_path -> Path`
- `CaptureConfig.task_css_path -> Path`
- `install_task_experience(vault, base_template, css_template, existing_appearance) -> dict`

The installed Base path is:

```text
00_Inbox/Obsidian Capture/开发任务中心.base
```

The installed CSS path is:

```text
.obsidian/snippets/obsidian-capture-task.css
```

The Base must use the following structural shape:

```yaml
filters:
  and:
    - file.ext == "md"
    - file.folder == "00_Inbox/Obsidian Capture/开发任务"
formulas:
  状态优先级: 'if(状态 == "阻塞", 0, if(状态 == "待验收", 1, if(状态 == "进行中", 2, if(状态 == "暂停", 3, if(状态 == "已完成", 4, if(状态 == "已交接", 5, 6))))))'
properties:
  file.name:
    displayName: 任务
views:
  - type: table
    name: 今日开发任务
    filters:
      and:
        - date(note["今日活跃"]) == today()
    order:
      - file.name
      - 状态
      - 项目
      - 当前进展
      - 下一步
      - 最后更新
      - 跨日
    sort:
      - property: formula.状态优先级
        direction: ASC
      - property: 最后更新
        direction: DESC
```

- [ ] Write a failing YAML contract test proving the first view is exactly `今日开发任务`, followed by `进行中`, `阻塞`, `待验收`, `跨日任务`, `已完成`, and `全部任务`.
- [ ] Add failing tests proving the global filter is limited to `00_Inbox/Obsidian Capture/开发任务` Markdown notes and the Base exposes no internal ID, Ledger path, machine path, quality score, or render revision.
- [ ] Add a failing test for today semantics: `今日活跃 == today()` includes material activity today, while yesterday’s untouched active task appears only in `进行中`.
- [ ] Add a failing sort contract test for status priority `阻塞 → 待验收 → 进行中 → 暂停 → 已完成 → 已交接 → 已取消`, then `最后更新 DESC`.
- [ ] Add a failing column test for `任务`, `状态`, `项目`, `当前进展`, `下一步`, `最后更新`, and `跨日`; `file.name` is displayed as `任务` and remains clickable.
- [ ] Add installation tests proving `.obsidian/appearance.json` is merged without dropping unrelated keys, the snippet is enabled exactly once, repeated installation is idempotent, and rollback restores the original bytes.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_task_center tests.test_refresh tests.test_migration -v
```

Expected red result: no dedicated Base/template, old seven-view Base mixes daily and formal assets, or CSS activation is not reversible.

- [ ] Create a dedicated Base instead of repurposing `config/obsidian-capture.base`; the old Base remains compatibility input until migration.
- [ ] Use structured Base `and/or/not` filters and a deterministic status-priority formula. Do not place business decisions in Base formulas.
- [ ] Keep the task center read-only: it reads card properties and does not mutate state or invoke enrichment.
- [ ] Install and enable the CSS by a byte-preserving merge of `appearance.json`; if the file is invalid JSON, fail closed and report `appearance_config_invalid`.
- [ ] Re-run the focused command. Expected result: Base syntax, views, sorting, installation, idempotency, and rollback tests pass.

**Agent08 candidate:** `feat(obsidian-capture): add dedicated development task center`

---

### Task 6: Enforce the terminal-only optional enrichment boundary

**Files:**

- Modify: `Codex-Ops/codex-capture/codex_capture/enrichment.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/runtime.py`
- Modify: `Codex-Ops/codex-capture/tests/test_enrichment.py`
- Modify: `Codex-Ops/codex-capture/tests/test_runtime.py`
- Modify: `GLOBAL_MODEL_ROUTING_RECORD.md` only after a separate explicit route approval; excluded from this implementation by default

**Interfaces:**

- `needs_terminal_enrichment(task, projection, quality, source_digest) -> bool`
- `build_enrichment_request(task, projection, source_items, source_digest) -> dict | None`
- `validate_enrichment_response(response, allowed_source_items) -> dict | None`

- [ ] Write failing tests proving restart, cross-day continuation, pause, account switch, compaction, repeat Hook, Base refresh, and active-task rendering never create an enrichment request.
- [ ] Add a failing test proving a clear terminal deterministic projection creates no request.
- [ ] Add a failing test proving a terminal projection with `needs_rewrite`, sufficient sources, and a new digest creates exactly one local candidate request.
- [ ] Add idempotency tests: the same source digest never creates a second request, and a failed validation keeps the deterministic card.
- [ ] Add strict response tests for the 500-character cap, allowlisted fields, cited source IDs, no unknown factual claim, no command/patch/tool output, and no lifecycle or publication fields.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_enrichment tests.test_runtime -v
```

Expected red result: current enable flag is too coarse and lacks terminal/digest/quality gating.

- [ ] Implement only local eligibility, request construction, and response validation.
- [ ] Keep `semantic_enhancement_enabled=false` and do not add a provider client, credential, network call, or fallback.
- [ ] When no registered route exists, keep the deterministic card and record `enrichment_route_unavailable` without affecting task status, quality evidence, or Hook exit code.
- [ ] Re-run the focused command. Expected result: all enrichment boundary tests pass with zero network calls.

**Agent08 candidate:** `feat(obsidian-capture): gate optional enrichment at terminal boundary`

---

### Task 7: Build reversible V3 task-card migration and fragment consolidation

**Files:**

- Create: `Codex-Ops/codex-capture/codex_capture/task_migration.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/refresh.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/migration.py`
- Modify: `Codex-Ops/codex-capture/bin/codex_capture_refresh.py`
- Create: `Codex-Ops/codex-capture/tests/test_task_migration.py`
- Modify: `Codex-Ops/codex-capture/tests/test_refresh.py`
- Modify: `Codex-Ops/codex-capture/tests/test_cli.py`

**Interfaces:**

- `TaskCardMigrator.scan(now) -> dict`
- `TaskCardMigrator.apply(report, now) -> dict`
- `TaskCardMigrator.rollback(mapping_digest, now) -> dict`
- `classify_fragment(card, state, assignments) -> str`
- `merge_fragment(target, fragment) -> dict`

Dry-run classifications are exactly:

```text
retain
merge_control_fragment
merge_status_fragment
archive_ambiguous
conflict
skip_formal_asset
skip_daily_report
```

- [ ] Create a temporary-Vault fixture containing:
  - a real goal card;
  - `确认`, `开始执行`, `授权确认`, and status-question fragments;
  - an ambiguous unrelated card;
  - an old `checkpoint` card;
  - an old `dormant` card;
  - a byte-sensitive manual region;
  - a malformed managed block;
  - the legacy Base and an empty `未命名.base`;
  - unrelated appearance settings and CSS snippets;
  - existing formal Agent10 assets and project daily reports.
- [ ] Write a dry-run test proving it writes only a report, records an immutable digest, lists every retain/merge/archive/conflict decision, and never includes note bodies in console output.
- [ ] Write deterministic merge tests: a control fragment merges only into the nearest compatible task with the same project and continuity evidence; any non-unique match becomes `archive_ambiguous`.
- [ ] Write failing apply tests for a changed source digest, changed managed block, changed manual bytes, Base collision, CSS collision, and appearance collision.
- [ ] Write an idempotent apply test and a byte-for-byte rollback test covering task states, thread/event assignments, cards, Base, CSS, appearance settings, and archived `未命名.base`.
- [ ] Add assertions proving project daily report bytes and formal Agent10 asset body bytes never change.
- [ ] Add CLI tests for explicit `--dry-run`, `--apply`, `--rollback`, readable counts, stable error codes, no identifiers/secrets in output, and exit code `2` on validation failure.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_task_migration tests.test_refresh tests.test_migration tests.test_cli -v
```

Expected red result: current V2 refresh rewrites broader views, cannot install/rollback CSS and task center together, and has no fragment mapping contract.

- [ ] Implement `TaskCardMigrator` separately from legacy Inbox migration. Reuse existing atomic writes, unique temporary files, backups, and digest helpers.
- [ ] Archive ambiguous fragments under `90_Archive/Obsidian Capture/开发任务碎片/` and record their mapping under `95_Ledgers/codex-capture/`; do not delete them or guess a target.
- [ ] Repartition only task states, task cards, event assignments, thread indexes, task center, CSS, appearance config, and named legacy Base assets.
- [ ] Never include daily reports or `01_Agents/Codex` formal asset bodies in the mutation set.
- [ ] Make apply verify the dry-run digest immediately before the first mutation. Make rollback validate all restore collisions before restoring any file.
- [ ] Re-run the focused command. Expected result: all migration, CLI, digest, idempotency, and rollback tests pass.

**Agent08 candidate:** `feat(obsidian-capture): migrate task cards to reversible v3 layout`

---

### Task 8: Extend Agent10’s terminal contract without changing historical assets

**Files:**

- Modify: `agent10-asset-library/asset_library/schema.py`
- Modify: `agent10-asset-library/asset_library/frontmatter.py` only if a new flat field is required
- Modify: `agent10-asset-library/tests/test_codex_capture_producer.py`
- Modify: `agent10-asset-library/tests/test_contract_rendering.py`
- Modify: `Codex-Ops/codex-capture/codex_capture/publishing.py`
- Modify: `Codex-Ops/codex-capture/tests/test_publishing.py`

**Interfaces:**

- Agent10 adds only the new formally publishable state `cancelled`.
- Existing V1/V2 states `active`, `checkpoint`, `handed_off`, `completed`, and `dormant` remain readable for historical draft validation during the compatibility window.
- New local-only states `in_progress`, `blocked`, `pending_acceptance`, and `paused` remain rejected by the formal draft schema.
- New publication attempts remain limited to `completed | handed_off | cancelled`.

- [ ] Add a failing Agent10 schema test for `cancelled` and regression tests for existing V1/V2 task-summary drafts.
- [ ] Add a failing test proving `in_progress`, `blocked`, `pending_acceptance`, and `paused` are rejected by Agent10 and cannot be generated by the Capture publisher.
- [ ] Add a golden test proving existing formal note bodies and existing flat frontmatter render byte-for-byte as before.
- [ ] Add a draft test proving new quality fields remain flat and no human-facing Chinese card properties leak into the formal Agent10 schema.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/agent10-asset-library
python3 -m unittest tests.test_codex_capture_producer tests.test_contract_rendering -v

cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_publishing -v
```

Expected red result: Agent10 rejects new statuses or Capture still treats dormant as publishable.

- [ ] Add only `cancelled` to the task-status compatibility enum and corresponding tests. Do not change asset status, knowledge status, writer semantics, REST authorization, path construction, or supervisor ownership.
- [ ] Keep historical assets untouched; compatibility is validated through fixture reads and new-draft validation only.
- [ ] Re-run both focused commands. Expected result: Agent10 and Capture publishing tests pass.

**Agent08 candidate:** `feat(agent10): accept obsidian capture v3 task statuses`

---

### Task 9: Integrate account-switch continuity and stable recovery branches

**Files:**

- Modify: `Codex-Ops/codex-capture/bin/codex_capture_continuity.py`
- Modify: `Codex-Ops/codex-capture/tests/test_cli.py`
- Modify: `Codex-Ops/codex-capture/tests/test_hook_config.py`
- Modify: `/Users/tristanzh/.agents/skills/codex-custom-provider-to-api/SKILL.md`
- Modify: `/Users/tristanzh/.agents/skills/codex-custom-provider-to-chatgpt/SKILL.md`
- Modify the canonical linked copies only after resolving symlink ownership

**Interfaces:**

- `codex_capture_continuity.py status --project-path /Users/tristanzh/agent/agent10-asset-library`
- `codex_capture_continuity.py create --project-path /Users/tristanzh/agent/agent10-asset-library`
- Public output states: `ready`, `no_active_task`, `ambiguous_task`, `migration_required`, `repair_required`, and `created`.

- [ ] Write CLI tests for an exact project path with one active task, no task, multiple candidates, a migrated Vault, an unmigrated Vault, digest mismatch, rollback, and restored migration.
- [ ] Add skill-contract tests proving both account-switch skills perform continuity status before auth mutation and create a marker only for `ready`.
- [ ] Add tests proving the CLI never exposes task ID, continuity key, session key, account information, marker path, token path, or note body.
- [ ] Run:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_cli tests.test_hook_config tests.test_tasks -v
```

Expected red result: current CLI only returns `created/no_unique_task` and cannot distinguish migration or repair states.

- [ ] Extend the CLI with read-only status and stable safe error codes. Do not add an account identifier to the marker or output.
- [ ] Update both skills so:
  - `ready` creates one marker and continues;
  - `no_active_task` continues without a marker;
  - `ambiguous_task` stops before auth mutation and reports the project collision;
  - `migration_required` reports the exact dry-run entrypoint;
  - `repair_required` stops before auth mutation and reports the refresh status entrypoint;
  - rollback removes the installed V3 expectation, and a later apply restores it.
- [ ] Validate both skill files with their existing local skill validator and re-run the focused command.

**Agent08 candidate:** skill files are machine-local, not committed here; record their hashes and validation result. Any repository mirror update must still go through Agent08.

---

### Task 10: Full regression, temporary-Vault E2E, live rollout, and Obsidian acceptance

**Files:**

- Modify only files already listed in Tasks 1–9
- Create runtime migration reports and backups only after temporary-Vault acceptance
- Do not create or modify formal Agent10 asset bodies during acceptance

- [ ] Run the complete Capture suite:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q codex_capture bin tests
```

Expected result: all tests pass; total is greater than the 65-test baseline.

- [ ] Run the complete Agent10 suite:

```bash
cd /Users/tristanzh/agent/agent10-asset-library
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m compileall -q asset_library tests
```

Expected result: all tests pass; total is greater than the 107-test baseline.

- [ ] Run the affected shared supervisor regressions without starting an isolated Agent10:

```bash
cd /Users/tristanzh/agent/web
node --test tests/agent10-service.test.mjs tests/platform-home-service.test.mjs tests/platform-backend-supervisor.test.mjs
```

Expected result: all affected Web tests pass and Agent10 ownership remains the shared supervisor.

- [ ] Run the temporary-Vault E2E:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest tests.test_task_migration tests.test_task_center tests.test_runtime -v
```

Expected result: fixture dry-run, apply, repeated apply, Hook continuation, terminal publication eligibility, and rollback all pass.

- [ ] Validate code and document hygiene:

```bash
cd /Users/tristanzh/agent
git -C agent10-asset-library diff --check
rg -n 'TODO|TBD|FIXME|未实现|稍后补充' \
  Codex-Ops/codex-capture/codex_capture \
  Codex-Ops/codex-capture/config \
  Codex-Ops/codex-capture/tests \
  agent10-asset-library/asset_library \
  agent10-asset-library/tests
```

Expected result: `git diff --check` has no output; placeholder scan has no newly introduced unresolved implementation marker.

- [ ] Run live refresh dry-run only:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 bin/codex_capture_refresh.py --dry-run
```

Expected result: exit code `0`, stable counts for retain/merge/archive/conflict, a source digest, and no note bodies or sensitive identifiers.

- [ ] Review the dry-run report. Apply only when:
  - manual conflicts are zero;
  - managed-region conflicts are zero;
  - all formal assets and daily reports are classified as skipped;
  - source digest matches immediately before apply;
  - Base, CSS, appearance, state, and card backups are present in the plan.

- [ ] Apply through the same explicit CLI:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 bin/codex_capture_refresh.py --apply
```

Expected result: exit code `0`, an idempotent mapping digest, dedicated task center installed, CSS enabled once, ambiguous fragments archived, and no daily/formal-asset mutation.

- [ ] Re-run `--apply` once. Expected result: the same mapping digest and zero additional mutations.
- [ ] Trigger one normal Hook continuation and one deterministic terminal test task. Verify the same cross-day task ID resumes, task-center fields update, and only the terminal publishable task reaches Agent10.
- [ ] In Obsidian, perform the human acceptance:
  - open `开发任务中心.base`;
  - confirm `今日开发任务` is the first view;
  - identify today’s tasks and statuses within 10 seconds;
  - confirm blocked and pending-acceptance items appear first;
  - open one active, blocked, pending-acceptance, completed, and cross-day task;
  - confirm each first screen shows objective, state, progress/result, verification/blocker, and next action without scrolling;
  - confirm properties are hidden only in task-card reading view;
  - confirm edit/source mode still exposes properties;
  - confirm internal IDs and machine paths are absent from the first screen and Base;
  - confirm the folded audit layer and links remain available.
- [ ] If live acceptance fails, use the recorded digest to rollback before any further change:

```bash
cd /Users/tristanzh/agent/Codex-Ops/codex-capture
DIGEST="$(python3 -c 'import json, os, pathlib; c=json.loads(pathlib.Path(os.environ.get("CODEX_CAPTURE_CONFIG_PATH", "/Users/tristanzh/.codex/codex-capture/config.json")).read_text()); p=pathlib.Path(c["vault_path"])/"95_Ledgers"/"codex-capture"/"refresh-reports"/"last-apply.json"; print(json.loads(p.read_text())["mapping_digest"])')"
python3 bin/codex_capture_refresh.py --rollback "$DIGEST"
```

This command reads the existing tested `last-apply.json` contract under the configured Vault and does not require a second pointer file.

- [ ] Capture final evidence:
  - changed file list;
  - Capture, Agent10, and Web test counts;
  - compile and diff-check results;
  - dry-run/apply/idempotency results;
  - Obsidian acceptance result;
  - zero-model-call evidence;
  - any skipped check and exact blocker;
  - Agent08 commit candidates and current read-only Git status.

## Execution Order and Stop Conditions

Execute Tasks 1–10 in order. Do not begin live apply before all temporary-Vault, Capture, Agent10, and affected Web regressions pass.

Stop and report without mutating the live Vault if any of these conditions occurs:

- the approved spec conflicts with a newer authoritative project document;
- task-card manual bytes cannot be isolated safely;
- a source digest changes between dry-run and apply;
- an ambiguous fragment would require semantic guessing;
- a project daily report or existing formal Agent10 body enters the write set;
- `.obsidian/appearance.json` cannot be parsed or merged losslessly;
- Agent10 is not owned by the shared supervisor;
- implementing enrichment would require an unregistered provider or data route.

## Plan Self-Review

- **Specification coverage:** Tasks 1–2 cover task identity, independent-goal boundaries, stable objectives, cross-day/restart/account continuity, material facts, history, and relations. Task 3 covers all four local quality dimensions and completion evidence. Task 4 covers the single-card dual-layer layout, state-specific first screen, manual ownership, conflict handling, and scoped CSS. Task 5 covers the unique daily browsing entry, views, today semantics, columns, and sort priority. Task 6 covers the terminal-only enrichment economics and zero-model default. Task 7 covers reversible migration and fragment consolidation. Task 8 covers the minimal Agent10 terminal compatibility change without historical mutation. Task 9 covers account-switch branches. Task 10 covers all acceptance criteria and live safety.
- **Scope review:** Project daily-report product rules, model-route registration, shared Web visual governance, Agent10 supervisor ownership, and existing formal asset bodies remain outside the mutation scope.
- **Interface review:** Task 1 owns lifecycle; Task 2 owns facts and projection; Task 3 owns quality; Task 4 consumes projection plus quality; Task 5 reads only rendered properties; Task 6 consumes terminal projection without changing facts; Task 7 migrates persisted V1/V2 forms; Task 8 accepts future terminal drafts; Task 9 reads migration and lifecycle status; Task 10 verifies the composed system.
- **TDD review:** Every deterministic state, parser, renderer, quality, migration, CLI, and schema behavior begins with a named failing test and an exact focused command.
- **Compatibility review:** Old lifecycle values remain readable through normalization; only new runtime writes use V3 states. Legacy Base and cards are archived or migrated reversibly. Formal assets and daily reports are explicit non-mutation fixtures.
- **Placeholder review:** No `TODO`, `TBD`, unspecified filename, unresolved interface, or implicit provider remains. The live rollback command reads the existing tested refresh record.
- **Git review:** No implementation task authorizes `git add`, `commit`, `push`, `pull`, `merge`, `rebase`, `stash`, `reset`, `checkout`, or `switch`; all Git writes remain Agent08-only.
