from scripts.create_report_20260702_close_dashboard import _build_data_reliability_summary


def test_data_reliability_summary_does_not_mark_filled_breadth_as_missing():
    market_radar = {
        "cn_market": {
            "indices": [
                {"name": "上证指数", "current": 4028.9, "change_pct": -1.6, "data_status": "ok"},
            ],
            "breadth": {
                "up_count": 2219,
                "down_count": 3161,
                "total_amount": 34505.52,
                "fund_flow_status": "missing",
            },
            "sectors": [
                {"name": "通信/5G", "current": 1.576, "change_pct": -8.27, "data_status": "ok"},
            ],
        },
    }

    summary = _build_data_reliability_summary(market_radar)

    assert "涨跌家数" in summary["verified"]
    assert "成交额" in summary["verified"]
    assert "涨跌家数" not in summary["missing"]
    assert "成交额" not in summary["missing"]
    assert "主力/超大单/大单净流入" in summary["missing"]
