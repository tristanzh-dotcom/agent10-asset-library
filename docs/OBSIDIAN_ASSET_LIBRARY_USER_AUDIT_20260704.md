# 统一 Agent 资产库用户审计设计文档

日期：2026-07-04

状态：用户审计版 / 待 TZ 确认

项目目录：`/Users/tristanzh/agent/agent10-asset-library`

设计底座：Obsidian Vault

## 1. 项目设计目标

本项目目标不是从零开发一个完整资料管理系统，而是为 `/Users/tristanzh/agent` 下所有子 Agent 建立统一的资产发布、整理、检索和治理层。

核心目标：

1. 让各 Agent 的高价值产出不再只停留在一次性页面、临时 JSON、日志或工作目录中。
2. 用 Obsidian 承担本地文件、Markdown、标签、双链、搜索、人工整理、迁移和长期阅读体验。
3. 保留各 Agent 原有业务数据库和运行态存储，不用 Obsidian 替代 SQLite、Chroma、ledger、工作目录或图像索引。
4. 建立统一资产契约，使 Agent02-09 的报告、PPT、病例、问答、审计证据、技能部署记录都能被一致登记。
5. 明确区分 Asset Library 与 RAG Knowledge Base：保存到 Obsidian 不等于加入知识库。
6. 为后续 Web `/assets`、RAG promotion、跨 Agent 复用和审计报告提供稳定基础。

### 1.1 UI 边界原则

本项目必须明确区分资料库本体 UI 与 Agent 治理 UI：

- Obsidian macOS App 是资料库本体 UI，负责资产记录的阅读、编辑、标签、双链、搜索、模板、迁移和人工整理。
- 后续 Web `/assets` 或本地 `3000` 端口页面是 Agent 治理 UI，负责子 Agent 接入状态、写入健康度、失败队列、mirror gap、promotion journal、schema drift、审计告警、任务重试和运行态治理。
- Web UI 不应重复实现 Obsidian 已经成熟覆盖的 note 阅读器、笔记编辑器、标签管理器或资料整理界面。
- Agent10 代码层只补 Obsidian 不天然提供的机器契约能力，包括 schema 校验、幂等、REST 写入、fallback、SQLite Mirror、reconciliation 和 RAG bridge。

因此，凡是 macOS Obsidian App 已能稳定满足的资料库操作，应优先采用 Obsidian 原生能力或安全成熟插件；Web 端只承载 Agent 治理和操作管理，不作为 Obsidian 的替代资料库产品。

## 2. 当前 Agent 数据现状

### Agent01：历史文件资产系统

状态：已退役。

现状：

- `web/server.mjs` 中标记为历史页面。
- `/agent01` 和 `/api/agent01/*` 保持 404 防线。
- `web/.agent01_uploads` 与 `web/.agent01_previews` 仍保留历史上传和预览文件。

资产处理建议：

- 不恢复 Agent01 业务。
- 将历史上传文件作为只读归档资产迁移或登记到 Obsidian。
- 标记为 `agent_id: agent01`、`status: retired`。

### Agent02：乘用车信息汇总

状态：业务运行中。

主要数据输入：

- 国内乘用车销量数据。
- JLR 官方 XLSX 数据。
- 外资/合资车企 source registry 与网络 evidence。
- 手动触发、定时触发、飞书推送触发。

主要处理：

- Python 国内销量流程生成飞书卡片 JSON。
- JLR 采集官方表格并 reconcile。
- 外资合资 workflow 使用 SQLite `event_evidence.sqlite` 管理事件证据。

主要输出和存储：

- `final_cleaned_intelligence.json`
- `daily_market_report.json`
- `raw_intelligence_snapshot.json`
- `workflows/jlr-sales/data/latest_snapshot.json`
- `workflows/jlr-sales/data/raw/*.xlsx`
- `workflows/foreign-jv-china-watch/data/latest_card_payload.json`
- `workflows/foreign-jv-china-watch/data/event_evidence.sqlite`

资产处理建议：

- 报告卡片、周期性快照、JLR 数据解释、外资合资分析报告应进入 Obsidian。
- 原始 XLSX 和 evidence SQLite 保留在 Agent02 原目录，只在 Obsidian note 中引用。
- 对事实类数据必须保留来源状态和验证状态。

### Agent03：宠物相关服务

状态：业务运行中。

主要数据输入：

- 馒头健康记录。
- 用户输入的观察、症状、化验单、图片。
- 历史 ledger。
- 权威兽医来源检索结果。

主要处理：

- MCHT pipeline 使用 first pass、retrieval、final decision。
- `historical_ledger.json` 通过文件锁和原子写入维护。
- ledger insights 用于长期健康状态分析。

主要输出和存储：

- `workflows/mantou-dog/data/historical_ledger.json`
- `workflows/mantou-dog/data/timeseries_metrics.json`
- `workflows/mantou-dog/data/pending_metric_drafts.json`
- `workflows/mantou-dog/data/source_cache/*.json`
- `workflows/mantou-dog/assets/photos/*`
- 单次 Markdown 健康报告和结构化 synthesis。

