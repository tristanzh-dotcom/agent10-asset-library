# 跨 Agent 硬件资料库最小设计

日期：2026-08-04  
状态：设计已获 TZ 确认，待实现计划  
适用范围：Agent10 Asset Library、AgentAssetVault、共享 Web 的硬件资料入口  

## 1. 目标与边界

### 1.1 目标

建立一套由 Agent10 治理、以 Obsidian 为人类可读主记录、可由多个入口提交的跨 Agent 硬件资料库，用于：

- 可靠检索型号、实物、尺寸、接口、电气和安装约束；
- 支撑 Agent12、Agent13 当前硬件和后续 Smart-Home 装配布局；
- 记录来源、实测过程、证据等级和最后核验时间；
- 支持同一硬件型号被多个 Agent 或共享平台复用；
- 为 Web 提供统一查询与受控资料申请入口；
- 通过明确的最终验收确认，避免草稿被误当成正式资料。

### 1.2 非目标

首期不建设：

- 项目配置、密钥、Token、Wi-Fi 信息、MAC、序列号或其他设备身份数据；
- 设备遥测、在线状态、远程控制或真机验收事实；
- 采购、价格、供应商和自动库存系统；
- 自动抓取厂商网页、批量下载外部文档或复制照片；
- 自动进入知识库/RAG；
- 复杂 Obsidian 插件依赖或独立硬件微服务。

资料记录最终验收与硬件实物验收是两个不同事实。型号资料被接受，不代表设备已安装、联网或通过真机测试。

## 2. 第一性原理

资料库必须分别回答：

1. 这是什么硬件？
2. 我们手上有哪些实物或批次？
3. 它能否用于某个 Agent、项目或装配目标？
4. 它有哪些尺寸、接口、电气和安全边界？
5. 每个结论来自哪里，何时核验？

因此，型号能力、实物库存、项目运行事实和物理验收事实不能混在一张卡中。资料库采用“多入口、单管道、一次最终确认”：入口可以很多，正式发布只能走同一套校验、证据和验收链路。

## 3. 系统架构

```text
Codex 工作流 ─┐
Web 表单/API ──┼→ 统一硬件草稿 → 校验/去重/证据审查 → TZ 最终验收
Obsidian 草稿 ─┤                                  ↓
未来 Agent API ─┘                    Agent10 写入 Obsidian + SQLite 镜像
                                                       ↓
                                             Web 查询投影/详情
```

- Agent10 负责 schema、内部 ID、去重、幂等、路径安全、写入锁、镜像和审计。
- Obsidian 是人类可读的主记录界面；Agent10 是写入和发布治理边界。
- SQLite 是可重建的查询镜像，不是独立事实源。
- Web 只读查询 Agent10 的脱敏投影；新增和补充先进入草稿/请求，不直接绕过 Agent10 写 Obsidian。
- 任何入口都必须携带来源、提交者/工作流、来源引用和草稿快照信息。

## 4. 三类核心记录

首期只建立三种记录，避免过早拆分成复杂数据库。

### 4.1 `HardwareModel` 型号主档

回答“这个型号理论上是什么、能做什么”。

必备字段：

```yaml
record_type: hardware_model
hardware_model_id: hwm_<stable-slug>
canonical_name: ""
manufacturer: ""
model_or_sku: ""
aliases: []
category: controller
lifecycle_status: draft
nominal_dimensions: {}
interfaces: []
electrical: {}
installation_constraints: {}
compatibility: {}
technical_documents: []
photo_refs: []
scope_refs: []
relations: []
evidence_records: []
last_verified_at: null
status: draft
```

型号主档不记录某块板子的序列号、MAC、项目当前运行状态、刷写结果、联网状态、密钥或真机验收结果。

型号 `lifecycle_status` 使用 `draft`、`candidate`、`verified`、`retired`；记录 `status` 使用 `active`、`archived`、`superseded`。

### 4.2 `HardwareUnit` 实物/批次卡

回答“我们手上具体有什么、在哪里、当前能否分配”。

必备字段：

```yaml
record_type: hardware_unit
hardware_unit_id: hwu_<stable-slug>
model_ref: "[[HWM - ...]]"
inventory_kind: single
quantity_total: 0
quantity_available: 0
quantity_reserved: 0
ownership_scope: shared
storage_location: null
condition: unknown
availability_status: planned
measured_dimensions: []
weight_g: null
photo_refs: []
layout_refs: []
relations: []
evidence_records: []
last_verified_at: null
status: active
```

