# -*- coding: utf-8 -*-
"""Build the A-share trader market radar payload used by the web dashboard.

The radar is deliberately scoped to A-share trading. External markets are
reduced to risk-impact labels so the report can use them as context without
turning into overseas trading advice.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Mapping
from datetime import date, datetime
import json
from pathlib import Path
import sqlite3
import threading
import time
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote, urlencode
from urllib.request import ProxyHandler, Request, build_opener, urlopen


EXTERNAL_SCOPE_NOTE = "外围只用于判断A股科技线风险偏好，不生成海外买卖建议。"

_EXTERNAL_GROUPS = {
    "us": {
        "title": "美股科技",
        "wanted": ("IXIC", "NDX", "SOX", "QQQ", "SOXX", "VIX"),
        "fallback_names": {
            "IXIC": "纳指",
            "NDX": "纳指100",
            "SOX": "费半/SOX",
            "QQQ": "QQQ",
            "SOXX": "SOXX",
            "VIX": "VIX",
        },
    },
    "kr": {
        "title": "韩国科技",
        "wanted": ("KS11", "KQ11"),
        "fallback_names": {
            "KS11": "KOSPI",
            "KQ11": "KOSDAQ",
        },
    },
    "jp": {
        "title": "日本风险偏好",
        "wanted": ("N225", "TOPX"),
        "fallback_names": {
            "N225": "日经225",
            "TOPX": "TOPIX",
        },
    },
}

_EASTMONEY_CACHE_PATH = Path(__file__).resolve().parents[2] / "data" / "market_radar_eastmoney_cache.json"
_ANALYSIS_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "stock_analysis.db"

_YAHOO_EXTERNAL_SYMBOLS = {
    "IXIC": "^IXIC",
    "NDX": "^NDX",
    "SOX": "^SOX",
    "QQQ": "QQQ",
    "SOXX": "SOXX",
    "VIX": "^VIX",
    "KS11": "^KS11",
    "KQ11": "^KQ11",
    "N225": "^N225",
    # Yahoo does not expose a stable TOPIX index symbol in this environment.
    # 1306.T is a TOPIX ETF proxy, so reports must treat it as risk context only.
    "TOPX": "1306.T",
}

_YAHOO_CN_INDEX_SYMBOLS = (
    ("000001", "上证指数", "000001.SS"),
    ("399001", "深证成指", "399001.SZ"),
    ("399006", "创业板指", "399006.SZ"),
    ("000688", "科创50", "000688.SS"),
    ("000016", "上证50", "000016.SS"),
    ("000300", "沪深300", "000300.SS"),
)

_YAHOO_FOCUS_SECTOR_SYMBOLS = (
    ("通信/5G", "515880", "通信ETF国泰", "515880.SS"),
    ("面板/京东方链", "000725", "京东方A", "000725.SZ"),
    ("AI服务器/工业富联", "601138", "工业富联", "601138.SS"),
    ("消费电子", "159732", "消费电子ETF华夏", "159732.SZ"),
    ("半导体", "515050", "半导体ETF", "515050.SS"),
)

_TENCENT_CN_INDEX_SYMBOLS = (
    ("sh000001", "000001", "上证指数"),
    ("sz399001", "399001", "深证成指"),
    ("sz399006", "399006", "创业板指"),
    ("sh000688", "000688", "科创50"),
    ("sh000016", "000016", "上证50"),
    ("sh000300", "000300", "沪深300"),
)

_TENCENT_FOCUS_SECTOR_SYMBOLS = (
    ("sh515880", "通信/5G", "515880", "通信ETF"),
    ("sz000725", "面板/京东方链", "000725", "京东方A"),
    ("sh601138", "AI服务器/工业富联", "601138", "工业富联"),
    ("sz159732", "消费电子", "159732", "消费电子ETF华夏"),
    ("sh515050", "半导体", "515050", "半导体ETF"),
)

_TIMEOUT_SENTINEL = object()
_BBI_WINDOWS = (3, 6, 12, 24)
_BBI_NEAR_THRESHOLD_PCT = 1.0

_TENCENT_CLEAN_INDEX_NAMES = {
    "000001": "\u4e0a\u8bc1\u6307\u6570",
    "399001": "\u6df1\u8bc1\u6210\u6307",
    "399006": "\u521b\u4e1a\u677f\u6307",
    "000688": "\u79d1\u521b50",
    "000016": "\u4e0a\u8bc150",
    "000300": "\u6caa\u6df1300",
}

_TENCENT_CLEAN_FOCUS_LABELS = {
    "515880": "\u901a\u4fe1/5G",
    "000725": "\u9762\u677f/\u4eac\u4e1c\u65b9\u94fe",
    "601138": "AI\u670d\u52a1\u5668/\u5de5\u4e1a\u5bcc\u8054",
    "159732": "\u6d88\u8d39\u7535\u5b50",
    "515050": "\u534a\u5bfc\u4f53",
}

_TENCENT_CLEAN_FOCUS_NAMES = {
    "515880": "\u901a\u4fe1ETF\u56fd\u6cf0",
    "000725": "\u4eac\u4e1c\u65b9A",
    "601138": "\u5de5\u4e1a\u5bcc\u8054",
    "159732": "\u6d88\u8d39\u7535\u5b50ETF\u534e\u590f",
    "515050": "\u534a\u5bfc\u4f53ETF",
}


def build_market_radar_payload(
    *,
    date: Optional[str] = None,
    data_manager: Any = None,
    account: Optional[Mapping[str, Any]] = None,
    cn_market: Optional[Mapping[str, Any]] = None,
    portfolio_matrix: Optional[Iterable[Mapping[str, Any]]] = None,
    trade_timeline: Optional[Iterable[Mapping[str, Any]]] = None,
    next_session_plan: Optional[Iterable[Mapping[str, Any]]] = None,
    market_stats_timeout_seconds: float = 4,
) -> Dict[str, Any]:
    """Return a normalized market_radar payload for report context_snapshot."""
    manager = data_manager or _default_data_manager()
    account_payload = _sanitize_mapping(account)
    cn_payload = _sanitize_mapping(cn_market)
    if not cn_payload:
        cn_payload = _build_cn_market_payload(
            manager,
            account_payload,
            report_date=date,
            market_stats_timeout_seconds=market_stats_timeout_seconds,
        )
    else:
        fetched_cn_payload = _build_cn_market_payload(
            manager,
            account_payload,
            report_date=date,
            market_stats_timeout_seconds=market_stats_timeout_seconds,
        )
        cn_payload = _merge_cn_market_payload(cn_payload, fetched_cn_payload)
        if "risk_light" not in cn_payload and account_payload.get("risk_light"):
            cn_payload["risk_light"] = account_payload["risk_light"]

    return {
        "version": 1,
        "date": date or _today_text(),
        "trader_scope": "a_share_only",
        "account": account_payload,
        "cn_market": cn_payload,
        "external_radar": build_external_radar(data_manager=manager),
        "portfolio_matrix": _enrich_portfolio_matrix_with_bbi(portfolio_matrix or [], report_date=date),
        "trade_timeline": [_sanitize_mapping(item) for item in (trade_timeline or [])],
        "next_session_plan": [_sanitize_mapping(item) for item in (next_session_plan or [])],
    }


def _enrich_portfolio_matrix_with_bbi(
    rows: Iterable[Mapping[str, Any]],
    *,
    report_date: Optional[str],
) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for raw in rows:
        item = _sanitize_mapping(raw)
        if not item:
            continue
        code = _safe_text(_first_present(item, ("code", "symbol", "stock_code", "stockCode")))
        bbi_details = _build_bbi_details(code, report_date=report_date)
        _apply_bbi_details(item, bbi_details)
        enriched.append(item)
    return enriched


def _build_bbi_details(code: str, *, report_date: Optional[str]) -> Dict[str, Any]:
    if not code:
        return {
            "position": "missing",
            "missing_reason": "缺少证券代码，不能计算BBI",
            "daily": {"value": None, "status": "missing"},
            "weekly": {"value": None, "status": "missing"},
            "source": "missing_code",
        }

    df, source = _load_bbi_history(code, report_date)
    close = _close_series_from_history(df)
    if close is None or close.empty:
        return {
            "position": "missing",
            "missing_reason": "未取得足够K线，不能计算BBI",
            "daily": {"value": None, "status": "missing"},
            "weekly": {"value": None, "status": "missing"},
            "source": source or "none",
        }

    daily = _latest_bbi_snapshot(close)
    weekly_close = _weekly_close_series(close)
    weekly = _latest_bbi_snapshot(weekly_close) if weekly_close is not None else {
        "value": None,
        "status": "missing",
        "missing_reason": "缺少日期索引，不能计算周BBI",
    }
    current = _safe_float(close.iloc[-1])
    position = _infer_bbi_position(current, daily.get("value"), weekly.get("value"))

    missing_reasons = [
        _safe_text(daily.get("missing_reason")),
        _safe_text(weekly.get("missing_reason")),
    ]
    missing_reason = "；".join(reason for reason in missing_reasons if reason)
    if position == "missing" and not missing_reason:
        missing_reason = "未取得足够K线，不能计算BBI"

    return {
        "position": position,
        "current": current,
        "daily": daily,
        "weekly": weekly,
        "source": source or "unknown",
        "missing_reason": missing_reason or None,
    }


def _load_bbi_history(code: str, report_date: Optional[str]) -> tuple[Any, str]:
    try:
        from src.services.history_loader import load_history_df
    except Exception:
        return None, "history_loader_unavailable"

    target_date = None
    if report_date:
        try:
            target_date = datetime.strptime(str(report_date)[:10], "%Y-%m-%d").date()
        except Exception:
            target_date = None
    try:
        return load_history_df(code, days=180, target_date=target_date)
    except Exception:
        return None, "history_fetch_failed"


def _close_series_from_history(df: Any) -> Any:
    if df is None or getattr(df, "empty", True):
        return None
    try:
        import pandas as pd
    except Exception:
        return None

    close_col = None
    for candidate in ("close", "Close", "收盘", "收盘价"):
        if candidate in df:
            close_col = candidate
            break
    if close_col is None:
        return None

    frame = df.copy()
    if "date" in frame:
        try:
            frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
            frame = frame.dropna(subset=["date"]).sort_values("date").set_index("date")
        except Exception:
            frame = frame.sort_index()
    else:
        frame = frame.sort_index()

    close = pd.to_numeric(frame[close_col], errors="coerce").dropna()
    return close if not close.empty else None


def _weekly_close_series(close: Any) -> Any:
    try:
        import pandas as pd
    except Exception:
        return None
    if not isinstance(getattr(close, "index", None), pd.DatetimeIndex):
        return None
    try:
        weekly = close.resample("W-FRI").last().dropna()
    except Exception:
        return None
    return weekly if not weekly.empty else None


def _latest_bbi_snapshot(close: Any) -> Dict[str, Any]:
    try:
        count = len(close)
    except Exception:
        count = 0
    if count < max(_BBI_WINDOWS):
        return {
            "value": None,
            "status": "missing",
            "missing_reason": f"少于{max(_BBI_WINDOWS)}根K线",
        }

    try:
        values = [float(close.rolling(window=window).mean().iloc[-1]) for window in _BBI_WINDOWS]
    except Exception:
        return {
            "value": None,
            "status": "missing",
            "missing_reason": "K线格式不支持BBI计算",
        }
    if any(value != value for value in values):
        return {
            "value": None,
            "status": "missing",
            "missing_reason": "均线窗口存在空值",
        }
    return {
        "value": round(sum(values) / len(values), 4),
        "status": "ok",
        "windows": list(_BBI_WINDOWS),
        "bar_count": count,
    }


def _infer_bbi_position(
    current: Optional[float],
    daily_bbi: Optional[float],
    weekly_bbi: Optional[float],
) -> str:
    if current is None or current <= 0:
        return "missing"
    reference = weekly_bbi if weekly_bbi not in (None, 0) else daily_bbi
    if reference in (None, 0):
        return "missing"
    distance_pct = (current - float(reference)) / float(reference) * 100
    if abs(distance_pct) <= _BBI_NEAR_THRESHOLD_PCT:
        return "near_bbi"
    if weekly_bbi not in (None, 0):
        return "above_weekly_bbi" if distance_pct > 0 else "below_weekly_bbi"
    return "above_daily_bbi" if distance_pct > 0 else "below_daily_bbi"


def _apply_bbi_details(item: Dict[str, Any], details: Mapping[str, Any]) -> None:
    position = _safe_text(details.get("position")) or "missing"
    item["bbi_position"] = position
    item["bbiPosition"] = position
    item["bbi_details"] = _sanitize_mapping(details)
    item["bbiDetails"] = item["bbi_details"]
    missing_reason = _safe_text(details.get("missing_reason"))
    if missing_reason:
        item["bbi_missing_reason"] = missing_reason
        item["bbiMissingReason"] = missing_reason

    key_levels = item.get("keyLevels") if isinstance(item.get("keyLevels"), list) else item.get("key_levels")
    if not isinstance(key_levels, list):
        key_levels = []
    key_levels = [str(level) for level in key_levels if not _is_missing_value(level)]
    daily = details.get("daily") if isinstance(details.get("daily"), Mapping) else {}
    weekly = details.get("weekly") if isinstance(details.get("weekly"), Mapping) else {}
    daily_value = _safe_float(daily.get("value"))
    weekly_value = _safe_float(weekly.get("value"))
    additions: List[str]
    if daily_value is None and weekly_value is None:
        additions = ["BBI: 未取得"]
    else:
        additions = []
        if daily_value is not None:
            additions.append(f"日BBI {daily_value:.3f}")
        if weekly_value is not None:
            additions.append(f"周BBI {weekly_value:.3f}")
    for level in additions:
        if level not in key_levels:
            key_levels.append(level)
    item["keyLevels"] = key_levels
    item["key_levels"] = key_levels


def build_external_radar(*, data_manager: Any = None) -> Dict[str, Any]:
    """Build US/KR/JP impact labels without emitting any overseas trade action."""
    groups = []
    manager = data_manager or _default_data_manager()
    for region, config in _EXTERNAL_GROUPS.items():
        groups.append(_build_external_group(region, config, _safe_get_main_indices(manager, region)))
    return {
        "scope_note": EXTERNAL_SCOPE_NOTE,
        "groups": groups,
    }


def _build_cn_market_payload(
    manager: Any,
    account_payload: Mapping[str, Any],
    *,
    report_date: Optional[str] = None,
    market_stats_timeout_seconds: float = 4,
) -> Dict[str, Any]:
    tencent_snapshot = _fetch_tencent_cn_market_snapshot()
    yahoo_snapshot = _fetch_yahoo_cn_market_snapshot()
    indices = [item for item in (tencent_snapshot.get("indices") if tencent_snapshot else []) if isinstance(item, Mapping)]
    sectors = [item for item in (tencent_snapshot.get("sectors") if tencent_snapshot else []) if isinstance(item, Mapping)]
    breadth = _normalize_breadth(tencent_snapshot.get("breadth", {}) if tencent_snapshot else {})

    if yahoo_snapshot:
        indices = _merge_keyed_rows(
            indices,
            yahoo_snapshot.get("indices"),
            key_candidates=("code", "name"),
        )
        sectors = _merge_keyed_rows(
            sectors,
            yahoo_snapshot.get("sectors"),
            key_candidates=("name", "matched_name"),
        )

    if len(indices) < 4:
        rows = _safe_get_main_indices(manager, "cn")
        fetched_indices = [_normalize_index_row(row) for row in rows]
        fetched_indices = [item for item in fetched_indices if item]
        if fetched_indices:
            indices = _merge_keyed_rows(
                indices,
                fetched_indices,
                key_candidates=("code", "name"),
            )

    stats = (
        {}
        if _breadth_has_counts(breadth)
        else _safe_get_market_stats(manager, timeout_seconds=market_stats_timeout_seconds)
    )
    normalized_stats = _normalize_breadth(stats)
    breadth = _merge_row(breadth, normalized_stats) if (breadth or normalized_stats) else {}

    if not sectors:
        sectors = _build_focus_sector_payload(manager)
    elif _should_enrich_focus_sectors(sectors):
        fetched_sectors = _build_focus_sector_payload(manager)
        sectors = _merge_keyed_rows(
            sectors,
            fetched_sectors,
            key_candidates=("name", "matched_name"),
        )

    eastmoney_snapshot = _fetch_eastmoney_cn_market_snapshot()
    if eastmoney_snapshot:
        indices = _merge_keyed_rows(
            indices,
            eastmoney_snapshot.get("indices"),
            key_candidates=("code", "name"),
        )
        breadth = _merge_row(breadth, eastmoney_snapshot.get("breadth", {}))
        sectors = _merge_keyed_rows(
            sectors,
            eastmoney_snapshot.get("sectors"),
            key_candidates=("name", "matched_name"),
        )
    cached_breadth = _fetch_cached_market_breadth(report_date)
    if cached_breadth:
        breadth = _merge_row(breadth, cached_breadth) if _row_has_numeric_data(breadth) else cached_breadth
    if breadth and _safe_float(breadth.get("main_net_inflow")) is None:
        breadth["fund_flow_status"] = "missing"
        breadth["fund_flow_missing_reason"] = "主力资金流接口当前未稳定返回；已保留涨跌家数/成交额，资金流不编造。"
    risk_light = _infer_cn_risk_light(indices, breadth) or _safe_text(account_payload.get("risk_light")) or "unknown"
    has_indices = bool(indices)
    has_breadth = bool(breadth)
    has_sectors = bool(sectors)
    data_status = "partial" if has_indices or has_breadth or has_sectors else "missing"

    if has_indices or has_breadth or has_sectors:
        summary = "A股雷达已接入指数与涨跌家数；资金/板块未取得时按缺失处理。"
    else:
        summary = "A股市场雷达未取得完整数据。"

    return {
        "risk_light": risk_light,
        "summary": summary,
        "indices": indices,
        "breadth": breadth,
        "sectors": sectors,
        "data_status": data_status,
        "source": "data_manager.get_main_indices/get_market_stats" if data_status != "missing" else "未取得",
    }


def _build_external_group(region: str, config: Mapping[str, Any], rows: List[Mapping[str, Any]]) -> Dict[str, Any]:
    wanted = tuple(str(code).upper() for code in config.get("wanted", ()))
    row_by_code = {
        _safe_text(_first_present(row, ("code", "symbol", "ticker"))).upper(): row
        for row in rows
        if _safe_text(_first_present(row, ("code", "symbol", "ticker")))
    }
    fallback_names = config.get("fallback_names") if isinstance(config.get("fallback_names"), Mapping) else {}
    missing_codes = [code for code in wanted if code not in row_by_code]
    fallback_rows = _fetch_external_fallback_rows(missing_codes, fallback_names)
    items = []
    for code in wanted:
        row = row_by_code.get(code) or fallback_rows.get(code)
        if row is None:
            items.append(
                {
                    "code": code,
                    "name": _safe_text(fallback_names.get(code)) or code,
                    "impact": "missing",
                    "data_status": "missing",
                    "missing_reason": "数据源未返回该项",
                }
            )
            continue

        change_pct = _first_float(row, ("change_pct", "changePct", "pct_chg", "pctChg", "percent", "change_percent", "涨跌幅"))
        item_impact = _impact_from_change(code, change_pct)
        items.append(
            {
                "code": code,
                "name": _safe_text(_first_present(row, ("name", "shortName", "display_name", "名称", "指数名称"))) or _safe_text(fallback_names.get(code)) or code,
                "current": _first_float(row, ("current", "price", "latest", "latest_price", "last", "last_price", "close", "收盘", "最新", "最新价", "当前价")),
                "change_pct": change_pct,
                "impact": item_impact,
                "data_status": "ok" if change_pct is not None else "missing",
                "source": _safe_text(row.get("source")) or "data_manager.get_main_indices",
                "data_date": _safe_text(_first_present(row, ("data_date", "dataDate", "date", "trade_date", "交易日期"))) or None,
                "proxy_note": _safe_text(row.get("proxy_note")) or None,
            }
        )

    group_impact = _aggregate_impact(items)
    missing_count = sum(1 for item in items if item.get("data_status") == "missing")
    note = "部分外围数据未取得，只能作为不完整风险雷达。" if missing_count else "外围数据已取得；仅用于A股风险偏好参考。"
    return {
        "region": region,
        "title": _safe_text(config.get("title")) or region,
        "impact": group_impact,
        "items": items,
        "note": note,
    }


def _aggregate_impact(items: List[Mapping[str, Any]]) -> str:
    known = [str(item.get("impact")) for item in items if item.get("impact") != "missing"]
    if not known:
        return "missing"
    negative = known.count("negative")
    positive = known.count("positive")
    if negative > positive:
        return "negative"
    if positive > negative:
        return "positive"
    return "neutral"


def _impact_from_change(code: str, change_pct: Optional[float]) -> str:
    if change_pct is None:
        return "missing"
    normalized = code.upper()
    if normalized == "VIX":
        if change_pct >= 2:
            return "negative"
        if change_pct <= -2:
            return "positive"
        return "neutral"
    if change_pct <= -0.5:
        return "negative"
    if change_pct >= 0.5:
        return "positive"
    return "neutral"


def _safe_get_main_indices(manager: Any, region: str) -> List[Mapping[str, Any]]:
    if manager is None or not hasattr(manager, "get_main_indices"):
        return []
    rows = _run_with_timeout(lambda: manager.get_main_indices(region=region), timeout_seconds=4)
    if rows is None:
        return []
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _safe_get_market_stats(manager: Any, *, timeout_seconds: float = 4) -> Dict[str, Any]:
    if manager is None or not hasattr(manager, "get_market_stats"):
        return {}
    stats = _run_with_timeout(lambda: manager.get_market_stats(purpose="market_radar"), timeout_seconds=timeout_seconds)
    if stats is _TIMEOUT_SENTINEL:
        return {}
    if stats is None:
        stats = _run_with_timeout(lambda: manager.get_market_stats(), timeout_seconds=timeout_seconds)
    if stats is None or stats is _TIMEOUT_SENTINEL:
        return {}
    return _sanitize_mapping(stats) if isinstance(stats, Mapping) else {}


def _safe_get_sector_rankings(manager: Any) -> List[Mapping[str, Any]]:
    if manager is None:
        return []
    rows: List[Mapping[str, Any]] = []
    for method_name in ("get_sector_rankings", "get_concept_rankings"):
        if not hasattr(manager, method_name):
            continue
        rankings = _run_with_timeout(lambda method_name=method_name: getattr(manager, method_name)(n=50), timeout_seconds=3)
        if rankings is None or rankings is _TIMEOUT_SENTINEL:
            continue
        rows.extend(_flatten_sector_rankings(rankings))
    return rows


def _run_with_timeout(callback: Any, *, timeout_seconds: float) -> Any:
    result: Dict[str, Any] = {}

    def target() -> None:
        try:
            result["value"] = callback()
        except Exception:
            result["value"] = None

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout_seconds)
    if thread.is_alive():
        return _TIMEOUT_SENTINEL
    return result.get("value")


def _flatten_sector_rankings(rankings: Any) -> List[Mapping[str, Any]]:
    if rankings is None:
        return []
    if isinstance(rankings, Mapping):
        containers = [rankings.get("top"), rankings.get("bottom"), rankings.get("sectors")]
    elif isinstance(rankings, tuple):
        containers = list(rankings)
    elif isinstance(rankings, list):
        containers = [rankings]
    else:
        containers = []

    rows: List[Mapping[str, Any]] = []
    for container in containers:
        if isinstance(container, list):
            rows.extend(row for row in container if isinstance(row, Mapping))
    return rows


def _build_focus_sector_payload(manager: Any) -> List[Dict[str, Any]]:
    rows = _safe_get_sector_rankings(manager)
    if not rows:
        return []

    focus_groups = (
        ("通信/5G", ("通信", "通讯", "5G", "通信设备")),
        ("面板/京东方链", ("面板", "显示", "光学", "消费电子", "电子元件")),
        ("AI服务器/工业富联", ("服务器", "算力", "人工智能", "通信设备", "电子设备", "半导体")),
    )
    sectors: List[Dict[str, Any]] = []
    used_row_ids = set()
    for label, keywords in focus_groups:
        match = _find_sector_match(rows, keywords, used_row_ids)
        if match is None:
            continue
        used_row_ids.add(id(match))
        change_pct = _first_float(match, ("change_pct", "changePct", "pct_chg", "pctChg", "涨跌幅"))
        sectors.append(
            {
                "name": label,
                "matched_name": _safe_text(_first_present(match, ("name", "sector", "board", "板块名称", "行业名称"))),
                "change_pct": change_pct,
                "strength": _strength_from_change(change_pct),
                "source": _safe_text(match.get("source")) or "data_manager.get_sector_rankings",
            }
        )
    return sectors


def _should_enrich_focus_sectors(sectors: List[Mapping[str, Any]]) -> bool:
    if not sectors:
        return True
    if len(sectors) < 3:
        return True
    return any(_safe_float(item.get("change_pct")) is None for item in sectors if isinstance(item, Mapping))


def _fetch_external_fallback_rows(codes: Iterable[str], fallback_names: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    specs = []
    for code in codes:
        normalized = code.upper()
        symbol = _YAHOO_EXTERNAL_SYMBOLS.get(normalized)
        if not symbol:
            continue
        specs.append(
            {
                "symbol": symbol,
                "code": normalized,
                "name": _safe_text(fallback_names.get(normalized)) or normalized,
                "source": "yahoo_chart_direct",
                "proxy_note": "TOPIX采用1306.T ETF作为亚洲风险偏好代理。" if normalized == "TOPX" else "",
            }
        )
    return {
        _safe_text(item.get("code")).upper(): item
        for item in _fetch_yahoo_quotes_batch(specs)
        if _safe_text(item.get("code"))
    }


def _fetch_yahoo_cn_market_snapshot() -> Dict[str, Any]:
    indices = _fetch_yahoo_quotes_batch(
        {
            "symbol": symbol,
            "code": code,
            "name": name,
            "source": "yahoo_chart_cn_index",
        }
        for code, name, symbol in _YAHOO_CN_INDEX_SYMBOLS
    )
    sectors: List[Dict[str, Any]] = []
    sector_quotes = _fetch_yahoo_quotes_batch(
        {
            "symbol": symbol,
            "code": code,
            "name": fallback_name,
            "source": "yahoo_chart_focus_proxy",
            "proxy_note": "用核心持仓/ETF作为板块强弱代理；不代表完整行业资金流。",
            "sector_label": label,
            "matched_name": fallback_name,
        }
        for label, code, fallback_name, symbol in _YAHOO_FOCUS_SECTOR_SYMBOLS
    )
    for quote in sector_quotes:
        if not quote:
            continue
        change_pct = _safe_float(quote.get("change_pct"))
        sectors.append(
            {
                "name": _safe_text(quote.get("sector_label")) or _safe_text(quote.get("name")),
                "matched_name": _safe_text(quote.get("matched_name")) or _safe_text(quote.get("name")),
                "code": quote.get("code"),
                "current": quote.get("current"),
                "change_pct": change_pct,
                "volume": quote.get("volume"),
                "strength": _strength_from_change(change_pct),
                "source": quote.get("source"),
                "data_date": quote.get("data_date"),
                "proxy_note": quote.get("proxy_note"),
            }
        )

    return {
        "indices": indices,
        "sectors": sectors,
    }


def _fetch_yahoo_quotes_batch(specs: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    spec_list = [dict(spec) for spec in specs if isinstance(spec, Mapping)]
    if not spec_list:
        return []
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(8, len(spec_list))) as executor:
        future_to_spec = {
            executor.submit(
                _fetch_yahoo_chart_quote,
                symbol=_safe_text(spec.get("symbol")),
                code=_safe_text(spec.get("code")),
                name=_safe_text(spec.get("name")),
                source=_safe_text(spec.get("source")) or "yahoo_chart_direct",
                proxy_note=_safe_text(spec.get("proxy_note")),
            ): spec
            for spec in spec_list
        }
        for future in as_completed(future_to_spec):
            spec = future_to_spec[future]
            try:
                item = future.result()
            except Exception:
                continue
            if not item:
                continue
            for passthrough_key in ("sector_label", "matched_name"):
                if passthrough_key in spec:
                    item[passthrough_key] = spec[passthrough_key]
            results.append(item)
    return results


def _fetch_yahoo_chart_quote(
    *,
    symbol: str,
    code: str,
    name: str,
    source: str,
    proxy_note: str = "",
) -> Dict[str, Any]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?range=5d&interval=1d"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "application/json,text/plain,*/*",
    }
    try:
        opener = build_opener(ProxyHandler({}))
        request = Request(url, headers=headers)
        with opener.open(request, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}

    result = ((payload.get("chart") or {}).get("result") or [None])[0] if isinstance(payload, Mapping) else None
    if not isinstance(result, Mapping):
        return {}
    meta = result.get("meta") if isinstance(result.get("meta"), Mapping) else {}
    current = _safe_float(meta.get("regularMarketPrice"))
    previous = _safe_float(meta.get("chartPreviousClose") or meta.get("previousClose"))

    if current is None:
        close_values = (
            (((result.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close")
            if isinstance(result.get("indicators"), Mapping)
            else None
        )
        if isinstance(close_values, list):
            for value in reversed(close_values):
                current = _safe_float(value)
                if current is not None:
                    break

    change = current - previous if current is not None and previous not in (None, 0) else None
    change_pct = (change / previous * 100) if change is not None and previous else None
    if current is None and change_pct is None:
        return {}

    timestamp = _safe_float(meta.get("regularMarketTime"))
    data_date = None
    if timestamp is not None:
        try:
            data_date = datetime.fromtimestamp(int(timestamp)).isoformat(timespec="seconds")
        except Exception:
            data_date = None

    item = {
        "code": code,
        "name": name,
        "current": current,
        "change": change,
        "change_pct": change_pct,
        "volume": _safe_float(meta.get("regularMarketVolume")),
        "source": source,
        "data_status": "ok",
        "data_date": data_date,
    }
    if proxy_note:
        item["proxy_note"] = proxy_note
    return item


def _fetch_tencent_cn_market_snapshot() -> Dict[str, Any]:
    """Fetch A-share index and focus-position quotes from Tencent qt.gtimg.cn."""
    symbols = [item[0] for item in _TENCENT_CN_INDEX_SYMBOLS] + [item[0] for item in _TENCENT_FOCUS_SECTOR_SYMBOLS]
    raw = _request_tencent_quotes(symbols)
    if not raw:
        return {}

    rows = _parse_tencent_quote_rows(raw)
    if not rows:
        return {}

    indices = []
    for symbol, code, fallback_name in _TENCENT_CN_INDEX_SYMBOLS:
        row = rows.get(symbol) or rows.get(code)
        if not row:
            continue
        item = _tencent_quote_to_index(code, fallback_name, row)
        if item:
            indices.append(item)

    sectors = []
    for symbol, label, code, fallback_name in _TENCENT_FOCUS_SECTOR_SYMBOLS:
        row = rows.get(symbol) or rows.get(code)
        if not row:
            continue
        item = _tencent_quote_to_focus_sector(label, code, fallback_name, row)
        if item:
            sectors.append(item)

    breadth: Dict[str, Any] = {}
    amount_values = [
        _safe_float(item.get("amount"))
        for item in indices
        if item.get("code") in {"000001", "399001"} and _safe_float(item.get("amount")) is not None
    ]
    if amount_values:
        breadth = {
            "total_amount": round(sum(amount_values), 2),
            "source": "tencent_quote_index_amount",
            "data_status": "partial",
            "data_date": _safe_text(_first_present(indices[0], ("data_date", "dataDate"))) or None,
            "amount_note": "腾讯指数快照推算沪深成交额，单位为亿元；不含涨跌家数与主力资金。",
        }

    return {
        "indices": indices,
        "breadth": breadth,
        "sectors": sectors,
    }


def _request_tencent_quotes(symbols: Iterable[str]) -> str:
    symbol_text = ",".join(str(symbol) for symbol in symbols if symbol)
    if not symbol_text:
        return ""
    url = f"https://qt.gtimg.cn/q={quote(symbol_text, safe=',')}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Referer": "https://gu.qq.com/",
        "Accept": "*/*",
    }
    try:
        opener = build_opener(ProxyHandler({}))
        request = Request(url, headers=headers)
        with opener.open(request, timeout=4) as response:
            raw = response.read()
        return raw.decode("gb18030", errors="replace")
    except Exception:
        return ""


def _parse_tencent_quote_rows(raw: str) -> Dict[str, Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for chunk in str(raw or "").split(";"):
        if '="' not in chunk:
            continue
        prefix, payload = chunk.split('="', 1)
        payload = payload.strip().strip('"')
        fields = payload.split("~")
        if len(fields) < 4:
            continue
        symbol = prefix.strip().removeprefix("v_")
        code = _safe_text(fields[2])
        row = {
            "symbol": symbol,
            "name": _safe_text(fields[1]),
            "code": code,
            "current": _safe_float(fields[3]),
            "previous_close": _safe_float(fields[4] if len(fields) > 4 else None),
            "open": _safe_float(fields[5] if len(fields) > 5 else None),
            "source": "tencent_quote",
            "data_status": "ok",
        }
        timestamp_index = _find_tencent_timestamp_index(fields)
        if timestamp_index is not None:
            row["data_date"] = _format_tencent_timestamp(fields[timestamp_index])
            row["change"] = _safe_float(fields[timestamp_index + 1] if len(fields) > timestamp_index + 1 else None)
            row["change_pct"] = _safe_float(fields[timestamp_index + 2] if len(fields) > timestamp_index + 2 else None)
            row["high"] = _safe_float(fields[timestamp_index + 3] if len(fields) > timestamp_index + 3 else None)
            row["low"] = _safe_float(fields[timestamp_index + 4] if len(fields) > timestamp_index + 4 else None)
        amount = _extract_tencent_amount(fields)
        if amount is not None:
            row["amount"] = amount
        if symbol:
            rows[symbol] = row
        if code:
            rows[code] = row
    return rows


def _find_tencent_timestamp_index(fields: List[str]) -> Optional[int]:
    for index, value in enumerate(fields):
        text = _safe_text(value)
        if len(text) == 14 and text.isdigit():
            return index
    return None


def _format_tencent_timestamp(value: Any) -> Optional[str]:
    text = _safe_text(value)
    if len(text) != 14 or not text.isdigit():
        return None
    return f"{text[0:4]}-{text[4:6]}-{text[6:8]} {text[8:10]}:{text[10:12]}:{text[12:14]}"


def _extract_tencent_amount(fields: List[str]) -> Optional[float]:
    for field in fields:
        text = _safe_text(field)
        if "/" not in text:
            continue
        parts = text.split("/")
        if len(parts) < 3:
            continue
        amount_yuan = _safe_float(parts[2])
        if amount_yuan is not None:
            return round(amount_yuan / 1e8, 2)
    return None


def _tencent_quote_to_index(code: str, fallback_name: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    current = _safe_float(row.get("current"))
    change_pct = _safe_float(row.get("change_pct"))
    if current is None and change_pct is None:
        return {}
    display_name = _TENCENT_CLEAN_INDEX_NAMES.get(code) or fallback_name or _safe_text(row.get("name"))
    return {
        "code": code,
        "name": display_name,
        "current": current,
        "change": _safe_float(row.get("change")),
        "change_pct": change_pct,
        "amount": _safe_float(row.get("amount")),
        "source": "tencent_quote",
        "data_status": "ok",
        "data_date": _safe_text(row.get("data_date")) or None,
    }


def _tencent_quote_to_focus_sector(label: str, code: str, fallback_name: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    current = _safe_float(row.get("current"))
    change_pct = _safe_float(row.get("change_pct"))
    if current is None and change_pct is None:
        return {}
    display_label = _TENCENT_CLEAN_FOCUS_LABELS.get(code) or label
    matched_name = _TENCENT_CLEAN_FOCUS_NAMES.get(code) or fallback_name or _safe_text(row.get("name"))
    return {
        "name": display_label,
        "matched_name": matched_name,
        "code": code,
        "current": current,
        "change": _safe_float(row.get("change")),
        "change_pct": change_pct,
        "amount": _safe_float(row.get("amount")),
        "strength": _strength_from_change(change_pct),
        "source": "tencent_quote",
        "data_status": "ok",
        "data_date": _safe_text(row.get("data_date")) or None,
    }


def _fetch_eastmoney_cn_market_snapshot() -> Dict[str, Any]:
    """Fetch a lightweight EastMoney push2 snapshot for dashboard fallback.

    This supplements the slower provider chain with directly verifiable quote
    fields. It intentionally records source/notes because f62 is EastMoney's
    quote-level capital-flow field, not an official exchange statistic.
    """
    secids = (
        "1.000001",
        "0.399001",
        "0.399006",
        "1.000688",
        "1.000016",
        "1.000300",
        "1.601138",
        "1.515880",
        "0.000725",
        "0.159732",
        "1.515050",
    )
    fields = "f12,f14,f2,f3,f4,f5,f6,f8,f15,f16,f17,f18,f20,f21,f23,f62"
    params = {
        "fltt": "2",
        "invt": "2",
        "fields": fields,
        "secids": ",".join(secids),
    }
    payload = _request_eastmoney_ulist(params)
    from_cache = False
    if not payload:
        payload = _read_eastmoney_cache()
        from_cache = bool(payload)

    rows = (payload.get("data") or {}).get("diff") if isinstance(payload, Mapping) else None
    if not isinstance(rows, list):
        return {}

    by_code: Dict[str, Mapping[str, Any]] = {
        _safe_text(row.get("f12")): row for row in rows if isinstance(row, Mapping) and _safe_text(row.get("f12"))
    }
    indices = []
    index_names = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
        "000688": "科创50",
        "000016": "上证50",
        "000300": "沪深300",
    }
    for code, name in index_names.items():
        row = by_code.get(code)
        if not row:
            continue
        indices.append(_eastmoney_quote_to_index(code, name, row))

    sh_flow = _safe_float(by_code.get("000001", {}).get("f62") if by_code.get("000001") else None)
    sz_flow = _safe_float(by_code.get("399001", {}).get("f62") if by_code.get("399001") else None)
    breadth: Dict[str, Any] = {}
    if sh_flow is not None or sz_flow is not None:
        breadth["main_net_inflow"] = round(((sh_flow or 0.0) + (sz_flow or 0.0)) / 1e8, 2)
        breadth["source"] = "eastmoney_push2_index_f62"
        breadth["fund_flow_note"] = "东方财富指数口径：上证指数+深证成指 f62，作为大盘资金近似参考。"

    sectors = []
    sector_specs = (
        ("通信/5G", "515880", "通信ETF国泰"),
        ("面板/京东方链", "000725", "京东方A"),
        ("AI服务器/工业富联", "601138", "工业富联"),
        ("消费电子", "159732", "消费电子ETF华夏"),
        ("半导体", "515050", "半导体ETF"),
    )
    for label, code, fallback_name in sector_specs:
        row = by_code.get(code)
        if not row:
            continue
        sectors.append(_eastmoney_quote_to_focus_sector(label, code, fallback_name, row))

    snapshot = {
        "indices": [item for item in indices if item],
        "breadth": breadth,
        "sectors": [item for item in sectors if item],
    }
    if from_cache:
        _mark_snapshot_as_cached(snapshot)
    else:
        _write_eastmoney_cache(payload)
    return snapshot


def _request_eastmoney_ulist(params: Mapping[str, Any]) -> Dict[str, Any]:
    base_urls = (
        "https://push2.eastmoney.com/api/qt/ulist.np/get",
        "https://push2his.eastmoney.com/api/qt/ulist.np/get",
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/",
        "Accept": "application/json,text/plain,*/*",
    }
    opener = build_opener(ProxyHandler({}))
    for base_url in base_urls:
        for _ in range(1):
            request_params = dict(params)
            request_params["_"] = str(int(time.time() * 1000))
            url = base_url + "?" + urlencode(request_params)
            try:
                request = Request(url, headers=headers)
                if opener is not None:
                    response = opener.open(request, timeout=3)
                else:
                    response = urlopen(request, timeout=3)
                with response:
                    raw = response.read().decode("utf-8", errors="replace")
                payload = json.loads(raw)
                rows = (payload.get("data") or {}).get("diff") if isinstance(payload, Mapping) else None
                if isinstance(rows, list) and rows:
                    return payload
            except Exception:
                time.sleep(0.1)
    return {}


def _read_eastmoney_cache() -> Dict[str, Any]:
    try:
        if not _EASTMONEY_CACHE_PATH.exists():
            return {}
        with _EASTMONEY_CACHE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _write_eastmoney_cache(payload: Mapping[str, Any]) -> None:
    try:
        _EASTMONEY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        cache_payload = dict(payload)
        cache_payload["_cached_at"] = datetime.now().isoformat(timespec="seconds")
        with _EASTMONEY_CACHE_PATH.open("w", encoding="utf-8") as handle:
            json.dump(cache_payload, handle, ensure_ascii=False)
    except Exception:
        return


def _mark_snapshot_as_cached(snapshot: Dict[str, Any]) -> None:
    for item in snapshot.get("indices", []):
        if isinstance(item, dict):
            item["data_status"] = "stale"
            item["source"] = f"{item.get('source') or 'eastmoney_push2'}_cached"
    breadth = snapshot.get("breadth")
    if isinstance(breadth, dict) and breadth:
        breadth["data_status"] = "stale"
        breadth["source"] = f"{breadth.get('source') or 'eastmoney_push2_index_f62'}_cached"
    for item in snapshot.get("sectors", []):
        if isinstance(item, dict):
            item["data_status"] = "stale"
            item["source"] = f"{item.get('source') or 'eastmoney_push2_proxy'}_cached"


def _fetch_cached_market_breadth(report_date: Optional[str]) -> Dict[str, Any]:
    """Reuse a same-day verified breadth snapshot when live providers are down."""
    if not report_date or not _ANALYSIS_DB_PATH.exists():
        return {}
    try:
        with sqlite3.connect(_ANALYSIS_DB_PATH) as connection:
            rows = connection.execute(
                """
                SELECT context_snapshot
                FROM analysis_history
                WHERE context_snapshot IS NOT NULL
                ORDER BY id DESC
                LIMIT 40
                """
            ).fetchall()
    except Exception:
        return {}

    target_date = str(report_date)[:10]
    for (snapshot_text,) in rows:
        try:
            snapshot = json.loads(snapshot_text or "{}")
        except Exception:
            continue
        if not isinstance(snapshot, Mapping):
            continue
        radar = snapshot.get("marketRadar") or snapshot.get("market_radar") or {}
        if not isinstance(radar, Mapping):
            continue
        radar_date = _safe_text(radar.get("date"))[:10]
        if radar_date and radar_date != target_date:
            continue
        cn_market = radar.get("cn_market") or radar.get("cnMarket") or {}
        breadth = cn_market.get("breadth") if isinstance(cn_market, Mapping) else None
        if not isinstance(breadth, Mapping) or not _row_has_numeric_data(breadth):
            continue
        cached = dict(breadth)
        cached["data_status"] = "stale"
        source = _safe_text(cached.get("source")) or "analysis_history"
        while source.endswith("_same_day_cache"):
            source = source[: -len("_same_day_cache")]
        cached["source"] = f"{source}_same_day_cache"
        cached["cache_note"] = f"实时广度接口失败，复用 {target_date} 本地已保存广度数据；仅作收盘复盘参考。"
        return cached
    return {}


def _eastmoney_quote_to_index(code: str, name: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "current": _safe_float(row.get("f2")),
        "change": _safe_float(row.get("f4")),
        "change_pct": _safe_float(row.get("f3")),
        "amount": _safe_float(row.get("f6")),
        "main_net_inflow": _safe_float(row.get("f62")),
        "source": "eastmoney_push2",
    }


def _eastmoney_quote_to_focus_sector(label: str, code: str, fallback_name: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    change_pct = _safe_float(row.get("f3"))
    fund_flow = _safe_float(row.get("f62"))
    return {
        "name": label,
        "matched_name": fallback_name,
        "code": code,
        "change_pct": change_pct,
        "fund_flow": round(fund_flow / 1e8, 2) if fund_flow is not None else None,
        "strength": _strength_from_change(change_pct),
        "source": "eastmoney_push2_proxy",
    }


def _find_sector_match(
    rows: List[Mapping[str, Any]],
    keywords: Iterable[str],
    used_row_ids: set,
) -> Optional[Mapping[str, Any]]:
    best: Optional[Mapping[str, Any]] = None
    best_score: Optional[float] = None
    for row in rows:
        if id(row) in used_row_ids:
            continue
        name = _safe_text(_first_present(row, ("name", "sector", "board", "板块名称", "行业名称")))
        if not name or not any(keyword in name for keyword in keywords):
            continue
        score = _first_float(row, ("change_pct", "changePct", "pct_chg", "pctChg", "涨跌幅"))
        score_for_sort = abs(score) if score is not None else 0
        if best is None or score_for_sort > (best_score or 0):
            best = row
            best_score = score_for_sort
    return best


def _normalize_index_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    name = _safe_text(_first_present(row, ("name", "shortName", "display_name", "名称", "指数名称")))
    if not name:
        return {}
    return {
        "code": _safe_text(_first_present(row, ("code", "symbol", "ticker", "代码", "指数代码"))),
        "name": name,
        "current": _first_float(row, ("current", "price", "latest", "latest_price", "last", "last_price", "close", "收盘", "最新", "最新价", "当前价", "点位")),
        "change": _first_float(row, ("change", "change_amount", "changeAmount", "涨跌额")),
        "change_pct": _first_float(row, ("change_pct", "changePct", "pct_chg", "pctChg", "percent", "change_percent", "涨跌幅")),
        "amount": _first_float(row, ("amount", "turnover", "成交额", "成交金额")),
        "source": _safe_text(row.get("source")) or "data_manager.get_main_indices",
        "data_date": _safe_text(_first_present(row, ("data_date", "dataDate", "date", "trade_date", "交易日期"))) or None,
    }


def _normalize_breadth(stats: Mapping[str, Any]) -> Dict[str, Any]:
    if not stats:
        return {}
    mapping = {
        "up_count": ("up_count", "upCount", "rise_count", "上涨家数", "上涨"),
        "down_count": ("down_count", "downCount", "fall_count", "下跌家数", "下跌"),
        "flat_count": ("flat_count", "flatCount", "flat", "平盘家数", "平盘"),
        "limit_up_count": ("limit_up_count", "limitUpCount", "涨停家数", "涨停"),
        "limit_down_count": ("limit_down_count", "limitDownCount", "跌停家数", "跌停"),
        "total_amount": ("total_amount", "totalAmount", "amount", "turnover", "成交额", "两市成交额"),
        "main_net_inflow": ("main_net_inflow", "mainNetInflow", "main_fund_flow", "主力净流入", "大盘资金净流入"),
    }
    result: Dict[str, Any] = {}
    for target, keys in mapping.items():
        for key in keys:
            value = _safe_float(stats.get(key))
            if value is not None:
                result[target] = int(value) if target.endswith("_count") else value
                break
    source = _safe_text(stats.get("source"))
    if source:
        result["source"] = source
    data_status = _safe_text(stats.get("data_status", stats.get("dataStatus")))
    if data_status:
        result["data_status"] = data_status
    data_date = _safe_text(stats.get("data_date", stats.get("dataDate")))
    if data_date:
        result["data_date"] = data_date
    return result


def _breadth_has_counts(breadth: Mapping[str, Any]) -> bool:
    return any(
        _safe_float(breadth.get(key)) is not None
        for key in ("up_count", "down_count", "flat_count", "limit_up_count", "limit_down_count")
    )


def _merge_cn_market_payload(manual: Mapping[str, Any], fetched: Mapping[str, Any]) -> Dict[str, Any]:
    if not fetched:
        return dict(manual)

    merged = dict(manual)
    for key, value in fetched.items():
        if _is_missing_value(merged.get(key)):
            merged[key] = value

    merged["indices"] = _merge_keyed_rows(
        manual.get("indices"),
        fetched.get("indices"),
        key_candidates=("code", "name"),
    )
    merged["sectors"] = _merge_keyed_rows(
        manual.get("sectors"),
        fetched.get("sectors"),
        key_candidates=("name", "matched_name"),
    )

    manual_breadth = manual.get("breadth") if isinstance(manual.get("breadth"), Mapping) else {}
    fetched_breadth = fetched.get("breadth") if isinstance(fetched.get("breadth"), Mapping) else {}
    merged["breadth"] = _merge_row(manual_breadth, fetched_breadth) if (manual_breadth or fetched_breadth) else {}

    if _has_usable_market_data(merged):
        merged["data_status"] = "partial"
    return merged


def _merge_keyed_rows(
    manual_rows: Any,
    fetched_rows: Any,
    *,
    key_candidates: Iterable[str],
) -> List[Dict[str, Any]]:
    manual_list = [dict(row) for row in manual_rows if isinstance(row, Mapping)] if isinstance(manual_rows, list) else []
    fetched_list = [dict(row) for row in fetched_rows if isinstance(row, Mapping)] if isinstance(fetched_rows, list) else []
    if not manual_list:
        return fetched_list
    if not fetched_list:
        return manual_list

    used = set()
    merged: List[Dict[str, Any]] = []
    for manual_row in manual_list:
        match_index = _find_matching_row_index(manual_row, fetched_list, key_candidates, used)
        if match_index is None:
            merged.append(manual_row)
            continue
        used.add(match_index)
        merged.append(_merge_row(manual_row, fetched_list[match_index]))

    for index, fetched_row in enumerate(fetched_list):
        if index not in used:
            merged.append(fetched_row)
    return merged


def _find_matching_row_index(
    row: Mapping[str, Any],
    candidates: List[Mapping[str, Any]],
    key_candidates: Iterable[str],
    used: set,
) -> Optional[int]:
    row_keys = {_safe_text(row.get(key)).lower() for key in key_candidates if _safe_text(row.get(key))}
    if not row_keys:
        return None
    for index, candidate in enumerate(candidates):
        if index in used:
            continue
        candidate_keys = {_safe_text(candidate.get(key)).lower() for key in key_candidates if _safe_text(candidate.get(key))}
        if row_keys & candidate_keys:
            return index
    return None


def _merge_row(primary: Mapping[str, Any], fallback: Mapping[str, Any]) -> Dict[str, Any]:
    merged = dict(primary)
    fallback_contributed = False
    for key, value in fallback.items():
        if _is_missing_value(merged.get(key)) and not _is_missing_value(value):
            merged[key] = value
            if key not in {"source", "data_status", "dataStatus"}:
                fallback_contributed = True
    if fallback_contributed:
        merged["source"] = _combine_sources(merged.get("source"), fallback.get("source"))
    if _row_has_numeric_data(merged):
        source = _safe_text(merged.get("source")).lower()
        merged_status = _safe_text(merged.get("data_status")).lower()
        fallback_status = _safe_text(fallback.get("data_status")).lower()
        if merged_status == "stale" or fallback_status == "stale" or "cache" in source:
            merged["data_status"] = "stale"
        elif merged_status == "partial" or fallback_status == "partial":
            merged["data_status"] = "partial"
        else:
            merged["data_status"] = "ok"
        merged.pop("missing_reason", None)
    return merged


def _combine_sources(*sources: Any) -> str:
    tokens: List[str] = []
    for source in sources:
        text = _safe_text(source)
        if not text:
            continue
        for token in text.replace("|", "+").replace(",", "+").split("+"):
            clean = token.strip()
            if clean and clean not in tokens:
                tokens.append(clean)
    return "+".join(tokens)


def _has_usable_market_data(payload: Mapping[str, Any]) -> bool:
    if any(_row_has_numeric_data(item) for item in payload.get("indices", []) if isinstance(item, Mapping)):
        return True
    if _row_has_numeric_data(payload.get("breadth", {})):
        return True
    if any(_row_has_numeric_data(item) for item in payload.get("sectors", []) if isinstance(item, Mapping)):
        return True
    return False


def _row_has_numeric_data(row: Any) -> bool:
    if not isinstance(row, Mapping):
        return False
    return any(
        _safe_float(row.get(key)) is not None
        for key in (
            "current",
            "change",
            "change_pct",
            "changePct",
            "amount",
            "up_count",
            "down_count",
            "total_amount",
            "main_net_inflow",
        )
    )


def _infer_cn_risk_light(indices: List[Mapping[str, Any]], breadth: Mapping[str, Any]) -> Optional[str]:
    changes = [
        _safe_float(item.get("change_pct", item.get("changePct")))
        for item in indices
        if _safe_float(item.get("change_pct", item.get("changePct"))) is not None
    ]
    avg_change = sum(changes) / len(changes) if changes else None
    up_count = _safe_float(breadth.get("up_count", breadth.get("upCount")))
    down_count = _safe_float(breadth.get("down_count", breadth.get("downCount")))
    total_active = (up_count or 0) + (down_count or 0)
    down_ratio = (down_count / total_active) if total_active else None
    up_ratio = (up_count / total_active) if total_active else None

    if (avg_change is not None and avg_change <= -3) or (down_ratio is not None and down_ratio >= 0.75):
        return "danger"
    if (avg_change is not None and avg_change <= -1) or (down_ratio is not None and down_ratio >= 0.6):
        return "defense"
    if (avg_change is not None and avg_change >= 1) and (up_ratio is not None and up_ratio >= 0.55):
        return "attack"
    if avg_change is not None or down_ratio is not None:
        return "balanced"
    return None


def _default_data_manager() -> Any:
    try:
        from data_provider.base import DataFetcherManager

        return DataFetcherManager()
    except Exception:
        return None


def _sanitize_mapping(value: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): _sanitize_value(val) for key, val in value.items()}


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_mapping(value)
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_present(row: Mapping[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in row and not _is_missing_value(row.get(key)):
            return row.get(key)
    return None


def _first_float(row: Mapping[str, Any], keys: Iterable[str]) -> Optional[float]:
    value = _first_present(row, keys)
    return _safe_float(value)


def _is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, Mapping):
        return not bool(value)
    if isinstance(value, list):
        return not bool(value)
    text = str(value).strip()
    return text in {"", "-", "--", "N/A", "n/a", "None", "none", "null", "NaN", "nan", "未取得", "数据缺失"}


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            if text.endswith("%"):
                text = text[:-1]
            if text.endswith("亿"):
                text = text[:-1]
            if text in {"", "-", "--", "N/A", "n/a", "None", "none", "null", "NaN", "nan", "未取得"}:
                return None
            parsed = float(text)
        else:
            parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed == parsed else None


def _strength_from_change(change_pct: Optional[float]) -> str:
    if change_pct is None:
        return "unknown"
    if change_pct >= 1:
        return "strong"
    if change_pct <= -1:
        return "weak"
    return "neutral"


def _today_text() -> str:
    return date.today().isoformat()
