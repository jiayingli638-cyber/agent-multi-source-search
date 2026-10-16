"""LangGraph 节点实现。

流程：
    understand ──► plan ──► fan_out(search) ──► aggregate ──► synthesize
       │                                        ▲
       └────────────(闲聊/无需检索)─────────────► synthesize
"""
from __future__ import annotations

import asyncio
import json
import re
import time

from ..adapters import registry
from ..core.config import settings
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind, SourcePlan
from .llm import complete
from .rerank import deduplicate, rank_and_trim
from .state import AgentState

log = get_logger(__name__)

_CHAT_HINTS = ("你好", "hi", "hello", "谢谢", "你是谁", "在吗", "测试一下")

_UNDERSTAND_SYSTEM = """你是网络检索 Agent 的查询理解模块。给定用户问题，输出严格的 JSON（不要 markdown 代码块）：
{
  "normalized_query": "规范化、补全后的核心检索式",
  "intent": "tech | news | compare | howto | opinion | academic | code | factual",
  "sub_queries": ["子查询1", "子查询2", "子查询3"],
  "need_search": true
}
要求：
- sub_queries 输出 2-4 条，覆盖不同侧面与中英文表达，用于并行检索。
- 若问题明显是寒暄或无需外部信息（如纯数学计算、常识自我介绍），need_search 设为 false。
- 只输出 JSON。"""

_SYNTH_SYSTEM = """你是严谨的信息整合专家。基于给定的检索证据回答用户问题。

硬性要求：
1. 只使用证据中出现的信息，禁止编造。证据不足时明确说明「现有资料未覆盖」。
2. 每个关键结论后用 [编号] 标注来源，编号对应证据序号。
3. 若多个来源说法冲突，指出冲突并说明各自出处。
4. 结构化输出：先给 3 句以内的「核心结论」，再分点展开，最后给「信息缺口 / 可信度说明」。
5. 用中文回答，语言精炼，不要复述问题。
6. 证据中若有「高赞评论」，可引用网友观点佐证，引用时必须注明网友昵称（如「网友『xxx』说：…」），不得篡改原意。
7. 在结尾另起一行输出「来源清单」，格式每行：`[编号] 平台名 - 标题 - URL`"""


# ---------------------------------------------------------------- 工具函数
def _extract_json(text: str) -> object | None:
    """从可能带 markdown 包裹的文本中提取 JSON。"""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 兜底：截取首个 { } 或 [ ]
    for opener, closer in (("[", "]"), ("{", "}")):
        start, end = text.find(opener), text.rfind(closer)
        if 0 <= start < end:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


# ---------------------------------------------------------------- 节点
async def understand_node(state: AgentState) -> dict:
    """查询理解与拆解。"""
    task = state["task"]
    emit = state.get("emit")

    if emit:
        await _safe_emit(emit, {"type": "tool", "name": "查询理解", "ok": True,
                                "result": "正在解析问题并生成检索式…"})

    fallback = {
        "normalized_query": task,
        "intent": "factual",
        "sub_queries": [task],
        "need_search": True,
    }
    if any(h in task.lower() for h in _CHAT_HINTS) and len(task) < 20:
        return {
            "normalized_query": task,
            "intent": "chat",
            "sub_queries": [],
            "need_search": False,
            "docs": [],
            "errors": {},
            "per_source": {},
        }

    try:
        raw = await complete(_UNDERSTAND_SYSTEM, task, temperature=0.0)
        data = _extract_json(raw)
        if not isinstance(data, dict):
            data = fallback
    except Exception as exc:  # noqa: BLE001
        log.warning("查询理解失败，使用兜底：%s", exc)
        data = fallback

    sub_queries = [q for q in (data.get("sub_queries") or []) if isinstance(q, str) and q.strip()]
    if not sub_queries:
        sub_queries = [data.get("normalized_query") or task]

    result = {
        "normalized_query": data.get("normalized_query") or task,
        "intent": data.get("intent") or "factual",
        "sub_queries": sub_queries[:4],
        "need_search": bool(data.get("need_search", True)),
        "docs": [],
        "errors": {},
        "per_source": {},
    }
    if emit:
        await _safe_emit(emit, {
            "type": "tool",
            "name": "查询拆解",
            "ok": True,
            "result": f"意图={result['intent']}，生成 {len(sub_queries)} 条子查询",
            "arguments": {"sub_queries": sub_queries[:4]},
        })
    return result


