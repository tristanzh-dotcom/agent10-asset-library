# Obsidian Capture 自动开发归档质量设计

日期：2026-07-17  
状态：已批准，待实施  
批准人：TZ  
批准记录：2026-07-17，授权编写可直接进入代码修改的实施计划  
范围：Codex Hooks、本地捕获运行时、Agent10 正式发布、Obsidian Vault 浏览与历史迁移  
前序规格：`2026-07-16-codex-development-capture-design.md`
后续补充规格：`2026-07-17-obsidian-capture-document-quality-v2-design.md`

后续补充规格经 TZ 批准后，优先覆盖本文关于任务切分、质量维度、语义增强、
任务卡编辑所有权、日报 Frontmatter、Base 兼容视图和现有派生文档重渲染的规则。

## 1. 权威边界

本规格在 TZ 最终批准后，替代前序规格中关于用户可见命名、任务粒度、
静默发布、内容质量和 Obsidian 视图的设计。前序规格中已经验证的 Hook
接入、Agent10 受限生产者、安全令牌、本地优先和失败重试边界继续有效。

在本规格实施并通过验收前，当前运行时代码和前序规格仍是执行事实。
本文件不授权启用外部模型路由，也不改变 Agent10 的 Web 监督器所有权。

## 2. 产品定义与命名

相关能力只有一个对外产品名：**Obsidian Capture**。

- `obsidian-capture` 是已经安装的显式保存 skill。
- `Codex-Ops/codex-capture` 是为零主动触发而建立的内部自动化运行时，
  不是第二个 skill。
- 对外统一使用“Obsidian Capture 自动开发归档”。
- `codex-capture`、`agent_id: codex` 和
  `workflow_id: development-capture` 仅作为兼容的内部标识。

用户可见标题、目录、Base 和正文不再以“Codex Capture”作为产品名。

## 3. 目标

1. 用户无需调用命令或 skill，正常使用 Codex 即可自动形成可读开发档案。
2. 一项有意义的开发任务对应一张任务卡，而不是一个 session 对应一张卡。
3. 每个项目每天形成一份可读日报。
4. 重启、上下文压缩、账号切换、provider 或模型切换不破坏任务连续性。
5. 交接、完成和长期静默具有明确且可审计的生命周期。
6. 噪声、ambient 建议、测试会话和无意义自动化不污染默认视图。
7. 默认路径不增加任何产品模型调用和外部模型流量。
8. Agent10 仍是正式资产的唯一发布治理层，Obsidian 是人类阅读界面。

## 4. 非目标

- 不保存原始 transcript。
- 不保存 shell 命令、补丁正文、工具完整输入输出或环境变量内容。
- 不把每个 turn、每次工具调用或每个 session 变成正式笔记。
- 不把 LLM 输出当成事实验证证据。
- 不在本阶段启用语义增强模型。
- 不改变 Web 共享监督器对 Agent10 的服务所有权。
- 不让 Obsidian 承担生产者认证、幂等或安全治理职责。

## 5. 当前问题证据

截至 2026-07-17，真实 Vault 中存在以下质量问题：

- `00_Inbox/Codex Capture` 中有 10 个以 16 位 session 哈希命名的草稿。
- `01_Agents/Codex` 中有 7 个旧式 session 总结。
- 草稿正文只有项目、事件数和发布状态，缺少目标、结论、验证和下一步。
- 正式总结拼接截断后的提示词与最终回复，无法稳定表达任务语义。
- ambient suggestion、安全筛选、Capture 测试和普通定时自动化被发布为正式资产。
- 当前测试覆盖安全、重试和幂等，但没有覆盖可读性、任务归属和内容质量。
- `hook-errors.jsonl` 中有 4 条 `FileNotFoundError`。

当前 `_atomic_write` 对同一目标固定使用 `<name>.tmp`。多个 Hook 并发写同一
session 状态时可能竞争同一个临时文件，这是现有证据最支持的根因假设。
实施必须先用并发回归测试复现；若复现结果不同，应先重新诊断，不得仅靠猜测修改。

## 6. 总体架构

```text
Codex Hooks
  -> 事件最小化、脱敏和来源分类
  -> 本地 append-only ledger
  -> 任务身份与连续性解析
  -> 可读任务卡
  -> 确定性质量门
  -> 终态发布 outbox
  -> Agent10 正式任务资产
  -> 项目滚动日报
  -> Obsidian Base、链接和历史视图
```

