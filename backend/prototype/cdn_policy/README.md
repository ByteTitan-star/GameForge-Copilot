# CDN 资源策略原型（cdn_policy）

## 目的

在不改动现有业务代码的前提下，提供一个**可独立运行、可单测验证**的 CDN 白名单
策略模块，作为后续"放开 LLM 生成游戏引用公共 CDN"这一改造的最小可验证基础。

## 背景

当前两处约束相互矛盾：

- `backend/app/forge/prompts.py` 的 `CODE_PROMPT` **禁止**任何 CDN / 网络请求；
- `backend/app/hosting/routes.py` 的 `_CSP` 却放行整个 `https:`（`script-src ...
  https:`），任意 https CDN 都能被加载。

放开 CDN 能让 LLM 用上 three.js / pixi.js / tailwind / 字体等专业库，直接提升
生成游戏的渲染质量；但"放行整个 https"= 任意外站脚本能跑在产物 iframe 里，存在
XSS 与稳定性风险。需要用**白名单**收敛来源，并让 CSP、提示词、QA 试玩共用同一份
白名单——这正是本原型要验证的核心抽象。

## 模块说明（本原型交付）

`cdn_policy.py` —— 纯标准库，不依赖 `app.*`：

| 符号 | 作用 |
|------|------|
| `ALLOWED_CDN_HOSTS` | 可信 CDN 白名单（jsdelivr / unpkg / cdnjs / 谷歌字体 / tailwind / threejs） |
| `extract_external_refs(html)` | 提取 HTML 中 http(s) 绝对外链，保序去重 |
| `validate_refs(refs, allowed)` | 校验外链主机是否全在白名单，返回 `(ok, 违规列表)` |
| `build_csp(allowed)` | 按白名单生成产物 iframe 的 CSP 头（取代放行 `https:`） |

`test_cdn_policy.py` —— 9 个用例，覆盖提取（含大小写/去重/相对路径排除）、校验
（白名单通过 / 违规 / 自定义白名单 / 空输入）、CSP 生成（含全部白名单域 / 无 `https:` 通配）。

## 对接清单（不在本原型内执行，仅列出后续落地点）

| 落点 | 现状 | 改为 |
|------|------|------|
| `hosting/routes.py` `_CSP` | 硬编码放行 `https:` | `_CSP = build_csp()` |
| `forge/prompts.py` `CODE_PROMPT` | "禁止 CDN" | "仅允许引用白名单内 CDN：`{sorted(ALLOWED_CDN_HOSTS)}`"，白名单从 `cdn_policy` 导入，单一来源 |
| `forge/graph.py` `qa_node` / `sandbox/playtest.py` | 仅 DOM 结构 + JS 错误检测 | 试玩前先 `validate_refs(extract_external_refs(html))`，违规写入 `playtest_errors` 触发 `code_node` 修复 |
| `frontend/GamePlayer.tsx` | 无需改 | CSP 收紧后 iframe 行为更确定，8s onLoad 兜底仍保留 |

> 这张表是"改动需求"的精确化——每一行 diff 都能对上某个具体需求点，落地时按表执行即可。

## 影响与风险

- **正向**：CSP 从"放行 https"收敛到白名单，XSS 攻击面收窄；CSP / 提示词 / QA 三方
  共用同一份白名单，增删域名只改 `ALLOWED_CDN_HOSTS` 一处。
- **风险**：白名单外的合法 CDN 会被 CSP 拦截 → 需要时在 `ALLOWED_CDN_HOSTS` 一处增补；
  提示词放开后 LLM 可能引用冷门库，QA 的 `validate_refs` 会兜住并回退修复。
- **不涉及**：Docker 沙箱镜像、Node 构建链路、多文件产物、多框架支持——本原型完全不
  触碰，是"低成本提升渲染质量"路线的最小切片，与多框架工程化路线正交。

## 验证

```bash
cd backend
# 方式一：被 pytest 显式收集（默认 testpaths=tests 不收本目录，故显式指明）
uv run pytest prototype/cdn_policy/ -v
# 方式二：完全独立运行，不依赖 pytest 收集配置
python prototype/cdn_policy/test_cdn_policy.py
```

预期：9 passed。
