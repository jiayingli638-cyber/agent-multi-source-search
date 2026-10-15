"""FastAPI 应用：与前端约定的 SSE 流式检索接口。"""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .adapters import registry
from .core.config import settings
from .core.http_client import close_client
from .core.logging_utils import get_logger, setup_logging
from .graph.agent import run_agent, run_agent_stream

setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("网络检索 Agent 启动 | 模型=%s | 已配置 Key=%s", settings.deepseek_model, settings.llm_ready)
    for item in registry.describe():
        flag = "✓" if item["available"] else "✗"
        log.info("  %s 数据源 %-24s %s", flag, item["name"], item["platform"])
    yield
    await close_client()
    log.info("服务已关闭")


app = FastAPI(
    title="多源网络检索 Agent",
    version="0.1.0",
    description="聚合国内外多源检索的 Agent 服务，流式返回检索过程与答案",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------- 请求模型
class HistoryMessage(BaseModel):
    role: str = "user"
    content: str = ""


class ChatRequest(BaseModel):
    task: str = Field(..., min_length=1, description="用户问题")
    history: list[HistoryMessage] = Field(default_factory=list, description="对话历史")


# ---------------------------------------------------------------- 路由
@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "llm_ready": settings.llm_ready,
        "model": settings.deepseek_model,
        "sources_total": len(registry.all()),
        "sources_available": len(registry.available()),
    }


@app.get("/api/sources")
async def sources() -> dict[str, Any]:
    """列出所有数据源及其可用状态，前端可据此展示能力面板。"""
    return {"sources": registry.describe()}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict[str, Any]:
    """非流式接口，便于脚本测试。"""
    result = await run_agent(
        req.task, [m.model_dump() for m in req.history]
    )
    return result.model_dump()


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """SSE 流式接口，事件格式与前端 App.tsx 完全对齐。"""
    task = req.task.strip()
    if not task:
        raise HTTPException(status_code=400, detail="task 不能为空")

    history = [m.model_dump() for m in req.history]

    async def event_generator():
        try:
            async for event in run_agent_stream(task, history):
                if event.get("type") == "__done__":
                    yield "data: [DONE]\n\n"
                    return
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:  # 客户端断开
            log.info("客户端断开连接，中止本次检索")
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("流式处理异常")
            payload = {"type": "error", "message": f"服务异常：{exc}"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 关闭反向代理缓冲，保证实时性
        },
    )
