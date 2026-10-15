"""共享 HTTP 客户端与网页正文抽取工具。

所有适配器复用同一个 AsyncClient，统一 UA / 超时 / 重试策略。
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import settings
from .logging_utils import get_logger

log = get_logger(__name__)

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    """返回进程级共享的异步 HTTP 客户端。"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.source_timeout),
            follow_redirects=True,
            headers={
                "User-Agent": DEFAULT_UA,
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            },
            limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


class TransientHTTPError(Exception):
    """可重试的临时错误（5xx / 429 / 网络超时）。"""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((TransientHTTPError, httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def fetch_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    json_body: Any = None,
) -> Any:
    client = get_client()
    resp = await client.request(method, url, params=params, headers=headers, json=json_body)
    if resp.status_code == 429 or resp.status_code >= 500:
        raise TransientHTTPError(f"HTTP {resp.status_code} from {url}")
    resp.raise_for_status()
    return resp.json()


async def fetch_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float | None = None,
) -> str:
    client = get_client()
    resp = await client.get(
        url, params=params, headers=headers, timeout=timeout or settings.source_timeout
    )
    resp.raise_for_status()
    return resp.text


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_SCRIPT_RE = re.compile(r"<(script|style|noscript)[^>]*>.*?</\1>", re.S | re.I)


def html_to_text(html: str, *, max_chars: int = 6000) -> str:
    """轻量 HTML → 纯文本。优先用 readability，失败则正则兜底。"""
    cleaned = _SCRIPT_RE.sub(" ", html)
    try:
        from readability import Document  # type: ignore

        doc = Document(cleaned)
        main = doc.summary(html_partial=True)
        text = _TAG_RE.sub(" ", main)
    except Exception:  # readability 依赖 lxml，失败时降级
        text = _TAG_RE.sub(" ", cleaned)
    text = _WS_RE.sub(" ", text).strip()
    return text[:max_chars]


async def extract_main_content(url: str, *, max_chars: int = 6000) -> str:
    """抓取网页并抽取正文，失败返回空串（不抛出，避免打断整体流程）。"""
    try:
        html = await fetch_text(url, timeout=min(settings.source_timeout, 15.0))
    except Exception as exc:  # noqa: BLE001
        log.debug("正文抓取失败 %s: %s", url, exc)
        return ""
    return html_to_text(html, max_chars=max_chars)


async def gather_with_limit(coros: list, limit: int | None = None) -> list:
    """带并发上限的 gather，异常以 None 占位返回。"""
    sem = asyncio.Semaphore(limit or settings.max_concurrency)

    async def _run(coro):
        async with sem:
            try:
                return await coro
            except Exception as exc:  # noqa: BLE001
                log.warning("并发任务失败: %s", exc)
                return None

    return await asyncio.gather(*(_run(c) for c in coros))
