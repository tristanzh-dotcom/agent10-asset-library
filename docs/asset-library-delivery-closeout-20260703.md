# 资料库功能交付收口记录

Date: 2026-07-03
Scope: Answer Result 资料库 / 保存到资料库完整闭环

## 已完成范围

- 当前问答结果可保存到资料库。
- 保存后生成本地文件：
  - `manifest.json`
  - `answer.md`
- 资料库列表页可访问：
  - `/assets`
- 资料详情可通过：
  - `/assets?asset_id=<asset_id>`
- 详情页以纯文本方式展示保存的 Markdown 内容。
- 资料可从详情页导出：
  - Word
  - PPT
- 导出记录写回 `manifest.exports`。
- 单个资产最多保留最新 5 条导出记录，剪枝时清理旧导出文件。
- 列表 API 支持分页底座：
  - `limit`
  - `before`
- `limit` 上限为 200。
- `asset_id` 走严格安全校验，阻断路径穿越。

## 明确不做

- 不做 PDF 导出。
- 不做加入知识库。
- 不调用 `/api/knowledge/add-generated`。
- 不写 FTS5。
- 不写 ChromaDB。
- 不调用 DeepSeek / codex-base / embeddings。
- 不做资产编辑、复杂标签、文件夹、全文搜索或 promotion。

## 关键 API

- `POST /api/assets/answers`
- `GET /api/assets/answers?limit=50&before=<ISO timestamp>`
- `GET /api/assets/answers/{asset_id}`
- `POST /api/assets/answers/{asset_id}/export/word`
- `POST /api/assets/answers/{asset_id}/export/ppt`

## 端到端验收结果

已通过 HTTP 验收：

1. `/ask` 返回 200。
2. `/assets` 返回 200。
3. `POST /api/assets/answers` 返回 200。
4. `GET /api/assets/answers?limit=1` 返回 200。
5. `GET /api/assets/answers/{asset_id}` 返回 200。
6. `POST /api/assets/answers/{asset_id}/export/word` 返回 200，content type 为 Word 文档。
7. `POST /api/assets/answers/{asset_id}/export/ppt` 返回 200，content type 为 PowerPoint 文档。
8. 验收资产 manifest 中：
   - `rag_status = not_indexed`
   - `exports` 包含 `word` 和 `ppt`
   - 对应导出文件存在

## 测试记录

已通过：

- focused asset/export/static tests: 14 passed
- non-live backend regression: 236 passed

完整 `tests/test_project_files.py` 已尝试：

- 49 passed
- 1 failed

失败项：

- `test_agent06_shell_uses_agent04_style_workflow_switch_contract`

失败位置：

- `/Users/tristanzh/agent/web/server.mjs`

判断：

- 该失败属于 shared web shell 合约，不在本资料库功能改动范围内。

## 当前验收服务

本地服务：

- `http://127.0.0.1:8006/ask`
- `http://127.0.0.1:8006/assets`

## 后续版本化

根据全局 AGENTS 规则，本业务仓库不在当前对话中执行：

- `git commit`
- `git push`
- `git pull`
- `git stash`
- `git rebase`

版本化交给 Agent08 Git Control。
