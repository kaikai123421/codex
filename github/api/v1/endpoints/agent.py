# -*- coding: utf-8 -*-
"""
Agent API endpoints.
"""

import asyncio
import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from src.config import get_config
from src.services.agent_model_service import list_agent_model_deployments

# Tool name -> Chinese display name mapping
TOOL_DISPLAY_NAMES: Dict[str, str] = {
    "get_realtime_quote":         "获取实时行情",
    "get_daily_history":          "获取历史K线",
    "get_chip_distribution":      "分析筹码分布",
    "get_analysis_context":       "获取分析上下文",
    "get_stock_info":             "获取股票基本面",
    "search_stock_news":          "搜索股票新闻",
    "search_comprehensive_intel": "搜索综合情报",
    "analyze_trend":              "分析技术趋势",
    "calculate_ma":               "计算均线系统",
    "get_volume_analysis":        "分析量能变化",
    "analyze_pattern":            "识别K线形态",
    "get_market_indices":         "获取市场指数",
    "get_sector_rankings":        "分析行业板块",
    "get_skill_backtest_summary": "获取技能回测概览",
    "get_strategy_backtest_summary": "获取策略回测概览",
    "get_stock_backtest_summary": "获取个股回测数据",
}

logger = logging.getLogger(__name__)

router = APIRouter()

class ChatRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    message: str
    session_id: Optional[str] = None
    skills: Optional[List[str]] = Field(
        default=None,
        validation_alias=AliasChoices("skills", "strategies"),
    )
    context: Optional[Dict[str, Any]] = None  # Previous analysis context for data reuse

    @property
    def effective_skills(self) -> Optional[List[str]]:
        """Return skill ids from the unified request shape."""
        return self.skills

class ChatResponse(BaseModel):
    success: bool
    content: str
    session_id: str
    error: Optional[str] = None

class SkillInfo(BaseModel):
    id: str
    name: str
    description: str

class SkillsResponse(BaseModel):
    skills: List[SkillInfo]
    default_skill_id: str = ""


class StrategiesResponse(BaseModel):
    strategies: List[SkillInfo]
    default_strategy_id: str = ""


class AgentModelDeployment(BaseModel):
    deployment_id: str
    model: str
    provider: str
    source: str
    api_base: Optional[str] = None
    deployment_name: Optional[str] = None
    is_primary: bool = False
    is_fallback: bool = False


class AgentModelsResponse(BaseModel):
    models: List[AgentModelDeployment]


STOCK_NAME_ALIASES: Dict[str, str] = {
    "消费电子ETF华夏": "159732",
    "消费电子ETF": "159732",
    "消费电子": "159732",
    "通信ETF国泰": "515880",
    "通信ETF": "515880",
    "通信": "515880",
    "工业富联": "601138",
    "新易盛": "300502",
    "京东方A": "000725",
    "京东方": "000725",
    "5GETF": "515050",
    "5G ETF": "515050",
    "5G": "515050",
}


def _has_stock_skill(skills: Optional[List[str]]) -> bool:
    return any(str(skill).lower() in {"stock", "stock_analyzer"} for skill in (skills or []))


def _should_use_local_stock_chat(request: ChatRequest) -> bool:
    # Legacy clients may still send lightweight fallback flags in context.
    # Ordinary stock questions must stay on the full executor path; failures are
    # handled by the degraded response instead of returning a lightweight report.
    return False


def _summarize_exception_for_user(exc: Exception) -> str:
    error_text = str(exc) or exc.__class__.__name__
    error_text = re.sub(r"<[^>]+>", " ", error_text)
    error_text = re.sub(r"\s+", " ", error_text).strip()
    if not error_text:
        error_text = exc.__class__.__name__
    if len(error_text) > 300:
        error_text = error_text[:300].rstrip() + "..."
    return error_text


