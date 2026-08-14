# GameForge

<p align="right">
  <strong>简体中文</strong> · <a href="README.en.md">English</a>
</p>

> 用自然语言，把游戏想法推进为可在浏览器直接试玩、管理与交付的作品。

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html">
    <img src="docs/showcase/assets/gameforge-home.gif" alt="GameForge 产品首页" width="100%" />
  </a>
</p>

<p align="center">
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html">打开产品展示</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html#watch">观看试玩展示</a>
</p>

## GameForge 是什么

GameForge 是一个面向浏览器游戏的 AI 辅助创作工作区。创作者从一句玩法描述开始，经过 AI 策划、人工确认和游戏生成，即可得到能够直接试玩的浏览器游戏，并继续完成版本管理、下载与发布。

## 产品链路

```mermaid
flowchart TB
    subgraph S1["01 · 创意输入"]
        direction LR
        A["描述游戏想法<br/>玩法 · 角色 · 规则"] --> B["AI 生成策划<br/>结构 · 关卡 · 视觉"]
    end

    subgraph S2["02 · 策划确认"]
        C{"人工审阅方案<br/>确认或继续调整"}
    end

    subgraph S3["03 · 游戏生成"]
        direction LR
        D["生成浏览器游戏<br/>实时反馈生成进度"]
        E["保存可运行版本<br/>草稿 · 版本管理"]
        D --> E
    end

    subgraph S4["04 · 体验交付"]
        direction LR
        F["浏览器内试玩<br/>验证玩法与操作"]
        G["下载 HTML<br/>或提交发布"]
        F --> G
    end

    B ==> C
    C ==>|确认通过| D
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

## 开发游戏展示

### 像素跑酷

<img src="docs/showcase/assets/demo-pixel-runner.gif" alt="像素跑酷动态游戏画面" width="100%" />

霓虹重力跑酷：空格或点击反转重力，避开障碍并累计分数。

### 塔防雏形

<img src="docs/showcase/assets/demo-tower-defense.gif" alt="塔防动态游戏画面" width="100%" />

卡通塔防原型：放置防御塔、拦截敌人波次，并观察关卡进度。

## 产品界面

| Forge 工作区 | 浏览器试玩 |
| --- | --- |
| <img src="docs/showcase/assets/product-forge.png" alt="GameForge Forge 工作区" width="100%" /> | <img src="docs/showcase/assets/product-gameplay.png" alt="GameForge 浏览器试玩页" width="100%" /> |
| 描述创意、查看 AI 策划并确认生成方向。 | 打开生成结果，直接验证玩法与操作体验。 |

## 产品能力

| 创作与生成 | 管理与交付 |
| --- | --- |
| **AI 策划与人工确认**<br/>把自然语言需求整理为可审阅的游戏方案。 | **版本与作品管理**<br/>统一管理草稿、历史版本和公开作品。 |
| **浏览器游戏生成**<br/>生成可直接运行的游戏，并实时反馈进度。 | **试玩、下载与发布**<br/>浏览器内试玩，下载独立 HTML 或提交发布。 |
| **完整创作闭环**<br/>从创意输入持续推进到可玩的游戏结果。 | **作品发现与互动**<br/>发现、收藏、点赞和分享更多游戏作品。 |

## 持续扩展

- 通过对话迭代已有游戏。
- 自定义角色、背景和音效素材上传。
- 更多游戏类型、模板与创作能力。

<p align="center">
  <strong>体验完整产品链路</strong><br /><br />
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html">打开在线产品展示</a>
  &nbsp;·&nbsp;
  <a href="https://htmlpreview.github.io/?https://raw.githubusercontent.com/ByteTitan-star/GameForge-Copilot/main/docs/showcase/index.html#watch">观看试玩视频</a>
</p>

## 许可证

[MIT](LICENSE)
