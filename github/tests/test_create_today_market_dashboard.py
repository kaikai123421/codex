import json
from types import SimpleNamespace

from scripts.create_today_market_dashboard import (
    _build_reused_inputs,
    _load_latest_dashboard_snapshot,
    build_today_dashboard_artifact,
)
from src.services.today_market_dashboard_service import save_today_market_dashboard


class FakeDb:
    def __init__(self, records):
        self.records = records
        self.saved_calls = []

    def get_analysis_history_paginated(self, **kwargs):
        return self.records, len(self.records)

    def save_analysis_history(self, result, query_id, report_type, news_content, context_snapshot, save_snapshot):
        self.saved_calls.append(
            {
                "result": result,
                "query_id": query_id,
                "report_type": report_type,
                "news_content": news_content,
                "context_snapshot": context_snapshot,
                "save_snapshot": save_snapshot,
            }
        )
        return 42


def _record(snapshot):
    return SimpleNamespace(context_snapshot=json.dumps(snapshot, ensure_ascii=False))


def test_load_latest_dashboard_snapshot_skips_legacy_records():
    legacy = _record({"report_kind": "old"})
    dashboard = _record({"market_radar": {"date": "2026-07-02", "account": {"position_pct": 78.5}}})

    snapshot = _load_latest_dashboard_snapshot(FakeDb([legacy, dashboard]))

    assert snapshot["market_radar"]["date"] == "2026-07-02"


def test_reused_inputs_mark_stale_snapshot_and_drop_old_trade_timeline_for_new_day():
    snapshot = {
        "market_radar": {
            "date": "2026-07-02",
            "account": {"position_pct": 78.5, "cash": 10896.04},
            "portfolio_matrix": [{"code": "515880", "name": "通信ETF"}],
            "trade_timeline": [{"time": "13:20", "target": "通信ETF"}],
            "next_session_plan": [{"phase": "10:30"}],
        }
    }

    reused = _build_reused_inputs(snapshot, trade_date="2026-07-03")

    assert reused["account"]["data_status"] == "stale_from_previous_report"
    assert reused["portfolio_matrix"][0]["data_status"] == "stale_from_previous_report"
    assert reused["trade_timeline"] == []
    assert reused["next_session_plan"] == []


def test_build_today_dashboard_artifact_persists_online_market_radar_context():
    snapshot = {
        "market_radar": {
            "date": "2026-07-02",
            "account": {"position_pct": 78.5},
            "portfolio_matrix": [{"code": "515880", "name": "通信ETF"}],
        }
    }
    captured_kwargs = {}

    def fake_market_builder(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "date": kwargs["date"],
            "account": kwargs["account"],
            "cn_market": {
                "indices": [{"code": "000001", "name": "上证指数", "current": 4056.78, "change_pct": 0.69}],
                "breadth": {"total_amount": 20597.05, "main_net_inflow": -122.45},
                "sectors": [{"name": "通信/5G", "current": 1.614, "change_pct": 2.41}],
            },
            "external_radar": {"groups": []},
            "portfolio_matrix": kwargs["portfolio_matrix"],
            "trade_timeline": kwargs["trade_timeline"],
            "next_session_plan": kwargs["next_session_plan"],
        }

    artifact = build_today_dashboard_artifact(
        trade_date="2026-07-03",
        latest_snapshot=snapshot,
        market_builder=fake_market_builder,
        generated_at="2026-07-03T12:30:00",
    )

    assert artifact.context_snapshot["market_radar"]["date"] == "2026-07-03"
    assert captured_kwargs["market_stats_timeout_seconds"] >= 30
    assert artifact.context_snapshot["market_radar"]["cn_market"]["indices"][0]["current"] == 4056.78
    assert artifact.context_snapshot["marketRadar"] is artifact.context_snapshot["market_radar"]
    assert artifact.result.dashboard["market_radar"] is artifact.context_snapshot["market_radar"]


