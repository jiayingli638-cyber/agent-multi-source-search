"""通用网页正文抓取适配器。

当搜索结果只提供摘要时，用它对高价值 URL 做二次正文抓取，
为最终答案提供更完整的证据。
"""
from __future__ import annotations

from ..core.http_client import extract_main_content
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)


class WebFetchAdapter(SourceAdapter):
    name = "web_fetch"
    kind = SourceKind.WEB
    platform = "网页正文"
    description = "对指定 URL 抓取正文，用于补充搜索结果摘要"

    def available(self) -> bool:
        return True

    async def _search(self, query: str, limit: int) -> list[Doc]:
        # query 在此处为「URL，可换行分隔多个」
        urls = [u.strip() for u in query.split() if u.strip().startswith("http")]
        docs: list[Doc] = []
        for idx, url in enumerate(urls[:limit]):
            content = await extract_main_content(url)
            if not content:
                continue
            docs.append(
                Doc(
                    title=content[:80],
                    url=url,
                    snippet=content[:300],
                    content=content,
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    engine_rank=idx + 1,
                    score=0.5,
                )
            )
        return docs