### 6.1 组件边界

捕获运行时按职责拆为以下模块：

- `events`：输入字段白名单、脱敏、来源分类和安全文本规范化。
- `tasks`：任务身份、归属、状态机、连续性和质量评分。
- `storage`：ledger、状态、索引、锁、唯一临时文件和恢复。
- `rendering`：任务卡、正式正文、日报和 Obsidian 链接。
- `publishing`：outbox、Agent10 客户端、重试和幂等结果登记。
- `runtime`：Hook 编排，不承载具体业务规则。

这些模块只使用本地确定性逻辑。Agent10 仍通过现有认证草稿接口接收终态资产。

## 7. 存储布局

用户可见布局：

```text
00_Inbox/
  Obsidian Capture/
    开发任务/
      YYYY-MM-DD - 项目名 - 任务标题.md

01_Agents/
  Codex/
    <Agent10 治理的正式任务资产>

02_Workflows/
  Obsidian Capture/
    项目日报/
      YYYY-MM-DD - 项目名 - 开发日报.md
    历史任务/
      <迁移后可读索引>
  Obsidian Capture 自动开发归档.base
```

内部布局继续保留兼容名称：

```text
95_Ledgers/codex-capture/
  <session-key>.jsonl
  states/tasks/<task-id>.json
  indexes/threads/<session-key>.json
  outbox/<task-id>.json
  quarantine/
  migration-reports/
  legacy-inbox/
  continuity-consumed/
  hook-errors.jsonl
```

底层 session 哈希只用于证据索引，不进入默认 Obsidian 视图。

## 8. 任务身份与数据模型

### 8.1 身份规则

- `task_id`：一项开发任务的稳定机器身份。
- `continuity_key`：显式交接产生的任务链身份。
- `session_key`：`thread_id` 的哈希，仅作 ledger 证据身份。
- `project_id`：规范化项目根路径的稳定本地身份。
- `asset_id`：Agent10 正式资产身份。

以上身份相互独立。账号、provider、模型和 reasoning 不参与任何身份计算。

同一 `thread_id` 默认继续当前任务；同一项目路径不能单独作为静默合并依据。
一个 thread 可在明确交接后包含多个任务，一个任务也可通过有效连续性标记跨 thread。

### 8.2 项目根识别

按以下优先级确定项目：

1. 有效交接或连续性标记中明确登记的项目。
2. 当前路径向上查找到的适用项目根或仓库根。
3. `/Users/tristanzh/agent` 下的规范化工作目录。
4. 无可靠项目时使用 `unassigned`，不得把 `/` 当成正式项目。

项目名称取根目录可读名称；内部 `project_id` 可使用规范路径摘要避免同名冲突。

### 8.3 可查询的扁平属性

任务卡和正式资产新增以下 Obsidian 友好字段：

- `capture_kind`: `task`
- `task_id`
- `continuity_key`
- `task_status`
- `capture_status`
- `quality_state`
- `quality_score`
- `verification_state`
- `project_id`
- `project_name`
- `project_path`
- `started_at`
- `last_activity_at`
- `ended_at`
- `previous_task`
- `next_task`

日报使用：

- `capture_kind`: `daily_report`
- `report_date`
- `project_id`
- `project_name`
- `task_count`
- `quality_state`
- `last_activity_at`

其中：

- `capture_status` 独立于任务生命周期，限定为 `local`、`publish_pending`、
  `published`；它只描述 Agent10 发布状态。
- `verification_state` 是从正文验证项确定性派生的扁平属性，限定为
  `observed`、`reported`、`not_applicable`、`missing`、`mixed`。存在多种非缺失
  验证等级时使用 `mixed`；没有验证项时使用 `missing`。

复杂的 route 转换和证据对象保留在正文或 ledger，不放入嵌套 frontmatter，
以符合 Obsidian Properties 的扁平数据模型。

## 9. 文件名与标题

任务卡文件名固定为：

```text
YYYY-MM-DD - 项目名 - 任务标题.md
```

规则：