资产处理建议：

- 单次问诊、健康报告、化验单解释、复诊记录应进入 Obsidian。
- `Mantou` 应作为 Obsidian subject 一等实体。
- 原 ledger 仍由 Agent03 维护，Obsidian 只保存可读病例视图和引用。
- 医疗/健康相关资产必须标记敏感级别和来源状态。

### Agent04：本地图像检索

状态：业务运行中。

主要数据输入：

- Apple Photos originals。
- EXIF、GPS、拍摄时间。

主要处理：

- 火山方舟 Ark 生成视觉描述与标签。
- SQLite FTS5 与 Jieba 做本地文本检索。
- 缩略图缓存、人脸/人物缓存辅助检索。

主要输出和存储：

- `data/limb_ark.sqlite3`
- `~/.cache/local-photo-model/thumbnails`
- `data/apple_people_cache.json`
- `data/face_profiles.pkl`
- `data/photo_face_index.pkl`

资产处理建议：

- 不应为每张照片生成 Obsidian note。
- 只为精选相册、搜索结果集、人物集合、事件集合生成资产 note。
- 大规模图像索引仍留在 Agent04 SQLite 与缩略图缓存中。

### Agent05：PPT 生成

状态：业务运行中。

主要数据输入：

- 用户 prompt。
- 内置模板。
- 用户上传 PPTX。
- 参考图和参考资料。

主要处理：

- opencode 生成 `edits.json`。
- gorden-ppt-skill 构建 `output.pptx`。
- analyzer 生成 `machine_extracted.json`。
- QuickLook 或 render 生成视觉预览。

主要输出和存储：

- `work/ppt-maker/<task>/output.pptx`
- `work/ppt-maker/<task>/edits.json`
- `work/ppt-maker/<task>/machine_extracted.json`
- `work/ppt-maker/<task>/orchestration_prompt.md`
- `work/ppt-maker/<task>/visual_preview/*`

资产处理建议：

- 每次成功生成 PPT 应生成 Obsidian note。
- `output.pptx` 作为附件或 source file 链接。
- prompt、模板、preview、质量检查结果应进入 frontmatter 或正文。

### Agent06：个人知识库

状态：业务运行中，且已具备 V0 资产库原型。

主要数据输入：

- 文本。
- 文件。
- OCR 文档。
- 用户问题。

主要处理：

- parse/chunk。
- FTS5。
- Chroma/Ollama embedding。
- query rewrite、rerank、answer generation。
- Word/PPT export。

主要输出和存储：

- `~/Documents/PKA_Data/.fts5/pka.db`
- `~/Documents/PKA_Data/.vector/`
- `~/Documents/PKA_Data/runtime/tasks/*.json`
- `~/Documents/PKA_Data/assets/answers/<date>/<asset>/manifest.json`
- `~/Documents/PKA_Data/assets/answers/<date>/<asset>/answer.md`
- `~/Documents/PKA_Data/assets/answers/<date>/<asset>/exports/*`

资产处理建议：

- Agent06 V0 资产是第一批迁移对象。
- `answer.md` 可直接转换为 Obsidian note。
- `rag_status` 需要升级为统一 `knowledge_status`。
- 继续保持保存资料与加入知识库之间的硬边界。

### Agent07：技能哨兵

状态：业务运行中。

主要数据输入：

- scout pipeline 配置。
- GitHub/source candidates。
- README、artifact hints、项目匹配评分。

主要处理：

- blind scout。
- source scoring。
- artifact guard。
- runtime orchestrator。
- dashboard state。

主要输出和存储：

- `data/scout_pipeline.json`
- `data/audit_wakeup.jsonl`
- `storage/runtime_shadow/*`
- `storage/logs/*`
- `artifacts/demo/*`

资产处理建议：

- 不把每次扫描都写入 Obsidian。
- 只登记高价值 lead、通过审核的技能候选、事故闭环、重要 artifact。
- 适合生成 `sentinel_lead`、`skill_candidate_review`、`audit_event` 类型资产。

### Agent08：Git 控制台

状态：业务运行中。

主要数据输入：

- Git repo manifest。
- `git status`、分支、ahead/behind、dirty state。
- 用户发起的 git mutation 操作。

主要处理：

- repo scan。
- health score。
- mutation safety gate。
- preflight snapshot。

主要输出和存储：

- `storage/snapshots/*.json`
- `storage/mutations/*.json`
- backend process state。

资产处理建议：

- Agent08 的资产是操作审计证据。
- 只将高风险 mutation、release checklist、关键 preflight 结果写入 Obsidian。
- 不把日常 scan 全量写入 Obsidian，避免噪音。

### Agent09：Skill Console

状态：业务运行中，但未接入 shared web contract。

主要数据输入：

