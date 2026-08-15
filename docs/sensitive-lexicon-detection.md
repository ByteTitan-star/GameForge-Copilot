# 敏感词词库检测方案设计

> 状态：**P1+P2 已落地；词库已扩裁赌毒/色情/暴恐/政治（待合入）**
> 作者：wangxin
> 关联代码：`backend/app/forge/guard.py`、`backend/app/forge/lexicon/`、`backend/app/forge/lexicons/`、`backend/app/forge/blacklist.txt`、`backend/app/core/config.py`
> 关联文档：护栏机制设计（quick_filter / Guard.audit / run_streamed_llm 既有架构）

---

## 1. 背景与目标

### 1.1 现状

护栏当前为两层结构：

| 层 | 实现 | 特点 |
|---|---|---|
| 快筛 `quick_filter` | `blacklist.txt` 正则/字面词黑名单，按 mtime 热加载 | 零成本、命中即决；当前仅越狱/恶意代码正则 + 运营自定义词 |
| LLM 审核 `Guard.audit` | 平台预设审核模型，0/1 判定 | 语义级兜底；依赖 AUDIT_MODEL 配置，超时降级快筛 |

问题：

* **覆盖面太薄**。现有正则只拦典型越狱与明显恶意代码，对色情、暴恐、赌博、毒品等中文违规内容零覆盖。`AUDIT_MODEL` 为空时语义级审核实际关闭，护栏只剩正则层。
* **合规量级差距**。《生成式 AI 服务管理暂行办法》配套备案实务常要求关键词库达到较大规模并覆盖多类风险。当前词表量级远不够；词库扩充是合规方向上的必需项。

### 1.2 目标

引入开源敏感词词库（裁剪后）+ Aho-Corasick 自动机匹配，形成三层审核结构：

> **AC 自动机大词库（主力快筛）→ blacklist.txt 自定义规则（保留现状）→ LLM 审核（语义兜底）**

* 万级词库下快筛仍毫秒级（扫描耗时与文本长度相关，与词库规模无关）。
* 误报可控：黑/白词库 + 游戏语境裁剪，避免正常游戏词被拦死。
* 运营自定义能力不回退：`blacklist.txt` 继续生效，热加载机制不变。

### 1.3 非目标

* 不上 MySQL/Redis 存词库。
* 不做后台管理界面（本期）。
* 不做变体对抗完备方案（拆字/谐音/拼音），仅轻量归一化。
* 不替换 LLM 审核层。
* **P1 已做灰名单前置约束文档；P2 已落地 suspect**：政治类等高误伤分类入灰名单，强制 LLM；无模型/失败 fail-open。

### 1.4 目标分层（避免误判进度）

| 阶段 | 实际目标 | 明确不是 |
|---|---|---|
| P1 | 补暴恐/色情/赌毒等**确定性**拦截；官方语料 0 误拦 block | 不等于备案达标 |
| P2 | suspect + 政治类极短清单；灰名单依赖 `AUDIT_MODEL` | 仍需单独合规 checklist / 评测报告；词库规模需继续人工扩裁 |

---

## 2. 技术选型

### 2.1 词库数据（选型结论：konsheng 为主，houbb 补充）

