# Obsidian Capture 文档质量 V2 设计

日期：2026-07-17  
状态：已批准，待实施  
批准人：TZ  
批准记录：2026-07-17，三个质量不确定项均采用推荐方案；设计完成后默认开始代码实施  
范围：任务边界、文档语义、有限语义增强、人工编辑保护、日报、Base 与历史派生文档  
前序规格：`2026-07-17-obsidian-capture-automatic-development-archive-quality-design.md`

## 1. 权威关系

本规格是前序规格的质量补充，优先覆盖以下内容：

- 完成后的新请求如何切分任务。
- 证据完整度、可读性和发布资格的定义。
- 终态长任务的有限语义增强。
- 自动重渲染与 Obsidian 人工编辑的所有权。
- 日报 Frontmatter、Base 兼容视图和当前派生文档修复。

前序规格中的安全边界、Ledger、Agent10 治理、Hook 接入、并发、迁移、账号切换
连续性和 Git 操作主权继续有效。

## 2. 第一性原理

Obsidian Capture 的人类可见文档不是 transcript 的副本，而是可从证据重建的工作
界面。质量按以下四个目标判断：

1. **正确**：结论能够回到不可变 Ledger 或受治理正式资产。
2. **高密度**：一分钟内可以理解目标、状态、结果、验证、风险和下一步。
3. **连续**：重启、切换账号、交接和同 thread 多任务不会混淆身份。
4. **可维护**：自动刷新不覆盖人工补充，损坏或冲突时失败关闭。

保存更多文字不等于更高质量。派生文档允许丢弃重复措辞，但不得丢失证据引用。

## 3. 当前真实问题

截至 2026-07-17，真实 Vault 中存在以下可复现问题：

- 5 张任务卡均把同一 `results` 内容重复用于“当前状态与结论”和“已完成工作”。
- Stop 回复只要包含“测试、验证、通过”之一，就会把整段回复再次放入“验证”。
- 4 张仍为 `active` 的任务卡显示 `quality_state: publishable`。
- 迁移、上线和后续文档质量审查被合并进同一任务卡。
- 日报没有 Frontmatter，无法命中 `capture_kind == "daily_report"` 的 Base 视图。
- 7 份旧正式资产使用 `codex-development-summary`，当前“正式总结”视图只查询新类型。
- 文件名直接截取首个 prompt，出现长句、Markdown 残片和无意义结尾。
- `unassigned` 中存在 Memory Writer 等内部流程噪声。

这些问题说明当前瓶颈不是“有没有保存”，而是任务边界和派生语义没有形成可靠契约。

## 4. 两层文档模型

### 4.1 确定性事实层

事实层始终启用，并且是唯一权威内容层：

- 脱敏后的目标、结果和允许的验证状态。
- 任务状态、项目、时间、连续性和发布状态。
- 对应 Ledger、交接文档和正式资产引用。
- 确定性抽取出的完成项、验证项、风险和下一步。

任何模型不可修改事实层、生命周期、分数、验证等级或连续性。

### 4.2 非权威语义层

语义层只用于终态长任务的标题和执行摘要：

- 输出 `readable_title` 和最多 5 条 `executive_summary`。
- 每条摘要必须引用一个或多个稳定 `source_item_id`。
- 显示时标记为“AI 整理摘要，以证据区为准”。
- 模型输出不是验证证据，不参与任务状态和发布门禁。
- 调用失败、输出不合法或一致性检查失败时，完全回退到确定性版本。

正式资产不得只包含语义层；确定性事实层和溯源必须同时存在。

## 5. 任务边界 V2

### 5.1 完成后默认切换

Stop 中明确报告完成时，仍只设置 `terminal_candidate`。下一条用户请求到来后：

- 短确认词将旧任务转为 `completed`，不创建新任务。
- 明确连续性表达继续旧任务并清除候选。
- 其他有意义请求确认旧任务完成，并创建独立新任务。

连续性表达采用版本化确定性前缀，包括：