- 标题从第一条有意义用户目标确定，不使用 session 哈希。
- 文件创建后不因后续措辞优化而改名；更准确的标题更新 `title` 属性。
- 同日同项目同名冲突时才追加 `task_id` 前 6 位。
- 文件名去除路径分隔符、控制字符和 Obsidian 链接危险字符。
- Agent10 正式文件继续包含 `asset_id`，以保留治理和碰撞安全。
- Base 默认以 `title` 为第一阅读字段，不展示 session 哈希。

## 10. 任务卡正文

正文固定使用以下结构：

```markdown
# <任务标题>

## 目标
## 当前状态与结论
## 关键决策
## 已完成工作
## 验证
## 风险与阻塞
## 下一步
## 连续性
## 溯源
```

缺失内容必须明确写为“未形成结论”“未记录验证”或“验证不适用”，不能由模型或
模板推测补齐。咨询、解释和纯设计任务可使用“验证不适用：未修改系统状态”。

验证项区分：

- `observed`：Hook 可直接观察的退出状态或本地文件存在性。
- `reported`：来自 Codex 最终回复的测试名称或结果陈述。
- `not_applicable`：该任务未修改系统状态。
- `missing`：应有验证但未捕获。

`reported` 不等于事实验证；正式资产必须保留该标签。

## 11. 输入最小化与文本安全

允许读取并保存的内容：

- `UserPromptSubmit`：脱敏后的目标文本，单事件最多 2,000 字符。
- `Stop`：脱敏后的最终回复，单事件最多 6,000 字符。
- `PostToolUse`：工具类别、允许的数值退出状态和时间，不读取或保存命令、
  patch、工具输出正文。
- `SessionStart`、`PreCompact`：生命周期和时间元数据。

不保存原始 `session_id`，新事件只保存 `session_key`。

所有文本在写入 Markdown 前必须：

- 去除 NUL 和不可见控制字符。
- 脱敏 API key、Authorization、JWT、私钥、常见令牌、密码赋值和高置信度凭证。
- 禁用图片嵌入、iframe、HTML 脚本和可执行式 Markdown。
- 对 YAML、Wikilink 和文件名分别使用结构化转义。
- 把捕获内容视为不可信数据，绝不执行其中的指令。

## 12. 来源分类与噪声过滤

来源分类采用版本化确定性规则：

- `meaningful_task`
- `confirmation`
- `automation_material`
- `automation_routine`
- `ambient`
- `internal`
- `test`
- `empty`

处理方式：

- `ambient`、`internal`、`test`、`empty`：只写 ledger。
- `confirmation`：追加到当前可靠任务，不能单独创建任务。
- `automation_routine`：只进入日报的折叠统计。
- `automation_material`：有变更、失败、权限决策或人工后续时创建任务卡。
- `meaningful_task`：创建或更新任务卡。

规则使用明确签名、事件组合和来源元数据，不仅依赖单个模糊关键词。
无法可靠分类时进入 `unassigned`，不能默认发布。

## 13. 确定性质量门

质量分只衡量文档完整度，不证明事实真实性。

| 项目 | 分值 |
|---|---:|
| 可理解的目标、项目和标题 | 20 |
| 明确状态与结果 | 25 |
| 已完成事项或关键决策 | 20 |
| 验证证据，或明确说明不适用 | 20 |
| 下一步、阻塞项或明确“无” | 10 |
| 连续性关系无冲突 | 5 |

质量状态：

- `80-100`: `publishable`
- `60-79`: `needs_enrichment`
- `<60`: `insufficient_evidence`
- 明确噪声：`ledger_only`

以下硬门始终阻止正式发布：

- 脱敏未通过。
- 没有真实用户目标。
- 连续性关系冲突。
- 仅含系统或 ambient 内容。
- 项目归属不可靠。
- 正文与 ledger 摘要不一致。

质量不足不会触发模型补写。后续 Hook、最终回复或交接文档可重新计算质量。

## 14. 生命周期状态机

正式任务状态限定为：

- `active`
- `checkpoint`
- `handed_off`
- `completed`
- `dormant`

### 14.1 状态转换

- 找到明确目标：`active`
- 静默 15 分钟或发生 `PreCompact`：`checkpoint`
- 同一任务出现新事件：`checkpoint -> active`
- 用户明确交接：`active/checkpoint -> handed_off`
- 明确完成被后续事件确认：`active/checkpoint -> completed`
- 24 小时无活动：`active/checkpoint -> dormant`

15 分钟不是完成条件，也不是正式发布条件。

