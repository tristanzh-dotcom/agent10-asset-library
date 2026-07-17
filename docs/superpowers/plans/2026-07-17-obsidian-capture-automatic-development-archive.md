# Obsidian Capture 自动开发归档实施计划

> **For agentic workers:** 按任务顺序执行，任何运行时代码修改前先跑对应红测；Git 写操作仅通过 Agent08。

**Goal:** 将现有安全的 session 捕获升级为确定性的任务级归档、受治理终态发布和可读 Obsidian 视图，不引入模型调用或外部数据流量。

**Architecture:** `codex-capture` 保持本地、事件驱动。`events/tasks/storage/rendering/publishing` 负责确定性任务流，Agent10 继续是唯一正式资产发布者；Web 仅维持既有监督器和认证代理。

## Global Constraints

- 不读取 transcript、命令、补丁、工具正文、凭证或账号信息。
- 不启用语义增强、自动重试任务或 Web 自动拉起。
- 保持旧 ledger 与旧正式资产可读；迁移只可 dry-run 后显式应用。
- 严格 TDD；所有任务先运行红测，再写最小实现。

### Task 1: Stage A 并发安全和任务运行时接线

**Files:** `Codex-Ops/codex-capture/codex_capture/{runtime,storage,tasks}.py`; `tests/{test_storage,test_runtime,test_tasks}.py`

- [ ] 写红测：两个 `CaptureRuntime` 实例并发处理同一 session，断言无 `FileNotFoundError`、ledger 事件不丢失且 task_id 稳定。
- [ ] 运行 `python3 -m unittest tests.test_storage tests.test_runtime tests.test_tasks -v`，确认因运行时未完全使用 session/maintenance 锁而失败。
- [ ] 仅以 `CaptureStorage.session_lock()` 包裹 append、任务解析、任务卡写入和 thread index 更新；维护发布使用非阻塞 maintenance 锁。
- [ ] 重跑上述测试并新增全量 `python3 -m unittest discover -s tests -p 'test_*.py'`。

### Task 2: Stage A 任务质量、生命周期和本地视图

**Files:** `Codex-Ops/codex-capture/codex_capture/{events,tasks,quality,rendering,runtime}.py`; 相应 `test_events.py`、`test_tasks.py`、`test_quality_rendering.py`

- [ ] 先写红测覆盖 ambient/test/empty 只入 ledger、15 分钟 checkpoint、24 小时 dormant、确认语句不新建任务、终态候选需后续证据确认。
- [ ] 实现或补全确定性分类、质量硬门与九段任务卡；断言正式默认文件名不含 session hash。
- [ ] 重跑模块测试及全量 Capture 测试。

### Task 3: Stage B Agent10 任务资产与 outbox

**Files:** `agent10-asset-library/asset_library/{schema,frontmatter,producer_api}.py`; `Codex-Ops/codex-capture/codex_capture/publishing.py`; 两仓相应测试。

- [ ] 红测：只有 publishable 的 `completed|handed_off|dormant` 任务可入 outbox；失败标记 `publish_pending`，下一 Hook 仅处理一个最早到期项，重复发布复用相同资产。
- [ ] 保持 `agent_id=codex`、令牌文件与既有草稿端点不变；实现最小 outbox 状态写回。
- [ ] 运行 Capture、Agent10 全量 Python 测试及 `compileall`。

### Task 4: Stage B Obsidian Base 和日报

**Files:** `Codex-Ops/codex-capture/config/obsidian-capture.base`; rendering/runtime 测试。

- [ ] 红测：Base 有七个指定视图，默认不展示 session hash；日报按 task_id 去重并在正式发布后链接资产。
- [ ] 写入可重建的 Base、任务卡和日报，不迁移历史内容。
- [ ] 用临时 Vault 验证 Markdown、YAML、链接和 Base 结构。

### Task 5: Stage C/D 真实 Hook 与迁移验收

**Files:** `bin/{codex_capture_hook,codex_capture_migrate}.py`; migration/CLI/E2E 测试。

- [ ] 红测：旧状态迁移可重复、dry-run 无写入、并发 Hook 无丢事件、Agent10 暂停后恢复可幂等发布。
- [ ] 保持 Hook 命令路径，切换其内部编排；迁移先只生成报告。
- [ ] 执行规格列出的 Capture、Agent10、Web 回归、`git diff --check`，再进行一项真实任务端到端验收。

**Budget:** 当前已提交 Stage A/B 基线可复用；剩余实现预计输入 85k–125k、输出 18k–28k tokens，低于规格的升级前阈值。每完成一个任务后重新估算。
