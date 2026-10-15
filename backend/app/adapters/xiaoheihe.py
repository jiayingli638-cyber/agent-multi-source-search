"""小黑盒（xiaoheihe.cn）适配器。

小黑盒是面向游戏玩家的社区平台（攻略 / 评测 / 资讯 / 热议）。
接口 `api.xiaoheihe.cn` 有双重门槛：

1. **签名**：必须携带 `hkey` / `_time` / `nonce` 三个参数
   （算法见 core/xhh_signing.py，已与网页端参考实现逐位对齐验证）。
2. **登录态**：服务端对匿名请求返回「非法请求」，需要有效会话 Cookie。

因此本适配器提供两种模式（用 XIAOHEIHE_MODE 切换）：

- **browser**（默认，推荐）：用 Playwright 打开小黑盒页面，在页面上下文里
  直接 `fetch()` 接口。好处是浏览器自动带上真实 Cookie、真实 UA、真实
  TLS 指纹与页面已捕获的环境参数，一次性绕过上述两个门槛。
  首次运行会弹出扫码登录，登录态持久化在 XIAOHEIHE_USER_DATA_DIR。

- **api**（轻量）：直接用 httpx 调接口，需要手工在 XIAOHEIHE_COOKIE 里
  粘贴网页版 Cookie。适合已登录且只想要极低开销的场景。

两种模式共用同一套签名与解析逻辑；任一失败都返回明确的降级提示，
不阻塞其他源。
"""
from __future__ import annotations

import asyncio
import json
import urllib.parse
from pathlib import Path
from typing import Any

from ..core.config import settings
from ..core.http_client import fetch_json
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from ..core.xhh_signing import base_api_params, create_signed_params
from .base import SourceAdapter

log = get_logger(__name__)

API_ORIGIN = "https://api.xiaoheihe.cn"
WEB_ORIGIN = "https://www.xiaoheihe.cn"

PATH_SEARCH_WELCOME = "/bbs/app/api/search/welcome_page/v2"
PATH_FEEDS = "/bbs/app/feeds"
PATH_LINK_TREE = "/bbs/app/link/tree"