### 14.2 无主动触发的完成判断

为了避免仅凭一句模型回复错误结束任务，`Stop` 中的完成措辞只产生内部
`terminal_candidate`：

- 后续用户确认或明确“收工/完成并归档”时转为 `completed`。
- 下一条明显不同的任务目标到来且没有继续旧任务时，确认旧候选为 `completed`。
- 用户继续原任务时取消候选并恢复 `active`。
- 无进一步证据时，24 小时后进入 `dormant`，不伪装成完成。

`terminal_candidate` 是内部判断字段，不是用户可见任务状态。

## 15. 重启、账号和 route 连续性

### 15.1 Codex 重启或上下文压缩

- 相同 `thread_id` 直接恢复原 `task_id`。
- `SessionStart`、`resume`、`compact` 和 `PreCompact` 不创建新任务。
- 状态从本地 task state 和 thread index 恢复，不依赖模型记忆。

### 15.2 账号、provider、模型或 reasoning 切换

- route 切换不是任务边界。
- 相同 thread 继续原任务。
- route 元数据只允许记录模式、provider、模型和时间。
- 不记录账号、邮箱、用户 ID、token、API key 或登录凭证。

### 15.3 新 thread 的一次性连续性标记

账号切换 skill 在可能产生新 thread 前写入一次性标记：

- `marker_id`
- `task_id`
- `continuity_key`
- `project_id`
- `created_at`
- `expires_at`
- `reason: route_switch`

标记有效期为 2 小时。新 thread 的项目和活动任务必须同时匹配；匹配后通过原子
移动消费一次。过期、已消费或项目不匹配的标记不能合并任务。

手工改变认证且没有标记时，必须依赖显式交接引用；否则建立新任务或进入
`unassigned`。

## 16. 交接与休眠

交接规则：

- 旧任务冻结为 `handed_off`。
- 新任务使用新 `task_id`。
- 两者共享 `continuity_key`。
- 旧卡写 `next_task`，新卡写 `previous_task`。
- 仅项目相同不能触发交接合并。
- 新任务读取明确交接文档后才建立链接。

休眠规则：

- 24 小时无活动转为 `dormant`。
- `dormant` 是未完成检查点，不等于 `completed`。
- 再次开展休眠工作时创建关联后继任务，不改写旧卡。

## 17. Agent10 正式发布

Agent10 继续使用：

- `agent_id: codex`
- `workflow_id: development-capture`
- `status: active`
- `knowledge_status: not_indexed`
- `sensitivity: audit_only`

新任务级正式资产使用：

- `asset_type: codex-development-task-summary`
- `capture_kind: task`
- 可读 `title`
- 稳定 `source_asset_path`，包含 `task_id` 和终态类别
- `source_refs` 指向一个或多个 session ledger 和显式交接文档

`source_status: grounded` 只表示正文可追溯到本地 ledger，不表示正文中的测试或
事实已经独立验证。验证等级必须在正文中明确。

### 17.1 发布条件

仅在以下条件同时满足时进入 outbox：

- 状态为 `completed`、`handed_off` 或 `dormant`。
- 质量为 `publishable`。
- 全部硬门通过。
- 该任务终态尚未有成功正式资产。

低质量终态继续保留在“待提升或失败”视图，不生成空洞正式资产。

### 17.2 outbox 与重试

- 当前事件先可靠落盘，再尝试任何网络操作。
- 每次 Hook 最多处理一个最旧的可发布 outbox 项。
- 第一次失败允许下一次正常 Hook 立即重试。
- 连续失败后使用 `30 秒 -> 2 分钟 -> 10 分钟 -> 30 分钟` 退避。
- 本地 Agent10 请求超时上限为 750 毫秒。
- 重复提交相同正文必须由 `source_content_hash` 和稳定来源路径幂等复用。
- Agent10 不可用不影响 ledger、任务卡或日报。

成功后，Inbox 任务卡保留为轻量跳转卡并从默认进行中视图隐藏，以避免用户建立的
链接失效。跳转卡显示可读标题、最终状态、结果摘要和正式资产链接，不再是空缩影。

## 18. 项目日报

每个项目每天一份：

```text
YYYY-MM-DD - 项目名 - 开发日报.md
```

任务卡发生有效更新时，本地确定性渲染器同步刷新当日日报。内容包括：

