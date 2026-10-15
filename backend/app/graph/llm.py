"""DeepSeek LLM 封装（基于 LangChain OpenAI 兼容接口）。"""
from __future__ import annotations

from functools import lru_cache

from langchain_openai import ChatOpenAI

from ..core.config import settings
from ..core.logging_utils import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=4)
def get_llm(*, reasoning: bool = False, temperature: float = 0.3, streaming: bool = False) -> ChatOpenAI:
    """获取 DeepSeek 客户端。DeepSeek 提供 OpenAI 兼容协议。

    Args:
        reasoning: 使用 deepseek-reasoner（更强推理，更慢更贵）
        temperature: 采样温度
        streaming: 是否流式
    """
    if not settings.llm_ready:
        raise RuntimeError(
            "未配置 DEEPSEEK_API_KEY，请在 backend/.env 中填写后重试"
        )
    model = settings.deepseek_reasoner_model if reasoning else settings.deepseek_model
    return ChatOpenAI(
        model=model,
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        temperature=temperature,
        streaming=streaming,
        timeout=120,
        max_retries=2,
    )


async def complete(system: str, user: str, *, reasoning: bool = False, temperature: float = 0.3) -> str:
    """一次性补全，返回纯文本。"""
    llm = get_llm(reasoning=reasoning, temperature=temperature)
    resp = await llm.ainvoke(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
    )
    content = resp.content
    if isinstance(content, list):  # 多模态分片兜底
        content = " ".join(str(c) for c in content)
    return str(content).strip()
