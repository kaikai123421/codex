# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
from unittest.mock import patch


class ReportKlineChartTestCase(unittest.TestCase):
    def test_virtual_report_codes_do_not_fetch_history(self) -> None:
        from src.services.report_kline_chart import build_report_kline_chart

        for code in ("PORTFOLIO", "MARKET"):
            with self.subTest(code=code):
                with patch("src.services.report_kline_chart.load_history_df") as mock_load:
                    self.assertIsNone(build_report_kline_chart(code))
                    mock_load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
