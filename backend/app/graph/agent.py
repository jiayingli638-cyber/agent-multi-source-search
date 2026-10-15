"""Agent 对外执行入口：把 LangGraph 的中间过程转成 SSE 事件流。"""
from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any

from ..core.logging_utils import event_payload, get_logger
from ..core.models import AgentResult, Doc, SearchStats
from .workflow import get_graph

log = get_logger(__name__)


class _EventBuffer:
    """把节点内 emit 的事件放进异步队列，供 SSE 消费。"""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def emit(self, payload: dict[str, Any]) -> None:
        await self.queue.put(payload)


async def run_agent_stream(
    task: str,
    history: list[dict[str, str]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """执行 Agent，逐条 yield SSE 事件字典。

    事件类型与前端 App.tsx 约定一致：
        start / tool / final / error
    """
    started = time.perf_counter()
    buffer = _EventBuffer()
    graph = get_graph()

    yield event_payload("start", task=task)

    state: dict[str, Any] = {
        "task": task,
        "history": history or [],
        "emit": buffer.emit,
    }

    async def _run_graph() -> dict[str, Any]:
        return await graph.ainvoke(state)

    graph_task = asyncio.create_task(_run_graph())
    final_state: dict[str, Any] | None = None
    graph_error: BaseException | None = None

    # 一边跑图，一边把节点事件实时推给前端
    while True:
        if graph_task.done() and buffer.queue.empty():
            break
        try:
            payload = await asyncio.wait_for(buffer.queue.get(), timeout=0.15)
        except asyncio.TimeoutError:
            if graph_task.done():
                break
            continue
        yield payload

    try:
        final_state = await graph_task
    except Exception as exc:  # noqa: BLE001
        graph_error = exc

    # 排空剩余事件
    while not buffer.queue.empty():
        yield buffer.queue.get_nowait()

    if graph_error is not None:
        log.exception("Agent 执行失败")
        yield event_payload("error", message=f"Agent 执行失败：{graph_error}")
        yield {"type": "__done__"}
        return

    final_state = final_state or {}
    top_docs: list[Doc] = final_state.get("top_docs") or []
    stats_raw = final_state.get("stats") or {}
    elapsed_ms = int((time.perf_counter() - started) * 1000)

    stats = SearchStats(
        total_fetched=stats_raw.get("total_fetched", 0),
        after_dedup=stats_raw.get("after_dedup", 0),
        per_source=stats_raw.get("per_source", {}),
        errors=stats_raw.get("errors", {}),
        elapsed_ms=elapsed_ms,
    )

    result = AgentResult(
        answer=final_state.get("answer", ""),
        citations=[_public_doc(d) for d in top_docs],
        stats=stats,
        sub_queries=final_state.get("sub_queries") or [],
        plan=final_state.get("plan") or [],
        degraded=bool(final_state.get("degraded")),
        notes=final_state.get("notes") or [],
    )

    yield event_payload(
        "final",
        content=result.answer,
        citations=[_public_doc(d).model_dump() for d in result.citations],
        stats=result.stats.model_dump(),
        sub_queries=result.sub_queries,
        plan=[p.model_dump() for p in result.plan],
        degraded=result.degraded,
        notes=result.notes,
    )
    yield {"type": "__done__"}


def _public_doc(doc: Doc) -> Doc:
    """裁掉正文，避免 SSE 负载过大（前端只展示摘要）。"""
    return doc.model_copy(update={"content": (doc.content or "")[:600]})


async def run_agent(
    task: str,
    history: list[dict[str, str]] | None = None,
) -> AgentResult:
    """非流式执行，返回完整结果（供测试与 API 复用）。"""
    answer = ""
    citations: list[Doc] = []
    stats = SearchStats()
    sub_queries: list[str] = []
    plan = []
    degraded = False
    notes: list[str] = []

    async for event in run_agent_stream(task, history):
        etype = event.get("type")
        if etype == "final":
            answer = event.get("content", "")
            citations = [Doc(**c) for c in event.get("citations", [])]
            stats = SearchStats(**event.get("stats", {}))
            sub_queries = event.get("sub_queries", [])
            degraded = event.get("degraded", False)
            notes = event.get("notes", [])
        elif etype == "error":
            answer = event.get("message", "Agent 执行失败")
            degraded = True

    return AgentResult(
        answer=answer,
        citations=citations,
        stats=stats,
        sub_queries=sub_queries,
        plan=plan,
        degraded=degraded,
        notes=notes,
    )