def _build_degraded_agent_response(session_id: str, exc: Exception) -> ChatResponse:
    error_text = _summarize_exception_for_user(exc)
    content = (
        "## 降级回答\n\n"
        "这次完整分析没有跑完，原因是模型、行情源或 Render 上游接口临时异常。"
        "我不会为了凑字编造 BBI、资金流或买卖结论。\n\n"
        "你现在可以先这样处理：\n"
        "- 点击重试，优先重新跑完整分析。\n"
        "- 如果仍失败，先只看页面已有的实时行情、K 线、成交量和持仓成本，不做新增决策。\n"
        "- 盘中遇到 502/超时，按“数据缺失”处理，不把它当成利多或利空。\n\n"
        f"故障摘要：{error_text}"
    )
    return ChatResponse(
        success=False,
        content=content,
        session_id=session_id,
        error=f"upstream_unavailable: {error_text[:240]}",
    )


def _extract_local_stock_code(message: str, context: Optional[Dict[str, Any]], skills: Optional[List[str]]) -> Optional[str]:
    """Extract an A-share/ETF code for dependency-light chat fallback."""
    normalized = (message or "").strip()
    compact = re.sub(r"\s+", "", normalized).upper()

    for name, code in sorted(STOCK_NAME_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if name.upper().replace(" ", "") in compact:
            return code

    match = re.search(r"(?<!\d)((?:[0135689]\d{5}|92\d{4}))(?!\d)", normalized)
    if match:
        return match.group(1)

    ctx = context or {}
    ctx_code = str(ctx.get("stock_code") or "").strip()
    if ctx_code and re.fullmatch(r"(?:[0135689]\d{5}|92\d{4})", ctx_code):
        return ctx_code
    return None


def _format_local_stock_chat_content(payload: Dict[str, Any]) -> str:
    report = payload.get("report") or {}
    meta = report.get("meta") or {}
    summary = report.get("summary") or {}
    details = report.get("details") or {}
    strategy = report.get("strategy") or {}

    stock_name = payload.get("stock_name") or meta.get("stock_name") or "标的"
    stock_code = payload.get("stock_code") or meta.get("stock_code") or ""
    price = meta.get("current_price")
    change_pct = meta.get("change_pct")
    action = summary.get("action_label") or summary.get("operation_advice") or "观察"
    trend = summary.get("trend_prediction") or "未取得"
    score = summary.get("sentiment_score")

    price_text = "未取得" if price is None else str(price)
    change_text = "未取得" if change_pct is None else f"{change_pct}%"
    score_text = "未取得" if score is None else str(score)
    lines = [
        f"## {stock_name}({stock_code}) 轻量问股结论",
        "",
        f"- 现价：{price_text}，涨跌幅：{change_text}",
        f"- 动作：{action}，趋势：{trend}，评分：{score_text}",
        f"- 摘要：{summary.get('analysis_summary') or '未取得摘要'}",
        "",
        "### BBI纪律",
        "- 本次走云端轻量兜底：不编造 BBI。没有完整日线/周线序列时，只能把 BBI 标为未取得。",
        "- 真正下单前仍按你的规则确认：价格相对 BBI、量价、资金方向、先试仓、确认后加仓、做错不加仓。",
    ]
    if details.get("technical_analysis"):
        lines.extend(["", "### 技术与量价", str(details["technical_analysis"])])
    if any(strategy.values()):
        lines.extend([
            "",
            "### 关键位",
            f"- 理想买点：{strategy.get('ideal_buy') or '未取得'}",
            f"- 二次买点：{strategy.get('secondary_buy') or '未取得'}",
            f"- 止损/失效：{strategy.get('stop_loss') or '未取得'}",
            f"- 止盈：{strategy.get('take_profit') or '未取得'}",
        ])
    return "\n".join(lines)


def _save_local_stock_chat(session_id: str, message: str, content: str) -> None:
    try:
        from src.storage import get_db

        db = get_db()
        db.save_conversation_message(session_id, "user", message)
        db.save_conversation_message(session_id, "assistant", content)
    except Exception as exc:
        logger.warning("保存轻量问股对话失败: %s", exc, exc_info=True)


def _run_local_stock_chat(request: ChatRequest, session_id: str) -> Optional[ChatResponse]:
    skills = request.effective_skills
    code = _extract_local_stock_code(request.message, request.context, skills)
    if not code:
        return None

    from src.services.analysis_service import AnalysisService

    service = AnalysisService()
    payload = service.analyze_stock_lightweight(
        stock_code=code,
        report_type="brief",
        report_language=(request.context or {}).get("report_language"),
    )
    if payload is None:
        content = (
            f"我识别到你在问 {code}，但轻量行情接口也失败了：{service.last_error or '未知错误'}。\n"
            "这次我不编造结论。先按数据缺失处理，等行情源恢复后再判断。"
        )
        _save_local_stock_chat(session_id, request.message, content)
        return ChatResponse(success=False, content=content, session_id=session_id, error=service.last_error)

    content = _format_local_stock_chat_content(payload)
    _save_local_stock_chat(session_id, request.message, content)
    return ChatResponse(success=True, content=content, session_id=session_id, error=None)


@router.get("/models", response_model=AgentModelsResponse)
async def get_agent_models():
    """Get configured Agent model deployments for frontend selection."""
    config = get_config()
    return AgentModelsResponse(
        models=[AgentModelDeployment(**item) for item in list_agent_model_deployments(config)]
    )


def _build_skills_response(config) -> SkillsResponse:
    from src.agent.factory import get_skill_manager
    from src.agent.skills.defaults import get_primary_default_skill_id

    skill_manager = get_skill_manager(config)
    available_skills = sorted(
        [
            skill
            for skill in skill_manager.list_skills()
            if getattr(skill, "user_invocable", True)
        ],
        key=lambda skill: (
            int(getattr(skill, "default_priority", 100)),
            skill.display_name,
            skill.name,
        ),
    )
    skills = [
        SkillInfo(id=skill.name, name=skill.display_name, description=skill.description)
        for skill in available_skills
    ]
    return SkillsResponse(
        skills=skills,
        default_skill_id=get_primary_default_skill_id(available_skills),
    )


@router.get("/skills", response_model=SkillsResponse)
async def get_skills():
    """
    Get available agent strategy skills.
    """
    return _build_skills_response(get_config())


@router.get("/strategies", response_model=StrategiesResponse, include_in_schema=False)
async def get_strategies():
    """Compatibility alias for legacy clients."""
    payload = _build_skills_response(get_config())
    return StrategiesResponse(
        strategies=payload.skills,
        default_strategy_id=payload.default_skill_id,
    )

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(request: ChatRequest):
    """
    Chat with the AI Agent.
    """
    session_id = request.session_id or str(uuid.uuid4())
    if _should_use_local_stock_chat(request):
        local_stock_response = await asyncio.to_thread(_run_local_stock_chat, request, session_id)
        if local_stock_response is not None:
            return local_stock_response

    config = get_config()
    
    if not config.is_agent_available():
        raise HTTPException(status_code=400, detail="Agent mode is not enabled")
    
    try:
        skills = request.effective_skills
        executor = _build_executor(config, skills or None)

        # Pass explicit skills into context for the orchestrator.
        # Direct assignment so caller-provided skills always take precedence
        # over any stale value carried in the context dict.
        ctx = dict(request.context or {})
        if skills is not None:
            ctx["skills"] = skills

        # Offload the blocking call to a thread to avoid blocking the event loop.
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: executor.chat(message=request.message, session_id=session_id,
                                  context=ctx),
        )

        return ChatResponse(
            success=result.success,
            content=result.content,
            session_id=session_id,
            error=result.error
        )
            
    except Exception as e:
        logger.error(f"Agent chat API failed: {e}")
        logger.exception("Agent chat error details:")
        return _build_degraded_agent_response(session_id, e)


