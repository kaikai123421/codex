# -*- coding: utf-8 -*-
"""Regression tests for AnalysisService light mode routing."""

from __future__ import annotations

import re
from pathlib import Path

from src.services.analysis_service import AnalysisService


def test_render_environment_does_not_force_light_mode(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-test")
    monkeypatch.delenv("RENDER_ANALYSIS_LIGHT_MODE", raising=False)

    service = AnalysisService()

    assert service._render_light_mode_enabled() is False


def test_light_mode_requires_explicit_env_opt_in(monkeypatch) -> None:
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("RENDER_SERVICE_ID", "srv-test")
    monkeypatch.setenv("RENDER_ANALYSIS_LIGHT_MODE", "true")

    service = AnalysisService()

    assert service._render_light_mode_enabled() is True


def test_render_blueprint_disables_analysis_light_mode_by_default() -> None:
    render_yaml = Path(__file__).resolve().parents[1] / "render.yaml"
    text = render_yaml.read_text(encoding="utf-8")

    assert re.search(
        r"key:\s*RENDER_ANALYSIS_LIGHT_MODE\s*\n\s*value:\s*\"false\"",
        text,
    )


def test_plain_analyze_stock_requires_separate_light_mode_escape_hatch() -> None:
    service_source = (
        Path(__file__).resolve().parents[1] / "src" / "services" / "analysis_service.py"
    ).read_text(encoding="utf-8")

    assert "ALLOW_ANALYZE_STOCK_LIGHT_MODE" in service_source
    assert "if allow_analyze_stock_light_mode and self._render_light_mode_enabled()" in service_source
