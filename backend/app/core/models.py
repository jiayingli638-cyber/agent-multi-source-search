"""全局领域模型：检索文档、来源候选、Agent 状态等。"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class SourceKind(str, Enum):
    """数据源类别，用于前端分组展示与路由计划。"""

    GENERAL_CN = "general_cn"        # 国内通用搜索（Bing 中国版）
    GENERAL_GLOBAL = "general_global"  # 国外通用搜索（Google）
    SOCIAL_CN = "social_cn"          # 国内社媒（MediaCrawler）
    CODE = "code"                    # 开源代码（GitHub）
    ACADEMIC = "academic"            # 学术/知识（Nexus / arXiv）
    WEB = "web"                      # 指定网页正文抓取
    RECRUIT = "recruit"              # 招聘/就业（BOSS 直聘）


class Doc(BaseModel):
    """归一化后的单条检索结果。所有适配器都必须产出 Doc。"""

    id: str = ""
    title: str = ""
    url: str = ""
    snippet: str = ""
    content: str = ""                # 正文（若已抓取）
    source: str = ""                 # 适配器名，如 bing_cn / github
    source_kind: SourceKind = SourceKind.WEB
    platform: str = ""               # 展示用平台名，如「微博」「GitHub」
    author: str = ""
    published_at: str = ""
    score: float = 0.0               # 相关性得分（0~1）
    engine_rank: int = 0             # 源内原始排名
    extras: dict[str, Any] = Field(default_factory=dict)  # 平台特有字段（stars/点赞等）
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def model_post_init(self, __context: Any) -> None:
        if not self.id:
            basis = f"{self.source}|{self.url}|{self.title}"
            self.id = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def dedup_key(self) -> str:
        """去重主键：优先 URL，其次标题归一化。"""
        if self.url:
            return self.url.split("?")[0].rstrip("/").lower()
        return " ".join(self.title.lower().split())

    @property
    def text(self) -> str:
        return self.content or self.snippet


class SourcePlan(BaseModel):
    """路由计划：某次查询需要调度哪些源、用什么子查询。"""

    source: str
    kind: SourceKind
    query: str
    reason: str = ""
    required: bool = False


class ToolEvent(BaseModel):
    """SSE 推送的工具执行事件。"""

    name: str
    ok: bool
    result: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class SearchStats(BaseModel):
    total_fetched: int = 0
    after_dedup: int = 0
    per_source: dict[str, int] = Field(default_factory=dict)
    errors: dict[str, str] = Field(default_factory=dict)
    elapsed_ms: int = 0


class AgentResult(BaseModel):
    answer: str = ""
    citations: list[Doc] = Field(default_factory=list)
    stats: SearchStats = Field(default_factory=SearchStats)
    sub_queries: list[str] = Field(default_factory=list)
    plan: list[SourcePlan] = Field(default_factory=list)
    degraded: bool = False
    notes: list[str] = Field(default_factory=list)


RouteDecision = Literal["search", "answer_directly"]
