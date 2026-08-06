# 跨 Agent 硬件资料库实施与验收

日期：2026-08-04  
发布边界：Agent10 Asset Library → AgentAssetVault → Web `/agent10`  交付状态：六阶段实现完成；物理装配/真机验收仍是独立后续门

## 1. 交付范围

本次实现保留“多入口、单管道、一次最终确认”语义：

- `hardware_model`：型号能力与技术资料；
- `hardware_unit`：Agent 范围内的实物/批次/耗材库存；
- `assembly_layout`：跨 Agent 的装配成员、约束、假设和待确认项。

Codex、Web 和未来 Agent 适配器进入同一个 intake；Obsidian 草稿空间已建立为入口命名空间；最终接受统一比较不可变 `snapshot_hash`。Obsidian 是人类可读主记录，SQLite 是可重建的查询镜像，Web 只读脱敏投影并提供受控请求/验收入口。

## 2. 真实写入结果

真实 Vault：`/Users/tristanzh/agent/AgentAssetVault`

- 在 `02_Hardware/` 建立固定目录、8 个索引/模板页面和型号/实物/布局命名空间；bootstrap 可重复执行且不覆盖已有页面。
- 从 Agent11 的硬件照片目录登记并复制 12 个文件；明确排除 `.DS_Store`。复制目标为 `02_Hardware/90_Evidence/photos/agent11/`。
- 首批发布 24 条记录：11 个型号（10 个 Agent12 硬件型号 + 1 个 Agent13 StickS3 候选型号）、10 个 Agent12 库存卡、3 个跨 Agent/Agent12/Agent13 布局页。
- `99_System/indexes/hardware.sqlite3`：24 个 intake 均为 `published`，24 个镜像记录，34 条关系边，0 个未解决硬件镜像缺口。
- 当前 Obsidian Local REST API 返回 HTTP 401，因此每条真实写入均按 Agent10 已有 REST-first/fallback 合同走原子文件回退；报告不把 REST 写入伪称为成功。运行时 API key 未写入仓库、Vault 硬件页面或 Web。

## 3. 证据边界

- Agent12 数量和使用关系来自 Agent11 项目硬件手册，标记为 `reported`；照片/标签结论标记为 `label_or_photo`。
- 防水盒约 `200×120×75 mm` 是项目资料中的近似标称值，不是本次实测；其余未知尺寸、弯折半径、孔位、热间距和净空保持空值/`unmeasured`。
- Agent13 只发布 StickS3 型号候选卡和干燥摆放布局；没有把设备身份、序列号、MAC、Wi-Fi、密钥、刷写、联网或提醒显示事实写入资料库。
- 布局页不代表已经钻孔、装盒、通电、联网、安装或通过 48–72 小时观察。
- Web 输出会移除本地证据路径、照片路径、技术文档路径、note 正文和敏感身份字段；页面只显示型号/库存/布局的脱敏摘要。

## 4. 入口与操作

Codex 本地入口：

```text
python3 -m asset_library validate-hardware <draft.json>
python3 -m asset_library prepare-hardware <draft.json> codex TZ <operation_key>
python3 -m asset_library accept-hardware <intake_id> TZ <snapshot_hash>
```

Web `/agent10`：

```text
GET  /api/agent10/hardware
GET  /api/agent10/hardware/summary
GET  /api/agent10/hardware/:id
GET  /api/agent10/hardware/relations
POST /api/agent10/hardware/drafts
PATCH /api/agent10/hardware/drafts/:id
POST /api/agent10/hardware/drafts/:id/reference
POST /api/agent10/hardware/drafts/:id/attachments
POST /api/agent10/hardware/drafts/:id/analyze
GET  /api/agent10/hardware/analysis-jobs/:id
POST /api/agent10/hardware/drafts/:id/prepare
POST /api/agent10/hardware/drafts/:id/accept
```

Web 页面保持共享 `上下分区`、共享侧栏/页脚和当前站点主题继承；浏览器不持有 Agent10 控制令牌或 Obsidian REST key。草稿提交后页面只在内存保留一个待验收快照，刷新不会伪造或恢复状态。

## 5. 验证记录

Agent10：