实物卡可表示单件、批次、耗材、备用件或尚未分配的共享库存。`hardware_unit_id` 是资料库内部引用，不是硬件身份标识。

实物 `availability_status` 使用 `planned`、`available`、`reserved`、`in_use`、`consumed`、`retired`；`condition` 使用 `new`、`good`、`worn`、`damaged`、`unknown`。

### 4.3 `AssemblyLayout` 装配布局页

回答“这些硬件如何放入防水盒、控制盒或智能平台节点”。

必备字段：

```yaml
record_type: assembly_layout
layout_id: lay_<stable-slug>
title: ""
scope: agent12
target: waterproof_enclosure
status: draft
member_refs: []
constraints: {}
assumptions: []
open_questions: []
evidence_refs: []
last_reviewed_at: null
```

布局页只引用型号和实物，不复制它们的规格。适配、干涉、净空不足和出线结论必须带测量、照片或文档证据。

布局 `status` 使用 `draft`、`measured`、`approved`、`superseded`。

## 5. 关系与范围

型号和实物使用统一的 `relations`，首期类型限制为：

- `used_by`
- `owned_by`
- `part_of_layout`
- `compatible_with`
- `incompatible_with`
- `replacement_for`
- `reserved_for`

范围使用 `scope_refs` 或 `ownership_scope`：

```yaml
scope_refs:
  - agent12
  - agent13
  - smart-home
```

一个型号可以被多个 Agent 使用；一个实物可以从某个 Agent 转为共享库存。关系变更不修改型号能力，也不复制出第二份型号卡。

## 6. 证据与核验

证据跟随具体声明，而不是只在记录末尾给出一个笼统评分。首期等级为：

| 等级 | 含义 |
| --- | --- |
| `official` | 厂商数据表、官方产品页或官方手册 |
| `measured` | 当前实物实测，含工具、方法和日期 |
| `label_or_photo` | 实物标签或照片可直接确认 |
| `reported` | 项目文档或人工转述，尚未独立核验 |
| `unverified` | 仅作待确认信息 |

一张卡允许不同字段组有不同证据。例如型号名称可为 `label_or_photo`，标称尺寸为 `official`，防水盒净尺寸为 `measured`。

实测记录至少包含：

```yaml
claim: dimensions
level: measured
source_ref: ""
tool: ""
method: ""
measured_at: null
```

未知值使用 `null` 或 `unverified`，不得用模型推测填充。

## 7. Obsidian 目录与命名

硬件资料使用 AgentAssetVault 的独立命名空间，不混入普通 Agent 产出资料：

```text
02_Hardware/
├── 00_Index/
│   ├── Hardware Home.md
│   ├── Models by Category.md
│   ├── Inventory by Scope.md
│   ├── Assembly Layouts.md
│   └── Needs Verification.md
├── 05_Inbox/
│   ├── codex/
│   ├── web/
│   └── obsidian/
├── 10_Models/
│   ├── Controllers/
│   ├── Sensors/
│   ├── Power/
│   ├── Wiring/
│   ├── Connectors/
│   ├── Enclosures/
│   ├── Tools/
│   └── Consumables/
├── 20_Units/
│   ├── agent12/
│   ├── agent13/
│   └── shared/
├── 30_Layouts/
│   ├── agent12/
│   ├── agent13/
│   └── cross-agent/
└── 90_Evidence/
    ├── photos/
    └── vendor-docs/
```

命名格式：

```text
HWM - <canonical name> - <hardware_model_id>.md
HWU - <scope> - <short name> - <hardware_unit_id>.md
LAY - <scope> - <target> - <layout_id>.md
```

文件名可读，稳定 ID 负责关联。索引页只生成链接和摘要，不复制硬件事实。Dataview 等插件可以作为展示增强，但不作为主记录依赖。

照片和厂商文档在 `90_Evidence` 中保存相对路径、来源、取得/拍摄时间、可选 SHA-256 和文档版本。当前 Agent11 的 12 项照片先登记来源；实际复制到 Vault、下载外部文档或改动 Obsidian 插件/服务，都需要单独授权。

## 8. 多入口与统一验收

### 8.1 入口

- Codex：从照片、测量、项目资料和对话生成结构化草稿；不能直接声称最终验收。
- Web：创建、编辑、补充、关联和提交验收请求；不能直接写 Obsidian。
- Obsidian：允许在 `05_Inbox/obsidian/` 进入草稿命名空间；已发布记录的直接变化必须重新校验。
- 未来 Agent12/Agent13：通过 Agent10 适配器批量提交；不能提交其他项目的秘密或运行事实。