- `继续`
- `补充`
- `再`
- `还有`
- `当前任务`
- `刚才`
- `前面`
- `上一项`
- `遗留`
- `同一任务`

该集合必须有正反例测试。无法确定时优先创建新任务，避免不同目标污染同一文档。

### 5.2 新任务身份

完成后创建的新任务：

- 使用新 `task_id`。
- 默认使用新 `continuity_key`。
- 不把普通先后关系伪装成 handoff。
- 保留内部 `origin_session_key` 关联，但不在默认视图显示。

只有显式交接或一次性连续性标记才能共享 `continuity_key`。

### 5.3 非终态目标漂移

尚未出现完成候选时，不用模型判断任务是否不同。只有以下情况允许切分：

- 用户使用明确的新任务前缀。
- 项目根可靠变化。
- 显式交接。

其他请求先作为目标修订进入当前任务，避免过度拆分。

### 5.4 同 thread 多任务的证据归属

一个 thread 可以先后包含多个任务，因此 thread 不能继续作为任务证据的唯一边界。

新增 append-only 事件归属索引：

```json
{
  "event_ref": "session-key:sequence",
  "task_id": "tsk_...",
  "assigned_at": "ISO-8601",
  "assignment_reason": "current|continued|new_after_terminal|handoff"
}
```

规则：

- 每个进入任务状态机的业务事件必须恰好归属一个 `task_id`。
- Ledger 先落盘，任务解析成功后再追加归属记录。
- `events_for_task` 只读取显式归属该任务的事件，不能再读取整个 session。
- thread index 保存 `current_task_id` 和有序 `task_history`，兼容读取旧 `task_id` 字段。
- 已写归属记录不可静默改写；历史修复只能通过带摘要的迁移映射追加更正记录。
- internal、ambient、test 和 routine automation 不产生任务归属记录。

这保证完成后的新任务即使继续使用同一 thread，也不会把后续目标和结果带回旧任务。

## 6. 信息抽取与正文

### 6.1 结构化来源项

每条可读内容先成为结构化来源项：

```json
{
  "source_item_id": "itm_<stable-digest>",
  "kind": "goal|result|decision|verification|risk|next_action",
  "text": "脱敏且限长的文本",
  "evidence_level": "observed|reported|not_applicable",
  "event_ref": "session-key:sequence"
}
```

来源项使用内容和事件位置的稳定摘要生成身份，重复 Hook 不重复创建。

### 6.2 确定性拆分

Stop 内容按 Markdown 标题、列表和明确句式拆分：

- 结论或状态句进入 `result`。
- “完成、修改、新增、恢复”等动作项进入完成工作。
- 测试命令、数量、退出状态或“不适用”进入验证。
- “风险、阻塞、尚未、未执行”进入风险。
- “下一步、待、需要”进入下一步。

单项显示长度受限，完整脱敏来源仍只保留在 Ledger。无法可靠分类的句子只进入
“证据摘录”，不得复制到多个业务章节。

### 6.3 任务卡结构

正文顺序调整为：

```markdown
# <可读标题>

> [!summary] AI 整理摘要（可选，非权威）

## 当前结论
## 目标
## 已完成工作
## 关键决策
## 验证
## 风险与阻塞
## 下一步
## 连续性
## 溯源

## 我的补充
```

每条信息只在一个业务章节出现。验证只显示验证项，不复制完整结果。

## 7. 标题质量

### 7.1 确定性标题

确定性标题：

- 去除 Markdown 标题、列表符、序号和交接模板前缀。
- 从首个真实目标中选取第一条语义完整句。
- 最长 32 个中文字符或等价字符宽度。
- 去除末尾孤立标点和 `-`。
- 无可靠标题时使用“项目名 - 开发任务”，而不是内部文本。

文件创建后保持路径稳定；标题改善只更新 `title` 和页面 H1。

### 7.2 语义标题

