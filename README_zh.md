<h1 align="center">🎮 GameForge</h1>

<p align="center">
  <a href="https://github.com/ByteTitan-star/GameForge-Copilot/releases/tag/v2.2.0"><img src="https://img.shields.io/badge/GameForge-v2.2.0-6e40c9" alt="GameForge v2.2.0" /></a>
  <img src="https://img.shields.io/badge/python-3.12-3776AB" alt="Python 3.12" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <a href="./README.md"><img src="https://img.shields.io/badge/English-555555" alt="English" /></a>
  <img src="https://img.shields.io/badge/%E4%B8%AD%E6%96%87-0A66C2" alt="中文" />
</p>

> 用自然语言，把游戏想法做成可玩的浏览器游戏——
> 既支持单文件 HTML，也支持 Vite/React、Phaser 等工程化构建，
> 再迭代、试玩与发布。

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html">
    <img src="docs/showcase/assets/gameforge-home-v2.gif" alt="GameForge 产品首页" width="100%" />
  </a>
</p>

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html">打开产品展示</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html#watch">观看试玩展示</a>
</p>

## GameForge 是什么

GameForge 是一个面向浏览器游戏的 AI 辅助创作工作区。创作者从一句玩法描述开始，由 Agent 自主完成策划、生成与试玩——仅在决策关键偏好未知时提出一个聚焦问题，此后直接依据记住的偏好自主决策——即可得到能直接在浏览器试玩的结果——可以是轻量单文件 HTML，也可以是 Vite 工程（React UI，以及 Canvas / Phaser / PixiJS 等渲染栈）——并继续完成版本管理、下载与发布。

## 产品链路

| 阶段 | 关键动作 | 阶段结果 |
| --- | --- | --- |
| 创意输入 | 在 Forge 工作区用自然语言说明玩法、角色和规则。 | 清晰的玩法描述 |
| AI 策划 | 将创作意图整理为可查看、可确认的游戏设计。 | 结构化策划方案 |
| 按需提问 | 决策关键偏好未知时，Agent 通过 ask_user 工具提出一个聚焦问题并记住回答；其余情况直接依据偏好记忆自主决策。 | 已澄清的决策（记住供下次使用） |
| 游戏生成 | 将方案转化为可运行的浏览器游戏并反馈进度。 | 可管理的游戏版本 |
| 浏览器试玩 | 直接打开游戏，验证玩法与操作体验。 | 真实试玩反馈 |
| 下载或发布 | 下载独立 HTML，或提交进入发布流程。 | 可交付的游戏作品 |

## 开发游戏展示

### 像素跑酷

<img src="docs/showcase/assets/demo-pixel-runner-v2.gif" alt="像素跑酷动态游戏画面" width="100%" />

霓虹重力跑酷：空格或点击反转重力，避开障碍并累计分数。

### 塔防雏形

<img src="docs/showcase/assets/demo-tower-defense-v2.gif" alt="塔防动态游戏画面" width="100%" />

卡通塔防原型：放置防御塔、拦截敌人波次，并观察关卡进度。

## 产品界面

| Forge 工作区 | 浏览器试玩 |
| --- | --- |
| <img src="docs/showcase/assets/product-forge.png" alt="GameForge Forge 工作区" width="100%" /> | <img src="docs/showcase/assets/product-gameplay.png" alt="GameForge 浏览器试玩页" width="100%" /> |
| 描述创意，Agent 自主策划与生成，仅在需要时回答一个澄清问题。 | 打开生成结果，直接验证玩法与操作体验。 |

## 核心特性

| 核心特性 | 说明 |
| --- | --- |
| 自然语言驱动 | 不需要编写代码，通过描述玩法开始创作。 |
| 记忆优先的自主 Agent | Agent 端到端完成策划与生成，依据已保存的偏好自主决策，仅在决策真正模糊时提问（[ADR-18](docs/adr/ADR-18-native-tool-hitl-no-fixed-gates.md)）。 |
| 偏好记忆 | 从你的需求与回答中沉淀长期口味（风格、难度、语言、题材），自动应用于后续每次创作。 |
| 多技术栈生成 | 支持单文件 HTML，或 Vite 工程（React UI，以及 Canvas / Phaser / PixiJS 等）。 |
| 浏览器原生 | 无需安装，生成结果可以立即打开试玩。 |
| 可交付产物 | 下载、保存与分享可玩的浏览器构建。 |
| 版本可追溯 | 统一管理草稿、历史版本和公开作品。 |
| 作品生态 | 支持发布、发现、收藏、点赞与分享。 |

<p align="center">
  <strong>体验完整产品链路</strong><br /><br />
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html">打开在线产品展示</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html#watch">观看试玩视频</a>
</p>

## 许可证

MIT © CodeTitan, 2026 — 详见 [LICENSE](LICENSE)。
