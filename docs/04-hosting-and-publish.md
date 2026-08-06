# 04 · 产物托管与发布审批

## 产物托管

### 产物形态
- 生成结果为一组静态文件：`index.html` + JS/CSS + 资源（图片/音频/数据）。
- 单入口、无后端依赖、无外部网络（自包含）。code 子图保证产物可直接静态托管。

### 产物安全（强制）
- 试玩页必须用 `<iframe sandbox="allow-scripts">`（**不加** `allow-same-origin`）挂载产物，隔离 cookie/LocalStorage/同源访问。
- `/play` 与 `/draft` 响应加 `Content-Security-Policy`：限制脚本来源、禁外链、禁内联事件（尽量）。
- 产物构建后做大小上限校验（见配额），超限拒绝托管。
- 生成的 JS 在访客浏览器执行，视为不可信内容；产物不得请求后端业务 API（CORS 拒绝跨域）。

### 产物配额
- 单产物解压后大小上限（默认 50MB，可配置），超限拒绝发布。
- 每用户草稿游戏数上限、已发布游戏数上限（可配置）。
- 版本保留上限（默认最近 20 个），超出归档或清理。

### 存储
- MVP：本地静态目录（`HOSTING_ROOT/{game_id}/{version}/`）或 S3 兼容对象存储。
- 路径规则：`{game_id}/{version}/index.html`，版本号单调递增。

### 访问路由
- 已发布游戏：`/play/{slug}` → 后端校验 `game.status=published` 后，内部转发到产物静态文件（X-Accel-Redirect 或后端 FileResponse）。
- 草稿试玩：仅 owner，`/draft/{game_id}/{version}` → 后端鉴权 owner 后同上转发。
- 公开路由 `/play/{slug}` 不要求登录；非 published 状态一律 404。
- 静态资源带长缓存头；版本切换通过 slug 指向新版本。
- slug 在审批通过时分配（全局唯一），draft 阶段为 null。

### 版本管理
- 每次生成/迭代产出一个新版本，旧版本保留可回看。
- 发布绑定某版本；下架后 slug 不再可访问（产物保留以便重新上架）。

## 发布审批工作流

### 状态机
```
draft ──submit──▶ submitted ──review──▶ reviewing
reviewing ──approve──▶ published   （publish_request.status=approved）
reviewing ──reject──▶ rejected     （publish_request.status=rejected，带理由）
rejected ──submit──▶ submitted     （改后重新提交）
published ──take_down──▶ taken_down
taken_down ──submit──▶ submitted    （重新上架必须再走审批，不直接回 published）
```
> 状态映射：`game.status` 是对外可见性唯一来源；`publish_request.status` 是审批单状态。approve 后两者分别为 published/approved，reject 后分别为 rejected/rejected。

| 状态 | 含义 | 谁能看 |
|---|---|---|
| draft | 草稿，生成/迭代中 | 仅创建者 |
| submitted | 已提交待审 | 创建者 + 管理员（仅待审队列） |
| reviewing | 审核中 | 创建者 + 管理员 |
| published | 已上架 | 所有人 |
| rejected | 被驳回 | 仅创建者（管理员可见驳回记录） |
| taken_down | 已下架 | 创建者可见记录，他人不可访问 |

### 可见性铁律
- **草稿/驳回态**：仅创建者可见，**管理员也不可见**（管理员只能在"待审队列"看到 submitted/reviewing）。
- **published**：所有人可访问 `/play/{slug}`。
- **taken_down**：slug 返回 404，创建者在后台可见历史记录。

> 这条对应你提的"不发布的仅个人可见，即使管理员也不可见；发布后管理员统一管理"。

### 审批操作
- 创建者：submit / 修改后重新 submit。
- 管理员：在审批工作台看待审队列 → approve / reject（必填理由）/ take_down。
- 所有审批操作落审计日志（谁、何时、动作、理由）。

### 下架
- 管理员下架已发布游戏，slug 立即不可访问。
- 下架带理由，创建者收到通知。
- 可重新提交发布走审批。

## 通知

- 审批结果、下架、配额告警通过站内消息 + 邮件通知创建者。
- 邮件走异步队列（IO 密集，禁止同步阻塞）。

## 与生成的关系

- 生成完成 → 草稿（draft）态，创建者可试玩、迭代。
- 创建者满意后 → submit → 走审批。
- 发布后若要大改 → 新版本生成 → 重新 submit → 审批通过后 slug 切到新版本。