async def plan_node(state: AgentState) -> dict:
    """路由：全量调度所有可用源（不按意图过滤）。

    用户要求「问了之后所有可用源都采集」，故不再用 LLM 挑源；
    直接把 available() 且 selectable_by_llm 的源全部纳入计划，
    每个源按类别分配最合适的子查询。
    """
    emit = state.get("emit")
    if not state.get("need_search"):
        return {"plan": []}

    user_q = state["normalized_query"]
    sub_queries = state.get("sub_queries") or [user_q]

    plans: list[SourcePlan] = []
    for adapter in registry.available():
        if not adapter.selectable_by_llm:
            continue
        plans.append(
            SourcePlan(
                source=adapter.name,
                kind=adapter.kind,
                query=_pick_query(adapter.kind, user_q, sub_queries),
                reason="全量采集",
            )
        )

    if emit:
        await _safe_emit(emit, {
            "type": "tool",
            "name": "调度规划",
            "ok": bool(plans),
            "result": f"全量调度 {len(plans)} 个数据源：" + "、".join(p.source for p in plans),
            "arguments": {"plan": [p.model_dump() for p in plans]},
        })
    return {"plan": plans}


def _pick_query(kind: SourceKind, user_q: str, sub_queries: list[str]) -> str:
    """按源类别挑选最合适的检索式，尽量贴合各源的语言/领域习惯。"""
    def has_cjk(q: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", q))

    def has_ascii(q: str) -> bool:
        return bool(re.search(r"[A-Za-z]", q))

    if kind == SourceKind.CODE:
        # GitHub 优先纯英文技术栈子查询
        for q in sub_queries:
            if has_ascii(q) and not has_cjk(q):
                return q
        for q in sub_queries:
            if has_ascii(q):
                return q
    elif kind == SourceKind.SOCIAL_CN:
        # 社媒优先中文口语子查询
        for q in sub_queries:
            if has_cjk(q):
                return q
    return user_q


async def fan_out_node(state: AgentState) -> dict:
    """并行调度所有选中源。"""
    plans: list[SourcePlan] = state.get("plan") or []
    if not plans:
        return {"docs": [], "errors": {}, "per_source": {}}

    emit = state.get("emit")

    async def run_one(plan: SourcePlan):
        adapter = registry.get(plan.source)
        if adapter is None:
            return plan.source, [], f"未注册的源：{plan.source}"
        started = time.perf_counter()
        # 子进程类源（MediaCrawler）内层超时可达 90s，外层必须 >= 内层，
        # 否则内层还没跑完就被这里提前杀掉，社媒源永远报「超时」。
        timeout = adapter.search_timeout or max(settings.source_timeout * 3, 45.0)
        try:
            docs = await asyncio.wait_for(
                adapter.search(plan.query, settings.max_results_per_source),
                timeout=timeout,
            )
            elapsed = (time.perf_counter() - started) * 1000
            if emit:
                degraded = bool(docs and docs[0].extras.get("mock"))
                await _safe_emit(emit, {
                    "type": "tool",
                    "name": plan.source,
                    "ok": not degraded,
                    "result": (
                        f"命中 {len(docs)} 条（{elapsed:.0f}ms）"
                        + ("｜降级为模拟数据" if degraded else "")
                    ),
                    "arguments": {"query": plan.query, "reason": plan.reason,
                                  "platform": adapter.platform},
                })
            return plan.source, docs, None
        except asyncio.TimeoutError:
            return plan.source, [], f"超时（>{timeout:.0f}s）"
        except Exception as exc:  # noqa: BLE001
            return plan.source, [], str(exc)

    results = await asyncio.gather(*(run_one(p) for p in plans))

    docs: list[Doc] = []
    errors: dict[str, str] = {}
    per_source: dict[str, int] = {}
    for name, items, err in results:
        if err:
            errors[name] = err
            per_source[name] = 0
        else:
            docs.extend(items)
            per_source[name] = len(items)

    log.info("fan_out 完成：%d 条原始结果，%d 个源报错", len(docs), len(errors))
    return {"docs": docs, "errors": errors, "per_source": per_source}


async def aggregate_node(state: AgentState) -> dict:
    """去重 + 相关性排序 + 多样性控制。"""
    emit = state.get("emit")
    raw = state.get("docs") or []
    query = state.get("normalized_query") or state["task"]

    deduped = deduplicate(raw)
    top = rank_and_trim(deduped, query, top_k=24, per_source_cap=4)

    errors = state.get("errors") or {}
    stats = {
        "total_fetched": len(raw),
        "after_dedup": len(deduped),
        "per_source": state.get("per_source") or {},
        "errors": errors,
    }

    if emit:
        detail = " · ".join(f"{k}:{v}" for k, v in (state.get("per_source") or {}).items())
        await _safe_emit(emit, {
            "type": "tool",
            "name": "归并去重",
            "ok": True,
            "result": f"原始 {len(raw)} 条 → 去重后 {len(deduped)} 条 → 精选 {len(top)} 条",
            "arguments": {"per_source": detail, "errors": errors},
        })
    return {"top_docs": top, "stats": stats}


async def synthesize_node(state: AgentState) -> dict:
    """基于证据生成带引用的答案。"""
    emit = state.get("emit")
    task = state["task"]
    top_docs: list[Doc] = state.get("top_docs") or []
    history = state.get("history") or []
    notes: list[str] = []
    degraded = False

    # 无需检索：直接回答
    if not state.get("need_search"):
        try:
            answer = await complete(
                "你是友善、简洁的助手。用中文直接回答用户，不要编造事实。",
                task,
                temperature=0.6,
            )
        except Exception as exc:  # noqa: BLE001
            answer = f"（模型调用失败：{exc}）"
        return {"answer": answer, "notes": notes, "degraded": False}

    if not top_docs:
        errors = state.get("errors") or {}
        note = "本次未获取到任何有效检索结果。"
        if errors:
            note += "失败源：" + "；".join(f"{k}({v[:60]})" for k, v in errors.items())
        notes.append(note)
        degraded = True
        try:
            answer = await complete(
                "你是严谨的助手。检索未返回结果，请如实告知用户并给出可行的下一步建议，不要编造内容。",
                f"用户问题：{task}\n\n情况：{note}",
                temperature=0.3,
            )
        except Exception as exc:  # noqa: BLE001
            answer = f"检索未返回结果。\n{note}\n（模型调用失败：{exc}）"
        return {"answer": answer, "notes": notes, "degraded": True}

    if any(d.extras.get("mock") for d in top_docs):
        degraded = True
        notes.append("部分来源为模拟数据（未配置凭证），结论仅供参考。")

    evidence_lines = []
    for idx, doc in enumerate(top_docs, start=1):
        body = (doc.content or doc.snippet or "")[:1200]
        extra = ""
        if doc.extras.get("stars"):
            extra = f" | stars={doc.extras['stars']}"
        evidence_lines.append(
            f"[{idx}] 来源={doc.platform or doc.source}{extra} | 标题={doc.title} | URL={doc.url}\n"
            f"    时间={doc.published_at or '未知'} | 作者={doc.author or '未知'}\n"
            f"    内容={body}"
        )
        # 附带高赞评论区观点，供答案引用网友观点
        hot = doc.extras.get("hot_comments") or []
        if hot:
            comment_text = "；".join(
                f"网友「{c['author']}」(赞{c['likes']})：{c['content']}" for c in hot
            )
            evidence_lines.append(f"    高赞评论：{comment_text}")
    evidence = "\n".join(evidence_lines)

    history_text = ""
    if history:
        recent = history[-6:]
        history_text = "\n".join(
            f"{'用户' if m.get('role') == 'user' else '助手'}：{str(m.get('content', ''))[:300]}"
            for m in recent
        )

    prompt = (
        f"用户问题：{task}\n\n"
        + (f"近期对话上下文：\n{history_text}\n\n" if history_text else "")
        + f"共 {len(top_docs)} 条检索证据：\n{evidence}"
    )

    try:
        answer = await complete(_SYNTH_SYSTEM, prompt, temperature=0.3)
    except Exception as exc:  # noqa: BLE001
        log.warning("答案生成失败：%s", exc)
        notes.append(f"答案生成失败：{exc}")
        degraded = True
        answer = _fallback_answer(task, top_docs)

    if emit:
        await _safe_emit(emit, {
            "type": "tool",
            "name": "答案生成",
            "ok": True,
            "result": f"已基于 {len(top_docs)} 条证据生成答案（{len(answer)} 字）",
        })
    return {"answer": answer, "notes": notes, "degraded": degraded}


def _fallback_answer(task: str, docs: list[Doc]) -> str:
    """LLM 不可用时的抽取式答案，保证永远有可交付产出。"""
    lines = [f"关于「{task}」，检索到以下 {len(docs)} 条相关资料（模型不可用，以下为原文摘要）：", ""]
    for idx, doc in enumerate(docs[:8], start=1):
        lines.append(f"[{idx}] {doc.title}")
        lines.append(f"    {(doc.content or doc.snippet)[:200]}")
        lines.append(f"    来源：{doc.platform or doc.source} - {doc.url}")
        lines.append("")
    return "\n".join(lines)


async def _safe_emit(emit, payload: dict) -> None:
    """事件推送失败不能中断主流程。"""
    try:
        result = emit(payload)
        if asyncio.iscoroutine(result):
            await result
    except Exception as exc:  # noqa: BLE001
        log.debug("事件推送失败：%s", exc)


def route_after_understand(state: AgentState) -> str:
    return "plan" if state.get("need_search") else "synthesize"