# 浏览器模式的默认 UA（与 Playwright 启动时保持一致的现代 Chrome）
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class XiaoHeiHeAdapter(SourceAdapter):
    """小黑盒社区内容检索。"""

    name = "xiaoheihe"
    kind = SourceKind.SOCIAL_CN
    platform = "小黑盒"
    requires_credentials = False  # browser 模式可交互登录，api 模式才需 Cookie
    description = "小黑盒游戏社区（攻略/评测/资讯/热议）"

    def __init__(self) -> None:
        self._browser_lock = asyncio.Lock()

    # ---------- 可用性 ----------
    def available(self) -> bool:
        return settings.xiaoheihe_enabled

    def unavailable_reason(self) -> str:
        return "小黑盒源已关闭（XIAOHEIHE_ENABLED=false）"

    @property
    def mode(self) -> str:
        return (settings.xiaoheihe_mode or "browser").strip().lower()

    # ---------- 检索入口 ----------
    async def _search(self, query: str, limit: int) -> list[Doc]:
        payloads: list[dict[str, Any]] = []

        if self.mode == "api" and settings.xiaoheihe_cookie.strip():
            payloads = await self._fetch_via_api()
        else:
            payloads = await self._fetch_via_browser()

        docs: list[Doc] = []
        seen: set[str] = set()
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            docs.extend(self._from_hot_search(payload, query, seen))
            docs.extend(self._from_feeds(payload, query, seen))

        # 兜底：站内搜索入口
        if not docs:
            docs.append(self._search_entry(query, reason=self._degrade_hint()))
        return docs[:limit]

    def _degrade_hint(self) -> str:
        if self.mode == "browser":
            return "浏览器模式未获取到内容（可能未完成登录或页面结构变化）"
        return "未配置 XIAOHEIHE_COOKIE，接口鉴权失败"

    # ---------- 通道 A：Playwright 浏览器桥接 ----------
    async def _fetch_via_browser(self) -> list[dict[str, Any]]:
        """在真实浏览器里请求接口，自动携带 Cookie 与真实环境。"""
        async with self._browser_lock:  # 浏览器较贵，串行执行
            try:
                return await asyncio.wait_for(
                    self._browser_worker(), timeout=settings.xiaoheihe_timeout
                )
            except asyncio.TimeoutError:
                log.warning("[xiaoheihe] 浏览器模式超时")
                return []
            except Exception as exc:  # noqa: BLE001
                log.warning("[xiaoheihe] 浏览器模式失败: %s", exc)
                return []

    async def _browser_worker(self) -> list[dict[str, Any]]:
        from playwright.async_api import async_playwright  # 延迟导入，未装不影响其它源

        user_data = Path(settings.xiaoheihe_user_data_dir).expanduser()
        user_data.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data),
                headless=settings.xiaoheihe_headless,
                user_agent=BROWSER_UA,
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            try:
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                await page.goto(
                    f"{WEB_ORIGIN}/app/bbs",
                    wait_until="domcontentloaded",
                    timeout=int(settings.xiaoheihe_timeout * 1000),
                )
                # 给页面脚本留出加载与注入环境参数的时间
                await page.wait_for_timeout(2000)

                results: list[dict[str, Any]] = []
                for path, extra in (
                    (PATH_SEARCH_WELCOME, None),
                    (PATH_FEEDS, {"offset": 0, "limit": 40}),
                ):
                    url = self._build_url(path, extra)
                    try:
                        payload = await page.evaluate(
                            """async (u) => {
                                const r = await fetch(u, {credentials: 'include',
                                    headers: {'accept': 'application/json, text/plain, */*'}});
                                const t = await r.text();
                                try { return JSON.parse(t); } catch { return {status:'failed', msg:t.slice(0,200)}; }
                            }""",
                            url,
                        )
                        results.append(payload)
                    except Exception as exc:  # noqa: BLE001
                        log.debug("[xiaoheihe] 页面内请求失败 %s: %s", path, exc)
                return results
            finally:
                await ctx.close()

    # ---------- 通道 B：httpx 直连 ----------
    async def _fetch_via_api(self) -> list[dict[str, Any]]:
        headers = self._headers()
        results: list[dict[str, Any]] = []
        for path, extra in (
            (PATH_SEARCH_WELCOME, None),
            (PATH_FEEDS, {"offset": 0, "limit": 40}),
        ):
            try:
                results.append(
                    await fetch_json(self._build_url(path, extra), headers=headers)
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("[xiaoheihe] API 请求失败 %s: %s", path, exc)
        return results

    # ---------- 请求构造 ----------
    def _build_url(self, path: str, extra: dict[str, Any] | None = None) -> str:
        params: dict[str, Any] = {**base_api_params(), **create_signed_params(path)}
        if extra:
            params.update(extra)
        return f"{API_ORIGIN}{path}?{urllib.parse.urlencode(params)}"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{WEB_ORIGIN}/",
            "Origin": WEB_ORIGIN,
            "User-Agent": BROWSER_UA,
        }
        cookie = settings.xiaoheihe_cookie.strip()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    # ---------- 解析：热搜榜 ----------
    def _from_hot_search(self, payload: dict, query: str, seen: set[str]) -> list[Doc]:
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return []

        ranks = payload.get("result", {}).get("Lists") or []
        tokens = self._tokens(query)
        docs: list[Doc] = []

        for rank in ranks:
            if not isinstance(rank, dict):
                continue
            rank_name = str(rank.get("head_text") or "榜单")
            for idx, item in enumerate(rank.get("items") or []):
                if not isinstance(item, dict):
                    continue
                title = str(item.get("text") or "").strip()
                desc = str(item.get("desc") or "").strip()
                if not title or not self._matches(f"{title} {desc}", tokens):
                    continue
                url = f"{WEB_ORIGIN}/app/search?q={urllib.parse.quote(title)}"
                if url in seen:
                    continue
                seen.add(url)
                docs.append(
                    Doc(
                        title=title[:160],
                        url=url,
                        snippet=desc[:300] or f"小黑盒 {rank_name}热榜",
                        content=f"{title} {desc}"[:1000],
                        source=self.name,
                        source_kind=self.kind,
                        platform=self.platform,
                        engine_rank=idx + 1,
                        score=max(0.35, 0.95 - idx * 0.03),
                        extras={
                            "rank": rank_name,
                            "hot_value": item.get("hot_value"),
                            "kind": "hot_search",
                        },
                    )
                )
        return docs

    # ---------- 解析：社区信息流 ----------
    def _from_feeds(self, payload: dict, query: str, seen: set[str]) -> list[Doc]:
        if not isinstance(payload, dict) or payload.get("status") != "ok":
            return []

        links = payload.get("result", {}).get("links") or []
        tokens = self._tokens(query)
        docs: list[Doc] = []

        for idx, link in enumerate(links):
            if not isinstance(link, dict):
                continue
            link_id = str(link.get("linkid") or link.get("link_id") or "")
            title = str(link.get("title") or "").strip()
            desc = str(link.get("description") or link.get("text") or "").strip()
            if not (title or desc) or not self._matches(f"{title} {desc}", tokens):
                continue

            url = (
                f"{WEB_ORIGIN}/app/bbs/link/{link_id}"
                if link_id
                else f"{WEB_ORIGIN}/app/search?q={urllib.parse.quote(query)}"
            )
            if url in seen:
                continue
            seen.add(url)

            user = link.get("user") or link.get("user_a") or {}
            docs.append(
                Doc(
                    title=(title or desc)[:160],
                    url=url,
                    snippet=desc[:300],
                    content=desc[:2000],
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    author=str(user.get("username") or user.get("nickname") or ""),
                    published_at=str(link.get("create_at") or link.get("timestamp") or "")[:19],
                    engine_rank=idx + 1,
                    score=max(0.3, 0.9 - idx * 0.03),
                    extras={
                        "link_id": link_id,
                        "comments": link.get("comment_num") or link.get("comment_count") or 0,
                        "likes": link.get("link_award_num") or link.get("like_num") or 0,
                        "kind": "feed",
                    },
                )
            )
        return docs

    # ---------- 兜底入口 ----------
    def _search_entry(self, query: str, reason: str = "") -> Doc:
        url = f"{WEB_ORIGIN}/app/search?q={urllib.parse.quote(query)}"
        note = "小黑盒未开放公开的关键词检索接口" if not reason else reason
        return Doc(
            title=f"在小黑盒搜索「{query}」",
            url=url,
            snippet=f"小黑盒站内搜索入口。{note}，此处提供可直接跳转的社区搜索页。",
            content="",
            source=self.name,
            source_kind=self.kind,
            platform=self.platform,
            engine_rank=99,
            score=0.2,
            extras={"kind": "search_entry", "degraded_reason": reason},
        )

    # ---------- 关键词匹配 ----------
    @staticmethod
    def _tokens(query: str) -> list[str]:
        stop = {"的", "了", "是", "在", "和", "与", "怎么", "如何", "什么", "为什么", "吗", "呢"}
        raw = query
        for ch in "？?，,。.！!、；;：:":
            raw = raw.replace(ch, " ")
        tokens = [t.strip().lower() for t in raw.split() if len(t.strip()) >= 2 and t.strip() not in stop]
        return tokens or [query.strip().lower()]

    @staticmethod
    def _matches(text: str, tokens: list[str]) -> bool:
        lowered = text.lower()
        return any(tok in lowered for tok in tokens if tok)
