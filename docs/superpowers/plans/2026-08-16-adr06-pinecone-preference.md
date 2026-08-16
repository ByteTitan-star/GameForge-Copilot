# ADR-06 实现计划：Pinecone Semantic Cache + LLM 偏好抽取

> **面向 AI 代理的工作者：** 按 Phase 顺序实现；每步可测；English Conventional Commits。

**目标：** 落地 Accepted ADR-06：分层语义命中、Pinecone 存储节点 result、LLM-only 偏好抽取、超额物理删除。

**技术栈：** FastAPI、Redis Exact、Pinecone（optional extra）、OpenAI-compat embeddings、平台 env 配置。

---

## 文件

| 文件 | 职责 |
| --- | --- |
| `backend/app/core/config.py` | 新 flags / 默认值 |
| `backend/.env.example` | Owner 自配模板 |
| `backend/app/llm/embeddings.py` | embed 客户端 |
| `backend/app/forge/cache/pinecone_store.py` | upsert/query 适配（可 mock） |
| `backend/app/forge/cache/semantic.py` | 分层 lookup + confirm LLM |
| `backend/app/forge/cache/routers.py` | Exact miss 后接 semantic |
| `backend/app/forge/memory/preferences.py` | 物理删除 earliest |
| `backend/app/forge/memory/llm_extract.py` | LLM 偏好抽取 |
| `backend/app/forge/memory/explicit.py` / `inferred.py` | 正式路径不再调用 |
| `backend/pyproject.toml` | optional `pinecone` |
| tests | mock Pinecone / embed / extract |

---

## Phase 0

- [ ] config + env.example
- [ ] preferences：超额物理删除；测试
- [ ] ADR README Status=Accepted

## Phase 1

- [ ] `embeddings.py` + 无 key 返回 None
- [ ] 单元测试 fake httpx

## Phase 2

- [ ] pinecone_store Protocol + InMemory 实现（测试）+ 真 SDK optional
- [ ] semantic_cache_lookup 分层；`confirm_semantic_candidate` LLM
- [ ] routers 接线；forbidden 节点不写
- [ ] 测试：0.84 miss / 0.90 confirm / 0.96 direct

## Phase 3

- [ ] `llm_extract.py`；graph/preferences 改走 LLM
- [ ] 无模型不抽取；测试

## Phase 4

- [ ] metrics counters（可最小：日志 metadata）
- [ ] FLAG-INVENTORY 更新
