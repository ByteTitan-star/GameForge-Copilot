# Login / Auth — Page Overrides

> 覆盖 `MASTER.md`。产品：GameForge-Copilot 认证（登录 / 注册 / 邮箱验证 / 忘记密码）。  
> **已废弃：** 酸黄粗野、像素动态、青绿分栏表单区。

---

## 风格基调

**VEX liquid glass 改造版（深色电影感认证）**

- 全视口氛围底：循环视频或等价暗色动态底（**无全局压暗遮罩**；对比不足时仅在表单背后局部加极轻 scrim）
- 导航/表单容器：`.liquid-glass` 或等效 frosted chip
- 字体：Inter + Noto Sans SC
- 主 CTA：白底黑字；链接/次要：白字 + 玻璃描边
- 入场：标题可 char-stagger 或整块 fade-up；表单字段 stagger 300–450ms

## 布局

- **推荐：** 全屏媒体底 + **居中/偏下玻璃表单**（转化清晰，符合参考的底部加权习惯）
- 备选：上导航（品牌 GameForge / 回首页）+ 下方单栏表单，无需左右分栏实色板
- Mobile：表单全宽，`px-5`，玻璃圆角略收

## 功能（对齐 docs）

1. 登录：邮箱 + 密码、记住我、忘记密码、注册入口  
2. 注册：邮箱 + 密码 + 确认 → 提示查邮件  
3. 邮箱验证：6 位/链接（mock 可先做码）  
4. 忘记密码：邮箱 → 已发送提示  
5. 语言：ZH/EN mock 切换可保留  
6. 特殊 mock：`fail@test.com` 模拟失败态  

## 组件

- 可见 label + 密码显隐（lucide）
- Primary：白实心「登录」
- Secondary：玻璃「注册」或文字链
- 错误 `role="alert"`；提交 loading 锁按钮

## Motion

- 进入淡入；提交 loading  
- `prefers-reduced-motion`：关闭 char-stagger，改瞬时显示  

## 文案语气

围绕「开始设计你的小游戏 / 进入工坊」，不要用投资、DeFi、咨询预约话术。
