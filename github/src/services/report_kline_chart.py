# -*- coding: utf-8 -*-
"""Build public K-line chart payloads for report views."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import pandas as pd

from src.services.history_loader import load_history_df

logger = logging.getLogger(__name__)

_BBI_WINDOWS = (3, 6, 12, 24)
_VIRTUAL_REPORT_CODES = {"PORTFOLIO", "MARKET"}


def build_report_kline_chart(
    stock_code: str,
    *,
    target_date: Optional[date] = None,
    days: int = 80,
    max_bars: int = 48,
) -> Optional[Dict[str, Any]]:
    """Return a real daily K-line chart payload, or None when unavailable."""

    code = str(stock_code or "").strip()
    if not code:
        return None
    if code.upper() in _VIRTUAL_REPORT_CODES:
        return None

    try:
        df, source = load_history_df(code, days=days, target_date=target_date)
    except Exception as exc:
        logger.debug("kline chart skipped for %s: %s", code, exc, exc_info=True)
        return None

    if df is None or getattr(df, "empty", True):
        return None

    frame = _normalize_history_frame(df)
    if frame is None or frame.empty:
        return None

    close = frame["close"]
    frame["ma5"] = close.rolling(window=5, min_periods=5).mean()
    frame["ma10"] = close.rolling(window=10, min_periods=10).mean()
    frame["ma20"] = close.rolling(window=20, min_periods=20).mean()
    frame["bbi"] = sum(close.rolling(window=window, min_periods=window).mean() for window in _BBI_WINDOWS) / len(_BBI_WINDOWS)

    trimmed = frame.tail(max_bars)
    bars: List[Dict[str, Any]] = []
    for _, row in trimmed.iterrows():
        item = {
            "date": row["date"].date().isoformat() if hasattr(row["date"], "date") else str(row["date"])[:10],
            "open": _round_or_none(row.get("open")),
            "high": _round_or_none(row.get("high")),
            "low": _round_or_none(row.get("low")),
            "close": _round_or_none(row.get("close")),
            "volume": _round_or_none(row.get("volume"), digits=0),
            "ma5": _round_or_none(row.get("ma5")),
            "ma10": _round_or_none(row.get("ma10")),
            "ma20": _round_or_none(row.get("ma20")),
            "bbi": _round_or_none(row.get("bbi")),
        }
        if all(item.get(key) is not None for key in ("open", "high", "low", "close")):
            bars.append(item)

    if len(bars) < 2:
        return None

    return {
        "source": source or "unknown",
        "data_date": bars[-1]["date"],
        "bars": bars,
        "warnings": [],
    }


def _normalize_history_frame(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    frame = df.copy()
    frame.columns = [str(column).lower() for column in frame.columns]
    required = {"date", "open", "high", "low", "close"}
    if not required.issubset(set(frame.columns)):
        return None

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    if frame.empty:
        return None
    return frame.sort_values("date")


def _round_or_none(value: Any, *, digits: int = 4) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return round(number, digits)
