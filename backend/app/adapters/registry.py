"""适配器注册表：统一发现、查询、按能力路由。"""
from __future__ import annotations

from ..core.logging_utils import get_logger
from ..core.models import SourceKind
from .base import SourceAdapter
from .bing_cn import BingCNAdapter
from .google_search import GoogleWebAdapter
from .github import GitHubAdapter
from .mediacrawler import build_mediacrawler_adapters
from .nexus import NexusAdapter
from .arxiv import ArxivAdapter
from .web_fetch import WebFetchAdapter
from .xiaoheihe import XiaoHeiHeAdapter
from .boss_zhipin import BossZhipinAdapter

log = get_logger(__name__)


class AdapterRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for adapter in [
            BingCNAdapter(),
            GoogleWebAdapter(),
            GitHubAdapter(),
            NexusAdapter(),
            ArxivAdapter(),
            WebFetchAdapter(),
            XiaoHeiHeAdapter(),
            BossZhipinAdapter(),
            *build_mediacrawler_adapters(),
        ]:
            self.register(adapter)

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def get(self, name: str) -> SourceAdapter | None:
        return self._adapters.get(name)

    def all(self) -> list[SourceAdapter]:
        return list(self._adapters.values())

    def by_kind(self, kind: SourceKind) -> list[SourceAdapter]:
        return [a for a in self._adapters.values() if a.kind == kind]

    def available(self) -> list[SourceAdapter]:
        return [a for a in self._adapters.values() if a.available()]

    def describe(self) -> list[dict]:
        return [a.info() for a in self._adapters.values()]

    def catalog_for_llm(self) -> str:
        """给路由 LLM 看的源清单（只列可用源，避免规划出无效任务）。"""
        lines = []
        for a in self._adapters.values():
            status = "可用" if a.available() else f"不可用({a.unavailable_reason()[:40]})"
            lines.append(
                f"- {a.name} | 展示名={a.platform or a.name} | 类别={a.kind.value} | "
                f"能力={a.description} | 状态={status}"
            )
        return "\n".join(lines)


registry = AdapterRegistry()

__all__ = ["AdapterRegistry", "registry", "SourceAdapter", "SourceKind"]
