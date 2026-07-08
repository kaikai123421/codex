# -*- coding: utf-8 -*-
"""Regression tests for stable web analysis task routing."""

from __future__ import annotations

import sys
import types
import unittest
from unittest.mock import MagicMock, patch

_orig_data_provider_base = sys.modules.get("data_provider.base")
_orig_data_provider = sys.modules.get("data_provider")

if _orig_data_provider_base is None:
    base_mod = types.ModuleType("data_provider.base")
    base_mod.canonical_stock_code = lambda x: (x or "").strip().upper()
    base_mod.is_bse_code = lambda x: str(x or "").strip().startswith(("4", "8"))
    base_mod.normalize_stock_code = lambda x: (x or "").strip().upper().removesuffix(".SH").removesuffix(".SZ")
    sys.modules["data_provider.base"] = base_mod

if _orig_data_provider is None:
    pkg_mod = types.ModuleType("data_provider")
    pkg_mod.base = sys.modules["data_provider.base"]
    sys.modules["data_provider"] = pkg_mod

from src.services.task_queue import AnalysisTaskQueue, TaskInfo, TaskStatus

if _orig_data_provider_base is None:
    sys.modules.pop("data_provider.base", None)
else:
    sys.modules["data_provider.base"] = _orig_data_provider_base

if _orig_data_provider is None:
    sys.modules.pop("data_provider", None)
else:
    sys.modules["data_provider"] = _orig_data_provider


class TaskQueueLightweightRouteTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._original_instance = AnalysisTaskQueue._instance
        AnalysisTaskQueue._instance = None

    def tearDown(self) -> None:
        queue = AnalysisTaskQueue._instance
        if queue is not None and queue is not self._original_instance:
            executor = getattr(queue, "_executor", None)
            if executor is not None and hasattr(executor, "shutdown"):
                executor.shutdown(wait=False)
        AnalysisTaskQueue._instance = self._original_instance

    def test_plain_web_analysis_task_uses_lightweight_route(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        task = TaskInfo(task_id="task-light", stock_code="601138", query_source="api")
        queue._tasks[task.task_id] = task
        queue._analyzing_stocks["601138"] = task.task_id

        service = MagicMock()
        service.analyze_stock_lightweight.return_value = {
            "stock_code": "601138",
            "stock_name": "工业富联",
            "report": "lightweight ok",
        }
        analysis_mod = types.ModuleType("src.services.analysis_service")
        analysis_mod.AnalysisService = MagicMock(return_value=service)

        with (
            patch.dict(sys.modules, {"src.services.analysis_service": analysis_mod}),
            patch("src.services.task_queue._dedupe_stock_code_key", side_effect=lambda code: code),
        ):
            result = queue._execute_task(
                "task-light",
                "601138",
                "detailed",
                False,
                notify=False,
                skills=None,
                report_language="zh",
            )

        self.assertEqual(result["stock_code"], "601138")
        service.analyze_stock_lightweight.assert_called_once_with(
            stock_code="601138",
            report_type="detailed",
            query_id="task-light",
            report_language="zh",
        )
        service.analyze_stock.assert_not_called()
        self.assertEqual(queue._tasks["task-light"].status, TaskStatus.COMPLETED)

    def test_skill_analysis_task_keeps_full_pipeline_route(self) -> None:
        queue = AnalysisTaskQueue(max_workers=1)
        task = TaskInfo(
            task_id="task-skill",
            stock_code="601138",
            query_source="api",
            skills=["stock_analyzer"],
        )
        queue._tasks[task.task_id] = task
        queue._analyzing_stocks["601138"] = task.task_id

        service = MagicMock()
        service.analyze_stock.return_value = {
            "stock_code": "601138",
            "stock_name": "工业富联",
            "report": "full ok",
        }
        analysis_mod = types.ModuleType("src.services.analysis_service")
        analysis_mod.AnalysisService = MagicMock(return_value=service)

        with (
            patch.dict(sys.modules, {"src.services.analysis_service": analysis_mod}),
            patch("src.services.task_queue._dedupe_stock_code_key", side_effect=lambda code: code),
        ):
            result = queue._execute_task(
                "task-skill",
                "601138",
                "detailed",
                False,
                notify=False,
                skills=["stock_analyzer"],
                report_language="zh",
            )

        self.assertEqual(result["stock_code"], "601138")
        service.analyze_stock.assert_called_once()
        service.analyze_stock_lightweight.assert_not_called()
        self.assertEqual(queue._tasks["task-skill"].status, TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
