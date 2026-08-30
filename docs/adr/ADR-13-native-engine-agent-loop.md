# ADR-13: Native Engine Agent Loop（Godot-first / Unity later）

* Status: **Accepted**
* Date: 2026-08-26
* Author: Auto（依 Owner 规划起草）
* Related: ADR-03（Sandbox）、ADR-09（Timeout / Tier）、ADR-11（Sandbox / Hosting 资源）、`docs/build-pipeline.md`、`engine_router`、CodeQaLoop

---

## 1. TL;DR

| 主题         | 决策（提案）                                                                                                       |
| ---------- | ------------------------------------------------------------------------------------------------------------ |
| 产品边界扩展     | 在现有 HTML / Vite 浏览器游戏管线旁新增 **Native Engine Agent Loop**：Generate → Validate / Build → Run → Observe → Repair |
| 首期引擎       | **Godot-first**；Unity 不与一期绑定，仅保留 Adapter 扩展点与后续里程碑                                                           |
| P0 成功标准    | 固定 Godot 模板下，Agent 可生成合法工程；完成引擎级校验 / Build；headless 启动成功；失败可基于结构化诊断自动 repair ≥1 轮                            |
| 与 Web 路线关系 | **平行管线，不替换现有路线**；复用 Agent 编排、Sandbox、CodeQaLoop、Tracing，不复用 Playwright 作为核心验收器                               |
| 架构原则       | LLM 生成游戏内容，平台控制引擎版本、模板、构建命令、依赖、运行参数与资源边界                                                                     |
| P0 非目标     | Unity、可视化试玩、多平台发布、任意插件安装、复杂 3D 游戏、产品 UI 完整接入                                                                 |

---

## 2. Context

### 2.1 现状

GameForge 当前受控游戏技术栈为：

```python
SUPPORTED_ENGINES = frozenset({
    "canvas",
    "phaser3",
    "pixijs",
})
```

现有闭环主要面向：

```text
LLM
 ↓
HTML / JS / TS
 ↓
Vite / Single HTML
 ↓
Browser
 ↓
Playwright
 ↓
Diagnose / Repair
```

产物以单 HTML 或 Vite `dist/` 为主，验证依赖浏览器启动、DOM / Console / 页面状态等 Web 信号。

该模型无法直接覆盖 Godot / Unity 等具有独立工程结构、引擎运行时和构建工具链的原生游戏工程。

### 2.2 驱动问题

需要验证以下 Agent 闭环是否能够成立：

```text
Natural Language Requirement
          ↓
      Generate
          ↓
    Validate / Build
          ↓
         Run
          ↓
       Observe
          ↓
       Diagnose
          ↓
        Repair
          └────────→ Validate / Build
```

核心目的不是立刻替代 Web Game Pipeline，而是回答：

> Agent 在真实游戏引擎、真实工程结构和真实运行时约束下，能否依靠构建错误与运行诊断持续收敛到可运行结果？

### 2.3 为什么 Godot-first

Godot 更适合作为 Native Engine Agent Loop 的首个验证对象：

| 维度         | Godot               | Unity                    |
| ---------- | ------------------- | ------------------------ |
| 自动化接口      | CLI / headless 友好   | BatchMode 可行，但工程链路更重     |
| 授权         | 开源                  | Editor / License 管理复杂度更高 |
| 工程规模       | 固定模板 + GDScript 易限制 | C# + Unity API 面更大       |
| Sandbox 镜像 | 相对容易固定              | Editor 镜像与构建资源更重         |
| Agent 收敛   | API 面较小，适合首轮 PoC    | 幻觉与依赖问题更复杂               |
| 首期目标       | 验证闭环                | 验证完成后再适配                 |

**Decision：**

> 使用 Godot 验证 Native Engine Agent Loop 的架构形态；Unity 作为后续 `EngineAdapter`，不与 Godot MVP 同期交付。

---

## 3. Decision

### 3.1 闭环统一抽象

原“Generate → Compile → Run → Logs → Repair”调整为：

```text
Generate
   ↓
Validate
   ↓
Build
   ↓
Run
   ↓
Observe
   ↓
Diagnose
   ↓
Repair
   └────────→ Validate
```

其中：

### Generate

Agent 仅允许在平台提供的固定 Template Workspace 内生成或修改：

* GDScript
* `.tscn` Scene
* 白名单 Resource
* 游戏配置
* 平台允许修改的项目文件

禁止 Agent：

* 修改 Godot 版本
* 修改基础 Docker 镜像
* 下载任意插件
* 修改构建工具链
* 自定义系统级依赖

### Validate

在真正执行 Build 之前执行低成本校验：

```text
Generated Files
    ↓
File / Path Policy
    ↓
Static API Policy
    ↓
Godot Parse / Import Validation
```

