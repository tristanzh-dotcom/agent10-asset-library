# Agent10 审计问题定向修复

日期：2026-10-03。TZ 已明确批准按 2026-10-02 审计方案实施，并要求避免过度工程化、执行最小充分测试。

## 约束

- 范围为审计报告的 11 项问题，不扩展业务功能。
- 保留标准库、SQLite、REST-first writer 和现有文件锁，不新增框架或依赖。
- 相同幂等 key 完全复用、不更新原 note；不同入库草稿不得覆盖库存批次。
- 已确认快照可续跑失败步骤；成功阶段不重复写入，published 复用回执。
- 校验和 GET 保持只读；正式 Vault、Obsidian、外部模型和部署不在本轮执行范围。
- 只用临时目录和合成内容测试。不提交、推送或操作正式凭据。
- 按 workspace Git sovereignty 在当前 checkout 编辑；不因技能默认流程创建工作树或提交。

## Task 1：硬件发布、图片和参考抓取

修复库存批次身份、accepted/partial 恢复、发布索引旧快照覆盖、异常图片清理失败开放、默认 opener 调用和 DNS 连接校验间隙。使用稳定 draft 身份区分批次；沿用 publication 记录少量阶段状态；复用现有锁保护最新快照读/渲染/写。异常容器拒绝，不声称已脱敏。参考抓取仅 public HTTPS，DNS 校验及实际连接必须针对同一地址集；空或无效 DNS 结果拒绝。网络失败保留链接，安全校验失败拒绝。

文件边界：hardware_service.py、hardware_notes.py、hardware_indexes.py、hardware_attachments.py、hardware_sources.py；必要时 hardware_store.py 和相应 tests。不修改 writer/http_server/locking/filesystem_fallback/producer_api/sqlite_mirror/runtime。

## Task 2：核心写入和安全入口

修复镜像失败后的重复笔记、首次写入初始化、回退权限、恢复路径、HTTP 有界读取及异常输入、codex 服务端约束。

在既有持久化写入记录保存幂等身份，重启后能够复用已写主记录。对崩溃窗口优先保存写入意图并按真实笔记的身份校验恢复；不以未完成记录直接声称成功。0600 文件替换后不放宽；临时和私有元数据文件以受限权限创建。恢复事件使用安全文件名并持有实际锁。HTTP 先校验令牌及长度，正文有容量/超时上限；错误输入返回明确非敏感错误。Codex 保持批准的 capture workflow/type 和 audit_only/not_indexed。

## 最小充分验证

先让每项新回归测试在原代码失败，再实现修复。最终只运行变更模块、共享原语及直接消费者测试（Level 3 bounded regression），不做完整 discovery、全包 compile、生产写入或外部调用。独立复核通过后交付未提交改动，记录具体命令和结果。

## 实施和验证记录

已实现审计 11 项定向修复。复核补充的日志 EOF 中断、原始换行校验、字段类型、已有空/部分硬件数据库只读，以及不合法图片头等边界，均先复现再修正；核心和硬件任务的限定复核已通过。

整体验证又复现了旧硬件请求恢复可能覆盖新版本的交错问题，以及成功检查点后失败记录清理被跳过的问题。已增加最小身份校验和可重试的精确清理：写入前保存当前镜像和同一记录已观察发布意图的摘要；恢复前核对摘要及真实主笔记，发生交错或证据不明确时拒绝，不回退新版本。同一路径、改名路径、新主笔记成功但镜像失败、旧索引失败续跑，以及正常新版本恢复均有定向回归。不新增表、依赖或生命周期引擎。最后一次独立限定复核确认两个问题均已解决，未发现新的限定范围阻塞项；本轮代码及临时数据验证完成，不代表生产验收。

最终限定复核没有扩大审计：历史正式数据修复、改名后旧笔记清理、历史记录保留/规模优化、恶意存储环境及其他关联卡片清理策略，均按原批准边界暂不纳入。缺少身份依据的历史恢复安全拒绝；真实服务、网络、断电及长期运行验收与本轮源代码证据分开。整轮复核报告已完成，原复核任务随后触及使用额度；最后补强由可用模型进行一次限定复核，没有重复整轮审计或账户操作。

主执行上下文在当前 checkout 执行以下 Level 3 最小充分回归：

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_audit_core tests.test_writer tests.test_collision tests.test_locking tests.test_http_server tests.test_runtime tests.test_producer_api tests.test_governance tests.test_governance_api tests.test_sqlite_mirror tests.test_filesystem_fallback tests.test_codex_capture_producer tests.test_agent06_adapter tests.test_agent14_adapter tests.test_hardware_hardening tests.test_hardware_sources tests.test_hardware_attachments tests.test_hardware_drafts tests.test_hardware_intake tests.test_hardware_store tests.test_hardware_service tests.test_hardware_notes tests.test_hardware_indexes tests.test_hardware_analysis tests.test_hardware_media tests.test_hardware_api -v
git diff --check
```

2026-10-03 最后补强之后的结果：209 项测试通过，0 failures/errors，退出码 0，测试耗时 1.872 秒；差异格式检查退出码 0，无输出。完整结果已读取。此前 201 项通过记录不覆盖最后发现的交错问题，以本次增加回归后的结果为准。边界按变更模块、共享锁/写入/权限原语和服务/API、分析、渲染直接消费者选择；未包含无关 bootstrap/seed/layout 功能或完整 discovery。

未执行完整测试发现、全包编译、正式 Vault/Obsidian 写入、真实参考网页抓取、外部模型调用、共享 Web 端到端验收、历史库存碰撞修复、部署、提交或推送。前两项未达到 Level 4/发布门禁；其余超出本轮代码及临时数据验收边界。图片检查验证容器/基础头和 EXIF 清理，不等于像素解码验收；损坏的已提交恢复日志仍拒绝自动修复。
