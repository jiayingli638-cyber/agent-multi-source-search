"""后端启动入口：python -m app.main 或 uv run python -m app.main"""
from __future__ import annotations

import uvicorn

from .core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level="info",
    )