- `skills-lock.json`
- local skill path。
- remote skill metadata。

主要处理：

- path security。
- SKILL.md hash。
- deploy。
- rollback。
- lock。

主要输出和存储：

- 更新后的 `skills-lock.json`
- runtime `.staging`
- runtime `.rollback`
- 部署后的 skill 目录状态。

资产处理建议：

- 记录技能版本审计、部署事务、rollback 事件。
- 与 Agent07 可形成 skill discovery -> review -> deploy 的资产链路。

## 3. 第一性原理判断

统一资产库要解决的不是“所有数据都放进一个数据库”，而是：

1. 哪些 Agent 产出值得长期保存、阅读、复用和审计。
2. 这些产出如何从临时运行态变成稳定的人类可读资产。
3. 如何保留来源链、事实状态、模型路线、生成上下文和附件。
4. 如何避免把资料保存误认为 RAG 入库。
5. 如何避免把 Obsidian 变成不可治理的垃圾堆。

因此，Obsidian 在本项目中的定位是：

```text
跨 Agent 资产视图层和人工治理层
```

它不是：

- Agent02 的事实数据库。
- Agent03 的健康 ledger。
- Agent04 的图像索引库。
- Agent06 的向量库。
- Agent08 的 git mutation 事务系统。

各 Agent 原有业务存储继续作为运行真相源。Obsidian 保存的是经过筛选、可读、可链接、可审计的资产视图。

## 4. 总体架构

推荐架构：

```text
Agent 原生业务系统
  -> Asset Emitter
  -> Unified Asset Writer
  -> Obsidian Vault
  -> Optional SQLite Mirror
  -> Explicit Knowledge Bridge
```

### 4.1 Agent 原生业务系统

每个 Agent 继续维护自己的核心运行数据。

示例：

- Agent02 继续维护 `event_evidence.sqlite` 和官方 XLSX。
- Agent03 继续维护 `historical_ledger.json`。
- Agent04 继续维护 `limb_ark.sqlite3`。
- Agent06 继续维护 FTS5、Chroma 和 raw ingest。
- Agent08 继续维护 mutation snapshot。

### 4.2 Asset Emitter

每个 Agent 在关键产出完成后，显式提交一个资产草稿。

草稿不直接操作 Obsidian，而是交给统一 writer。

草稿应包含：

- 资产标题。
- 资产类型。
- 所属 agent 和 workflow。
- 正文 Markdown。
- 原始文件引用。
- 附件引用。
- provenance。
- source status。
- knowledge status。
- sensitivity。

### 4.3 Unified Asset Writer

统一 writer 负责：

- 校验 asset draft。
- 生成稳定 `asset_id`。
- 生成 Obsidian note。
- 写入 YAML frontmatter。
- 复制或链接附件。
- 建立双链。
- 更新可选 SQLite mirror。
- 返回资产路径给调用方。

### 4.4 Obsidian Vault

Obsidian Vault 是用户实际浏览、整理、搜索和复用资料的主界面。

主资产是 Markdown note，而不是 JSON manifest。

Obsidian Vault 的 UI 入口是 macOS Obsidian App。项目不在 Web 端重复建设资料库本体交互；Web 端只查看和操作 Agent 生产、写入、索引、审计、重试等治理状态。

### 4.5 Optional SQLite Mirror

SQLite mirror 用于：

- Web `/assets` 快速分页。
- API 查询。
- 自动校验。
- 资产统计。
- 重建索引。

SQLite mirror 可从 Obsidian Vault 重建，不是唯一真相。

### 4.6 Explicit Knowledge Bridge

Knowledge Bridge 负责从 Obsidian 资产显式加入 RAG。

规则：

- 保存到 Obsidian 不等于加入知识库。
- 只有用户确认 promotion 后，资产才进入 Agent06 或其他 RAG 系统。
- promotion 必须回写 `knowledge_status`，且必须处理回写失败造成的状态不一致。
- 支持撤销和移除索引。

promotion 采用两阶段流程：

1. 先确认 Obsidian note 可写，并将 `knowledge_status` 从 `not_indexed` 更新为 `promoting`。
2. 执行 RAG ingest，记录目标知识库、索引 ID、chunk IDs 和 ingest 时间。
3. RAG ingest 成功后，回写 `knowledge_status: indexed`、`knowledge_index_id`、`knowledge_promoted_at`。
4. RAG ingest 失败时，回写 `knowledge_status: promotion_failed`，并记录失败原因。
5. 如果 RAG 已成功但 Obsidian 回写失败，必须写入独立 promotion journal，路径为 `99_System/audit/.promotion-journal.jsonl`，由 reconciliation job 后续修复 note 状态。
6. reconciliation job 扫描 `promoting`、`promotion_failed` 和 promotion journal，重试或提示人工处理。触发规则：Unified Asset Writer 启动时必须运行一次，并提供手动运行入口；如果后续实现常驻服务，默认可每 15 分钟运行一次。单条 promotion 默认最多重试 3 次；超过上限后将 `knowledge_status` 置为 `promotion_requires_manual_review`，并在 `99_System/audit/` 写入人工处理记录。