终态增强可建议更短标题，但不得改名已有文件。Base 首列显示 `title`，文件路径继续
保持稳定以避免 Wikilink 失效。

## 8. 三维质量模型

单一 `quality_state` 不再同时表达三种含义。

### 8.1 证据完整度

- `evidence_score`: `0-100`
- `evidence_state`: `sufficient|partial|insufficient`

它只评价目标、结果、验证、风险、下一步和连续性的覆盖，不证明事实真实性。

### 8.2 可读性

- `readability_state`: `clear|verbose|duplicate|conflict|needs_review`

确定性检查包括重复率、章节长度、标题质量、空章节比例、相互矛盾的状态陈述和
系统文本污染。模型不得自行把 `needs_review` 改成 `clear`。

### 8.3 发布资格

- `publication_eligibility`:
  `not_terminal|blocked|ready|publish_pending|published`

只有满足以下全部条件时为 `ready`：

- 任务是 `completed`、`handed_off` 或 `dormant`。
- `evidence_state == sufficient`。
- `readability_state == clear`，或语义层失败但确定性正文仍通过长度与去重硬门。
- 全部安全、项目、连续性和 Ledger 一致性硬门通过。

因此 active 任务可以有 90 分证据完整度，但必须显示 `not_terminal`，不能显示
`publishable`。

## 9. 有限语义增强路由

### 9.1 触发条件

仅在以下条件全部满足时尝试一次：

- 任务已进入终态。
- 确定性事实层通过安全硬门。
- 正文超过 1,200 字符，或结果来源项不少于 3 条。
- 该 `task_id + terminal_state + source_digest` 尚未尝试过。

短任务和普通日报不调用模型。

### 9.2 预算

- 每个终态任务最多 1 次。
- 输入最多 6,000 个脱敏字符。
- 输出最多 800 token。
- 不自动重试。
- 每日最多 5 个任务，超出部分使用确定性版本。

### 9.3 数据边界

只允许发送：

- `source_item_id`
- 脱敏后的目标、结果、决策、验证、风险和下一步文本
- 项目可读名称

禁止发送：

- Ledger 文件。
- 原始 transcript。
- 命令、patch、工具输出或文件内容。
- 绝对路径、账号、邮箱、token、API key 或认证文件。

### 9.4 路由门禁

实现前必须在
`/Users/tristanzh/agent/GLOBAL_MODEL_ROUTING_RECORD.md`
登记 `obsidian_capture_terminal_enrichment` 产品路由，明确 provider、模型、
数据类别、推理位置、费用预算和 fail-closed 策略。

路由未登记或不可用时，`semantic_enhancement_enabled` 保持 `false`，确定性路径
继续正常工作。不得借用 Codex 开发会话模型或静默切换 provider。

### 9.5 输出一致性检查

模型输出必须是固定 JSON schema，并满足：

- 只包含 `readable_title`、`executive_summary` 和对应 `source_item_ids`。
- 引用的来源项全部存在且属于当前任务。
- 输出中的数字、日期、测试数量、状态值、代码标识符和文件名必须在引用来源中出现。
- 不允许输出命令、路径、凭证形态、验证等级或新的下一步承诺。
- 摘要超过 5 条、单条超过 160 字或出现未知字段时整体拒绝。

该检查不能把模型摘要提升为事实证据，因此即使通过也必须保留非权威标识。

## 10. 人工编辑所有权

任务卡使用明确管理边界：

```markdown
<!-- obsidian-capture:managed:start revision=2 source_digest=... -->
<系统管理区>
<!-- obsidian-capture:managed:end -->

<!-- obsidian-capture:manual:start -->
## 我的补充
<人工内容>
<!-- obsidian-capture:manual:end -->
```

规则：

- 自动化只替换完整系统管理区。
- 人工区逐字节保留。
- 首次生成记录 `render_revision`、`source_digest` 和 `managed_digest`。
- 管理区摘要与记录不一致时，不覆盖文件，设置
  `readability_state: conflict` 并生成内部冲突报告。
