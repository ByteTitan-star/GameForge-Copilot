# ADR Issue Hygiene + Knowledge #147 P0 实现计划

> **面向 AI 代理的工作者：** 按任务顺序执行；步骤使用复选框跟踪。

**目标：** 将 ADR-13/14 Accepted 同步到仓库与 Issue；补齐 #147 剩余 P0（circuit breaker + tokenizer-aware budget）。

**架构：** Knowledge 熔断与 LLM 熔断同构但 fail-open（打开时返回空检索、记 `circuit_open`，不抛错阻断主流程）。Token 预算改为 BGE/WordPiece 对齐启发式（CJK 按字、拉丁按词片），不引入重型 tokenizer 依赖。

**技术栈：** Python 3.12、asyncio、pytest、现有 `settings` / Prometheus metrics

---

## 文件

- 修改：`docs/adr/ADR-13-native-engine-agent-loop.md`、`docs/adr/ADR-14-pinecone-rag-knowledge-base.md`
- 创建：`backend/app/forge/knowledge/circuit.py`
- 修改：`backend/app/forge/knowledge/retriever.py`、`metrics.py`、`config.py`
- 修改：`backend/app/forge/memory/context_builder.py`（`estimate_tokens`）
- 测试：`backend/tests/forge/knowledge/test_knowledge_circuit.py`、更新 schema/guards 相关 token 测试

---

### 任务 A1：提交 ADR Accepted

- [ ] 仅 stage 两个 ADR 文件并 commit（英文 Conventional Commit）
- [ ] 不包含 imgs / PDF / 无关 schema 噪声

### 任务 A2：Issue 收口

- [ ] #142：勾选已完成项 + ADR Accepted → close（引用 #145）
- [ ] #143：勾选 R0 完成项 + ADR Accepted → close；剩余指向 #146/#147
- [ ] #147：勾选已合入 P0；留下 circuit breaker / tokenizer（实现后勾）/ 全部 P1
- [ ] #146：保持 open，comment 说明排在 #147 gate 之后

### 任务 B1：Knowledge circuit breaker（TDD）

- [ ] 写失败测试：阈值失败后 retrieve 短路返回 [] 且 status=circuit_open；成功清零
- [ ] 实现 in-process 熔断 + config 开关
- [ ] retriever 在 fail/timeout 记失败，ok/no_hit 记成功；打开时跳过检索
- [ ] 测试通过

### 任务 B2：Tokenizer-aware budget（TDD）

- [ ] 写测试：拉丁按词片、CJK 按字；明显优于纯 char/4
- [ ] 实现 `estimate_tokens` WordPiece 对齐启发式
- [ ] 相关测试通过

### 任务 B3：验证与 #147 更新

- [ ] `uv run pytest tests/forge/knowledge/ tests/forge/memory/test_session_summary_synth.py`
- [ ] 更新 #147 checklist；是否 commit/PR 由用户确认（本计划实现可先 commit 在 feat 分支）