- 今日任务
- 完成结果
- 关键决策
- 验证状态
- 交接关系
- 遗留问题
- 下一步
- 自动化运行折叠统计

日报按 `task_id` 去重。账号切换、重启和多个 checkpoint 不增加任务数。
前一天日报由下一次跨日 Hook 冻结；没有后续 Hook 时保留最后一版滚动日报。

日报链接规则：

- 正式发布前链接 Inbox 任务卡。
- 正式发布后重新渲染为 Agent10 正式资产链接。
- 交接任务使用 `previous_task` 和 `next_task` 建立双向链接。

## 19. 可选语义增强

本项目当前没有匹配的已登记产品模型路由。语义增强状态固定为：

- lifecycle: `dormant`
- execution: `not_implemented`
- availability: `unknown`
- runtime flag: `semantic_enhancement_enabled = false`

首版不得调用外部模型。

未来只有在 TZ 单独批准并更新
`/Users/tristanzh/agent/GLOBAL_MODEL_ROUTING_RECORD.md` 后才能启用。启用后仍须满足：

- 所有项目每天最多一个合并批次。
- 至少 3 个 `publishable` 任务，或存在跨任务交接、冲突决策等明确收益。
- 只发送已脱敏任务卡结构字段。
- 不发送 ledger、原始对话、命令、patch、文件内容或账号信息。
- 模型只能改善分组、去重和措辞，不能改变状态、事实、验证和连续性。
- 输出逐项引用 `task_id` 并通过确定性一致性检查。
- 每天最多尝试一次，不自动重试。
- 失败时继续使用确定性日报。

## 20. Obsidian Base 设计

新增 `02_Workflows/Obsidian Capture 自动开发归档.base`，默认显示可读 `title`，
项目、任务状态、质量状态、验证状态和最后活动时间。session 哈希和底层 ledger
字段不进入默认列。

视图：

1. **今日任务**：当天任务与正式结果，按项目分组。
2. **进行中**：`active` 和 `checkpoint`。
3. **待提升或失败**：低于 80 分、硬门失败、`publish_pending` 或连续性冲突。
4. **正式总结**：仅显示 `codex-development-task-summary`。
5. **项目日报**：按日期倒序、按项目分组。
6. **交接链**：显示 `previous_task`、`next_task` 和 `continuity_key`。
7. **历史记录**：旧式 session 总结和迁移索引，默认不打开。

普通阅读不依赖 DataviewJS 或自定义远程插件。Base 失效时，Markdown、YAML、
Wikilink 和目录结构仍保持完整可读。

## 21. 历史迁移

迁移必须先 dry-run，并生成包含数量、分类、目标路径和跳过原因的报告。

### 21.1 旧 Inbox

- 将 `00_Inbox/Codex Capture` 原样移动到
  `95_Ledgers/codex-capture/legacy-inbox`。
- 不删除或覆盖任何旧文件。
- 新 Base 不查询旧 Inbox。

### 21.2 旧正式资产

- `01_Agents/Codex` 中现有正式资产保持原路径、原 `asset_id` 和原正文。
- ambient、安全筛选和测试资产只进入历史视图。
- 普通成功自动化进入历史自动化统计。
- 得分不低于 60 的有意义历史任务生成可读“历史任务索引”，链接原正式资产。
- 不为同一历史内容再次发布 Agent10 正式资产。

### 21.3 迁移映射

每条迁移记录包含：

- legacy session key
- classification
- new task ID 或跳过原因
- legacy Inbox 路径
- legacy asset ID 和路径
- readable index path
- migration timestamp

重复运行必须产生相同结果，不重复创建索引。

旧 `Codex 开发过程.base` 移入内部 legacy 区保存；新 Base 是唯一默认入口。

## 22. 并发、错误与恢复

### 22.1 并发写

- 同一 session/task 使用本地 `flock`。
- 不同 task 可并行。
- 原子写使用同目录唯一临时文件，不复用固定 `.tmp`。
- 写入后 `fsync` 文件，并在需要时同步父目录。
- ledger 追加、状态更新和 thread index 更新在锁内保持顺序。
- finalize 使用非阻塞全局维护锁，避免重复发布。

### 22.2 损坏状态

- JSON 状态解析失败时移入 `quarantine`。
- 从 append-only ledger 确定性重建 task state。
- 重建失败时保留 ledger，并在“待提升或失败”显示错误代码。
- 不静默丢弃事件。