| 候选 | 许可证 | 规模 | 维护状态（2026-08 实测） | 结论 |
|---|---|---|---|---|
| [konsheng/Sensitive-lexicon](https://github.com/konsheng/Sensitive-lexicon) | MIT | 约 8.4 万词，17 个分类 txt | 2026-06 仍在更新 | **主词库来源**：裁剪后入库 |
| [houbb/sensitive-word-data](https://github.com/houbb/sensitive-word-data) | Apache-2.0 | 带现成白名单 | 2025-07 | **补充**：白名单直接复用思路 |
| observerss/textfilter | 无 LICENSE | — | — | **否决** |
| cjh0613/tencent-sensitive-words | AGPL-3.0 | — | — | **否决**（传染性） |

词库**裁剪后**静态进仓库；不引入子模块、不运行时拉取。文件头 / `NOTICE` 标明上游与日期。

### 2.2 匹配引擎：pyahocorasick（BSD-3）

一次构建、多次扫描；构建在启动/热加载时完成。备选 ahocorapy 仅在无法装 C 扩展时考虑。

### 2.3 不引入整备框架

业界共识：`pyahocorasick` + 裁剪 txt + 自写归一化薄层。

---

## 3. 方案设计

### 3.1 整体结构（评审修订：流水线顺序）

```
quick_filter(text)                        # guard.py，对外签名不变
 ├─ 0. audit_quick_filter 开关
 ├─ 1. blacklist.txt 正则/字面规则          # 对【原文】匹配，行为零变化
 ├─ 2. audit_lexicon_enabled？否则结束
 ├─ 3. 归一化 normalize(text)              # 全半角 / 去干扰（繁简可延后）
 ├─ 4. 白名单最长匹配 → 掩码跳过片段
 ├─ 5. AC 扫描 block 词库 → 命中即决
 └─ 6. AC 扫描 suspect → suspected=True（不即决；Guard.audit 强制 LLM）
```

**为何 blacklist 先于归一化、且对原文跑：** 越狱正则依赖英文词界与空格（如 `ignore previous instructions`），去空白/符号会改变命中语义；承诺「自定义规则层行为零变化」必须用原文。

### 3.2 词库文件布局

```
backend/app/forge/lexicons/
 ├─ NOTICE                      # 上游许可与拉取日期
 ├─ allow.txt                   # 白名单
 ├─ block/                      # 黑名单级：命中即决
 │   ├─ terrorism.txt
 │   ├─ porn.txt
 │   └─ gambling_drugs.txt
 └─ suspect/                    # 灰名单级：升级 LLM
     └─ politics.txt            # 极短清单
```

* **稳定 category 枚举**写在代码里（`terrorism` / `porn` / `gambling_drugs` / `politics`），文件名只是数据源。
* `lexicons/` 按目录树最新 mtime 热加载。
* 部署：随 `COPY backend/app` 进镜像；热更可挂 volume。

### 3.3 归一化层（P1）

| 项 | 示例 | 说明 |
|---|---|---|
| 全角→半角 | `赌．博` → `赌.博` | 码点平移 |
| 拉丁小写 | `HeRoIn` → `heroin` | 防英文大小写绕过 |
| 去干扰字符 | `赌*博`、`赌 博` | 剔除常见符号与空白后匹配 |

P1 可不做繁简；拆字/谐音/拼音交给 LLM。evidence：P1 可用命中词面；完整原文区间回映有单测后再上。

### 3.4 判定语义

| 级别 | 命中行为 |
|---|---|
| block | 即决拦截，`category` = 稳定枚举 |
| allow | 最长匹配优先，掩码后跳过 |
| suspect | `suspected=True`，不即决；`Guard.audit` 强制 LLM；无模型/失败放行 |

裁剪原则：

* 玩法描述词（击杀、爆头、射击、空投、开黑）不进 block，可进 allow 或剔除。
* 过宽词（「女人」「然后」等）直接剔除。
* 长度 ≤2 且未经人工确认的词不进 block。
* **suspect 必须极短**：避免流式窗高频刷 LLM。

### 3.5 配置项

```python
audit_lexicon_enabled: bool = True   # 关则完全跳过 AC 层
audit_lexicon_dir: str = ""          # 空 = 内置 app/forge/lexicons/
```

`audit_quick_filter` 语义不变（控整个快筛层）。

### 3.6 依赖

```toml
pyahocorasick = "^2.1"
```

---

## 4. 关键风险与对策

### 4.1 误报（核心风险）

三重对策：入库前裁剪、白名单、（P2）灰名单。  
**P1 入口条件**：官方游戏 / 模板语料全量扫描，断言 0 命中 block；评测脚本可复现。

### 4.2 性能

AC 扫描 ~O(文本长度)；构建仅在热加载时发生。

### 4.3 词库维护

静态进仓、季度级人工同步上游；禁止自动同步绕过裁剪。

### 4.4 灰名单成本（P2 前置约束）

流式窗 500ms 内，高频灰词会强制刷 LLM。P2 必须：极短清单、同窗去重、生产必配 `AUDIT_MODEL`。`AUDIT_MODEL` 空时灰名单 fail-open（与现状一致）。

### 4.5 仓库与归因

`lexicons/NOTICE` 写清 MIT/Apache 来源；敏感分类词表进仓需接受托管/镜像扫描风险。

---

## 5. 实施计划

### P1：黑名单级最小闭环（本期）

1. pyahocorasick + `lexicons/` + 自动机构建/热加载  
2. 裁剪暴恐 / 色情 / 赌博毒品入 block  
3. 归一化（全半角 + 去干扰）+ allow.txt  
4. `quick_filter`：原文 blacklist → 归一化 AC  
5. **验证**：官方语料 0 误拦；单测绿；audit 耗时无劣化  

### P2：灰名单与扩展分类（本期续）

1. `AuditResult.suspected`；`Guard.audit` 灰名单强制 LLM  
2. `suspect/politics.txt` 极短清单  
3. **验证**：LLM 判 0 放行 / 判 1 拦截（保留 politics category）/ 无模型与 LLM 挂掉放行  

两步均不动 `run_streamed_llm` 编排与 WS ATTACKED 字段形状（category 取值集合版本化扩充）。

---

## 6. 测试策略

| 层 | 用例 |
|---|---|
| 归一化 | 全角/干扰字符变体命中同一词 |
| 自动机 | 多词命中；空文本；构建可加载 |
| 判定 | block 即决；suspect 返回疑似；allow 长词优先；开关关闭回退 |
| 灰名单×LLM | 判 0 放行；判 1 带 category 拦截；无模型/挂掉放行 |
| 热加载 | 目录 mtime 变化重建 |
| 回归 | blacklist.txt 既有用例全绿 |
| 误报基线 | 官方 assets + 模板文本 0 block / 0 suspect 命中 |

---

## 7. 备选方案与否决理由（存档）

| 备选 | 否决理由 |
|---|---|
| MySQL/Redis 存词库 | 只读静态数据上 DB 过度设计 |
| Python 整备框架 | 维护无保障；AC 已够 |
| 全量照搬上游 | 游戏语境误拦不可接受 |
| 运行时拉 GitHub | 供应链 + 绕过裁剪 |
| 替换 LLM 审核 | 词库只能拦已知词，语义仍需 LLM |
