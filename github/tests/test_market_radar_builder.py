from src.services.market_radar_builder import (
    build_external_radar,
    build_market_radar_payload,
)
import src.services.market_radar_builder as market_radar_builder
import pytest
import pandas as pd


@pytest.fixture(autouse=True)
def disable_live_market_fallbacks(monkeypatch):
    monkeypatch.setattr(market_radar_builder, "_request_tencent_quotes", lambda symbols: "")
    monkeypatch.setattr(market_radar_builder, "_fetch_yahoo_cn_market_snapshot", lambda: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_eastmoney_cn_market_snapshot", lambda: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_external_fallback_rows", lambda codes, fallback_names: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_cached_market_breadth", lambda report_date: {})


class FakeDataManager:
    def __init__(self, indices_by_region, market_stats=None, sector_rankings=None):
        self.indices_by_region = indices_by_region
        self.market_stats = market_stats or {}
        self.sector_rankings = sector_rankings

    def get_main_indices(self, region="cn"):
        return self.indices_by_region.get(region)

    def get_market_stats(self, *, purpose="unspecified"):
        return self.market_stats

    def get_sector_rankings(self, n=5):
        return self.sector_rankings


def test_build_external_radar_returns_only_impact_labels_and_missing_data():
    manager = FakeDataManager(
        {
            "us": [
                {"code": "IXIC", "name": "纳指", "change_pct": -0.55, "current": 25337.59},
                {"code": "VIX", "name": "VIX", "change_pct": 3.2, "current": 18.5},
            ],
            "kr": None,
            "jp": [{"code": "N225", "name": "日经225", "change_pct": 0.12, "current": 40200}],
        }
    )

    radar = build_external_radar(data_manager=manager)

    assert radar["scope_note"] == "外围只用于判断A股科技线风险偏好，不生成海外买卖建议。"
    groups = {group["region"]: group for group in radar["groups"]}
    assert groups["us"]["impact"] == "negative"
    assert groups["jp"]["impact"] == "neutral"
    assert groups["kr"]["impact"] == "missing"
    assert groups["kr"]["items"][0]["data_status"] == "missing"
    assert "action" not in groups["us"]
    assert all("action" not in item for group in radar["groups"] for item in group["items"])


def test_build_market_radar_payload_preserves_a_share_scope_and_empty_sections():
    payload = build_market_radar_payload(
        date="2026-07-02",
        data_manager=FakeDataManager({}),
        account={"position_pct": 78.5, "risk_light": "defense"},
    )

    assert payload["trader_scope"] == "a_share_only"
    assert payload["date"] == "2026-07-02"
    assert payload["account"]["position_pct"] == 78.5
    assert payload["cn_market"]["risk_light"] == "defense"
    assert payload["portfolio_matrix"] == []
    assert payload["trade_timeline"] == []
    assert payload["next_session_plan"] == []


def test_build_market_radar_payload_backfills_cn_market_from_data_manager():
    payload = build_market_radar_payload(
        date="2026-07-02",
        data_manager=FakeDataManager(
            {
                "cn": [
                    {"code": "000001", "name": "上证指数", "current": 4027.26, "change_pct": -2.26},
                    {"code": "399001", "name": "深证成指", "current": 15782.22, "change_pct": -3.44},
                    {"code": "399006", "name": "创业板指", "current": 4194.21, "change_pct": -4.07},
                ],
            },
            market_stats={
                "up_count": 790,
                "down_count": 4676,
                "flat_count": 120,
                "limit_up_count": 31,
                "limit_down_count": 66,
                "total_amount": 35754,
            },
        ),
        account={"risk_light": "balanced"},
    )

    cn_market = payload["cn_market"]
    assert cn_market["risk_light"] == "danger"
    assert cn_market["data_status"] == "partial"
    assert len(cn_market["indices"]) == 3
    assert cn_market["breadth"]["down_count"] == 4676
    assert cn_market["summary"].startswith("A股雷达已接入")


def test_external_radar_does_not_duplicate_korea_or_japan_aliases():
    radar = build_external_radar(
        data_manager=FakeDataManager(
            {
                "kr": [
                    {"code": "KS11", "name": "KOSPI", "change_pct": -0.2, "current": 3000},
                    {"code": "KQ11", "name": "KOSDAQ", "change_pct": -0.4, "current": 800},
                ],
                "jp": [
                    {"code": "N225", "name": "日经225", "change_pct": 0.2, "current": 40200},
                    {"code": "TOPX", "name": "TOPIX", "change_pct": 0.1, "current": 2800},
                ],
            }
        )
    )

    groups = {group["region"]: group for group in radar["groups"]}
    assert [item["code"] for item in groups["kr"]["items"]] == ["KS11", "KQ11"]
    assert [item["code"] for item in groups["jp"]["items"]] == ["N225", "TOPX"]
    assert all(item["data_status"] == "ok" for item in groups["kr"]["items"])
    assert all(item["data_status"] == "ok" for item in groups["jp"]["items"])


def test_external_radar_carries_source_and_data_date_when_available():
    radar = build_external_radar(
        data_manager=FakeDataManager(
            {
                "us": [
                    {
                        "code": "IXIC",
                        "name": "纳指",
                        "change_pct": -0.55,
                        "current": 25337.59,
                        "source": "Yahoo Finance",
                        "data_date": "2026-07-02",
                    },
                ],
            }
        )
    )

    us_group = {group["region"]: group for group in radar["groups"]}["us"]
    ixic = next(item for item in us_group["items"] if item["code"] == "IXIC")
    assert ixic["source"] == "Yahoo Finance"
    assert ixic["data_date"] == "2026-07-02"
    assert us_group["note"]


def test_cn_market_merges_manual_placeholders_with_fetched_data():
    payload = build_market_radar_payload(
        date="2026-07-02",
        data_manager=FakeDataManager(
            {
                "cn": [
                    {"code": "000001", "name": "上证指数", "current": 4027.26, "change_pct": -2.26},
                    {"code": "399001", "name": "深证成指", "current": 15782.22, "change_pct": -3.44},
                    {"code": "399006", "name": "创业板指", "current": 4194.21, "change_pct": -4.07},
                    {"code": "000688", "name": "科创50", "current": 1987.29, "change_pct": -7.69},
                ],
            },
            market_stats={
                "up_count": 790,
                "down_count": 4676,
                "total_amount": 35754,
            },
        ),
        cn_market={
            "risk_light": "defense",
            "indices": [
                {"code": "000001", "name": "上证指数", "change_pct": -1.60},
                {"code": "399001", "name": "深证成指", "data_status": "missing"},
                {"code": "399006", "name": "创业板指", "data_status": "missing"},
                {"code": "000688", "name": "科创50", "data_status": "missing"},
            ],
            "breadth": {"data_status": "missing"},
        },
    )

    cn_market = payload["cn_market"]
    by_code = {item["code"]: item for item in cn_market["indices"]}
    assert by_code["000001"]["current"] == 4027.26
    assert by_code["000001"]["change_pct"] == -1.60
    assert by_code["399001"]["current"] == 15782.22
    assert by_code["399006"]["data_status"] == "ok"
    assert cn_market["breadth"]["up_count"] == 790
    assert cn_market["breadth"]["down_count"] == 4676


def test_cn_market_normalizes_provider_aliases_and_focus_sectors():
    payload = build_market_radar_payload(
        date="2026-07-02",
        data_manager=FakeDataManager(
            {
                "cn": [
                    {
                        "symbol": "000001",
                        "名称": "上证指数",
                        "latest_price": "4,027.26",
                        "pct_chg": "-2.26%",
                        "turnover": "35754亿",
                    },
                ],
            },
            market_stats={
                "上涨家数": "790",
                "下跌家数": "4676",
                "两市成交额": "35754亿",
                "主力净流入": "-1986.64",
            },
            sector_rankings=(
                [{"name": "面板", "change_pct": 2.2}],
                [
                    {"name": "通信设备", "change_pct": -2.1},
                    {"name": "半导体", "change_pct": -4.8},
                ],
            ),
        ),
    )

    cn_market = payload["cn_market"]
    index = cn_market["indices"][0]
    assert index["current"] == 4027.26
    assert index["change_pct"] == -2.26
    assert index["amount"] == 35754
    assert cn_market["breadth"]["up_count"] == 790
    assert cn_market["breadth"]["main_net_inflow"] == -1986.64
    sectors = {item["name"]: item for item in cn_market["sectors"]}
    assert sectors["通信/5G"]["change_pct"] == -2.1
    assert sectors["通信/5G"]["strength"] == "weak"
    assert sectors["面板/京东方链"]["change_pct"] == 2.2
def test_cn_market_uses_eastmoney_push2_fallback_for_funds_and_focus_sectors(monkeypatch):
    monkeypatch.setattr(
        market_radar_builder,
        "_fetch_eastmoney_cn_market_snapshot",
        lambda: {
            "indices": [
                {"code": "000001", "name": "上证指数", "current": 4028.9, "change_pct": -2.03},
                {"code": "399001", "name": "深证成指", "current": 15498.81, "change_pct": -3.85},
            ],
            "breadth": {
                "main_net_inflow": -1217.96,
                "source": "eastmoney_push2_index_f62",
            },
            "sectors": [
                {
                    "name": "通信/5G",
                    "matched_name": "通信ETF国泰",
                    "change_pct": -8.27,
                    "fund_flow": -13.60,
                    "strength": "weak",
                    "source": "eastmoney_push2_proxy",
                },
                {
                    "name": "AI服务器/工业富联",
                    "matched_name": "工业富联",
                    "change_pct": -8.54,
                    "fund_flow": -23.57,
                    "strength": "weak",
                    "source": "eastmoney_push2_proxy",
                },
            ],
        },
    )

    payload = build_market_radar_payload(
        date="2026-07-02",
        data_manager=FakeDataManager({}),
    )

    cn_market = payload["cn_market"]
    assert {item["code"] for item in cn_market["indices"]} == {"000001", "399001"}
    assert cn_market["breadth"]["main_net_inflow"] == -1217.96
    sectors = {item["name"]: item for item in cn_market["sectors"]}
    assert sectors["通信/5G"]["fund_flow"] == -13.60
    assert sectors["AI服务器/工业富联"]["strength"] == "weak"


def test_cn_market_prefers_fresh_eastmoney_funds_over_same_day_cache(monkeypatch):
    monkeypatch.setattr(
        market_radar_builder,
        "_fetch_tencent_cn_market_snapshot",
        lambda: {
            "indices": [{"code": "000001", "name": "上证指数", "current": 4054.0, "change_pct": 0.62}],
            "breadth": {
                "total_amount": 24979.85,
                "source": "tencent_quote_index_amount",
                "data_status": "partial",
                "data_date": "2026-07-03 13:45:36",
            },
            "sectors": [],
        },
    )
    monkeypatch.setattr(
        market_radar_builder,
        "_fetch_cached_market_breadth",
        lambda report_date: {
            "up_count": 3826,
            "down_count": 1569,
            "main_net_inflow": -122.45,
            "source": "analysis_history_same_day_cache",
            "data_status": "stale",
        },
    )
    monkeypatch.setattr(
        market_radar_builder,
        "_fetch_eastmoney_cn_market_snapshot",
        lambda: {
            "indices": [],
            "breadth": {
                "main_net_inflow": -26.44,
                "source": "eastmoney_push2_index_f62",
                "fund_flow_note": "东方财富指数口径",
            },
            "sectors": [],
        },
    )

    payload = build_market_radar_payload(
        date="2026-07-03",
        data_manager=FakeDataManager({}),
    )

    breadth = payload["cn_market"]["breadth"]
    assert breadth["up_count"] == 3826
    assert breadth["down_count"] == 1569
    assert breadth["main_net_inflow"] == -26.44
    assert "eastmoney_push2_index_f62" in breadth["source"]
    assert "analysis_history_same_day_cache" in breadth["source"]


def test_cn_market_uses_tencent_quote_fallback_when_eastmoney_is_unavailable(monkeypatch):
    monkeypatch.setattr(market_radar_builder, "_fetch_yahoo_cn_market_snapshot", lambda: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_eastmoney_cn_market_snapshot", lambda: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_cached_market_breadth", lambda report_date: {})
    monkeypatch.setattr(
        market_radar_builder,
        "_request_tencent_quotes",
        lambda symbols: "\n".join(
            [
                'v_sh000001="1~上证指数~000001~4028.90~4112.45~4054.09~~~~~~~~~~~~~~20260702161418~-83.55~-2.03~4093.68~4019.21~4028.90/656233612/1577183734747";',
                'v_sz399001="51~深证成指~399001~15498.81~16119.17~15729.92~~~~~~~~~~~~~~20260702161445~-620.36~-3.85~15886.70~15453.52~15498.81/857269760/1873367630201";',
                'v_sh515880="1~通信ETF~515880~1.576~1.714~1.618~~~~~~~~~~~~~~20260702150003~-0.138~-8.05~1.640~1.560~1.576/8400000/13238400";',
                'v_sh601138="1~工业富联~601138~64.020~70.000~68.000~~~~~~~~~~~~~~20260702150003~-5.980~-8.54~70.100~63.900~64.020/2000000/128040000";',
            ]
        ),
    )

    payload = build_market_radar_payload(
        date="2026-07-02",
        data_manager=FakeDataManager({}),
    )

    cn_market = payload["cn_market"]
    by_code = {item["code"]: item for item in cn_market["indices"]}
    assert by_code["000001"]["source"] == "tencent_quote"
    assert by_code["000001"]["current"] == 4028.90
    assert by_code["399001"]["change_pct"] == -3.85
    assert cn_market["breadth"]["data_status"] == "partial"
    assert cn_market["breadth"]["total_amount"] == 34505.52
    sectors = {item["name"]: item for item in cn_market["sectors"]}
    assert sectors["通信/5G"]["matched_name"] == "通信ETF国泰"
    assert sectors["通信/5G"]["change_pct"] == -8.05
    assert sectors["AI服务器/工业富联"]["matched_name"] == "工业富联"


def test_portfolio_matrix_is_enriched_with_daily_and_weekly_bbi(monkeypatch):
    history = pd.DataFrame(
        {
            "date": pd.date_range("2025-10-01", periods=180, freq="B"),
            "close": [10 + index * 0.5 for index in range(180)],
        }
    )
    monkeypatch.setattr(
        market_radar_builder,
        "_load_bbi_history",
        lambda code, report_date: (history, "test_history"),
    )

    payload = build_market_radar_payload(
        date="2026-07-03",
        data_manager=FakeDataManager({}),
        portfolio_matrix=[
            {
                "code": "601138",
                "name": "工业富联",
                "action": "hold",
                "actionLabel": "持有",
                "keyLevels": ["支撑 64.00"],
            }
        ],
    )

    item = payload["portfolio_matrix"][0]
    assert item["bbi_position"] == "above_weekly_bbi"
    assert item["bbiPosition"] == "above_weekly_bbi"
    assert item["bbi_details"]["daily"]["value"] is not None
    assert item["bbi_details"]["weekly"]["value"] is not None
    assert item["bbi_details"]["source"] == "test_history"
    assert any("日BBI" in level for level in item["keyLevels"])
    assert any("周BBI" in level for level in item["keyLevels"])


def test_portfolio_matrix_records_bbi_missing_reason_when_history_unavailable(monkeypatch):
    monkeypatch.setattr(
        market_radar_builder,
        "_load_bbi_history",
        lambda code, report_date: (None, "none"),
    )

    payload = build_market_radar_payload(
        date="2026-07-03",
        data_manager=FakeDataManager({}),
        portfolio_matrix=[
            {
                "code": "515880",
                "name": "通信ETF",
                "action": "watch",
                "actionLabel": "观察",
            }
        ],
    )

    item = payload["portfolio_matrix"][0]
    assert item["bbi_position"] == "missing"
    assert item["bbiPosition"] == "missing"
    assert item["bbi_missing_reason"] == "未取得足够K线，不能计算BBI"
    assert "BBI: 未取得" in item["keyLevels"]
