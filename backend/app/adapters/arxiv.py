"""arXiv 适配器：预印本学术检索（Nexus 的补充）。"""
from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from ..core.config import settings
from ..core.http_client import fetch_text
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)

_ATOM = "{http://www.w3.org/2005/Atom}"


class ArxivAdapter(SourceAdapter):
    name = "arxiv"
    kind = SourceKind.ACADEMIC
    platform = "arXiv"
    description = "计算机/AI 领域预印本论文检索"

    def available(self) -> bool:
        return settings.arxiv_enabled

    def unavailable_reason(self) -> str:
        return "已通过 ARXIV_ENABLED=false 关闭"

    async def _search(self, query: str, limit: int) -> list[Doc]:
        xml = await fetch_text(
            settings.arxiv_api_url,
            params={
                "search_query": f"all:{query}",
                "start": 0,
                "max_results": min(limit, 20),
                "sortBy": "relevance",
                "sortOrder": "descending",
            },
        )
        root = ET.fromstring(xml)
        docs: list[Doc] = []
        for idx, entry in enumerate(root.findall(f"{_ATOM}entry")[:limit]):
            title = self._txt(entry, "title")
            summary = self._txt(entry, "summary")
            link = ""
            for l in entry.findall(f"{_ATOM}link"):
                if l.get("rel") == "alternate" or l.get("type") == "text/html":
                    link = l.get("href", "")
                    break
            authors = [self._txt(a, "name") for a in entry.findall(f"{_ATOM}author")]
            docs.append(
                Doc(
                    title=re.sub(r"\s+", " ", title).strip(),
                    url=link or f"https://arxiv.org/abs/{self._txt(entry, 'id').rsplit('/', 1)[-1]}",
                    snippet=re.sub(r"\s+", " ", summary).strip()[:400],
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    author=", ".join(a for a in authors[:3] if a),
                    published_at=self._txt(entry, "published")[:10],
                    engine_rank=idx + 1,
                    score=max(0.3, 1.0 - idx * 0.07),
                    extras={"type": "preprint"},
                )
            )
        return docs

    @staticmethod
    def _txt(node, tag: str) -> str:
        el = node.find(f"{_ATOM}{tag}")
        return el.text if el is not None and el.text else ""