### 8.2 状态机

```text
captured → normalized → needs_evidence → review_pending → accepted → published
```

异常状态：`rejected`、`superseded`、`changed_after_acceptance`。

### 8.3 最终验收

验收针对不可变草稿快照。验收对象至少记录：

```yaml
acceptance:
  status: accepted
  accepted_revision: 3
  accepted_by: TZ
  accepted_at: null
  snapshot_hash: sha256:<64hex>
  evidence_refs: []
```

验收时必须确认：字段和引用合法、来源可追溯、敏感信息已排除、关系无冲突、草稿未在审核期间变化。验收后才执行 Obsidian 写入和 SQLite 镜像更新；任何后续字段变化都会要求新修订和新验收，不允许静默覆盖。

最终验收可以从 Codex 或 Web 发起，但两者必须调用同一个 Agent10 受控验收操作；入口不同不能产生不同的验收语义。

## 9. Web 入口设计

当前共享 Web 已有 `/agent10` 资产库页面和治理接口，硬件资料首期作为该页面内的工作区，不新增独立硬件服务。

页面结构：

```text
Agent10 资产库
├── 总览
├── 硬件资料
│   ├── 型号
│   ├── 实物库存
│   ├── 装配布局
│   └── 待核验
└── 治理状态
```

最小操作：

- 搜索和按 Agent、类别、记录类型、证据状态筛选；
- 查看型号卡、实物卡、布局页和关联关系；
- 发起登记新型号、登记实物/批次、补充测量、创建布局；
- 查看资料快照、验收状态和 Obsidian 原文引用。

建议的契约名称（设计阶段，未部署）：

```text
GET  /api/agent10/hardware
GET  /api/agent10/hardware/:id
POST /api/agent10/hardware/requests
GET  /api/agent10/hardware/relations
```

GET 返回经过脱敏的公开投影；POST 只创建草稿/请求。Web 不持有 Obsidian REST 密钥，也不把绝对路径、运行时 Token 或上游原始错误发送到浏览器。

Web 状态只使用：

```text
已登记 · 待核验 · 待同步 · 已归档
```

不能显示“设备已就绪”“真机已应用”等超出资料证据的结论。

## 10. 首期实施顺序与验收标准

### 10.1 实施顺序

1. 用 Agent11 已有 12 项照片验证三类记录和证据模型；
2. 录入 Agent12 当前到位的硬件型号与实物/批次；
3. Agent13 硬件到位后复用相同型号和实物结构；
4. 建立防水盒、控制盒和智能平台节点的首批布局页；
5. 再实现 Web 查询工作区和草稿请求入口。

### 10.2 首期完成标准

- 每条型号、实物和布局记录都有稳定 ID；
- 字段未知时明确为 `null` 或 `unverified`；
- 每个关键声明都有来源或实测记录；
- 型号和实物没有重复主档；
- Agent12、Agent13、shared 和 smart-home 关系可以共存；
- 草稿、验收和发布状态可区分；
- 发布后可从 Obsidian 和 SQLite 镜像复核；
- 不含密钥、Token、MAC、序列号和项目运行事实；
- 未授权时不发生真实 Vault 写入、照片迁移、外部抓取或 Web 发布改动。

### 10.3 扩展路线

**V1：资料库闭环**

多入口草稿、Agent10 校验与最终验收、Obsidian 主记录、SQLite 镜像和基础 Web 查询。

**V1.1：协作效率**

Web 草稿/验收队列、批量实物登记、尺寸补录、变更对比和 Agent12/Agent13 适配器。

**V2：智能平台承接**

跨 Agent 兼容性图、标准化接口/电压/机械约束、BOM 与布局辅助、替代件影响分析，以及 Smart-Home 节点的受控关联。

## 11. 当前明确的操作边界

本设计只冻结数据和流程，不授权以下动作：

- 向真实 AgentAssetVault 写入记录；
- 从 Agent11 复制照片或下载厂商文档；
- 修改共享 Web 的 `/agent10` 页面或 API；
- 新增 Agent12/Agent13 生产者适配器；
- 变更 Obsidian 插件、服务或运行时令牌；
- 进行 Git 提交或远端发布。

这些动作需要进入后续实现计划，并按 Agent10、共享 Web、Agent08 Git Control 各自的治理入口执行。