主要检查：

* 工程结构是否合法
* `project.godot` 是否存在
* Main Scene 是否存在
* GDScript 是否存在解析错误
* Scene / Resource 引用是否完整
* 是否调用禁止 API
* 是否修改平台保护文件

Validate Failure 直接进入 Diagnose / Repair，避免无意义 Build。

### Build

`Build` 是跨引擎统一抽象。

Godot 下主要对应：

```text
Project Import / Validation
+
Configured Export
```

P0 固定：

* Godot 版本
* Linux Target
* Export Preset
* Export Template
* Output Path

平台控制构建命令，LLM 不直接生成 Shell Command。

未来 Unity Adapter 可将同一阶段映射为：

```text
C# Compile
+
Unity BatchMode Build
```

因此 ADR 不使用 `Compile` 作为跨引擎统一阶段名。

### Run

Build 成功后进入受控运行阶段。

Godot P0：

```text
Exported Artifact / Project
        ↓
Sandbox Process
        ↓
Headless Runtime
        ↓
Ready Signal / Runtime Error / Timeout
```

运行必须设置：

* Process Timeout
* CPU / Memory Limit
* PID Limit
* Filesystem Scope
* Network Policy
* 最大日志大小

### Observe

统一收集：

```text
stdout
stderr
exit_code
engine_version
phase
elapsed_ms
ready_signal
error_type
```

并转换为结构化诊断对象：

```json
{
  "engine": "godot",
  "phase": "run",
  "error_type": "RUNTIME_ERROR",
  "exit_code": 1,
  "summary": "...",
  "stderr_excerpt": "...",
  "affected_files": [],
  "retryable": true
}
```

禁止直接把无限原始日志全部注入 LLM。

### Diagnose / Repair

Repair Agent 输入由平台构建：

```text
Current Code Diff
+
Engine Version
+
Build / Runtime Phase
+
Structured Diagnostics
+
Relevant Log Excerpt
+
Repair History
```

进入有界 Repair Loop：

```text
Repair
  ↓
Validate
  ↓
Build
  ↓
Run
  ↓
Success ?
 ├─ Yes → PASS
 └─ No
      ↓
 Budget Available ?
 ├─ Yes → Repair
 └─ No  → FAIL
```

Repair 必须具有：

* 最大轮次
* 最大 Token Budget
* 最大总执行时间
* 重复错误熔断
* 相同 Patch 熔断

---

## 3.2 Engine Adapter

禁止在现有业务代码中不断增加：

```python
if engine == "godot":
    ...
elif engine == "unity":
    ...
```

新增统一引擎适配层：

```text
EngineAdapter

├── prepare()
├── validate()
├── build()
├── run()
├── collect_diagnostics()
└── package()
```

第一期实现：

```text
EngineAdapter
└── GodotAdapter
```

后续：

```text
EngineAdapter
├── GodotAdapter
└── UnityAdapter
```

Web 路线暂不强制迁移到此抽象，避免 P0 为统一架构重构现有稳定路径。

待 Native Pipeline 稳定后，再评估是否抽象统一：

```text
WebEngineAdapter
NativeEngineAdapter
```

---

## 3.3 Engine Router

现有 Web Engine Router：

```python
canvas
phaser3
pixijs
```

Native Engine 不应仅通过：

```python
SUPPORTED_ENGINES.add("godot")
```

完成接入。

建议逐步演进为：

```text
EngineSpec
├── id
├── family: web | native
├── capabilities
├── adapter
├── runtime
└── enabled
```

例如：

```text
godot
family = native
adapter = GodotAdapter
enabled = feature_flag
```

原则：

> 未知引擎、不可用引擎、未开启引擎必须显式失败或要求重新选择，禁止静默回退成 Canvas 并标记成功。

---

## 3.4 Template-first

P0 不允许 Agent 从空目录自由生成 Godot 工程。

平台提供固定：

```text
godot_template/
├── project.godot
├── export_presets.cfg
├── scenes/
├── scripts/
├── assets/
└── gameforge/
    ├── bootstrap.gd
    └── runtime_probe.gd
```

Agent 主要负责：

```text
GameDesignSpec
       ↓
Scenes / GDScript
       ↓
Allowed Resources
```

平台负责：

* Bootstrap
* Runtime Probe
* Export Preset
* Godot Version
* Directory Contract
* Build / Run Commands

减少 Agent 对基础设施的控制面。

---

## 3.5 Runtime Readiness Protocol

“进程没有立即退出”不能等价于游戏运行成功。

平台模板提供统一 Ready Protocol。

例如：

```text
GAMEFORGE_READY
```

只有满足最低启动条件后才输出。

Harness 判断：

