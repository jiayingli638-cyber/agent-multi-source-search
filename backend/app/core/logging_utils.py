"""结构化日志与 SSE 事件桥。"""
from __future__ import annotations

import logging
import sys
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

console = Console(file=sys.stdout, force_terminal=False)

_configured = False


def setup_logging(level: int = logging.INFO) -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True, show_path=False)],
    )
    # 降低第三方库噪音
    for noisy in ("httpx", "httpcore", "urllib3", "openai", "langchain", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def _norm(value: Any) -> Any:
    """把任意对象整理成可 JSON 序列化的结构。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _norm(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_norm(v) for v in value]
    if hasattr(value, "value"):  # Enum
        return _norm(value.value)
    if hasattr(value, "model_dump"):  # pydantic
        return _norm(value.model_dump())
    return str(value)


def event_payload(event_type: str, **fields: Any) -> dict[str, Any]:
    """构造前端约定的 SSE data 负载。"""
    payload: dict[str, Any] = {"type": event_type}
    for key, value in fields.items():
        payload[key] = _norm(value)
    return payload