class SessionItem(BaseModel):
    session_id: str
    title: str
    message_count: int
    created_at: Optional[str] = None
    last_active: Optional[str] = None

class SessionsResponse(BaseModel):
    sessions: List[SessionItem]

class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]]


@router.get("/chat/sessions", response_model=SessionsResponse)
async def list_chat_sessions(limit: int = 50, user_id: Optional[str] = None):
    """获取聊天会话列表

    Args:
        limit: Maximum number of sessions to return.
        user_id: Optional platform-prefixed user identifier for session
            isolation.  When provided, only sessions whose session_id
            starts with this prefix are returned.  The value must
            include the platform prefix, e.g. ``telegram_12345``,
            ``feishu_ou_abc``.
    """
    from src.storage import get_db
    sessions = get_db().get_chat_sessions(
        limit=limit,
        session_prefix=user_id,
        extra_session_ids=[user_id] if user_id else None,
    )
    return SessionsResponse(sessions=sessions)


@router.get("/chat/sessions/{session_id}", response_model=SessionMessagesResponse)
async def get_chat_session_messages(session_id: str, limit: int = 100):
    """获取单个会话的完整消息"""
    from src.storage import get_db
    messages = get_db().get_conversation_messages(session_id, limit=limit)
    return SessionMessagesResponse(session_id=session_id, messages=messages)


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """删除指定会话"""
    from src.storage import get_db
    count = get_db().delete_conversation_session(session_id)
    return {"deleted": count}


