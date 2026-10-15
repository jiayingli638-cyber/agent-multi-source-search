"""GitHub 适配器：开源代码与仓库信息检索。

使用 GitHub REST API v3：
- /search/repositories  仓库检索
- /search/code          代码片段检索（需认证）
- /search/issues        Issue / PR 讨论检索

未配置 GITHUB_TOKEN 时仍可用匿名额度（10 req/min），但速率低；
配置后为 30 req/min（search）且有更高总量。
"""
from __future__ import annotations

import re

from ..core.config import settings
from ..core.http_client import fetch_json
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)

_LANG_HINT = re.compile(r"\b(python|javascript|typescript|java|go|rust|c\+\+|c#|php|ruby|kotlin|swift)\b", re.I)


class GitHubAdapter(SourceAdapter):
    name = "github"
    kind = SourceKind.CODE
    platform = "GitHub"
    description = "开源仓库 / 代码 / Issue 检索"

    def available(self) -> bool:
        # 无 token 也可用（匿名），因此始终可用
        return True

    def unavailable_reason(self) -> str:
        return "未配置 GITHUB_TOKEN，使用匿名额度（速率受限）"

    @property
    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            h["Authorization"] = f"Bearer {settings.github_token}"
        return h

    async def _search(self, query: str, limit: int) -> list[Doc]:
        docs: list[Doc] = []
        docs.extend(await self._search_repos(query, limit))
        if len(docs) < limit:
            docs.extend(await self._search_issues(query, limit - len(docs)))
        return docs

    async def _search_repos(self, query: str, limit: int) -> list[Doc]:
        data = await fetch_json(
            f"{settings.github_api_url}/search/repositories",
            params={"q": query, "per_page": min(limit, 20), "sort": "stars", "order": "desc"},
            headers=self._headers,
        )
        docs: list[Doc] = []
        for idx, repo in enumerate(data.get("items", [])[:limit]):
            desc = repo.get("description") or ""
            topics = ", ".join(repo.get("topics", [])[:6])
            docs.append(
                Doc(
                    title=f"{repo.get('full_name', '')} — {desc[:80]}",
                    url=repo.get("html_url", ""),
                    snippet=desc,
                    content=f"语言：{repo.get('language') or 'N/A'}；Topics：{topics}；"
                    f"Stars：{repo.get('stargazers_count', 0)}；Forks：{repo.get('forks_count', 0)}。"
                    f"{desc}",
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    author=(repo.get("owner") or {}).get("login", ""),
                    published_at=(repo.get("updated_at") or "")[:10],
                    engine_rank=idx + 1,
                    score=max(0.3, 1.0 - idx * 0.07),
                    extras={
                        "stars": repo.get("stargazers_count", 0),
                        "forks": repo.get("forks_count", 0),
                        "language": repo.get("language"),
                        "type": "repository",
                    },
                )
            )
        return docs

    async def _search_issues(self, query: str, limit: int) -> list[Doc]:
        try:
            data = await fetch_json(
                f"{settings.github_api_url}/search/issues",
                params={"q": query, "per_page": min(limit, 10), "sort": "reactions"},
                headers=self._headers,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("GitHub issues 检索失败: %s", exc)
            return []

        docs: list[Doc] = []
        for idx, issue in enumerate(data.get("items", [])[:limit]):
            docs.append(
                Doc(
                    title=issue.get("title", ""),
                    url=issue.get("html_url", ""),
                    snippet=(issue.get("body") or "")[:280],
                    source=self.name,
                    source_kind=self.kind,
                    platform=self.platform,
                    author=(issue.get("user") or {}).get("login", ""),
                    published_at=(issue.get("updated_at") or "")[:10],
                    engine_rank=idx + 1,
                    score=max(0.2, 0.8 - idx * 0.07),
                    extras={"type": "issue", "comments": issue.get("comments", 0)},
                )
            )
        return docs