- 标记缺失、嵌套或重复时失败关闭，不尝试猜测修复。
- 用户可通过显式修复命令选择接受系统版本或保留人工版本；Hook 不自动决策。

日报采用同样的系统区/人工区边界。

## 11. 日报 V2

日报必须包含扁平 Frontmatter：

- `capture_kind: daily_report`
- `report_date`
- `project_id`
- `project_name`
- `task_count`
- `active_count`
- `terminal_count`
- `blocked_count`
- `last_activity_at`
- `render_revision`
- `source_digest`

正文包括：

- 今日结论
- 今日任务
- 已完成
- 验证概览
- 风险与阻塞
- 下一步
- 自动化运行
- 我的补充

日报只聚合任务结构字段和链接，不把任务卡全文再次复制进日报。

## 12. Base V2

Base 使用官方支持的字符串布尔表达式或结构化 `and/or/not`，不引入 DataviewJS。

视图调整为：

1. **今日任务**：限定 Capture 任务目录，并按当天活动时间筛选。
2. **进行中**：`active|checkpoint`，显示发布资格而不是旧 `quality_state`。
3. **需补充或发布待处理**：证据不足、可读性异常、冲突或 `publish_pending`。
4. **正式总结**：兼容
   `codex-development-task-summary` 和旧 `codex-development-summary`，
   增加“当前规范/历史资产”标识。
5. **项目日报**：查询 `capture_kind == "daily_report"`。
6. **交接链**：显示可读标题、前后任务链接和 `continuity_key`。
7. **历史记录**：旧正式资产与迁移索引，默认不打开。

Base 解析测试必须证明每种视图至少能命中一个对应 fixture，不能只验证视图名称存在。

## 13. 历史与现有文档修复

### 13.1 不可变内容

以下内容不改写：

- append-only Ledger。
- 7 份旧 Agent10 正式资产的正文、路径和 `asset_id`。
- 已归档的 10 份旧 Inbox 原文件。

### 13.2 可重建内容

允许从 Ledger 重建：

- 当前任务卡。
- 当前日报。
- Base。
- 轻量历史索引。

### 13.3 修复流程

提供独立命令：

```text
render-refresh --dry-run
render-refresh --apply <report-digest>
render-refresh --rollback <render-digest>
```

流程：

1. dry-run 列出将变化的文件、原因、旧/新摘要和冲突。
2. apply 前验证来源与目标摘要未变化。
3. 原文件备份到
   `95_Ledgers/codex-capture/render-backups/<timestamp>/`。
4. 只重建无人工冲突的派生文件。
5. rollback 验证当前文件仍是系统生成版本后再恢复。

为 10 份旧 Inbox 和 7 份旧正式资产建立轻量历史索引，只记录来源、归档路径、
迁移时间、分类和可读性状态，不生成未经验证的历史语义总结。

### 13.4 当前任务状态重分区

当前已经混合多个目标的 task state 不能只靠 Markdown 重渲染修复。升级时先执行
独立的状态重分区 dry-run：

- 从 Ledger 顺序重放 V2 任务边界规则。
- 旧任务保留原 `task_id`，直到首个明确切分点。
- 切分点及后续事件使用新 `task_id`，并写入迁移映射。
- 为每个业务事件建立 5.4 所述归属记录。
- 更新 thread index 的 `current_task_id` 和 `task_history`。
- 已有正式资产涉及切分点后的内容时停止自动重分区，进入人工审查。
- apply 前校验 Ledger、task state、任务卡和 thread index 摘要。
- rollback 恢复 task state、thread index 和派生文档，但不改写 Ledger。

重分区报告必须显示旧任务、新任务、切分事件、原因和所有目标路径，不显示正文内容。

## 14. 错误处理

新增稳定错误代码：

- `render_manual_conflict`
- `render_marker_invalid`
- `render_source_changed`
- `semantic_route_unavailable`
- `semantic_output_rejected`
- `task_boundary_ambiguous`