class SendChatRequest(BaseModel):
    """Request body for sending chat content to notification channels."""

    content: str = Field(..., min_length=1, max_length=50000)
    title: Optional[str] = None


@router.post("/chat/send")
async def send_chat_to_notification(request: SendChatRequest):
    """
    Send chat session content to configured notification channels.
    Uses run_in_executor to avoid blocking the event loop.
    """
    from src.notification import NotificationService

    loop = asyncio.get_running_loop()
    success = await loop.run_in_executor(
        None,
        lambda: NotificationService().send(request.content),
    )
    if not success:
        return {
            "success": False,
            "error": "no_channels",
            "message": "未配置通知渠道，请先在设置中配置",
        }
    return {"success": True}


def _build_executor(config, skills: Optional[List[str]] = None):
    """Build and return a configured AgentExecutor (sync helper)."""
    from src.agent.factory import build_agent_executor
    return build_agent_executor(config, skills=skills)


async def _run_research_in_background(
    agent,
    question: str,
    context: Optional[Dict[str, Any]],
    *,
    timeout: int,
):
    """Run deep research off the event loop with an internal overall timeout."""
    return await asyncio.to_thread(
        agent.research,
        question,
        context,
        timeout_seconds=timeout,
    )


# ============================================================
# Deep research endpoint
# ============================================================

class ResearchRequest(BaseModel):
    question: str
    stock_code: Optional[str] = None

class ResearchResponse(BaseModel):
    success: bool
    content: str
    sources: List[str] = Field(default_factory=list)
    token_usage: int = 0
    error: Optional[str] = None