## 5. Obsidian Vault 目录方案

建议创建专用 Vault：

```text
AgentAssetVault/
  00_Inbox/
  01_Agents/
    Agent01/
    Agent02/
    Agent03/
    Agent04/
    Agent05/
    Agent06/
    Agent07/
    Agent08/
    Agent09/
  02_Workflows/
  03_Subjects/
    Mantou/
    JLR/
  04_Collections/
  05_Exports/
  90_Attachments/
    Agent02/
    Agent03/
    Agent05/
    Agent06/
  95_Ledgers/
  99_System/
    schemas/
    templates/
    indexes/
    audit/
```

目录职责：

- `00_Inbox`：未整理资产。
- `01_Agents`：按 Agent 浏览资产。
- `02_Workflows`：按 workflow 聚合。
- `03_Subjects`：按主题实体聚合，例如 Mantou、JLR、某车企、某项目。
- `04_Collections`：人工整理集合。
- `05_Exports`：Word、PPT、PDF 等导出资产。
- `90_Attachments`：附件、原始文件副本、预览图。
- `95_Ledgers`：跨 Agent 资产流水和审计索引。
- `99_System`：schema、模板、自动索引、系统审计。

Vault 根路径建议：

```text
/Users/tristanzh/agent/AgentAssetVault/
```

理由：
- 与 `agent10-asset-library` 同级，保持 `/Users/tristanzh/agent` 下的 Agent 工程统一布局。
- 避免把 Vault 放进某个具体 Agent 目录，防止被误判为单 Agent 私有数据。
- 该路径是 V1 推荐默认值；如果后续指定已有 Obsidian Vault，应通过配置覆盖。

Vault 路径解析优先级：

1. 环境变量 `AGENT_ASSET_VAULT_PATH`。
2. `/Users/tristanzh/agent/agent10-asset-library/config.json` 中的 `vault_path` 字段。
3. 默认值 `/Users/tristanzh/agent/AgentAssetVault/`。

Unified Asset Writer 启动时必须按上述优先级解析最终 Vault 路径，并在启动日志中记录解析来源和值。

## 6. 统一 Frontmatter Schema

每条资产 note 必须有 YAML frontmatter。

建议核心字段：

```yaml
asset_id: ast_20260704_a1b2c3d4
asset_schema_version: 1
title: 示例资产标题
agent_id: agent06
workflow_id: ask
asset_type: pka_answer
status: active
knowledge_status: not_indexed
knowledge_index_id: ""
knowledge_promoted_at: ""
source_status: grounded
sensitivity: normal
source_content_hash: sha256:...
hash_source: ""
created_at: 2026-07-04T10:00:00+08:00
updated_at: 2026-07-04T10:00:00+08:00
source_asset_path: /Users/tristanzh/agent/agent06-pka/...
source_refs: []
input_refs: []
file_refs: []
export_refs: []
model_route: ""
subject_refs:
  - Mantou
collection_refs: []
tags:
  - agent/agent06
  - workflow/ask
  - type/pka-answer
  - knowledge/not-indexed
```

字段说明：

- `asset_id`：跨 Agent 唯一 ID。
- `agent_id`：生产资产的 Agent。
- `workflow_id`：具体工作流。
- `asset_type`：资产类型。
- `knowledge_status`：是否进入 RAG。
- `knowledge_index_id`：查询态字段，仅在 `knowledge_status: indexed` 时由 Knowledge Bridge 写入；默认不存在或不参与 draft 校验。
- `knowledge_promoted_at`：查询态字段，仅在 `knowledge_status: indexed` 时由 Knowledge Bridge 写入；默认不存在或不参与 draft 校验。
- `source_status`：事实或来源状态。
- `sensitivity`：敏感级别。
- `source_content_hash`：资产正文规范化后的 SHA-256，用于幂等、漂移检测和恢复校验。
- `hash_source`：标记 `source_content_hash` 的组合规则版本；正文资产默认空字符串，非正文或附件型资产必须写入明确规则名。
- `source_asset_path`：原系统中的源文件或源目录。
- `source_refs`：事实来源 URL、文件、chunk、evidence row 等。
- `file_refs`：附件或原始文件。
- `export_refs`：Word、PPT、PDF 等导出结果。
- `subject_refs`：主题实体。

### 6.1 Schema Migration

`asset_schema_version` 必须有明确演进策略，避免未来 v2/v3 字段变化破坏已存在 note。

迁移原则：

