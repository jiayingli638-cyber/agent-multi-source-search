"""适配器基类：所有数据源统一接口。

新增一个源只需：
1. 继承 SourceAdapter
2. 实现 name / kind / platform / available / _search
3. 在 registry.py 中注册
"""
from __future__ import annotations

import abc
import time

from ..core.config import settings
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind

log = get_logger(__name__)


class SourceAdapter(abc.ABC):
    """检索源适配器抽象基类。"""

    name: str = "base"
    kind: SourceKind = SourceKind.WEB
    platform: str = ""          # 前端展示名，如「Bing (中国版)」
    requires_credentials: bool = False
    description: str = ""

    # ---------- 子类需实现 ----------
    @abc.abstractmethod
    async def _search(self, query: str, limit: int) -> list[Doc]:
        """执行真实检索，返回归一化 Doc 列表。"""

    def available(self) -> bool:
        """该源当前是否可用（凭证/依赖是否就绪）。"""
        return True

    def unavailable_reason(self) -> str:
        return "未配置"

    # ---------- 统一入口 ----------
    async def search(self, query: str, limit: int | None = None) -> list[Doc]:
        """带超时、异常隔离、mock 降级的检索入口。"""
        limit = limit or settings.max_results_per_source
        started = time.perf_counter()
        if not self.available():
            reason = self.unavailable_reason()
            log.info("[%s] 不可用：%s", self.name, reason)
            if settings.enable_mock_fallback:
                return self._mock(query, limit, reason)
            return []

        try:
            docs = await self._search(query, limit)
        except Exception as exc:  # noqa: BLE001
            log.warning("[%s] 检索异常: %s", self.name, exc)
            if settings.enable_mock_fallback:
                return self._mock(query, limit, f"检索失败：{exc}")
            return []

        for idx, doc in enumerate(docs):
            doc.source = doc.source or self.name
            doc.source_kind = doc.source_kind or self.kind
            doc.platform = doc.platform or self.platform or self.name
            if not doc.engine_rank:
                doc.engine_rank = idx + 1
        elapsed = (time.perf_counter() - started) * 1000
        log.info("[%s] 命中 %d 条，耗时 %.0fms", self.name, len(docs), elapsed)
        return docs[:limit]

    # ---------- mock 兜底 ----------
    def _mock(self, query: str, limit: int, reason: str) -> list[Doc]:
        """无凭证/失败时的占位结果，明确标注 degraded，避免误导用户。"""
        samples = [
            ("{q} —— 官方文档与权威解读", "https://example.com/docs/{idx}"),
            ("{q} 的行业现状与数据报告", "https://example.com/report/{idx}"),
            ("关于 {q} 的深度技术分析", "https://example.com/analysis/{idx}"),
        ]
        docs: list[Doc] = []
        for idx in range(min(limit, 2)):
            title_tpl, url_tpl = samples[idx % len(samples)]
            docs.append(
                Doc(
                    title=title_tpl.format(q=query),
                    url=url_tpl.format(idx=idx),
                    snippet=f"[模拟数据·{self.platform or self.name}] {reason}。配置凭证后将返回真实结果。",
                    content="",
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform or self.name,
                    engine_rank=idx + 1,
                    score=0.01,
                    extras={"mock": True, "degraded_reason": reason},
                )
            )
        return docs

    # ---------- 元信息 ----------
    def info(self) -> dict:
        return {
            "name": self.name,
            "platform": self.platform or self.name,
            "kind": self.kind.value,
            "available": self.available(),
            "requires_credentials": self.requires_credentials,
            "description": self.description,
            "unavailable_reason": "" if self.available() else self.unavailable_reason(),
        }