```text
Process Started
      ↓
Fatal Error?
 ├─ Yes → FAIL
 └─ No
      ↓
Ready Signal Before Timeout?
 ├─ Yes → RUN_OK
 └─ No  → READY_TIMEOUT
```

P0 的 `RUN_OK` 只证明：

> 工程能够被引擎成功加载并进入预期运行状态。

**不证明：**

* 画面正确
* 玩法正确
* 手感正确
* 美术正确
* 游戏可完整通关

这些属于后续 Playtest / Visual QA。

---

## 3.6 Error Taxonomy

Native Loop 至少统一以下错误：

```text
POLICY_DENIED
TEMPLATE_INVALID
VALIDATION_FAILED
BUILD_FAILED
RUN_FAILED
READY_TIMEOUT
RUNTIME_ERROR
RESOURCE_LIMIT
REPAIR_EXHAUSTED
INTERNAL_ERROR
```

所有错误必须：

```text
Raw Failure
    ↓
Error Classifier
    ↓
Structured Diagnostic
    ↓
Repair / Fail
```

避免 Repair Agent 直接处理不受控的全量 stderr。

---

## 3.7 Sandbox 与安全边界

Native Game Agent 的生成代码执行继续遵循 ADR-03。

P0 默认：

* 网络关闭
* 无宿主 Docker Socket
* 无宿主目录写权限
* 无生产密钥
* Workspace 外文件禁止写入
* CPU / Memory / PID / Disk / Timeout 限额
* 日志长度限制
* 禁止安装任意 Godot Plugin
* 禁止下载任意二进制依赖

额外增加 Godot 生成代码静态策略。

重点检查高风险能力，包括但不限于：

```text
OS / Process Execution
Arbitrary File Access
External Network
Dynamic Native Library
Unapproved Plugin
```

原则：

> Static Policy 用于减少危险代码进入执行阶段；Sandbox 才是最终安全边界。

不能以正则 / 静态扫描代替隔离执行。

---

## 3.8 Build 与 Runtime

逻辑上必须区分：

```text
Build Environment
Runtime Environment
```

但 P0 **不要求物理拆成两个镜像**。

为了降低 PoC 复杂度：

```text
gameforge-godot-builder
```

可同时承担：

* Validate
* Export
* Headless Run

但不同阶段使用不同：

* Command
* Timeout
* Resource Limit
* Filesystem Permission

当 P1 数据证明镜像体积、冷启动、安全或资源隔离存在明显问题后，再考虑拆分：

```text
gameforge-godot-builder
gameforge-godot-runner
```

避免 P0 为“架构纯洁性”引入不必要工程量。

---

## 3.9 Observability

所有 Native Engine Run 纳入现有 Trace。

建议 Span：

```text
native_engine
├── generate
├── validate
├── build
├── run
├── diagnose
└── repair
```

核心指标：

```text
validate_ok
build_ok
run_ok
repair_attempted
repair_success
repair_rounds
build_latency_ms
run_latency_ms
total_latency_ms
timeout_rate
error_type
engine
engine_version
```

需要能够回答：

* 最常见失败发生在哪个阶段？
* 哪类错误最容易被 Repair 修复？
* Repair 第几轮之后收益快速降低？
* Godot 闭环主要耗时在 Build 还是 Run？
* 哪类 Prompt 最容易失败？

---

## 4. Phases

| 阶段                   | 范围                                                                                             | 规划估算            |
| -------------------- | ---------------------------------------------------------------------------------------------- | --------------- |
| **P0 PoC**           | Feature flag / 独立入口；固定 Template；Generate → Validate → Build → Headless Run → Diagnose → Repair | 1.5–2.5 周       |
| **P1 Product MVP**   | 接入 Forge 主 Workflow；EngineAdapter；完整 Trace；失败自动 Repair；基础指标                                    | 累计约 4–6 周       |
| **P2 Playtest**      | HTML5 Preview / Screenshot / Recording / Script Assertion / HITL / Benchmark                   | 再 +4–8 周        |
| **P3 Unity Adapter** | Unity Template + C# + BatchMode + Build / Run / Logs / Repair                                  | 单独评估，不与 P1 承诺绑定 |

以上为工程规划估算，不作为 ADR 的技术正确性前提。

---

## 5. P0 Scope

### In Scope

```text
Godot 4.x 固定版本
2D 小型游戏
固定 Template
GDScript
固定 Main Scene Contract
Linux Build Target
Headless Runtime
Structured Diagnostics
≥1 Round Repair
Feature Flag
Trace
```

### Out of Scope

```text
Unity
复杂 3D
任意插件
Asset Store
用户自选 Godot Version
多平台打包
Steam / App Store
多人联机
完整 Visual QA
产品级浏览器试玩
```

---

## 6. P0 Evaluation