- `99_System/schemas/` 下维护 schema 文件和迁移说明，例如 `asset_schema_v1.md`、`migration_01_to_02.md`。
- 新增字段必须定义 default 值，旧 note 在读取时可被补齐。
- 字段废弃时优先标记 `deprecated`，不直接改名，避免破坏 Obsidian 查询和人工链接。
- SQLite Mirror 在读取时做 schema normalization，把旧 note 映射成当前 API 需要的规范形态。
- 默认不原地批量改写已有 note；只有 TZ 明确批准迁移任务时，migration runner 才可以执行写回。
- migration runner 必须先生成 dry-run 报告，列出受影响 note、字段变化和可回滚依据。

### 6.2 Sensitivity 枚举

`sensitivity` 必须使用固定枚举，避免各 Agent 自行发明值导致筛选、备份和审计策略失效。

合法值：
- `normal`：常规资产，默认值；可进入普通 Vault 浏览、搜索和本地备份流程。
- `sensitive`：包含个人健康、照片、隐私数据或非公开业务信息；默认不复制大附件，备份和展示需要更严格策略。
- `restricted`：不应离开本地机器，不进入任何 sync/remote；只能本地引用或本地备份。
- `audit_only`：仅审计用途，不在 Web 列表和普通搜索中暴露正文；可展示标题、状态和最小必要 metadata。

### 6.3 Knowledge Status 枚举

`knowledge_status` 必须使用固定枚举，作为 Knowledge Bridge、RAG ingest、reconciliation job 和 UI 筛选的共同状态来源。

合法值：
- `not_indexed`：默认值；资产尚未进入任何知识库或 RAG 索引。
- `promoting`：promotion 已发起，RAG ingest 或回写流程进行中。
- `indexed`：已进入 RAG，且 Obsidian note 状态回写成功。
- `promotion_failed`：ingest 或回写失败，可由 reconciliation job 重试。
- `promotion_requires_manual_review`：重试耗尽或出现不可自动恢复错误，需要人工处理。

### 6.4 Source Status 枚举

`source_status` 必须使用固定枚举，用于区分资产内容的来源可信度和后续审计要求。

合法值：
- `grounded`：有可追溯来源且已完成校验。
- `pending`：来源待补充或正在校验中。
- `uncertain`：存在来源，但来源可靠性、完整性或解释仍不稳定。
- `unverified`：已记录来源线索，但尚未执行验证。

### 6.5 Asset Status 枚举

`status` 必须使用固定枚举，作为资产生命周期、删除策略、列表筛选和审计恢复的共同状态来源。

合法值：
- `active`：默认值；资产在 Vault 中可见、可操作。
- `archived`：已归档，不在默认列表展示。
- `deleted_in_vault`：已从 Obsidian Vault 移除，原系统数据不受影响。
- `source_deleted`：原始业务系统数据已删除，仅保留 Obsidian 资产视图。

## 7. 资产类型建议

第一批资产类型：

```text
agent01_legacy_upload
agent02_market_report
agent02_jlr_sales_snapshot
agent02_foreign_jv_report
agent03_mcht_case_report
agent03_mcht_metric_record
agent03_aquatic_report
agent04_photo_collection
agent04_search_result_set
agent05_ppt_deck
agent05_ppt_template_analysis
agent06_pka_answer
agent06_ingested_source_summary
agent07_sentinel_lead
agent07_skill_candidate_review
agent08_git_mutation_audit
agent08_release_checklist
agent09_skill_deploy_audit
```

## 8. 标签与双链规范

标签用于机器筛选，双链用于人工浏览。

推荐标签：

```text
#agent/agent02
#workflow/foreign-jv-china-watch
#type/market-report
#knowledge/not-indexed
#source/grounded
#sensitivity/normal
#status/active
```

推荐双链：

```text
[[Agent02]]
[[foreign-jv-china-watch]]
[[JLR]]
[[Mantou]]
[[Agent06 Knowledge Base]]
```

原则：

- `agent_id`、`workflow_id`、`asset_type` 必须同时出现在 frontmatter 和 tags 中。
- 重要 subject 必须用 Obsidian 双链。
- 高价值 workflow 应有对应 workflow index note。

## 9. Agent 接入策略

### 第一优先级：Agent06

原因：

- 已有 V0 资产库。
- 已有 `manifest.json + answer.md + exports`。
- 已经验证保存、列表、详情、导出、删除闭环。

接入动作：

1. 将 `answer.md` 转为 Obsidian note。
2. 将 `manifest.json` 映射为 frontmatter。
3. 将 `rag_status` 迁移为 `knowledge_status`。
4. 将 exports 写入 `export_refs`。
5. 保持不自动加入知识库。

### 第二优先级：Agent05

原因：

- 生成物天然是资产。
- 输出目录结构清晰。
- PPTX、edits、preview、prompt 都有复用价值。

接入动作：

1. 成功生成 `output.pptx` 后生成 note。
2. 附加 prompt、template、quality result。
3. 链接或复制 `output.pptx` 到 Vault attachments。
4. 记录 `machine_extracted.json` 和 `edits.json`。

### 第三优先级：Agent03

原因：

- Mantou 健康资料长期价值高。
- 需要 subject-based timeline。

接入动作：

