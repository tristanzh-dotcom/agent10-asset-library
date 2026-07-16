# Codex 开发过程自动捕获设计

日期：2026-07-16  
状态：已批准并执行中  
批准人：TZ

## 决策与范围

TZ 已批准：每次打开 Codex 后，无需人工触发，自动把开发过程中的关键上下文保存到 `AgentAssetVault`，并可在 Obsidian 中按会话、日期、项目和状态查看。

本设计扩展 Agent10 的生产者边界：在既有 `agent06` 之外，新增受限的本机生产者 `codex`。它仅能通过 Agent10 的本地、令牌保护的草稿接口写入正式资产；不会绕过 Agent10 的 schema、碰撞检查、原子写入、镜像和治理边界。历史“V1 仅 Agent06”文档仍描述当时范围；本设计只就开发过程捕获扩展其范围。

## 目标

1. 广进窄出：每个有意义的 Hook 事件保留可追溯的会话账本；每个静默会话只产生一份正式总结。
2. 零主动操作：用户不需要调用 skill、命令或模板。
3. 本地优先、无逐回合模型调用：Hook 是标准库 Python；不读取不稳定 transcript，不向外发送事件数据。
4. 可恢复和幂等：网络/Agent10 暂不可用时保留待处理草稿；后续收敛器重试，不重复发布。
5. 可读：Obsidian 有独立 Base，区分会话草稿、正式总结和待提升项目。

## 生命周期

```text
Codex SessionStart/UserPromptSubmit/PostToolUse/PreCompact/Stop
    -> 95_Ledgers/codex-capture/<session>.jsonl  （完整、本地、只追加）
    -> 00_Inbox/Codex Capture/<session>.md       （会话草稿，持续刷新）
    -> 下一次 Codex 生命周期事件触发的静默会话收敛器
    -> Agent10 POST /api/agent10/drafts           （codex 受限生产者）
    -> 01_Agents/Codex/<date> - codex - ...md     （正式、幂等资产）
    -> Codex 开发过程.base                         （Obsidian 查询视图）
```

`Stop` 是一次 turn 的停止而非任务完成，因此它只能刷新草稿；任一次后续生命周期事件会先收敛已静默至少 15 分钟的旧会话。该方式不需要常驻进程、定时 Codex 任务或额外模型调用。

## 数据最小化与安全

- 不读取 `transcript_path`，不保存工具完整输入/输出、shell 命令、补丁全文、令牌或环境变量。
- 用户提示和 Stop 最后回复仅保存经过模式脱敏、长度限制后的本地摘要；命中 `api key`、`token`、`secret`、`password`、私钥或典型高熵凭证的片段替换为 `[REDACTED]`。
- 正式资产使用 `sensitivity: audit_only`、`knowledge_status: not_indexed`，不会自动进入知识检索。
- Agent10 控制令牌只从本机权限受限文件读取；绝不写入配置、账本、Markdown 或日志。
- Hook 无论自身失败或 Agent10 不可用都返回成功，不能中断 Codex；失败信息只写本地诊断状态。

## 正式资产契约

正式摘要的固定身份为：

- `agent_id: codex`
- `workflow_id: development-capture`
- `asset_type: codex-development-summary`
- `status: active`
- `knowledge_status: not_indexed`
- `source_status: grounded`
- `sensitivity: audit_only`

摘要的 `source_refs` 指向该会话 JSONL 账本，`source_content_hash` 由稳定的规范化摘要生成。重复收敛同一事件序号必须复用既有正式资产；新增事件才产生新版本总结。

## Obsidian 可读性

新增 `02_Workflows/Codex 开发过程.base`，默认提供：

- **会话草稿**：`00_Inbox/Codex Capture`，按最后活动时间倒序；
- **正式总结**：`01_Agents/Codex`，按创建时间倒序；
- **待提升/失败**：从草稿的 `capture_status` 筛选；
- **按项目**：显示 `project_path`、会话、事件数和最后活动时间。

正式资产仍由 Agent10 管理；Obsidian 用于阅读、搜索、链接和手工组织，不承担生产者授权或治理职责。

## 非目标

- 不把每条操作变成正式笔记。
- 不发送数据到第三方、云端 Webhook 或逐回合模型 API。
- 不修改现有 Agent10 `writer.py` 与 `tests/test_writer.py` 脏改动。
- 不替代 `obsidian-capture` skill 的人工保存能力；该 skill 保留为显式补记入口。

## 验收标准

1. Hook 配置包含 SessionStart、UserPromptSubmit、PostToolUse、PreCompact 和 Stop，且配置可解析。
2. 仿真 Hook 输入会生成脱敏账本与更新中的会话草稿；不保存原始 shell 命令或凭证。
3. 静默收敛器只处理已静默且未发布的新事件，会在 Agent10 不可用后继续保留待处理状态。
4. Agent10 接受 `codex` 草稿、拒绝未授权 agent，并将笔记放在 `01_Agents/Codex/`。
5. 重复收敛同一会话不重复生成资产。
6. Obsidian Base 文件能解析并包含上述三类视图。
