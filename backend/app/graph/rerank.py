"""归并去重与相关性排序。"""
from __future__ import annotations

import math
import re
from collections import defaultdict

from ..core.logging_utils import get_logger
from ..core.models import Doc

log = get_logger(__name__)

_WORD_RE = re.compile(r"[a-zA-Z0-9]+|[\u4e00-\u9fff]")
_STOP = {
    "的", "了", "是", "在", "和", "与", "对", "从", "有", "会", "这", "那", "什么", "如何",
    "怎么", "为什么", "the", "a", "an", "of", "to", "in", "is", "are", "for", "how", "what",
    "why", "and", "or", "on", "with",
}


def tokenize(text: str) -> list[str]:
    """中英混合粗粒度分词（无需 jieba，覆盖面够用）。"""
    tokens = _WORD_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOP and len(t) > 0]


def _bm25_like_score(query_tokens: list[str], doc: Doc, avg_len: float) -> float:
    """简化版 BM25，避免引入额外依赖。"""
    doc_tokens = tokenize(f"{doc.title} {doc.snippet} {doc.content[:1500]}")
    if not doc_tokens:
        return 0.0
    freqs: dict[str, int] = defaultdict(int)
    for t in doc_tokens:
        freqs[t] += 1

    k1, b = 1.5, 0.75
    doc_len = len(doc_tokens)
    score = 0.0
    for qt in set(query_tokens):
        f = freqs.get(qt, 0)
        if f == 0:
            continue
        idf = 1.0 + math.log(1 + 1.0 / (1 + 0.5))
        score += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * doc_len / max(avg_len, 1)))
    return score


def deduplicate(docs: list[Doc]) -> list[Doc]:
    """按 URL/标题归并重复结果，保留信息量更大的一条，并合并来源标记。"""
    grouped: dict[str, Doc] = {}
    for doc in docs:
        key = doc.dedup_key
        if not key:
            continue
        existing = grouped.get(key)
        if existing is None:
            grouped[key] = doc
            continue
        # 保留正文更长 / 摘要更长者作为主体
        keep, drop = (doc, existing) if len(doc.text) > len(existing.text) else (existing, doc)
        merged_sources = set(
            str(keep.extras.get("merged_from", keep.platform or keep.source)).split(",")
        )
        merged_sources.add(drop.platform or drop.source)
        keep.extras["merged_from"] = ",".join(sorted(s for s in merged_sources if s))
        keep.extras["duplicate_count"] = int(keep.extras.get("duplicate_count", 1)) + 1
        grouped[key] = keep

    result = list(grouped.values())
    log.info("去重：%d → %d", len(docs), len(result))
    return result


def rank_and_trim(
    docs: list[Doc],
    query: str,
    *,
    top_k: int = 24,
    per_source_cap: int = 4,
) -> list[Doc]:
    """相关性排序 + 来源多样性控制，避免单一源刷屏。"""
    query_tokens = tokenize(query)
    if not query_tokens:
        return docs[:top_k]

    lengths = [len(tokenize(f"{d.title} {d.snippet} {d.content[:1500]}")) for d in docs] or [1]
    avg_len = sum(lengths) / len(lengths)

    for doc in docs:
        lexical = _bm25_like_score(query_tokens, doc, avg_len)
        # 归一化到 0~1，并融合源内排名与人工权重
        rank_bonus = 1.0 / (1.0 + doc.engine_rank)
        title_hit = sum(1 for t in query_tokens if t in doc.title.lower()) / max(len(query_tokens), 1)
        raw = 0.55 * math.tanh(lexical) + 0.25 * title_hit + 0.20 * rank_bonus
        doc.score = round(max(0.0, min(1.0, raw * 1.4)), 4)

    docs.sort(key=lambda d: (-d.score, d.engine_rank))

    # 来源多样性：每个平台先取 per_source_cap 条，再按需补齐
    picked: list[Doc] = []
    used: dict[str, int] = defaultdict(int)
    for doc in docs:
        key = doc.platform or doc.source
        if used[key] < per_source_cap:
            picked.append(doc)
            used[key] += 1
        if len(picked) >= top_k:
            return picked

    for doc in docs:
        if doc not in picked:
            picked.append(doc)
        if len(picked) >= top_k:
            break
    return picked
