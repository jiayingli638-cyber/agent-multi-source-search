"""LangGraph 状态定义。"""
from __future__ import annotations

from typing import Annotated, Any, Callable

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from ..core.models import Doc, SourcePlan


def merge_docs(left: list[Doc], right: list[Doc]) -> list[Doc]:
    """并行节点写回时的 reducer：直接拼接，由后续去重统一处理。"""
    return (left or []) + (right or [])


def merge_dicts(left: dict, right: dict) -> dict:
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    """在 LangGraph 各节点间流转的状态。"""

    # 输入
    task: str                                    # 用户原始问题
    history: list[dict[str, str]]                # 对话历史

    # 查询理解
    normalized_query: str                        # 规范化后的检索式
    sub_queries: list[str]                       # 拆解出的子查询
    intent: str                                  # 问题类型：tech/news/compare/howto/...

    # 路由
    plan: list[SourcePlan]                       # 待调度的源
    need_search: bool                            # 是否需要联网检索

    # 检索结果（并行写回）
    docs: Annotated[list[Doc], merge_docs]
    errors: Annotated[dict[str, str], merge_dicts]
    per_source: Annotated[dict[str, int], merge_dicts]

    # 后处理
    top_docs: list[Doc]
    stats: dict[str, Any]

    # 输出
    answer: str
    notes: list[str]
    degraded: bool

    # 事件回调（不参与序列化）
    emit: Callable[[dict], Any]
