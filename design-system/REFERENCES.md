# Style References（学习笔记，非照抄清单）

用户提供的外部 UI 规格用于**提炼原则**。实现产品 UI 时改造成 GameForge 语境，禁止复制品牌名、占位文案与业务结构。

## 1. NovaAI — 深色电影 + 玻璃编辑式

- 固定玻璃顶栏、全屏 scroll-scrub 视频、80vh spacer  
- mono 微标签、白字 drop-shadow、frost panel 能力列表  
- **我们用在：** Landing  

## 2–3. VEX — Liquid glass Hero

- 视频 raw 无压暗、`.liquid-glass`、字级入场、底栏双 CTA  
- **我们用在：** Auth（登录/注册）主气质  

## 4. RIVR — 浅色软玻璃 Dashboard Hero

- `#f0f0f0` 画布、圆角媒体舞台、白玻璃浮卡、motion 微交互  
- **我们用在：** Forge / Setting / Admin  

## 5. TOONHUB（已实现预览）

- 手办轮播 + 变色背景 + grain  
- **我们用在：** 作品发现 / 精选游戏展示，非整站默认  

## 改造检查

写任何前端页之前问三句：

1. 这是游戏创作工具的哪一类表面？（上表）  
2. 有没有误用参考站的行业话术？  
3. 深色玻璃 vs 浅色工作台是否与 `MASTER.md` 映射一致？  
