"""Google 搜索适配器。

人机验证（验证码）问题的工程解法：
直接抓 google.com 会立刻触发 reCAPTCHA，且随 IP 归属、请求频率迅速恶化。
生产可用路线是走搜索 API 中转服务，由服务商承担 IP 池与验证码绕过：

- Serper (https://serper.dev)：便宜、响应快，返回结构化 JSON。
- SerpAPI (https://serpapi.com)：老牌，稳定性好，支持多地区。

本适配器统一封装上述两家；两者都未配置时降级为 mock，
并在结果中显式标注 degraded_reason，提示去申请 API。
"""
from __future__ import annotations

from ..core.config import settings
from ..core.http_client import fetch_json
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)


class GoogleWebAdapter(SourceAdapter):
    name = "google_web"
    kind = SourceKind.GENERAL_GLOBAL
    platform = "Google 搜索"
    requires_credentials = True
    description = "国外通用搜索；经 Serper / SerpAPI 中转，规避直接抓取的人机验证"

    @property
    def provider(self) -> str:
        p = (settings.google_search_provider or "").lower()
        if p == "serper" and settings.serper_api_key:
            return "serper"
        if p == "serpapi" and settings.serpapi_api_key:
            return "serpapi"
        # 显式配置的 provider 缺失时，自动回退到另一家可用的
        if settings.serper_api_key:
            return "serper"
        if settings.serpapi_api_key:
            return "serpapi"
        return ""

    def available(self) -> bool:
        return bool(self.provider)

    def unavailable_reason(self) -> str:
        return "未配置 SERPER_API_KEY / SERPAPI_API_KEY（Google 直抓会被验证码拦截）"

    async def _search(self, query: str, limit: int) -> list[Doc]:
        if self.provider == "serper":
            return await self._search_serper(query, limit)
        return await self._search_serpapi(query, limit)

    # ---------- Serper ----------
    async def _search_serper(self, query: str, limit: int) -> list[Doc]:
        data = await fetch_json(
            "https://google.serper.dev/search",
            method="POST",
            json_body={"q": query, "num": max(limit, 10), "gl": "us", "hl": "en"},
            headers={"X-API-KEY": settings.serper_api_key, "Content-Type": "application/json"},
        )
        docs: list[Doc] = []
        for idx, item in enumerate(data.get("organic", [])[:limit]):
            docs.append(
                Doc(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    engine_rank=idx + 1,
                    score=max(0.2, 1.0 - idx * 0.08),
                    extras={"provider": "serper", "position": item.get("position", idx + 1)},
                )
            )
        return docs

    # ---------- SerpAPI ----------
    async def _search_serpapi(self, query: str, limit: int) -> list[Doc]:
        data = await fetch_json(
            "https://serpapi.com/search.json",
            params={
                "q": query,
                "num": max(limit, 10),
                "hl": "en",
                "gl": "us",
                "api_key": settings.serpapi_api_key,
            },
        )
        docs: list[Doc] = []
        for idx, item in enumerate(data.get("organic_results", [])[:limit]):
            docs.append(
                Doc(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    engine_rank=idx + 1,
                    score=max(0.2, 1.0 - idx * 0.08),
                    extras={"provider": "serpapi", "position": item.get("position", idx + 1)},
                )
            )
        return docs