建立固定小样本集，而不是只证明“某个 Demo 跑过一次”。

建议首批至少：

```text
10–20 个固定 Prompt
```

覆盖：

* Platformer
* Top-down
* Shooter
* Puzzle
* Collect Game
* Simple Physics
* Multi-scene

记录：

```text
First Validate Pass Rate
First Build Pass Rate
First Run Pass Rate
Repair Recovery Rate
Final Run Success Rate
Average Repair Rounds
P50 / P95 Latency
```

P0 暂不提前承诺高成功率目标。

目标是：

> 得到可复现 baseline，并证明失败可以通过结构化诊断进入自动修复，而非人工手动介入。

---

## 7. Consequences

### 7.1 正向

* GameForge 从浏览器代码生成扩展到真实游戏引擎工程。
* 验证 Agent 在编译器 / 引擎运行时约束下的自动收敛能力。
* `EngineAdapter` 为未来 Unity 提供明确扩展边界。
* Build / Run / Diagnose / Repair 能够形成真正可评测闭环。
* 与现有 Agent Harness、Sandbox、Tracing、CodeQaLoop 能力形成复用。

### 7.2 成本

* Godot 镜像明显大于 Node / Vite Builder。
* 冷启动、构建与执行成本提升。
* GDScript / Godot API 幻觉将增加 Repair 压力。
* Headless Run 无法替代视觉和玩法验收。
* Native Runtime 扩大生成代码攻击面。

### 7.3 风险缓解

```text
API Hallucination
→ Template + Skill + Static Validation + Repair

Unsafe Generated Code
→ Policy + Sandbox

Large Logs
→ Structured Diagnostics + Truncation

Infinite Repair
→ Budget + Circuit Breaker

Engine Drift
→ Pinned Version

Infrastructure Hallucination
→ LLM Cannot Control Build Commands
```

---

## 8. Rollback

Feature flag：

```text
native_engine_enabled = false
```

关闭后：

```text
Engine Router
    ↓
Web Engine Only
    ↓
canvas / phaser3 / pixijs
```

Native Pipeline 不修改现有 Web Artifact Contract。

删除或停用：

```text
GodotAdapter
Godot Template
Godot Builder Image
```

不得影响现有 HTML / Vite 路径。

---

## 9. Acceptance Checklist

* [ ] Godot 版本由平台固定，LLM 无权修改
* [ ] 固定 Template 能被确定性创建
* [ ] Agent 仅能修改白名单工程文件
* [ ] Validate Failure 可以进入 Repair
* [ ] Build Failure 可以进入 Repair
* [ ] Runtime Failure / Timeout 可以进入 Repair
* [ ] Repair 有最大轮次、Token、时间预算
* [ ] Headless Runtime 有明确 Ready Protocol
* [ ] stdout / stderr / exit code 转换为结构化 Diagnostics
* [ ] 日志进入 LLM 前完成 Secret Redaction 与长度控制
* [ ] Sandbox 默认无外网、无生产密钥、无宿主写权限
* [ ] Native Loop Trace 可看到 Generate / Validate / Build / Run / Repair
* [ ] 建立固定 Benchmark，而非只跑通单 Demo
* [ ] Feature flag 关闭时现有 Web Pipeline 零行为变化
* [ ] 未知 / 不可用 Engine 不允许静默回退 Canvas 后标记成功

---

## 10. Owner Decisions

### D1. 一期范围

**建议：批准 P0 PoC。**

暂不直接承诺 P1 产品 MVP。

P0 首先证明：

```text
Generate
→ Validate
→ Build
→ Headless Run
→ Diagnostics
→ Repair
```

能够稳定串通。

### D2. P0 是否要求浏览器预览

**建议：不要求。**

P0：

```text
Headless RUN_OK
```

即可作为运行闭环验收。

可视化预览归入 P2。

### D3. Unity 是否同步进入一期

**建议：否。**

仅保留：

```text
EngineAdapter
```

扩展点。

Unity 在 Godot Pipeline 形成稳定错误模型、指标和 Repair Contract 后另开 ADR。

### D4. Unity 是否写公开路线图

**建议：暂不作为承诺型公开 Roadmap。**

可描述为：

> Native engine architecture is designed for future engine adapters.

避免 PoC 阶段形成 Unity 产品交付承诺。

---

## 11. Final Decision Summary

一期批准目标：

> **在固定 Godot Template 与受控 Sandbox 中，实现 Agent 从自然语言需求生成 Godot 游戏工程，经 Validate / Build 后完成 Headless Run，并基于结构化 Build / Runtime Diagnostics 自动 Repair 至少一轮；形成可复现 Benchmark 和阶段级 Trace。**

这即定义为 GameForge Native Engine Agent Loop P0 完成。