### 22.3 错误分类

诊断日志只记录时间、事件类型、session/task 摘要和错误代码：

- `capture_lock_timeout`
- `capture_write_failed`
- `state_rebuild_failed`
- `classification_failed`
- `publish_pending`
- `daily_render_failed`
- `migration_skipped`
- `capture_internal_error`

不得记录 prompt、回复正文、路径外敏感内容或异常中的原始 payload。

### 22.4 降级行为

- Agent10 不可用：保留 outbox 和任务卡。
- Obsidian Local REST 不可用：由 Agent10 既有受治理 fallback 处理。
- Base 无法解析：Markdown 和目录仍可读。
- 连续性不确定：进入 `unassigned`，不合并。
- Hook 本身失败：返回 0，不阻断 Codex，并写最小错误日志。

## 23. 性能与运行成本

### 23.1 Hook 延迟预算

- 当前事件的本地持久化目标：p95 小于 150 毫秒。
- 网络发布发生在持久化之后，单次上限 750 毫秒。
- 每个 Hook 最多处理一个 outbox 项。
- hooks.json 保留 5 秒外部硬超时，但内部路径不应依赖耗尽该超时。

### 23.2 磁盘与模型流量

- ledger 是本地 append-only 审计记录，不自动上传。
- 任务卡和日报是确定性 Markdown。
- 首版额外产品模型输入 token：`0`。
- 首版额外产品模型输出 token：`0`。
- 未来语义增强启用后，建议每日硬上限为输入 8,000 token、输出 2,000 token，
  且每天最多一次；最终限额必须随模型路由批准。

## 24. 测试策略

任务状态机、隐私、并发、幂等和迁移属于严格 TDD 范围。实施时必须先出现能解释
失败原因的最小红测，再修改生产代码。

### 24.1 捕获运行时

- ambient、internal、test、empty 和 automation 分类。
- “确认”等短回复只追加，不创建任务。
- 同 thread 重启保持 `task_id`。
- route 切换不改变任务身份。
- 一次性标记的匹配、过期、消费和项目不匹配。
- handoff 的双向关系和新 task ID。
- 15 分钟 checkpoint、24 小时 dormant 和 dormant 后继任务。
- 质量评分阈值、硬门和“验证不适用”。
- 文件名清洗、稳定命名和冲突后缀。
- 凭证、JWT、私钥、Markdown embed 和 HTML 脱敏。
- 并发 Hook 不丢事件、不产生 `FileNotFoundError`。
- 损坏状态隔离和 ledger 重建。
- outbox 单项处理、退避和幂等重试。
- 日报按 task ID 去重和跨日冻结。
- 迁移 dry-run、应用和重复运行幂等。

### 24.2 Agent10

- 新任务字段能够验证并渲染为扁平 YAML。
- `codex-development-task-summary` 使用现有受限生产者。
- 可读标题和 `source_asset_path` 参与正确幂等。
- 旧 `codex-development-summary` 仍可读取。
- Agent06 和其他 Agent 契约不受影响。
- 未授权 agent、未认证 API 和路径碰撞继续被拒绝。

### 24.3 Obsidian 与端到端

- Base 文件可解析，并包含 7 个预期视图。
- 默认视图不出现 session 哈希、ambient 或旧乱码草稿。
- 事件到任务卡、终态、outbox、Agent10 正式资产和日报的完整链路。
- Agent10 停止后任务仍落盘，恢复后下一次 Hook 幂等发布。
- 同 thread 重启和新 thread 连续性标记的真实演练。
- Obsidian 中标题、属性、双向链接和日报可人工阅读。

### 24.4 回归命令

实施完成前至少运行：

```bash
python3 -m unittest discover -s /Users/tristanzh/agent/Codex-Ops/codex-capture/tests -p 'test_*.py'
python3 -m compileall /Users/tristanzh/agent/Codex-Ops/codex-capture
python3 -m unittest discover -s /Users/tristanzh/agent/agent10-asset-library/tests -p 'test_*.py'
node --test \
  /Users/tristanzh/agent/web/tests/agent10-service.test.mjs \
  /Users/tristanzh/agent/web/tests/platform-home-service.test.mjs \
  /Users/tristanzh/agent/web/tests/platform-backend-supervisor.test.mjs
git diff --check
```

