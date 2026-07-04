import src.services.market_radar_builder as market_radar_builder


def test_tencent_quote_rows_prefer_clean_dashboard_labels_over_garbled_source_names():
    index = market_radar_builder._tencent_quote_to_index(
        "000001",
        "\u4e0a\u8bc1\u6307\u6570",
        {
            "name": "\ufffd\ufffd\u05a4\u05b8\ufffd\ufffd",
            "current": 4056.78,
            "change_pct": 0.69,
            "data_date": "2026-07-03 12:05:00",
        },
    )
    sector = market_radar_builder._tencent_quote_to_focus_sector(
        "\u901a\u4fe1/5G",
        "515880",
        "\u901a\u4fe1ETF",
        {
            "name": "\u034d\ufffd\ufffdETF\ufffd\ufffd\ufffd",
            "current": 1.614,
            "change_pct": 2.41,
            "data_date": "2026-07-03 12:05:58",
        },
    )

    assert index["name"] == "\u4e0a\u8bc1\u6307\u6570"
    assert sector["name"] == "\u901a\u4fe1/5G"
    assert sector["matched_name"] == "\u901a\u4fe1ETF\u56fd\u6cf0"


def test_cn_market_payload_enriches_breadth_counts_when_tencent_only_has_amount(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        market_radar_builder,
        "_fetch_tencent_cn_market_snapshot",
        lambda: {
            "indices": [{"code": "000001", "name": "\u4e0a\u8bc1\u6307\u6570", "current": 4060.0, "change_pct": 0.8}],
            "breadth": {"total_amount": 22000.0, "source": "tencent_quote_index_amount"},
            "sectors": [],
        },
    )
    monkeypatch.setattr(market_radar_builder, "_fetch_yahoo_cn_market_snapshot", lambda: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_eastmoney_cn_market_snapshot", lambda: {})
    monkeypatch.setattr(market_radar_builder, "_fetch_cached_market_breadth", lambda report_date: {})
    monkeypatch.setattr(market_radar_builder, "_build_focus_sector_payload", lambda manager: [])

    def fake_stats(manager, *, timeout_seconds=4):
        captured["timeout_seconds"] = timeout_seconds
        return {
            "up_count": 3738,
            "down_count": 1662,
            "flat_count": 115,
            "source": "akshare_fallback",
        }

    monkeypatch.setattr(market_radar_builder, "_safe_get_market_stats", fake_stats)

    payload = market_radar_builder._build_cn_market_payload(
        manager=object(),
        account_payload={},
        report_date="2026-07-03",
        market_stats_timeout_seconds=35,
    )

    assert captured["timeout_seconds"] == 35
    assert payload["breadth"]["total_amount"] == 22000.0
    assert payload["breadth"]["up_count"] == 3738
    assert payload["breadth"]["down_count"] == 1662


def test_merge_row_preserves_all_sources_when_fallback_contributes_values():
    merged = market_radar_builder._merge_row(
        {
            "total_amount": 22000.0,
            "source": "tencent_quote_index_amount",
            "data_status": "partial",
        },
        {
            "main_net_inflow": -122.45,
            "source": "eastmoney_push2_index_f62",
            "fund_flow_note": "东方财富指数口径",
        },
    )

    assert merged["main_net_inflow"] == -122.45
    assert "tencent_quote_index_amount" in merged["source"]
    assert "eastmoney_push2_index_f62" in merged["source"]