1. 每次健康报告生成 `agent03_mcht_case_report` note。
2. `Mantou` 作为 subject note 聚合所有病例。
3. 引用照片、source cache、ledger relation。
4. 标记 sensitivity。

### 第四优先级：Agent02

原因：

- 报告与事实来源链复杂，需要稳定 provenance。

接入动作：

1. 每次 market report / JLR snapshot / foreign JV report 生成 note。
2. 原始 XLSX 和 SQLite evidence 不搬迁，只引用。
3. source status 必须保留。
4. 对“待查”或 pending evidence 明确标记。

### 第五优先级：Agent04

原因：

- 资产量大，不适合全量 note 化。

接入动作：

1. 仅对精选集合、搜索结果集、人物集合生成 note。
2. note 中引用照片 ID、thumbnail、查询条件。
3. 原图和 SQLite 索引继续留在 Agent04。

### 第六优先级：Agent07、Agent08、Agent09

原因：

- 主要是审计型资产。
- 必须控制噪音。

接入动作：

1. Agent07 只保存高价值 lead 和审核事件。
2. Agent08 只保存高风险 mutation、release checklist、关键 preflight。
3. Agent09 只保存 deploy/rollback 事务和技能版本审计。

## 10. 实施步骤

### Phase 1：设计与契约冻结

交付：

- Obsidian Vault 目录规范。
- frontmatter schema。
- asset type registry。
- tag/link 规范。
- Agent06 V0 迁移映射。

验收：

- 能人工阅读并判断任意资产应落到哪个目录。
- 能判断哪些数据不应该进入 Obsidian。

### Phase 2：Vault 初始化

交付：

- 创建专用 Obsidian Vault。
- 创建 `99_System/schemas`。
- 创建 Agent index notes。
- 创建 workflow index notes。
- 创建 subject note 模板。

验收：

- Obsidian 可打开。
- 搜索、标签、双链可用。
- 基础模板可人工创建一条资产。

### Phase 3：Unified Asset Writer

交付：

- 资产草稿 schema。
- Markdown note writer。
- frontmatter writer。
- 附件 copy/link 策略。
- 路径安全校验。
- 幂等写入规则。

验收：

- 给定 asset draft，可稳定生成一条 Obsidian note。
- 重复写入不会产生重复资产。
- source path 不允许路径穿越。

### Phase 4：Agent06 和 Agent05 接入

交付：

- Agent06 V0 资产迁移或同步。
- Agent05 PPT 生成结果发布到 Vault。
- 导出文件 refs。

验收：

- Obsidian 中能看到问答资料和 PPT 资料。
- 附件可打开。
- `knowledge_status` 默认 `not_indexed`。

### Phase 5：Agent03 和 Agent02 接入

交付：

- Mantou 病例 note。
- JLR/市场报告 note。
- foreign JV evidence summary note。

验收：

- `[[Mantou]]` 能看到健康时间线。
- JLR 和车企报告能追溯原始数据和来源。

### Phase 6：选择性接入 Agent04、Agent07、Agent08、Agent09

交付：

- Agent04 collection note。
- Agent07 lead note。
- Agent08 mutation audit note。
- Agent09 skill deploy audit note。

验收：

- 高价值资产可见。
- 低价值运行噪音不进入 Vault。

### Phase 7：Knowledge Bridge

交付：

- Obsidian note promotion 到 Agent06 RAG。
- promotion confirmation。
- `knowledge_status` 回写。
- remove/unindex 策略。

验收：

- 保存资料不会自动进入 RAG。
- 用户显式确认后才进入知识库。
- 可追踪 promotion 来源。

## 11. 具体落地方案

### 11.1 Asset Draft 数据结构

各 Agent 不直接写 Obsidian，而是提交统一 draft。

示例：

```json
{
  "agent_id": "agent06",
  "workflow_id": "ask",
  "asset_type": "agent06_pka_answer",
  "title": "某问题的回答",
  "body_markdown": "# 某问题的回答\n\n...",
  "source_status": "grounded",
  "knowledge_status": "not_indexed",
  "sensitivity": "normal",
  "source_content_hash": "sha256:...",
  "source_asset_path": "/Users/tristanzh/Documents/PKA_Data/assets/answers/...",
  "file_refs": [],
  "export_refs": [],
  "source_refs": [],
  "subject_refs": [],
  "tags": []
}
```

### 11.2 Note 生成规则

文件名建议：

```text
YYYY-MM-DD - <agent_id> - <short-title> - <asset_id>.md
```

`short-title` 生成规则：

1. 取 `title` 前 50 个有效字符。
2. 将 `/ \ : * ? " < > |` 以及 ASCII 控制字符替换为 `-`。
3. 将连续多个 `-` 合并为单个 `-`。
4. 去除首尾 `-`、`.` 和空白。
5. 如果结果为空、`.` 或 `..`，使用 `asset_id` 替代。

示例：

