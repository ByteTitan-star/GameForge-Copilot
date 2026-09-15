<h1 align="center">🎮 GameForge</h1>

<p align="center">
  <a href="https://github.com/ByteTitan-star/GameForge-Copilot/releases/tag/v2.2.0"><img src="https://img.shields.io/badge/GameForge-v2.2.0-6e40c9" alt="GameForge v2.2.0" /></a>
  <img src="https://img.shields.io/badge/python-3.12-3776AB" alt="Python 3.12" />
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT" /></a>
  <img src="https://img.shields.io/badge/English-0A66C2" alt="English" />
  <a href="./README_zh.md"><img src="https://img.shields.io/badge/%E4%B8%AD%E6%96%87-555555" alt="Chinese" /></a>
</p>

> Use natural language to turn a game idea into a playable browser game —
> from single-file HTML to Vite/React and Phaser projects — then iterate,
> playtest, and publish.

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html?lang=en">
    <img src="docs/showcase/assets/gameforge-home-v2.gif" alt="GameForge product home" width="100%" />
  </a>
</p>

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html?lang=en">Open product showcase</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html?lang=en#watch">Watch game showcases</a>
</p>

## What is GameForge?

GameForge is an AI-assisted workspace for creating browser games. Creators start with a gameplay description and the agent plans, generates, and playtests autonomously — asking one focused question only when a decision-critical preference is unknown, then deciding directly from remembered preferences — delivering a playable result in the browser — whether as a compact HTML build or a Vite project (React UI, Canvas / Phaser / PixiJS, and more) — and can keep managing versions, downloading, or publishing.

## Product flow

| Stage | Key action | Stage output |
| --- | --- | --- |
| Creative input | Describe the gameplay, characters, and rules in natural language in the Forge workspace. | A clear gameplay brief |
| AI planning | Turn the creative direction into a game design that can be reviewed and confirmed. | A structured design plan |
| On-demand clarification | When a decision-critical preference is unknown, the agent asks one focused question via the `ask_user` tool and remembers the answer; otherwise it decides directly from your preference memory. | A clarified decision, saved for next time |
| Game generation | Turn the plan into a runnable browser game with live progress feedback. | A manageable game version |
| Browser playtest | Open the game directly and validate the gameplay and controls. | Real playtest feedback |
| Download or publish | Download a standalone HTML build or submit the game for publishing. | A deliverable game |

## Created game showcase

### Pixel Runner

<img src="docs/showcase/assets/demo-pixel-runner-v2.gif" alt="Animated Pixel Runner gameplay" width="100%" />

A neon gravity runner. Press Space or click to reverse gravity, avoid obstacles, and build your score.

### Tower Defense Prototype

<img src="docs/showcase/assets/demo-tower-defense-v2.gif" alt="Animated tower defense gameplay" width="100%" />

A colorful tower defense prototype. Place defensive towers, stop enemy waves, and track level progress.

## Product interface

| Forge workspace | Browser playtest |
| --- | --- |
| <img src="docs/showcase/assets/product-forge.png" alt="GameForge Forge workspace" width="100%" /> | <img src="docs/showcase/assets/product-gameplay.png" alt="GameForge browser playtest" width="100%" /> |
| Describe an idea, watch the agent plan and generate, and answer a clarifying question only when asked. | Open the generated result and validate the gameplay and controls directly. |

## Core features

| Core feature | Description |
| --- | --- |
| Natural-language driven | Start creating by describing the gameplay instead of writing code. |
| Autonomous agent, memory-first | The agent plans and generates end to end, deciding from your saved preferences and asking a question only when a decision is truly ambiguous ([ADR-18](docs/adr/ADR-18-native-tool-hitl-no-fixed-gates.md)). |
| Preference memory | Long-term taste (style, difficulty, language, genre) is captured from your requests and answers and applied to every future creation. |
| Flexible game stacks | Generate single-file HTML or Vite projects with React UI and engines such as Canvas, Phaser, and PixiJS. |
| Browser native | Open and play generated results immediately without extra installation. |
| Deliverable builds | Download, save, and share playable browser builds. |
| Traceable versions | Manage drafts, previous versions, and public creations in one place. |
| Creation ecosystem | Publish, discover, favorite, like, and share game creations. |

<p align="center">
  <strong>Experience the complete product flow</strong><br /><br />
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html?lang=en">Open the online product showcase</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html?lang=en#watch">Watch the game showcase video</a>
</p>

## License

MIT © CodeTitan, 2026 — see [LICENSE](LICENSE).