```text
python3 -m unittest discover -s tests -v
# 154 tests: OK
PYTHONPYCACHEPREFIX=/tmp/agent10-hardware-pycache python3 -m compileall -q asset_library tests
# OK
```

目标运行时 API：loopback bearer 复核 `GET /api/agent10/hardware?q=ESP32&scope=agent12` 返回 HTTP 200；返回投影不含绝对路径。

Web：

```text
node --check server.mjs
# OK
node --test tests/agent10-service.test.mjs tests/agent10-hardware-browser.test.mjs
# 5 tests: OK
node --test tests/new-agent-publishing-contract.test.mjs
# 18 tests: OK
node --test --test-concurrency=1 tests/*.test.mjs
# 629 tests: 558 pass, 58 fail, 13 cancelled
```

`agent10-hardware-browser.test.mjs` 在 `light-tech` 和 `jlr` 两个可用主题、桌面与窄屏尺寸下通过，检查了共享主题继承、硬件卡渲染和横向溢出。

随后通过平台已有的受控生命周期入口完成了 Web 与 Agent10 的单 Agent 重载：Web `/agent10` 已返回新硬件工作区，Agent10 `restart_service` 返回 `ok=true`、`state=repaired`、`blastRadius=current_agent`、`affectedAgents=[agent10]`。实时 loopback 复核结果：硬件列表 HTTP 200/24 条、关系 HTTP 200/34 条、治理 HTTP 200/0 个缺口；Puppeteer 在 1280×720 与 390×844 下均显示 24 张卡、无横向溢出，当前站点主题为 `light-tech`。

共享 Web 组合回归仍有预存失败。完整 `npm test` 的失败/取消合计为 58/13；它们集中在本次未修改的 Agent03、Agent04、Agent06、Agent07、平台基线和既有发布契约。聚焦组合中可归因的代表项为：

- `platform-home-service.test.mjs` 中 4 项 Agent03/平台配置断言失败；
- `platform-region-contract-browser.test.mjs` 中 6 项 Agent07/Agent13/Harness/Agent02 断言失败；
- `platform-visible-text-contract-browser.test.mjs` 中 1 项 Agent07 退役文案断言失败。

这些失败涉及本次未修改的 Agent07/Agent03/Agent02/Harness 文件；本次新增的 Agent10 服务、硬件浏览器测试和 Agent10 publishing contract 均通过，未把这些预存回归归因或改写为 Agent10 成功。

## 6. 后续明确工作

1. 修复并由共享 Web 所有者复核上述预存回归后，再做全 Web release gate。
2. 为 Agent12/Agent13 到货实物补录卷尺/卡尺测量、孔位、线缆弯折半径、安装净空和照片证据；每次补录都创建新修订并重新接受。
3. 需要官方厂商文档时，单独登记文档 URL、版本和核验日期；本次没有外部抓取。
4. 若需要 Obsidian REST 主写入，先修复本地插件令牌的 401，再重新执行一个无改动的 REST-first smoke；当前文件回退结果已经完整落盘且镜像无缺口。

## 7. 2026-08-06 工作流继续结果

- `/agent10` 已收敛为“我的硬件 / 录入 / 编辑”两个子页面；库存查询使用脱敏 `summary`，不要求 TZ 理解 `hardware_model`、`hardware_unit` 或 JSON。
- 录入支持最多 6 张受限图片，以及一个同时容纳 HTTPS 地址、资料标题、厂商/第三方来源、版本/发布日期的参考资料输入框。仅在点击后抓取；抓取失败仍保留 `link_only` 资料，不伪造硬件候选。
- 流程固定为“识别 → 候选建议 → TZ 编辑 → 生成确认包 → 最终验收”。图片/网页分析结果永远是 candidate；孔位、弯折半径、热间距、净空和未明确尺寸保持未核验。
- `Agent10 / hardware_reference_analysis` 已登记为 OpenAI `gpt-5.5` 受控路线；当前实现无凭据时明确返回 `unavailable` 并允许手工确认，不调用备用模型。未执行真实外部模型调用、真实新硬件写入或 Git 提交。
- 本次定向验证：Agent10 46 个 Python 测试通过；Web `node --check` 通过，Agent10 服务/契约/桌面窄屏与录入闭环测试通过。完整共享 Web 回归未作为本次最小验证范围执行。
