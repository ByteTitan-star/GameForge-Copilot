# GameForge

<p align="right">
  <a href="README.md">简体中文</a> · <strong>English</strong>
</p>

> Use natural language to turn a game idea into a browser-ready experience that can be played, managed, and delivered.

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/docs/readme-redesign/docs/showcase/index.html?lang=en">
    <img src="docs/showcase/assets/gameforge-home.gif" alt="GameForge product home" width="100%" />
  </a>
</p>

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/docs/readme-redesign/docs/showcase/index.html?lang=en">Open product showcase</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/docs/readme-redesign/docs/showcase/index.html?lang=en#watch">Watch game showcases</a>
</p>

## What is GameForge?

GameForge is an AI-assisted workspace for creating browser games. Creators start with a gameplay description, move through AI planning, human review, and game generation, then receive a browser game they can play immediately, manage as versions, download, or publish.

## Product flow

```mermaid
flowchart TB
    subgraph S1["01 · Creative input"]
        direction LR
        A["Describe the game idea<br/>Gameplay · Characters · Rules"] --> B["Generate an AI plan<br/>Structure · Levels · Visuals"]
    end

    subgraph S2["02 · Plan and review"]
        C{"Review the plan<br/>Approve or keep refining"}
    end

    subgraph S3["03 · Game generation"]
        direction LR
        D["Generate a browser game<br/>Track progress in real time"]
        E["Save a runnable build<br/>Drafts · Version management"]
        D --> E
    end

    subgraph S4["04 · Play and deliver"]
        direction LR
        F["Play in the browser<br/>Validate gameplay and controls"]
        G["Download HTML<br/>or submit for publishing"]
        F --> G
    end

    B ==> C
    C ==>|Approved| D
    E ==> F

    classDef primary fill:#e8fff6,stroke:#18a875,stroke-width:2px,color:#092018
    classDef decision fill:#fff7d6,stroke:#d7a719,stroke-width:2px,color:#332600
    classDef output fill:#f4f7f6,stroke:#83958f,stroke-width:1.5px,color:#17211e
    class A,B,D,F primary
    class C decision
    class E,G output
    style S1 fill:#f8fffc,stroke:#b7ded0,stroke-width:1px
    style S2 fill:#f8fffc,stroke:#b7ded0,stroke-width:1px
    style S3 fill:#fffdf5,stroke:#e6d28d,stroke-width:1px
    style S4 fill:#fffdf5,stroke:#e6d28d,stroke-width:1px
```

## Created game showcase

### Pixel Runner

<img src="docs/showcase/assets/demo-pixel-runner.gif" alt="Animated Pixel Runner gameplay" width="100%" />

A neon gravity runner. Press Space or click to reverse gravity, avoid obstacles, and build your score.

### Tower Defense Prototype

<img src="docs/showcase/assets/demo-tower-defense.gif" alt="Animated tower defense gameplay" width="100%" />

A colorful tower defense prototype. Place defensive towers, stop enemy waves, and track level progress.

## Product interface

| Forge workspace | Browser playtest |
| --- | --- |
| <img src="docs/showcase/assets/product-forge.png" alt="GameForge Forge workspace" width="100%" /> | <img src="docs/showcase/assets/product-gameplay.png" alt="GameForge browser playtest" width="100%" /> |
| Describe an idea, review the AI plan, and confirm the generation direction. | Open the generated result and validate the gameplay and controls directly. |

## Product capabilities

| Create and generate | Manage and deliver |
| --- | --- |
| **AI planning with human review**<br/>Turn natural-language requirements into a game plan that can be reviewed. | **Versions and game library**<br/>Manage drafts, previous versions, and public creations in one place. |
| **Browser game generation**<br/>Generate a directly runnable game with live progress feedback. | **Play, download, and publish**<br/>Play in the browser, download standalone HTML, or submit for publishing. |
| **End-to-end creation flow**<br/>Move continuously from an initial idea to a playable game result. | **Discovery and interaction**<br/>Discover, favorite, like, and share more game creations. |

## Expanding next

- Iterate on an existing game through conversation.
- Upload custom character, background, and audio assets.
- Add more game genres, templates, and creation capabilities.

<p align="center">
  <strong>Experience the complete product flow</strong><br /><br />
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/docs/readme-redesign/docs/showcase/index.html?lang=en">Open the online product showcase</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/docs/readme-redesign/docs/showcase/index.html?lang=en#watch">Watch the game showcase video</a>
</p>

## License

[MIT](LICENSE)