错误不得包含原始 prompt、模型输入、模型输出、人工区正文或凭证。

语义层失败不阻断事实层、任务卡和日报。确定性正文已通过去重、长度与安全硬门时，
语义层失败也不阻断终态发布；确定性正文自身仍为 `verbose`、`duplicate` 或
`conflict` 时继续阻断。人工冲突只阻断对应文件覆盖。

## 15. 流量与性能

确定性 Hook 路径仍维持：

- 当前事件本地持久化 p95 小于 150 毫秒。
- 不在 Hook 前台等待模型。
- 语义增强进入本地 outbox，由维护阶段异步处理。
- 同一 Hook 最多处理一个增强任务或一个 Agent10 发布任务，并设置总时间预算。

默认短任务额外模型 token 为 0。长终态任务理论上限为输入约 4,000 token、输出
800 token；每日硬上限由已登记产品路由强制执行。

## 16. 测试策略

严格 TDD 覆盖：

- 完成后新目标切新任务。
- “继续、补充、还有、当前任务”等保持旧任务。
- 新任务不错误继承 `continuity_key`。
- 同一 thread 中两个任务只读取各自显式归属的事件。
- 旧 thread index 可升级为 `current_task_id + task_history`。
- 结果、完成项和验证不重复。
- active 任务永远不是发布就绪。
- 日报 Frontmatter 可被 Base 命中。
- 旧、新正式资产同时出现在兼容视图。
- 标题去除 Markdown、孤立标点和超长文本。
- Memory Writer、ambient、system/developer 内容只进 Ledger。
- 人工区在多次重渲染后逐字节保持。
- 管理区人工修改、标记损坏和来源摘要变化失败关闭。
- 模型未登记、超预算、超长、非法 JSON、未知来源引用和新增事实时回退。
- render-refresh 的 dry-run、apply、幂等和 rollback。
- 当前混合 task state 的重分区 dry-run、apply、冲突停止和 rollback。

真实 Vault 验收使用当前问题样本作为 fixture，但不得在测试中读取用户实际 Vault。

## 17. 验收标准

1. 同一业务信息不在多个正文业务章节重复。
2. 当前审查请求不会继续污染已完成的迁移任务卡。
3. active 任务显示 `publication_eligibility: not_terminal`。
4. 5 份日报可被“项目日报”视图命中。
5. 7 份旧正式资产可在“正式总结”或“历史记录”中找到。
6. 自动刷新不改变“我的补充”区的任何字节。
7. 语义增强关闭或失败时仍生成完整确定性文档。
8. 语义增强摘要逐条引用有效来源项，并明确标记非权威。
9. 当前任务卡和日报可通过 dry-run、摘要校验和备份安全重建。
10. Capture、Agent10 和 Web 受影响回归全部通过。

## 18. 上线顺序

1. 任务边界和三维质量字段。
2. 结构化来源项、去重正文和安全标题。
3. 人工编辑边界和日报 Frontmatter。
4. Base 兼容视图与 fixture 命中测试。
5. render-refresh 可逆修复当前派生文档。
6. 登记并实现有限语义增强路由。
7. 临时 Vault E2E。
8. 真实 Vault dry-run、应用、Obsidian 人工验收。

语义增强不能阻塞前五步上线；路由未登记时以前五步作为可用正式版本。

## 19. 非目标

- 不把人工区内容上传给模型。
- 不让模型判断完成、验证真实性、项目归属或任务连续性。
- 不重写旧 Agent10 正式资产。
- 不把所有历史 session 重新概括成新事实。
- 不使用模型修复损坏 Frontmatter 或管理区标记。
- 不在本规格中改变 Agent10 监督器、认证接口或 Git 主权。

## 20. 批准后下一步

TZ 已授权在设计完成后默认开始实施。下一步编写实施计划、风险拆分和新的 token
预算，然后按严格 TDD 开始代码修改；不再等待逐项确认。
