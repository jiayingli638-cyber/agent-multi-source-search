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
    description = "对指定 URL 抓取正文（仅接受 URL，不参与检索调度）"

    # 该源语义是「按 URL 抓正文」，query 必须是 http(s) URL，而非自然语言检索词。
    # 若交给路由 LLM 调度，LLM 会给它一个检索式，_search 里过滤后为空 → 0 命中 1ms。
    # 因此禁止其被规划器直接选中，仅保留作为 URL 抓取能力。
    selectable_by_llm = False

    def available(self) -> bool:
        return True

    async def _search(self, query: str, limit: int) -> list[Doc]:
        # query 在此处为「URL，可换行分隔多个」
        urls = [u.strip() for u in query.split() if u.strip().startswith("http")]
        if not urls:
            log.warning(
                "[web_fetch] 未收到任何 URL（query=%r），跳过正文抓取。"
                "该源仅接受 http(s) URL，不应作为普通检索源被调度。",
                query[:120],
            )
            return []
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