def test_build_today_dashboard_artifact_marks_post_close_snapshot_status():
    def fake_market_builder(**kwargs):
        return {
            "date": kwargs["date"],
            "cn_market": {"indices": [], "breadth": {}, "sectors": [], "data_status": "missing"},
            "external_radar": {"groups": []},
            "portfolio_matrix": [],
            "trade_timeline": [],
            "next_session_plan": [],
        }

    artifact = build_today_dashboard_artifact(
        trade_date="2026-07-03",
        latest_snapshot={},
        market_builder=fake_market_builder,
        generated_at="2026-07-03T16:10:00",
    )

    assert artifact.context_snapshot["data_reliability"]["session_status"] == "post_close"
    assert artifact.context_snapshot["market_radar"]["cn_market"]["session_status"] == "post_close"
    assert "收盘后快照" in artifact.markdown
    assert artifact.result.dashboard["core_conclusion"]["time_sensitivity"] == "post_close"
    assert artifact.result.trend_prediction == "收盘后雷达刷新"
    assert "收盘后先看当天收盘行情" in artifact.markdown
    assert "盘中先看真实行情" not in artifact.markdown


def test_build_today_dashboard_artifact_exposes_same_day_stale_market_freshness():
    def fake_market_builder(**kwargs):
        return {
            "date": kwargs["date"],
            "cn_market": {
                "indices": [
                    {
                        "code": "000001",
                        "name": "上证指数",
                        "current": 4056.78,
                        "change_pct": 0.69,
                        "data_status": "stale",
                        "data_date": "2026-07-03 12:05:00",
                    }
                ],
                "breadth": {
                    "total_amount": 20597.05,
                    "data_status": "stale",
                    "data_date": "2026-07-03 12:05:00",
                },
                "sectors": [],
                "data_status": "partial",
            },
            "external_radar": {"groups": []},
            "portfolio_matrix": [],
            "trade_timeline": [],
            "next_session_plan": [],
        }

    artifact = build_today_dashboard_artifact(
        trade_date="2026-07-03",
        latest_snapshot={},
        market_builder=fake_market_builder,
        generated_at="2026-07-03T12:54:00",
    )

    reliability = artifact.context_snapshot["data_reliability"]
    assert reliability["market_freshness"] == "same_day_stale"
    assert reliability["market_freshness_label"] == "今日滞后数据"
    assert artifact.context_snapshot["market_radar"]["cn_market"]["market_freshness"] == "same_day_stale"
    assert "same_day_stale" in artifact.markdown


def test_save_today_market_dashboard_saves_market_radar_history_record():
    db = FakeDb([
        _record({
            "market_radar": {
                "date": "2026-07-02",
                "account": {"position_pct": 78.5},
                "portfolio_matrix": [{"code": "515880", "name": "通信ETF"}],
            }
        })
    ])

    def fake_market_builder(**kwargs):
        return {
            "date": kwargs["date"],
            "account": kwargs["account"],
            "cn_market": {
                "indices": [{"code": "000001", "name": "上证指数", "current": 4056.78, "change_pct": 0.69}],
                "breadth": {"total_amount": 20597.05, "main_net_inflow": -122.45},
                "sectors": [{"name": "通信/5G", "current": 1.614, "change_pct": 2.41}],
            },
            "external_radar": {"groups": [{"region": "US", "title": "美股", "impact": "中性"}]},
            "portfolio_matrix": kwargs["portfolio_matrix"],
            "trade_timeline": kwargs["trade_timeline"],
            "next_session_plan": kwargs["next_session_plan"],
        }

    history_id, artifact = save_today_market_dashboard(
        db,
        trade_date="2026-07-03",
        market_builder=fake_market_builder,
        generated_at="2026-07-03T14:50:00",
    )

    assert history_id == 42
    assert db.saved_calls
    saved = db.saved_calls[0]
    assert saved["query_id"] == "today_market_dashboard_20260703"
    assert saved["report_type"] == "detailed"
    assert saved["save_snapshot"] is True
    assert saved["context_snapshot"]["market_radar"]["date"] == "2026-07-03"
    assert saved["context_snapshot"]["marketRadar"] is saved["context_snapshot"]["market_radar"]
    assert artifact.result.dashboard["market_radar"]["cn_market"]["indices"][0]["current"] == 4056.78