Git 只允许只读检查；任何提交、分支或推送必须通过 `/agent08`。

## 25. 验收标准

1. 新的有意义任务在 Obsidian 中以可读文件名和标题出现。
2. ambient、测试和空会话只留 ledger，不进入默认视图。
3. 任务卡包含目标、状态、决策、工作、验证、风险、下一步和连续性。
4. 质量不足的任务不会被发布为正式总结。
5. 15 分钟静默只产生 checkpoint；完成、交接和 dormant 按本规格转换。
6. Codex 重启、上下文压缩和相同 thread 的账号切换不改变 task ID。
7. 新 thread 只有在有效标记或显式交接时才连续。
8. Agent10 不可用时不丢数据，恢复后由正常 Hook 幂等发布。
9. 每项目每天只有一份按 task ID 去重的日报。
10. 默认运行不产生额外产品模型 token 或外部数据流量。
11. Base 默认视图不显示乱码索引，正式总结可按项目和标题阅读。
12. 历史资产不删除、不覆盖，并有迁移报告和可读历史入口。
13. 并发回归不再产生 `FileNotFoundError` 或事件丢失。
14. Capture、Agent10 和 Web 相关回归全部通过。

## 26. 分阶段上线

### 阶段 A：本地状态和质量核心

- 先完成并发回归、唯一临时文件和锁。
- 引入 task state、身份、分类、质量门和渲染器。
- 在临时 Vault 完成测试，不切换真实 Hook。

### 阶段 B：Agent10 与新 Obsidian 视图

- 扩展扁平 frontmatter 字段。
- 接入任务终态 outbox。
- 创建新目录、日报和 Base。
- 验证 Agent06、Agent10 监督器和 Web 消费者不回归。

### 阶段 C：真实 Hook 切换

- 保持原 hook 命令路径，替换其内部编排。
- 对一个新任务做真实端到端验收。
- 验证延迟、并发、重启和发布恢复。

### 阶段 D：历史迁移

- 先生成 dry-run 报告。
- 应用可读索引和 legacy 移动。
- 在 Obsidian 中人工确认默认视图和历史视图。

语义增强不属于以上阶段，需另行批准模型路由。

## 27. 回滚与兼容

- 底层 ledger 路径和格式保持可读，新增字段向后兼容。
- 旧 state 在首次读取时迁移为 task state，原文件先备份到 legacy。
- 旧正式资产和 asset ID 不变。
- 新 Base 和日报均为可重建派生物。
- 若真实 Hook 验收失败，可通过 Git Control 恢复旧运行时，同时保留新 ledger、
  outbox 和迁移报告。
- 回滚不得删除新事件或重写 Agent10 历史资产。

## 28. 实施会话 token 预算

以下估算针对本规格批准后的**确定性首版代码实施**，不包含未来语义增强路由，
也不包含当前设计会话已经消耗的 token。

| 实施阶段 | 预计输入 token | 预计输出 token |
|---|---:|---:|
| 计划、契约梳理和红测设计 | 25,000-35,000 | 5,000-8,000 |
| Capture 状态机、质量门、并发与恢复 | 45,000-65,000 | 10,000-15,000 |
| Agent10 契约、Obsidian Base 与迁移 | 35,000-50,000 | 7,000-11,000 |
| 端到端调试、回归和真实验收 | 30,000-45,000 | 5,000-9,000 |
| **合计** | **135,000-195,000** | **27,000-43,000** |

建议实施预算按输入 `180,000`、输出 `40,000` token 预留。测试日志和文件读取会
进入输入 token；实际计费还会受到缓存命中、模型路由和上下文复用影响。

本估算采用单主 Agent 执行，不包含额外并行 sub-agent。若后续明确授权独立代码审查
或并行测试 Agent，预计额外增加输入 `40,000-70,000`、输出 `8,000-15,000`。

在真正修改代码前，必须基于最终实施计划、实际变更文件和当时工作树状态再次给出
一次更窄的 token 预算；若预计超过输入 `220,000` 或输出 `50,000`，应先向 TZ
报告原因和缩减方案。

## 29. 批准后下一步

TZ 最终审阅并批准本规格后，下一步仅编写详细实施计划和重新估算实施 token。
在实施计划再次明确文件范围、红测顺序和验收命令之前，不开始运行时代码修改。
