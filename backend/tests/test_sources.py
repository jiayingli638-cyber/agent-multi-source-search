"""数据源连通性自检脚本。

用法：
    python -m tests.test_sources            # 检查全部源
    python -m tests.test_sources github     # 只检查指定源
"""
from __future__ import annotations

import asyncio
import sys
import time

from app.adapters import registry
from app.core.http_client import close_client
from app.core.logging_utils import setup_logging

setup_logging()

QUERY = "LangGraph multi-agent architecture"
CN_QUERY = "大模型 Agent 框架对比"


async def check(name: str, query: str) -> tuple[str, bool, str]:
    adapter = registry.get(name)
    if adapter is None:
        return name, False, "未注册"
    started = time.perf_counter()
    try:
        docs = await asyncio.wait_for(adapter.search(query, 3), timeout=60)
    except Exception as exc:  # noqa: BLE001
        return name, False, f"异常：{exc}"
    elapsed = (time.perf_counter() - started) * 1000
    if not docs:
        return name, False, f"0 条（{elapsed:.0f}ms）"
    mocked = bool(docs[0].extras.get("mock"))
    sample = docs[0].title[:50]
    status = "MOCK" if mocked else "OK"
    return name, not mocked, f"{status} {len(docs)} 条（{elapsed:.0f}ms）示例：{sample}"


async def main() -> int:
    targets = sys.argv[1:]
    adapters = registry.all()
    if targets:
        adapters = [a for a in adapters if a.name in targets]

    print(f"\n{'=' * 78}\n数据源自检（共 {len(adapters)} 个）\n{'=' * 78}")
    print(f"{'源':<24}{'平台':<16}{'状态'}")
    print("-" * 78)

    failures = 0
    for adapter in adapters:
        query = CN_QUERY if adapter.name in ("bing_cn",) else QUERY
        if adapter.name.startswith("mediacrawler"):
            query = CN_QUERY
        name, ok, detail = await check(adapter.name, query)
        if not ok:
            failures += 1
        print(f"{name:<24}{adapter.platform:<16}{detail}")

    print("-" * 78)
    print(f"通过 {len(adapters) - failures} / {len(adapters)}；失败或降级 {failures} 个")
    print("提示：显示 MOCK 表示该源缺少凭证，已在 .env 中补齐后即可返回真实数据。\n")

    await close_client()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
