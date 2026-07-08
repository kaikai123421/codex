# -*- coding: utf-8 -*-
"""Regression tests for AnalysisService light mode routing."""

from __future__ import annotations

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