```text
01_Agents/Agent06/2026-07-04 - agent06 - 某问题的回答 - ast_20260704_abcd12.md
```

### 11.3 附件策略

两种模式：

1. `link`：只记录原路径，不复制大文件。
2. `copy`：复制到 Vault `90_Attachments`。

建议：

- PPTX、Word、小型图片：copy。
- 大型照片库原图、SQLite、Chroma、ledger：link。
- 敏感健康照片：默认 link，除非 TZ 明确允许 copy。

### 11.4 幂等策略

幂等 key：

```text
agent_id + workflow_id + source_asset_path + source_content_hash
```

`source_content_hash` 统一算法：

- 算法固定为 SHA-256。
- 输入固定为 `body_markdown` 的 UTF-8 规范化字节流。
- 规范化规则：统一换行为 `\n`，去除 UTF-8 BOM，保留正文内部空白，不做语义改写。
- 记录格式为 `sha256:<64位hex>`。
- hash 值必须写入 frontmatter 的 `source_content_hash` 字段。
- 如果资产没有正文 Markdown，例如纯附件资产，则使用固定字段 metadata JSON 与身份附件 SHA-256 列表组合生成。

非正文资产 hash 规则：

- metadata JSON 字段固定为 `{asset_type, agent_id, source_asset_path, title, workflow_id}`。
- 字段按字母序排序，使用紧凑 JSON 序列化，无空格、无缩进，UTF-8 编码。
- 附件 hash 取 `file_refs` 中参与资产身份判定的文件；如草稿显式标记 `primary: true`，只使用 primary 文件；否则使用所有 `identity: true` 文件，按 `path` 字母序排序后逐个计算原始字节 SHA-256。
- 组合输入为 `metadata_json_bytes + "|" + attachment_hash_list_json`，其中 `attachment_hash_list_json` 是按路径排序后的紧凑 JSON，元素包含 `{path, sha256}`。
- 最终值为组合输入的 SHA-256，记录格式仍为 `sha256:<64位hex>`。
- frontmatter 必须写入 `hash_source: metadata_v1_plus_identity_attachment_sha256_list`，声明组合规则版本。

规则：

- 相同 key 重复提交时更新原 note。
- 生成新版本时增加 `version` 或 `updated_at`。
- 不允许 silent duplicate。
- 如果同一 `asset_id` 但 `source_content_hash` 不同，必须进入版本更新流程，不能覆盖旧正文而不留痕。

### 11.5 删除策略

Obsidian 删除不应自动删除 Agent 原系统数据。

资产生命周期状态必须使用 6.5 定义的 `status` 枚举。

删除行为：

- 从 Obsidian 移除 note 只是移除资产视图。
- 原始业务文件是否删除，由对应 Agent 决定。
- 删除需要记录审计。

### 11.6 写入安全策略

Unified Asset Writer 必须把 Obsidian Vault 当作共享写入目标处理，不能直接覆盖写文件。

强制规则：

1. 所有 note 写入必须使用 tmp-file + atomic rename。
2. tmp 文件必须写在目标 note 同一文件系统和同一目录内，确保 rename 原子性。
3. 写入前必须获取 Vault 级或目标路径级排他锁，锁文件建议位于 `99_System/audit/.asset-writer.lock`。
4. 锁机制在 macOS/Linux 上使用 `fcntl`/`flock`，锁超时时间默认 30 秒；lock file 内写入 holder PID、hostname、started_at 和 operation_id，作为诊断元数据。获取锁超时必须失败返回，不允许绕过。
5. 写前必须执行 collision check：基于 `asset_id`、幂等 key、目标路径和 `source_content_hash` 检查重复或冲突。
6. 写入流程为：生成内容 -> 写 tmp -> fsync tmp -> atomic rename -> fsync 目录 -> 更新 SQLite Mirror。
7. SQLite Mirror 更新失败时，note 不回滚；必须向 `99_System/audit/.mirror-gap.jsonl` 写入 gap journal，记录 `{asset_id, vault_path, fail_reason, timestamp, retry_count}`，因为 Vault note 是主资产视图。
8. mirror-gap-scanner 在 Unified Asset Writer 启动时运行一次，并提供手动运行入口；如果后续实现常驻服务，可定时运行。它读取 `.mirror-gap.jsonl`，对每个未解决条目重试 Mirror upsert，成功后写入 `resolved_at`，失败则增加 `retry_count` 并保留错误。已解决条目只允许通过 journal compact 归档，不直接静默删除。
9. crash recovery 启动时必须扫描残留 tmp 文件和 lock 状态，生成恢复报告，不直接静默删除。
10. crash recovery 必须检查 lock file 中的 holder PID 是否仍存活；如果 PID 不存活，仅允许清理 stale lock metadata 和 stale operation record，并在 `99_System/audit/` 写入 stale-lock recovery audit event；如果 PID 存活，则不得破坏锁或修改其元数据。

### 11.7 `asset_id` 生成规则

