# -*- coding: utf-8 -*-
"""Agent chat history API regressions."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def teardown_function() -> None:
    DatabaseManager.reset_instance()
    Config.reset_instance()


def test_chat_session_messages_api_does_not_expose_provider_trace(tmp_path: Path) -> None:
    DatabaseManager.reset_instance()
    Config.reset_instance()
    db = DatabaseManager(db_url=f"sqlite:///{tmp_path / 'trace.db'}")
    session_id = "api-trace-hidden"
    user_id = db.save_conversation_message(session_id, "user", "visible question")
    assistant_id = db.save_conversation_message(session_id, "assistant", "visible answer")
    db.save_agent_provider_turn(
        session_id=session_id,
        run_id="run-hidden",
        provider="deepseek",
        model="deepseek/deepseek-chat",
        anchor_user_message_id=user_id,
        anchor_assistant_message_id=assistant_id,
        messages=[
            {
                "role": "assistant",
                "content": "checking",
                "reasoning_content": "SECRET_REASONING",
                "tool_calls": [{"id": "call_1", "name": "echo", "arguments": {}}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "SECRET_TOOL_RESULT"},
        ],
        contains_reasoning=True,
        contains_tool_calls=True,
        contains_thinking_blocks=False,
        must_roundtrip=True,
        estimated_tokens=10,
    )

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        client = TestClient(create_app(static_dir=tmp_path / "static"))
        response = client.get(f"/api/v1/agent/chat/sessions/{session_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session_id
    assert [(msg["role"], msg["content"]) for msg in payload["messages"]] == [
        ("user", "visible question"),
        ("assistant", "visible answer"),
    ]
    assert "SECRET_REASONING" not in response.text
    assert "SECRET_TOOL_RESULT" not in response.text
    assert "tool_calls" not in response.text


def test_agent_chat_forwards_stock_context_to_executor(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.return_value = SimpleNamespace(
        success=True,
        content="ok",
        error=None,
    )
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor):
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat",
                    json={
                        "message": "如果不考虑 TTM 呢",
                        "session_id": "s1",
                        "context": {
                            "stock_code": "600519",
                            "stock_name": "匿名标的",
                        },
                    },
                )

    assert response.status_code == 200
    kwargs = executor.chat.call_args.kwargs
    assert kwargs["message"] == "如果不考虑 TTM 呢"
    assert kwargs["session_id"] == "s1"
    assert kwargs["context"]["stock_code"] == "600519"
    assert kwargs["context"]["stock_name"] == "匿名标的"


def test_agent_chat_ignores_legacy_lightweight_flag_for_full_executor_path(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.return_value = SimpleNamespace(
        success=True,
        content="full analysis despite legacy lightweight flag",
        error=None,
    )
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor) as build_executor:
                with patch("src.services.analysis_service.AnalysisService") as service_cls:
                    client = TestClient(create_app(static_dir=tmp_path / "static"))
                    response = client.post(
                        "/api/v1/agent/chat",
                        json={
                            "message": "601138 how is it now",
                            "session_id": "s-legacy-light-flag",
                            "skills": ["stock_analyzer"],
                            "context": {
                                "stockCode": "601138",
                                "use_lightweight_stock_fallback": True,
                            },
                        },
                    )

    assert response.status_code == 200
    assert response.json()["content"] == "full analysis despite legacy lightweight flag"
    build_executor.assert_called_once()
    service_cls.return_value.analyze_stock_lightweight.assert_not_called()
    kwargs = executor.chat.call_args.kwargs
    assert kwargs["context"]["skills"] == ["stock_analyzer"]
    assert kwargs["context"]["use_lightweight_stock_fallback"] is True


def test_agent_chat_stream_forwards_stock_context_to_executor(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.return_value = SimpleNamespace(
        success=True,
        content="ok",
        error=None,
        total_steps=1,
    )
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor):
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat/stream",
                    json={
                        "message": "如果不考虑 TTM 呢",
                        "session_id": "s1",
                        "context": {
                            "stock_code": "600519",
                            "stock_name": "匿名标的",
                        },
                    },
                )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    kwargs = executor.chat.call_args.kwargs
    assert kwargs["message"] == "如果不考虑 TTM 呢"
    assert kwargs["session_id"] == "s1"
    assert kwargs["context"]["stock_code"] == "600519"
    assert kwargs["context"]["stock_name"] == "匿名标的"


@pytest.mark.skip(reason="ordinary stock chat should use the full agent path, not the lightweight path")
def test_agent_chat_stream_uses_local_stock_fallback_for_stock_skill(tmp_path: Path) -> None:
    config = SimpleNamespace(is_agent_available=lambda: True)
    analysis_payload = {
        "stock_code": "601138",
        "stock_name": "工业富联",
        "report": {
            "meta": {
                "stock_code": "601138",
                "stock_name": "工业富联",
                "current_price": 64.72,
                "change_pct": -1.2,
            },
            "summary": {
                "analysis_summary": "轻量分析摘要",
                "action_label": "观察",
                "trend_prediction": "震荡",
                "sentiment_score": 45,
            },
            "details": {"technical_analysis": "BBI未取得，不编造。"},
            "strategy": {
                "ideal_buy": "等待BBI确认",
                "secondary_buy": None,
                "stop_loss": "跌破BBI重新评估",
                "take_profit": None,
            },
        },
    }

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor") as build_executor:
                with patch("src.services.analysis_service.AnalysisService") as service_cls:
                    service_cls.return_value.analyze_stock_lightweight.return_value = analysis_payload
                    client = TestClient(create_app(static_dir=tmp_path / "static"))
                    response = client.post(
                        "/api/v1/agent/chat/stream",
                        json={
                            "message": "工业富联怎么看",
                            "session_id": "s-stock",
                            "skills": ["stock_analyzer"],
                        },
                    )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert "工业富联" in response.text
    assert "BBI" in response.text
    build_executor.assert_not_called()


@pytest.mark.skip(reason="ordinary stock chat should use the full agent path, not the lightweight path")
def test_agent_chat_stream_uses_camel_case_context_stock_code_for_followup(tmp_path: Path) -> None:
    config = SimpleNamespace(is_agent_available=lambda: True)
    analysis_payload = {
        "stock_code": "601138",
        "stock_name": "Industrial Fulian",
        "report": {
            "meta": {
                "stock_code": "601138",
                "stock_name": "Industrial Fulian",
                "current_price": 64.72,
                "change_pct": -1.2,
            },
            "summary": {
                "analysis_summary": "local context fallback summary",
                "action_label": "observe",
                "trend_prediction": "weak",
                "sentiment_score": 45,
            },
            "details": {"technical_analysis": "BBI is below price."},
            "strategy": {"ideal_buy": "wait for BBI confirmation"},
        },
    }

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor") as build_executor:
                with patch("src.services.analysis_service.AnalysisService") as service_cls:
                    service_cls.return_value.analyze_stock_lightweight.return_value = analysis_payload
                    client = TestClient(create_app(static_dir=tmp_path / "static"))
                    response = client.post(
                        "/api/v1/agent/chat/stream",
                        json={
                            "message": "how is it now",
                            "session_id": "s-context-stock",
                            "skills": ["stock_analyzer"],
                            "context": {
                                "stockCode": "601138",
                                "stockName": "Industrial Fulian",
                            },
                        },
                    )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert "local context fallback summary" in response.text
    build_executor.assert_not_called()


@pytest.mark.skip(reason="ordinary stock chat should keep analyzing and degrade only when dependencies fail")
def test_agent_chat_stream_stock_skill_without_code_fails_fast(tmp_path: Path) -> None:
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor") as build_executor:
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat/stream",
                    json={
                        "message": "how is it now",
                        "session_id": "s-missing-stock",
                        "skills": ["stock_analyzer"],
                    },
                )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert '"success": false' in response.text
    assert "stock_code_required" in response.text
    build_executor.assert_not_called()


def test_agent_chat_stream_keeps_stock_skill_on_full_executor_path(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.return_value = SimpleNamespace(
        success=True,
        content="full stock analysis result",
        error=None,
        total_steps=3,
    )
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor) as build_executor:
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat/stream",
                    json={
                        "message": "601138 how is it now",
                        "session_id": "s-stock-full",
                        "skills": ["stock_analyzer"],
                        "context": {"stockCode": "601138", "stockName": "Industrial Fulian"},
                    },
                )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert "full stock analysis result" in response.text
    build_executor.assert_called_once()
    assert executor.chat.call_args.kwargs["context"]["skills"] == ["stock_analyzer"]


def test_agent_chat_stream_returns_degraded_done_when_executor_raises_502(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.side_effect = RuntimeError("upstream returned HTML error page (HTTP 502 / 502)")
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor):
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat/stream",
                    json={
                        "message": "601138 how is it now",
                        "session_id": "s-stock-502",
                        "skills": ["stock_analyzer"],
                    },
                )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert '"success": false' in response.text
    assert "upstream_unavailable" in response.text
    assert "降级回答" in response.text


def test_agent_chat_returns_degraded_response_when_executor_returns_empty_content(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.return_value = SimpleNamespace(success=True, content="   ", error=None)
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor):
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat",
                    json={
                        "message": "601138 how is it now",
                        "session_id": "s-stock-empty-json",
                        "skills": ["stock_analyzer"],
                    },
                )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["content"].strip()
    assert payload["content"] != "无内容"
    assert payload["error"] == "empty_response: analysis_finished_without_content"


def test_agent_chat_stream_returns_degraded_done_when_executor_returns_empty_content(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.return_value = SimpleNamespace(
        success=True,
        content="无内容",
        error=None,
        total_steps=3,
    )
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor):
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat/stream",
                    json={
                        "message": "601138 how is it now",
                        "session_id": "s-stock-empty-stream",
                        "skills": ["stock_analyzer"],
                    },
                )

    assert response.status_code == 200
    assert '"type": "done"' in response.text
    assert '"success": false' in response.text
    assert "empty_response" in response.text
    assert "analysis_finished_without_content" in response.text
    assert "无内容" not in response.text


def test_agent_chat_returns_degraded_response_without_raw_html_when_executor_raises_502(tmp_path: Path) -> None:
    executor = MagicMock()
    executor.chat.side_effect = RuntimeError(
        "<!DOCTYPE html><html><head><title>502</title></head><body>Bad Gateway</body></html>"
    )
    config = SimpleNamespace(is_agent_available=lambda: True)

    with patch("api.middlewares.auth.is_auth_enabled", return_value=False):
        with patch("api.v1.endpoints.agent.get_config", return_value=config):
            with patch("api.v1.endpoints.agent._build_executor", return_value=executor):
                client = TestClient(create_app(static_dir=tmp_path / "static"))
                response = client.post(
                    "/api/v1/agent/chat",
                    json={
                        "message": "601138 how is it now",
                        "session_id": "s-stock-502-json",
                        "skills": ["stock_analyzer"],
                    },
                )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert "降级回答" in payload["content"]
    assert "upstream_unavailable" in payload["error"]
    assert "<html" not in payload["content"].lower()
    assert "<title" not in payload["error"].lower()