@router.post("/research", response_model=ResearchResponse)
async def agent_research(request: ResearchRequest):
    """Run a deep-research query via the ResearchAgent.

    Similar to the ``/research`` bot command but exposed as a REST endpoint.
    """
    config = get_config()
    if not config.is_agent_available():
        raise HTTPException(status_code=400, detail="Agent mode is not enabled")

    question = request.question
    context: Optional[Dict[str, Any]] = None
    if request.stock_code:
        question = f"[Stock: {request.stock_code}] {question}"
        context = {"stock_code": request.stock_code}

    try:
        from src.agent.research import ResearchAgent
        from src.agent.factory import get_tool_registry
        from src.agent.llm_adapter import LLMToolAdapter

        registry = get_tool_registry()
        llm_adapter = LLMToolAdapter(config)
        budget = getattr(config, "agent_deep_research_budget", 30000)

        agent = ResearchAgent(
            tool_registry=registry,
            llm_adapter=llm_adapter,
            token_budget=budget,
        )

        research_timeout = getattr(config, "agent_deep_research_timeout", 180)

        result = await _run_research_in_background(
            agent,
            question,
            context,
            timeout=research_timeout,
        )
        if getattr(result, "timed_out", False):
            logger.warning("Agent research API timed out after %ss", research_timeout)
            return ResearchResponse(
                success=False,
                content="",
                sources=[],
                token_usage=0,
                error=f"Deep research timed out after {research_timeout}s",
            )

        return ResearchResponse(
            success=result.success,
            content=result.report,
            sources=[f"Sub-question {i+1}: {q}" for i, q in enumerate(result.sub_questions)],
            token_usage=result.total_tokens,
            error=result.error if not result.success else None,
        )
    except Exception as e:
        logger.error("Agent research API failed: %s", e)
        logger.exception("Agent research error details:")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def agent_chat_stream(request: ChatRequest):
    """
    Chat with the AI Agent, streaming progress via SSE.
    Each SSE event is a JSON object with a 'type' field:
      - thinking: AI is deciding next action
      - tool_start: a tool call has begun
      - tool_done: a tool call finished
      - generating: final answer being generated
      - done: analysis complete, contains 'content' and 'success'
      - error: error occurred, contains 'message'
    """
    session_id = request.session_id or str(uuid.uuid4())
    local_stock_response = None
    if _should_use_local_stock_chat(request):
        local_stock_response = await asyncio.to_thread(_run_local_stock_chat, request, session_id)
    if local_stock_response is not None:
        async def local_event_generator():
            yield "data: " + json.dumps({"type": "thinking"}, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({
                "type": "tool_done",
                "tool": "get_realtime_quote",
                "display_name": TOOL_DISPLAY_NAMES.get("get_realtime_quote", "获取实时行情"),
                "success": local_stock_response.success,
            }, ensure_ascii=False) + "\n\n"
            yield "data: " + json.dumps({
                "type": "done",
                "success": local_stock_response.success,
                "content": local_stock_response.content,
                "error": local_stock_response.error,
                "total_steps": 1,
                "session_id": session_id,
            }, ensure_ascii=False) + "\n\n"

        return StreamingResponse(
            local_event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    config = get_config()
    if not config.is_agent_available():
        raise HTTPException(status_code=400, detail="Agent mode is not enabled")

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    # Pass explicit skills into context for the orchestrator.
    # Direct assignment so caller-provided skills always take precedence.
    skills = request.effective_skills
    stream_ctx = dict(request.context or {})
    if skills is not None:
        stream_ctx["skills"] = skills

    def progress_callback(event: dict):
        # Enrich tool events with display names
        if event.get("type") in ("tool_start", "tool_done"):
            tool = event.get("tool", "")
            event["display_name"] = TOOL_DISPLAY_NAMES.get(tool, tool)
        asyncio.run_coroutine_threadsafe(queue.put(event), loop)

    def run_sync():
        try:
            executor = _build_executor(config, skills or None)
            result = executor.chat(
                message=request.message,
                session_id=session_id,
                progress_callback=progress_callback,
                context=stream_ctx,
            )
            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "type": "done",
                    "success": result.success,
                    "content": result.content,
                    "error": result.error,
                    "total_steps": result.total_steps,
                    "session_id": session_id,
                }),
                loop,
            )
        except Exception as exc:
            logger.error(f"Agent stream error: {exc}")
            degraded = _build_degraded_agent_response(session_id, exc)
            asyncio.run_coroutine_threadsafe(
                queue.put({
                    "type": "done",
                    "success": False,
                    "content": degraded.content,
                    "error": degraded.error,
                    "total_steps": 0,
                    "session_id": session_id,
                }),
                loop,
            )

    async def event_generator():
        # Start executor in a thread so we don't block the event loop
        fut = loop.run_in_executor(None, run_sync)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=300.0)
                except asyncio.TimeoutError:
                    yield "data: " + json.dumps({"type": "error", "message": "分析超时"}, ensure_ascii=False) + "\n\n"
                    break
                yield "data: " + json.dumps(event, ensure_ascii=False) + "\n\n"
                if event.get("type") in ("done", "error"):
                    break
        finally:
            try:
                await asyncio.wait_for(fut, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                # Cleanup taking longer than 5s is treated as an expected timeout; no warning.
                logger.debug("agent executor cleanup timed out after 5s for session %s", session_id)
            except Exception as exc:
                logger.warning("agent executor cleanup error (ignored): %s", exc, exc_info=True)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