`asset_id` 只能由 Unified Asset Writer 生成，各 Agent draft 不应自行指定最终 ID。

生成规则：

- 前缀固定为 `ast`。
- 日期部分取 draft 提交时的 UTC+8 日期，格式为 `YYYYMMDD`。
- 随机部分使用加密安全随机数生成 8 位小写 hex。
- 最终格式为 `ast_YYYYMMDD_<8位hex>`，例如 `ast_20260704_a1b2c3d4`。
- Writer 生成后必须检查 Vault、SQLite Mirror 和本次写入批次中不存在相同 `asset_id`。
- 如发生碰撞，Writer 最多重新生成 5 次；仍失败时中止写入并记录 audit event，不允许降级为时间戳或自增 ID。
- V1 采用全 Vault 共享 8 位 hex 碰撞域，基于少于 10 万条资产的阶段假设；未来可升级为 `ast_<agent_id>_YYYYMMDD_<8位hex>`，但必须继续保留旧 ID 的全局唯一性检查和兼容读取。

## 12. 风险与治理

### 风险 1：Obsidian 被写成垃圾堆

控制：

- 只写高价值资产。
- Agent07/08/09 默认低频审计写入。
- Agent04 不做全量照片 note。

### 风险 2：事实来源丢失

控制：

- `source_refs` 必填。
- Agent02/03 必须记录 `source_status`。
- 对 pending/uncertain 标记清楚。

### 风险 3：误污染 RAG

控制：

- `knowledge_status` 默认 `not_indexed`。
- promotion 必须显式确认。
- 不允许 Asset Writer 直接调用 RAG ingest。

### 风险 4：隐私和敏感资料扩散

控制：

- `sensitivity` 必填。
- Mantou 健康和照片资产默认敏感。
- 大文件和敏感附件默认 link，不 copy。

### 风险 5：业务系统和 Obsidian 状态不一致

控制：

- 原系统仍是真相源。
- Obsidian note 记录 `source_asset_path`。
- SQLite mirror 可重建。
- 定期运行 consistency audit。

### 12.6 备份与恢复

Vault 是资产视图和人工整理结果的主承载点，必须有独立备份策略。

备份策略：

- Vault 可选择纳入本地 git 版本控制，但默认不配置 remote，不自动推送，避免敏感资产外泄。
- `.gitignore` 必须排除 `90_Attachments` 中的大文件、缓存文件、可重建 preview，以及 TZ 指定的敏感目录。
- schema、index note、audit journal 建议进入本地版本控制；包含健康、照片、私密报告正文的 note 是否进入 git，由敏感级别策略决定。
- 大型附件采用原路径引用、外部备份或按需 copy，不默认进入 git。
- Vault snapshot 周期应配置化；V1 可先提供手动 snapshot，常驻服务成型后再设置默认每周 snapshot，并把 snapshot 记录写入 Agent08 audit 目录或后续统一审计目录。

恢复策略：

- Obsidian note 是资产视图主记录；SQLite Mirror 是查询索引和恢复辅助，不是唯一真相。
- 如果 SQLite Mirror 损坏，从 Vault frontmatter 全量重建。
- 如果 Vault note 丢失但 SQLite Mirror 仍在，可用 mirror 中的 frontmatter 字段重建基本 note，但正文格式可能降级。
- 如果 Vault 与 Agent 原系统同时存在但状态不一致，以 Agent 原系统为运行真相源，以 Vault note 为人工整理真相源，生成 reconciliation 报告后人工确认。
- 备份恢复流程必须保留 `asset_id`、`source_content_hash`、`source_asset_path`、`knowledge_status` 和 audit journal。

## 13. 推荐 V1 范围

V1 应只做以下事情：

1. 建立 Obsidian Vault contract。
2. 建立统一 frontmatter schema。
3. 建立 Asset Draft schema。
4. 实现或设计 Unified Asset Writer。
5. 接入 Agent06 V0 answer assets。
6. 接入 Agent05 PPT output。
7. 明确不做自动 RAG promotion。
8. 明确不迁移 Agent02/03/04 的底层数据库。

V1 不做：

- 全量 Agent04 照片 note 化。
- 全量 Agent08 scan note 化。
- 自动知识库入库。
- 重型 DMS。
- 替代 Agent06 RAG。
- 替代各 Agent 原业务存储。

## 14. 最终设计判断

统一 Agent Asset Library 应定义为：

```text
以 Obsidian 为人类可读底座的跨 Agent 资产发布与治理层
```

它的核心价值不是集中存储所有字节，而是让所有 Agent 的重要产出拥有统一的：

- 资产身份。
- 可读 Markdown。
- 标签和双链。
- 来源链。
- 附件引用。
- 生命周期状态。
- 知识库状态。
- 审计记录。

Obsidian 负责承载用户体验和长期整理能力。

Agent Asset Library 负责资产契约、写入治理、跨 Agent 一致性和未来 RAG bridge。
