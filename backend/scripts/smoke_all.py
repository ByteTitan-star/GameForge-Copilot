"""一键接口冒烟：对运行中的后端逐个发 HTTP 请求，验证接口存活 + 主链路联通。

用法（须先起 API + Worker + Postgres/Redis/RabbitMQ，且 ENV=development）::

    cd backend
    uv run python -m scripts.smoke_all

三层检查：
  - Layer 1 全量存活：对全部 ~75 个端点不带 token 探活（公开→2xx，鉴权→401，admin→401）。
  - Layer 2 主链路：注册→验证邮箱→登录→读 /me→建游戏→建 run（验到 201 后立即 cancel，
    不耗 LLM token）。
  - Layer 3 管理域：提供 SMOKE_ADMIN_TOKEN 时合法调用 admin 只读端点。

可选环境变量：
  SMOKE_API            后端根地址，默认 http://127.0.0.1:8000
  SMOKE_ADMIN_TOKEN    管理员 Bearer，提供则合法调用 admin 域
  SMOKE_LLM_APIKEY     真实 LLM key + SMOKE_LLM_MODEL，提供则真创建配置（否则用假 key 验证「拒绝」）
  SMOKE_LLM_MODEL      配置用模型名，默认 claude-sonnet-5-20250929
  SMOKE_LLM_PROVIDER   配置用 provider，默认 anthropic
  SMOKE_VERIFY_CODE    手动指定邮箱验证码（跳过 dev 自动获取）
  SMOKE_NO_LAYER2=1    跳过注册/生成等写操作，只跑只读探活

注意：
  - 生成类接口验到 201 后立即 cancel；若 Worker 在取消前消费，forge 节点前的 _check_ctrl 会拦截，
    正常不会消耗 LLM token。为彻底零消耗，可临时停 Worker 或用无效 key。
  - 破坏性 dev 接口（queue/purge、redis/flush）默认跳过，需手动验证。
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import sys
import time
from dataclasses import dataclass, field

import httpx

API = os.getenv("SMOKE_API", "http://127.0.0.1:8000").rstrip("/")
ADMIN_TOKEN = os.getenv("SMOKE_ADMIN_TOKEN", "").strip()
LLM_APIKEY = os.getenv("SMOKE_LLM_APIKEY", "").strip()
LLM_MODEL = os.getenv("SMOKE_LLM_MODEL", "claude-sonnet-5-20250929")
LLM_PROVIDER = os.getenv("SMOKE_LLM_PROVIDER", "anthropic")
VERIFY_CODE = os.getenv("SMOKE_VERIFY_CODE", "").strip()
RUN_LAYER2 = os.getenv("SMOKE_NO_LAYER2", "") != "1"
TIMEOUT = 15.0
BOGUS_UUID = "00000000-0000-0000-0000-000000000000"
OFFICIAL_SLUG = "official-neon-snake"
_MISSING = object()

# Layer 1 探活期望：按 kind 映射可接受状态码（命中即 PASS，5xx/网络错 FAIL，其余 WARN）
EXPECT_BY_KIND: dict[str, set[int]] = {
    "public_get": {200, 304, 400, 404},
    "public_post": {400, 422},  # 不带 body → 422 也算路由存活
    "dev_safe": {200},
    "dev_requeue": {404, 422},  # 假 run_id → 404/422
    "auth": {401, 403, 422},  # 不带 token / 缺 body
    "admin": {401, 403, 422},
}

# (group, method, path, kind) —— path 模板中的 {param} 由 fill() 填充
LAYER1: list[tuple[str, str, str, str]] = [
    # 基础设施 / 托管（公开）
    ("infra", "GET", "/healthz", "public_get"),
    ("infra", "GET", "/ready", "public_get"),
    ("infra", "GET", "/play/{slug}", "public_get"),
    ("infra", "GET", "/draft/{game_id}/{version}", "public_get"),
    # 公开端点
    ("public", "GET", "/api/v1/official-games", "public_get"),
    ("public", "GET", "/api/v1/games/public", "public_get"),
    ("public", "GET", "/api/v1/games/featured", "public_get"),
    ("public", "GET", "/api/v1/games/public/{slug}", "public_get"),
    ("public", "GET", "/api/v1/templates", "public_get"),
    ("public", "GET", "/api/v1/u/{handle}", "public_get"),
    ("public", "POST", "/api/v1/auth/register", "public_post"),
    ("public", "POST", "/api/v1/auth/login", "public_post"),
    ("public", "POST", "/api/v1/auth/refresh", "public_post"),
    ("public", "POST", "/api/v1/auth/verify-email", "public_post"),
    ("public", "POST", "/api/v1/auth/resend-verification", "public_post"),
    ("public", "POST", "/api/v1/auth/password/reset", "public_post"),
    ("public", "POST", "/api/v1/auth/password/reset/confirm", "public_post"),
    ("public", "GET", "/api/v1/auth/oauth/{provider}/start", "public_get"),
    ("public", "GET", "/api/v1/auth/oauth/{provider}/callback", "public_get"),
    # dev 调试（仅 development）
    ("dev", "GET", "/api/v1/dev/verification-code", "dev_safe"),
    ("dev", "GET", "/api/v1/dev/runtime/status", "dev_safe"),
    ("dev", "GET", "/api/v1/dev/queue/stats", "dev_safe"),
    ("dev", "POST", "/api/v1/dev/queue/purge", "dev_destruct"),
    ("dev", "POST", "/api/v1/dev/redis/flush", "dev_destruct"),
    ("dev", "POST", "/api/v1/dev/runs/{run_id}/requeue", "dev_requeue"),
    # 需登录（user）
    ("auth", "POST", "/api/v1/auth/logout", "auth"),
    ("auth", "POST", "/api/v1/auth/password/change", "auth"),
    ("auth", "GET", "/api/v1/me/favorites", "auth"),
    ("auth", "GET", "/api/v1/me/llm-configs", "auth"),
    ("auth", "POST", "/api/v1/me/llm-configs", "auth"),
    ("auth", "GET", "/api/v1/me/llm-configs/models", "auth"),
    ("auth", "POST", "/api/v1/me/llm-configs/test", "auth"),
    ("auth", "PATCH", "/api/v1/me/llm-configs/{config_id}", "auth"),
    ("auth", "DELETE", "/api/v1/me/llm-configs/{config_id}", "auth"),
    ("auth", "POST", "/api/v1/me/llm-configs/{config_id}/test", "auth"),
    ("auth", "GET", "/api/v1/me/notifications", "auth"),
    ("auth", "POST", "/api/v1/me/notifications/{notification_id}/read", "auth"),
    ("auth", "GET", "/api/v1/me/profile", "auth"),
    ("auth", "PATCH", "/api/v1/me/profile", "auth"),
    ("auth", "GET", "/api/v1/me/runs/active", "auth"),
    ("auth", "GET", "/api/v1/me/usage", "auth"),
    ("auth", "GET", "/api/v1/me/usage/breakdown", "auth"),
    ("auth", "POST", "/api/v1/games", "auth"),
    ("auth", "GET", "/api/v1/games", "auth"),
    ("auth", "POST", "/api/v1/games/fork/{slug}", "auth"),
    ("auth", "PATCH", "/api/v1/games/{game_id}", "auth"),
    ("auth", "GET", "/api/v1/games/{game_id}", "auth"),
    ("auth", "DELETE", "/api/v1/games/{game_id}", "auth"),
    ("auth", "GET", "/api/v1/games/{game_id}/analytics", "auth"),
    ("auth", "POST", "/api/v1/games/{game_id}/favorite", "auth"),
    ("auth", "POST", "/api/v1/games/{game_id}/like", "auth"),
    ("auth", "POST", "/api/v1/games/{game_id}/runs", "auth"),
    ("auth", "GET", "/api/v1/games/{game_id}/runs", "auth"),
    ("auth", "POST", "/api/v1/games/{game_id}/runs/{run_id}/hitl/resolve", "auth"),
    ("auth", "GET", "/api/v1/games/{game_id}/usage", "auth"),
    ("auth", "GET", "/api/v1/games/{game_id}/versions", "auth"),
    ("auth", "POST", "/api/v1/games/{game_id}/versions/{version}/activate", "auth"),
    ("auth", "POST", "/api/v1/games/{game_id}/publish/submit", "auth"),
    ("auth", "GET", "/api/v1/runs/{run_id}", "auth"),
    ("auth", "POST", "/api/v1/runs/{run_id}/cancel", "auth"),
    ("auth", "GET", "/api/v1/runs/{run_id}/events", "auth"),
    ("auth", "POST", "/api/v1/runs/{run_id}/pause", "auth"),
    ("auth", "POST", "/api/v1/runs/{run_id}/resume", "auth"),
    ("auth", "POST", "/api/v1/runs/{run_id}/retry", "auth"),
    # 需管理员
    ("admin", "GET", "/api/v1/admin/analytics/top", "admin"),
    ("admin", "GET", "/api/v1/admin/audit-logs", "admin"),
    ("admin", "GET", "/api/v1/admin/games", "admin"),
    ("admin", "PATCH", "/api/v1/admin/games/{game_id}/featured", "admin"),
    ("admin", "PATCH", "/api/v1/admin/games/{game_id}/schedule", "admin"),
    ("admin", "GET", "/api/v1/admin/settings", "admin"),
    ("admin", "PUT", "/api/v1/admin/settings", "admin"),
    ("admin", "GET", "/api/v1/admin/usage", "admin"),
    ("admin", "GET", "/api/v1/admin/users", "admin"),
    ("admin", "PATCH", "/api/v1/admin/users/{user_id}", "admin"),
    ("admin", "DELETE", "/api/v1/admin/users/{user_id}", "admin"),
    ("admin", "GET", "/api/v1/publish/queue", "admin"),
    ("admin", "POST", "/api/v1/publish/{publish_request_id}/approve", "admin"),
    ("admin", "POST", "/api/v1/publish/{publish_request_id}/reject", "admin"),
    ("admin", "POST", "/api/v1/games/{game_id}/take-down", "admin"),
]


@dataclass
class Case:
    group: str
    label: str
    method: str
    path: str
    status: int | None
    verdict: str  # PASS / FAIL / WARN / SKIP
    note: str = ""


@dataclass
class Runner:
    client: httpx.AsyncClient
    cases: list[Case] = field(default_factory=list)

    # ---- 基础工具 ----
    @staticmethod
    def fill(path: str) -> str:
        """把路径模板里的 {param} 填成合法占位值。"""
        return (
            path.replace("{slug}", OFFICIAL_SLUG)
            .replace("{provider}", "github")
            .replace("{game_id}", BOGUS_UUID)
            .replace("{run_id}", BOGUS_UUID)
            .replace("{config_id}", BOGUS_UUID)
            .replace("{publish_request_id}", BOGUS_UUID)
            .replace("{notification_id}", BOGUS_UUID)
            .replace("{user_id}", BOGUS_UUID)
            .replace("{version}", "1")
            .replace("{handle}", "smoke-no-such-user")
        )

    @staticmethod
    def judge(status: int | None, expect: set[int]) -> str:
        if status is None or status >= 500:
            return "FAIL"
        return "PASS" if status in expect else "WARN"

    @staticmethod
    def err_msg(resp: object) -> str:
        if resp is None:
            return "网络错误/超时"
        try:
            j = resp.json()  # type: ignore[attr-defined]
        except Exception:
            text = getattr(resp, "text", "")
            return (text or "")[:120]
        if isinstance(j, dict):
            err = j.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err)[:120]
            return str(j.get("detail") or j)[:120]
        return str(j)[:120]

    async def call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: object = _MISSING,
        params: dict[str, str] | None = None,
    ) -> tuple[int | None, object]:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            resp = await self.client.request(
                method,
                API + self.fill(path),
                headers=headers,
                json=body if body is not _MISSING else None,
                params=params,
                timeout=TIMEOUT,
            )
        except httpx.HTTPError:
            return None, None
        return resp.status_code, resp

    def add(
        self,
        group: str,
        label: str,
        method: str,
        path: str,
        status: int | None,
        verdict: str,
        note: str = "",
    ) -> None:
        self.cases.append(Case(group, label, method, path, status, verdict, note))

    async def step(
        self,
        group: str,
        label: str,
        method: str,
        path: str,
        *,
        expect: set[int],
        token: str | None = None,
        body: object = _MISSING,
        params: dict[str, str] | None = None,
    ) -> tuple[bool, object]:
        """发请求、判定、记录，返回 (是否 PASS, data 字段)。"""
        status, resp = await self.call(method, path, token=token, body=body, params=params)
        verdict = self.judge(status, expect)
        data = None
        if status is not None and 200 <= status < 300 and resp is not None:
            try:
                data = resp.json().get("data")  # type: ignore[attr-defined]
            except Exception:
                data = None
        note = "" if verdict == "PASS" else self.err_msg(resp)
        self.add(group, label, method, path, status, verdict, note)
        return verdict == "PASS", data

    async def fetch_verify_code(self, email: str) -> str:
        """development 下从 Redis 取验证码（或用 SMOKE_VERIFY_CODE）。"""
        if VERIFY_CODE:
            return VERIFY_CODE
        with contextlib.suppress(httpx.HTTPError):
            await self.client.post(
                f"{API}/api/v1/auth/resend-verification",
                json={"email": email},
                timeout=TIMEOUT,
            )
        for _ in range(20):
            try:
                r = await self.client.get(
                    f"{API}/api/v1/dev/verification-code",
                    params={"email": email},
                    timeout=TIMEOUT,
                )
                if r.status_code == 200:
                    data = (r.json() or {}).get("data") or {}
                    if data.get("code"):
                        return str(data["code"])
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.3)
        return ""

    # ---- Layer 0：健康检查 ----
    async def health(self) -> None:
        for path, key in [("/healthz", "存活"), ("/ready", "依赖就绪")]:
            status, resp = await self.call("GET", path)
            detail = ""
            if path == "/ready" and resp is not None:
                with contextlib.suppress(Exception):
                    detail = " · " + ",".join(
                        f"{k}={'ok' if v else 'DOWN'}"
                        for k, v in (resp.json() or {}).items()  # type: ignore[attr-defined]
                    )
            ok = status == 200
            self.add(
                "health",
                f"{key} {path}",
                "GET",
                path,
                status,
                "PASS" if ok else "FAIL",
                "" if ok else self.err_msg(resp) + detail,
            )

    # ---- Layer 1：全量探活（不带 token）----
    async def layer1(self) -> None:
        for group, method, path, kind in LAYER1:
            if kind == "dev_destruct":
                self.add(
                    group,
                    f"{method} {path}",
                    method,
                    path,
                    None,
                    "SKIP",
                    "破坏性操作，默认跳过（手动验证）",
                )
                continue
            expect = EXPECT_BY_KIND[kind]
            status, resp = await self.call(method, path)
            verdict = self.judge(status, expect)
            self.add(
                group,
                f"{method} {path}",
                method,
                path,
                status,
                verdict,
                "" if verdict == "PASS" else self.err_msg(resp),
            )

    # ---- Layer 2：主链路（合法请求）----
    async def layer2(self) -> None:
        email = f"smoke-{int(time.time())}@example.com"
        pw = "password12345"
        token = await self._l2_register_login(email, pw)
        if not token:
            self.add("L2 写流程", "主链路", "-", "-", None, "SKIP", "未拿到 token，后续跳过")
            return
        await self._l2_me_reads(token)
        await self._l2_llm(token)
        await self._l2_games_runs(token, email)

    async def _l2_register_login(self, email: str, pw: str) -> str | None:
        g = "L2 认证"
        await self.step(
            g,
            "注册",
            "POST",
            "/api/v1/auth/register",
            expect={200, 201},
            body={"email": email, "password": pw},
        )
        code = await self.fetch_verify_code(email)
        if code:
            await self.step(
                g,
                "验证邮箱",
                "POST",
                "/api/v1/auth/verify-email",
                expect={200},
                body={"email": email, "code": code},
            )
        else:
            self.add(
                g,
                "验证邮箱",
                "POST",
                "/api/v1/auth/verify-email",
                None,
                "WARN",
                "未取到验证码（确认 ENV=development + Redis 已起）",
            )
        ok, data = await self.step(
            g,
            "登录",
            "POST",
            "/api/v1/auth/login",
            expect={200},
            body={"email": email, "password": pw},
        )
        return (data or {}).get("access_token") if ok else None

    async def _l2_me_reads(self, token: str) -> None:
        g = "L2 只读"
        reads = [
            ("个人资料", "GET", "/api/v1/me/profile", None),
            ("用量", "GET", "/api/v1/me/usage", None),
            ("用量明细", "GET", "/api/v1/me/usage/breakdown", None),
            ("收藏列表", "GET", "/api/v1/me/favorites", None),
            ("通知列表", "GET", "/api/v1/me/notifications", None),
            ("活跃 run", "GET", "/api/v1/me/runs/active", None),
            ("LLM 配置列表", "GET", "/api/v1/me/llm-configs", None),
            ("模型列表", "GET", "/api/v1/me/llm-configs/models", {"provider": "anthropic"}),
        ]
        for label, method, path, params in reads:
            await self.step(g, label, method, path, expect={200}, token=token, params=params)

    async def _l2_llm(self, token: str) -> None:
        g = "L2 写流程"
        # dry 连通测试：假 key → 200 且 tested_ok=false（接口正常工作）
        await self.step(
            g,
            "LLM dry 测试(假key)",
            "POST",
            "/api/v1/me/llm-configs/test",
            expect={200},
            token=token,
            body={"provider": LLM_PROVIDER, "model": LLM_MODEL, "apikey": "sk-smoke-invalid"},
        )
        # 创建配置：有真 key 期望 201，否则期望 400（连通失败=接口正确拒绝）
        expect = {201} if LLM_APIKEY else {400}
        label = "创建 LLM 配置" + ("(真key)" if LLM_APIKEY else "(假key→应拒)")
        await self.step(
            g,
            label,
            "POST",
            "/api/v1/me/llm-configs",
            expect=expect,
            token=token,
            body={
                "provider": LLM_PROVIDER,
                "model": LLM_MODEL,
                "apikey": LLM_APIKEY or "sk-smoke-invalid",
                "is_default": True,
            },
        )

    async def _l2_games_runs(self, token: str, email: str) -> None:
        g = "L2 写流程"
        ts = int(time.time())
        ok, data = await self.step(
            g,
            "创建游戏",
            "POST",
            "/api/v1/games",
            expect={201},
            token=token,
            body={"title": f"smoke-{ts}", "requirement": "smoke requirement"},
        )
        if not ok or not data:
            self.add(g, "游戏相关链路", "-", "-", None, "SKIP", "创建游戏失败，后续跳过")
            return
        game_id = str(data.get("game_id"))
        gbase = f"/api/v1/games/{game_id}"
        await self.step(g, "游戏详情", "GET", gbase, expect={200}, token=token)
        await self.step(g, "版本列表", "GET", f"{gbase}/versions", expect={200}, token=token)
        await self.step(g, "我的游戏列表", "GET", "/api/v1/games", expect={200}, token=token)
        await self.step(g, "点赞", "POST", f"{gbase}/like", expect={200}, token=token)
        await self.step(g, "收藏", "POST", f"{gbase}/favorite", expect={200}, token=token)
        await self._l2_run(token, game_id)
        await self.step(
            g,
            "Fork 官方游戏",
            "POST",
            "/api/v1/games/fork/{slug}",
            expect={200, 201, 404, 409},
            token=token,
        )
        await self.step(
            g,
            "提交发布",
            "POST",
            f"{gbase}/publish/submit",
            expect={200, 201, 409},
            token=token,
            body={"version": 1},
        )

    async def _l2_run(self, token: str, game_id: str) -> None:
        g = "L2 写流程"
        ok, data = await self.step(
            g,
            "创建 run",
            "POST",
            f"/api/v1/games/{game_id}/runs",
            expect={201},
            token=token,
            body={"requirement": "smoke run"},
        )
        if not ok or not data:
            return
        run_id = str(data.get("run_id"))
        rbase = f"/api/v1/runs/{run_id}"
        # 验到 201 后立即 cancel：避免 Worker 真跑 LLM（节点前 _check_ctrl 会拦截）
        await self.step(
            g, "取消 run(防耗token)", "POST", f"{rbase}/cancel", expect={200}, token=token
        )
        await self.step(g, "run 状态", "GET", rbase, expect={200}, token=token)
        await self.step(g, "run 事件", "GET", f"{rbase}/events", expect={200}, token=token)

    # ---- Layer 3：管理域（可选）----
    async def layer3(self) -> None:
        g = "L3 admin"
        if not ADMIN_TOKEN:
            self.add(
                g,
                "admin 域",
                "-",
                "-",
                None,
                "SKIP",
                "未设 SMOKE_ADMIN_TOKEN，admin 端点仅在 Layer1 做了 401 探活",
            )
            return
        for label, path in [
            ("用户列表", "/api/v1/admin/users"),
            ("游戏列表", "/api/v1/admin/games"),
            ("系统用量", "/api/v1/admin/usage"),
            ("全局设置", "/api/v1/admin/settings"),
            ("审计日志", "/api/v1/admin/audit-logs"),
            ("Top 分析", "/api/v1/admin/analytics/top"),
            ("发布队列", "/api/v1/publish/queue"),
        ]:
            await self.step(g, label, "GET", path, expect={200}, token=ADMIN_TOKEN)

    # ---- 报告 ----
    def report(self) -> int:
        groups: dict[str, list[Case]] = {}
        for c in self.cases:
            groups.setdefault(c.group, []).append(c)
        order = list(dict.fromkeys(c.group for c in self.cases))
        counts = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
        for group in order:
            print(f"\n— {group} —")
            for c in groups[group]:
                counts[c.verdict] += 1
                tag = {"PASS": "[ OK ]", "FAIL": "[FAIL]", "WARN": "[WARN]", "SKIP": "[SKIP]"}[
                    c.verdict
                ]
                code = c.status if c.status is not None else "  —"
                line = f"{tag} {str(code):>4}  {c.label}"
                if c.note:
                    line += f"  · {c.note}"
                print(line)
        total = len(self.cases)
        print(
            f"\n合计 {total} 项：✅ {counts['PASS']} 通过 · "
            f"⚠ {counts['WARN']} 告警 · ✗ {counts['FAIL']} 失败 · ⊘ {counts['SKIP']} 跳过"
        )
        return counts["FAIL"]


async def main() -> None:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    print(
        f"GameForge 接口冒烟 → {API}\n（Layer2 写流程：{'开' if RUN_LAYER2 else '关'} · "
        f"admin token：{'已提供' if ADMIN_TOKEN else '未提供'}）"
    )
    async with httpx.AsyncClient() as client:
        runner = Runner(client)
        await runner.health()
        await runner.layer1()
        if RUN_LAYER2:
            await runner.layer2()
        await runner.layer3()
        failed = runner.report()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
