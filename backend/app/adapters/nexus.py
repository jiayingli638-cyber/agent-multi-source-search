"""Nexus 适配器：国外学术 / 跨库文献与知识检索。

说明：题目要求「接入 Nexus 提供的 API」。Nexus 在学界最常见的同名实体是
Crossref 的元数据检索服务（api.crossref.org），因此默认对接 Crossref：

- 无需 Key，配置 NEXUS_MAILTO 可进入 polite pool，速率与稳定性更好。
- 若你采购的是自建 / 商业版 Nexus 端点，只需改 .env 中
  NEXUS_API_URL 与 NEXUS_API_KEY，本适配器会自动带上 Bearer 认证与
  常见响应字段的兼容映射，无需改代码。
"""
from __future__ import annotations

from ..core.config import settings
from ..core.http_client import fetch_json
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)


class NexusAdapter(SourceAdapter):
    name = "nexus"
    kind = SourceKind.ACADEMIC
    platform = "Nexus（学术/文献）"
    description = "国外学术与文献元数据检索，默认对接 Crossref，可指向自建 Nexus 端点"

    def available(self) -> bool:
        return True  # Crossref 公共端点无需凭证

    def unavailable_reason(self) -> str:
        return "Nexus 端点不可用"

    @property
    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if settings.nexus_api_key:
            h["Authorization"] = f"Bearer {settings.nexus_api_key}"
        return h

    async def _search(self, query: str, limit: int) -> list[Doc]:
        params: dict[str, object] = {"query": query, "rows": min(limit, 20)}
        if settings.nexus_mailto:
            params["mailto"] = settings.nexus_mailto

        data = await fetch_json(settings.nexus_api_url, params=params, headers=self._headers)
        items = self._extract_items(data)

        docs: list[Doc] = []
        for idx, item in enumerate(items[:limit]):
            docs.append(
                Doc(
                    title=self._first_str(item, "title", "name", "display_name"),
                    url=self._first_str(item, "URL", "url", "link", "doi_url"),
                    snippet=self._make_snippet(item),
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    author=self._authors(item),
                    published_at=self._year(item),
                    engine_rank=idx + 1,
                    score=max(0.3, 1.0 - idx * 0.07),
                    extras={
                        "doi": item.get("DOI") or item.get("doi", ""),
                        "publisher": item.get("publisher", ""),
                        "type": item.get("type", ""),
                        "cited_by": item.get("is-referenced-by-count", 0),
                    },
                )
            )
        return docs

    # ---------- 兼容多种响应结构 ----------
    @staticmethod
    def _extract_items(data: object) -> list[dict]:
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
        if isinstance(data, dict):
            msg = data.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("items"), list):
                return [d for d in msg["items"] if isinstance(d, dict)]
            for key in ("items", "results", "data", "hits", "docs", "records"):
                value = data.get(key)
                if isinstance(value, list):
                    return [d for d in value if isinstance(d, dict)]
                if isinstance(value, dict) and isinstance(value.get("hits"), list):
                    return [d for d in value["hits"] if isinstance(d, dict)]
        return []

    @staticmethod
    def _first_str(item: dict, *keys: str) -> str:
        for key in keys:
            raw = item.get(key)
            if isinstance(raw, list) and raw:
                raw = raw[0]
            if isinstance(raw, dict):
                raw = raw.get("value") or raw.get("name")
            if isinstance(raw, str) and raw.strip():
                return raw.strip()
        return ""

    def _make_snippet(self, item: dict) -> str:
        abstract = item.get("abstract") or item.get("description") or item.get("summary") or ""
        if abstract:
            return self._strip_tags(str(abstract))[:400]
        container = self._first_str(item, "container-title", "journal", "venue")
        publisher = self._first_str(item, "publisher", "source")
        return f"{container or publisher}".strip(" ·")

    @staticmethod
    def _strip_tags(text: str) -> str:
        import re

        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text)).strip()

    def _authors(self, item: dict) -> str:
        authors = item.get("author") or item.get("authors") or []
        if isinstance(authors, list) and authors:
            names = []
            for a in authors[:3]:
                if isinstance(a, dict):
                    names.append(f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", ""))
                elif isinstance(a, str):
                    names.append(a)
            joined = ", ".join(n for n in names if n)
            return f"{joined} 等" if len(authors) > 3 else joined
        return ""

    def _year(self, item: dict) -> str:
        for key in ("published-print", "published-online", "published", "issued", "date"):
            raw = item.get(key)
            if isinstance(raw, dict) and isinstance(raw.get("date-parts"), list):
                parts = raw["date-parts"][0]
                if parts:
                    return str(parts[0])
            if isinstance(raw, str) and raw[:4].isdigit():
                return raw[:4]
        return ""
