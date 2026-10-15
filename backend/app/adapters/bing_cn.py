"""Bing 检索适配器。

两条路线：
- 官方 API（Azure Bing Web Search v7）：稳定、推荐。配置 BING_SEARCH_API_KEY 后自动优先使用。
- HTML 抓取（cn.bing.com）：无需 Key。Bing 中国版对频繁请求会返回验证页，
  这里做了限速 + 解析容错，并明确告知是否需要转向官方 API。

说明：若官方 API 与 HTML 都不可用，按用户要求应在 Bing 官网申请官方 API。
本项目已在 README 中给出申请路径。
"""
from __future__ import annotations

import asyncio
import re
import time
from urllib.parse import quote_plus, urlparse, parse_qs

from bs4 import BeautifulSoup

from ..core.config import settings
from ..core.http_client import fetch_json, fetch_text
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)

# 简单的进程内限速，避免触发 Bing 反爬
_last_request_at = 0.0
_rate_lock = asyncio.Lock()
_MIN_INTERVAL = 1.2


async def _rate_limit() -> None:
    global _last_request_at
    async with _rate_lock:
        now = time.monotonic()
        wait = _MIN_INTERVAL - (now - _last_request_at)
        if wait > 0:
            await asyncio.sleep(wait)
        _last_request_at = time.monotonic()


_DECORATE_RE = re.compile(r"\s*[-–—|]\s*(百度|Bing|必应)\s*$", re.I)


class BingCNAdapter(SourceAdapter):
    name = "bing_cn"
    kind = SourceKind.GENERAL_CN
    platform = "Bing (中国版)"
    description = "国内通用搜索引擎；优先走官方 API，缺失时降级 HTML 抓取"

    def available(self) -> bool:
        return bool(settings.bing_search_api_key) or settings.bing_html_enabled

    def unavailable_reason(self) -> str:
        return "未配置 BING_SEARCH_API_KEY 且已关闭 HTML 抓取"

    @property
    def using_official_api(self) -> bool:
        return bool(settings.bing_search_api_key)

    async def _search(self, query: str, limit: int) -> list[Doc]:
        if self.using_official_api:
            try:
                return await self._search_api(query, limit)
            except Exception as exc:  # noqa: BLE001
                log.warning("Bing 官方 API 失败，回退 HTML：%s", exc)
                if not settings.bing_html_enabled:
                    raise
        return await self._search_html(query, limit)

    # ---------- 官方 API ----------
    async def _search_api(self, query: str, limit: int) -> list[Doc]:
        data = await fetch_json(
            settings.bing_search_endpoint,
            params={
                "q": query,
                "count": min(limit, 20),
                "mkt": "zh-CN",
                "setLang": "zh-hans",
                "responseFilter": "Webpages",
                "textDecorations": False,
            },
            headers={"Ocp-Apim-Subscription-Key": settings.bing_search_api_key},
        )
        docs: list[Doc] = []
        for idx, item in enumerate(data.get("webPages", {}).get("value", [])[:limit]):
            docs.append(
                Doc(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    engine_rank=idx + 1,
                    score=max(0.2, 1.0 - idx * 0.08),
                    extras={"provider": "bing_v7", "date": item.get("dateLastCrawled", "")},
                )
            )
        return docs

    # ---------- HTML 抓取 ----------
    async def _search_html(self, query: str, limit: int) -> list[Doc]:
        await _rate_limit()
        url = f"https://cn.bing.com/search?q={quote_plus(query)}&count={min(limit, 20)}&mkt=zh-CN"
        html = await fetch_text(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "Referer": "https://cn.bing.com/",
            },
        )

        if "验证" in html[:3000] or "captcha" in html[:3000].lower():
            raise RuntimeError("Bing 触发人机验证，请配置官方 API Key（BING_SEARCH_API_KEY）")

        soup = BeautifulSoup(html, "lxml")
        docs: list[Doc] = []
        for li in soup.select("li.b_algo"):
            a = li.select_one("h2 a")
            if not a or not a.get("href"):
                continue
            href = self._clean_url(a["href"])
            snippet_el = li.select_one(".b_caption p") or li.select_one("p")
            title = _DECORATE_RE.sub("", a.get_text(" ", strip=True))
            docs.append(
                Doc(
                    title=title,
                    url=href,
                    snippet=snippet_el.get_text(" ", strip=True) if snippet_el else "",
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    engine_rank=len(docs) + 1,
                    score=max(0.2, 1.0 - len(docs) * 0.08),
                    extras={"provider": "bing_html"},
                )
            )
            if len(docs) >= limit:
                break
        return docs

    @staticmethod
    def _clean_url(url: str) -> str:
        """Bing 结果常带 /ck/a?...&u=a1<base64> 跳转，尝试还原真实地址。"""
        if "bing.com/ck/a" not in url:
            return url
        try:
            qs = parse_qs(urlparse(url).query)
            raw = qs.get("u", [""])[0]
            if raw.startswith("a1"):
                import base64

                padded = raw[2:] + "=" * (-len(raw[2:]) % 4)
                return base64.urlsafe_b64decode(padded).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            pass
        return url
