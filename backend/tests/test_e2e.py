"""Agent 端到端测试：走完整 LangGraph 链路，验证 SSE 事件与最终答案。"""
from __future__ import annotations

import asyncio
import sys
import time

from app.core.http_client import close_client
from app.core.logging_utils import setup_logging
from app.graph.agent import run_agent_stream

setup_logging()

QUESTIONS = {
    "tech": "LangGraph 和 AutoGen 在多智能体编排上的主要区别是什么？",
    "code": "有没有开源的 MediaCrawler 替代方案？",
    "cn": "最近大家怎么评价国产大模型 Agent 的落地效果？",
}


async def run_case(label: str, question: str) -> bool:
    print(f"\n{'=' * 78}\n[{label}] {question}\n{'=' * 78}")
    started = time.perf_counter()
    tool_events, final, errors = [], None, []

    async for event in run_agent_stream(question):
        etype = event.get("type")
        if etype == "tool":
            tool_events.append(event)
            mark = "✓" if event.get("ok") else "✗"
            print(f"  {mark} [{event.get('name')}] {event.get('result')}")
        elif etype == "final":
            final = event
        elif etype == "error":
            errors.append(event.get("message"))
            print(f"  ✗ 错误：{event.get('message')}")

    elapsed = time.perf_counter() - started
    if errors or not final:
        print(f"\n结果：失败（{elapsed:.1f}s）{errors}")
        return False

    stats = final.get("stats", {})
    print(f"\n  检索统计：原始 {stats.get('total_fetched')} 条 → 去重 {stats.get('after_dedup')} 条")
    print(f"  各源产出：{stats.get('per_source')}")
    if stats.get("errors"):
        print(f"  源异常  ：{stats.get('errors')}")
    print(f"  引用条数：{len(final.get('citations', []))}；降级={final.get('degraded')}")
    print(f"\n  ---- 答案预览（前 700 字）----\n{final.get('content', '')[:700]}")
    print(f"\n结果：通过（{elapsed:.1f}s，工具事件 {len(tool_events)} 条）")
    return True


async def main() -> int:
    keys = sys.argv[1:] or ["tech"]
    ok = 0
    for key in keys:
        if key not in QUESTIONS:
            print(f"未知用例：{key}，可用：{list(QUESTIONS)}")
            continue
        if await run_case(key, QUESTIONS[key]):
            ok += 1
    print(f"\n{'=' * 78}\n端到端通过 {ok}/{len(keys)}\n{'=' * 78}")
    await close_client()
    return 0 if ok == len(keys) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
