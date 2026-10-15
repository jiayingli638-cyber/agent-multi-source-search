"""LangGraph 工作流装配。"""
from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from ..core.logging_utils import get_logger
from .nodes import (
    aggregate_node,
    fan_out_node,
    plan_node,
    route_after_understand,
    synthesize_node,
    understand_node,
)
from .state import AgentState

log = get_logger(__name__)


def build_graph():
    """构建并编译检索 Agent 图。

    拓扑：
        START → understand → (条件) → plan → fan_out → aggregate → synthesize → END
                          ↘ (无需检索) ─────────────────────────→ synthesize
    """
    graph = StateGraph(AgentState)

    graph.add_node("understand", understand_node)
    graph.add_node("plan", plan_node)
    graph.add_node("fan_out", fan_out_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "understand")
    graph.add_conditional_edges(
        "understand",
        route_after_understand,
        {"plan": "plan", "synthesize": "synthesize"},
    )
    graph.add_edge("plan", "fan_out")
    graph.add_edge("fan_out", "aggregate")
    graph.add_edge("aggregate", "synthesize")
    graph.add_edge("synthesize", END)

    compiled = graph.compile()
    log.info("LangGraph 检索工作流已编译完成")
    return compiled


@lru_cache(maxsize=1)
def get_graph():
    return build_graph()
