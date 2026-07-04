from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

from src.analyzer import AnalysisResult
from src.services.market_radar_builder import build_market_radar_payload


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports"


@dataclass
class TodayDashboardArtifact:
    report_path: Path
    markdown: str
    context_snapshot: dict[str, Any]
    result: AnalysisResult


def parse_context_snapshot(raw_snapshot: Any) -> dict[str, Any]:
    if isinstance(raw_snapshot, dict):
        return raw_snapshot
    if not raw_snapshot:
        return {}
    if isinstance(raw_snapshot, str):
        try:
            parsed = json.loads(raw_snapshot)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def load_latest_dashboard_snapshot(db: Any, *, limit: int = 50) -> dict[str, Any]:
    records, _total = db.get_analysis_history_paginated(offset=0, limit=limit)
    for record in records:
        snapshot = parse_context_snapshot(getattr(record, "context_snapshot", None))
        radar = snapshot.get("market_radar") or snapshot.get("marketRadar")
        if isinstance(radar, dict) and radar:
            snapshot["market_radar"] = radar
            snapshot["marketRadar"] = radar
            return snapshot
    return {}


def _copy_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _copy_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def build_reused_inputs(latest_snapshot: Mapping[str, Any], *, trade_date: str) -> dict[str, Any]:
    radar = latest_snapshot.get("market_radar") or latest_snapshot.get("marketRadar") or {}
    radar = radar if isinstance(radar, Mapping) else {}
    previous_date = str(radar.get("date") or "")

    account = _copy_mapping(radar.get("account"))
    if account:
        account["data_status"] = "stale_from_previous_report"
        account["source_note"] = (
            f"latest saved dashboard snapshot date={previous_date or 'unknown'}; "
            "refresh with user screenshots after close"
        )

    portfolio_matrix = _copy_list(radar.get("portfolio_matrix") or radar.get("portfolioMatrix"))
    for item in portfolio_matrix:
        item["data_status"] = "stale_from_previous_report"
        item["source_note"] = f"latest saved dashboard snapshot date={previous_date or 'unknown'}"

    same_trade_day = previous_date == trade_date
    trade_timeline = _copy_list(radar.get("trade_timeline") or radar.get("tradeTimeline")) if same_trade_day else []
    next_session_plan = _copy_list(radar.get("next_session_plan") or radar.get("nextSessionPlan")) if same_trade_day else []

    return {
        "account": account,
        "portfolio_matrix": portfolio_matrix,
        "trade_timeline": trade_timeline,
        "next_session_plan": next_session_plan,
        "previous_snapshot_date": previous_date,
    }


def _fmt(value: Any) -> str:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:,.2f}"
    return str(value) if value not in (None, "") else "未取得"


def _first_rows(rows: Any, count: int = 6) -> list[Mapping[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows[:count] if isinstance(row, Mapping)]


def _row_has_value(row: Mapping[str, Any]) -> bool:
    return any(row.get(key) not in (None, "", "未取得") for key in ("current", "change_pct", "total_amount", "main_net_inflow"))


def _collect_market_rows(cn_market: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    for key in ("indices", "sectors"):
        value = cn_market.get(key)
        if isinstance(value, list):
            rows.extend(item for item in value if isinstance(item, Mapping))
    breadth = cn_market.get("breadth")
    if isinstance(breadth, Mapping):
        rows.append(breadth)
    return rows


def infer_market_freshness(market_radar: Mapping[str, Any], *, trade_date: str) -> tuple[str, str]:
    cn_market = _copy_mapping(market_radar.get("cn_market") or market_radar.get("cnMarket"))
    usable_rows = [row for row in _collect_market_rows(cn_market) if _row_has_value(row)]
    if not usable_rows:
        return "missing", "行情数据缺失"

    same_day_rows = [
        row
        for row in usable_rows
        if str(row.get("data_date") or row.get("dataDate") or "")[:10] == trade_date
    ]
    if not same_day_rows:
        return "stale_other_day", "非今日旧数据"

    stale_rows = [
        row
        for row in same_day_rows
        if str(row.get("data_status") or row.get("dataStatus") or "").lower() in {"stale", "cached"}
        or "cache" in str(row.get("source") or "").lower()
    ]
    if stale_rows:
        return "same_day_stale", "今日滞后数据"
    return "same_day_current", "今日在线数据"


def _market_rows_markdown(market_radar: Mapping[str, Any]) -> str:
    cn_market = _copy_mapping(market_radar.get("cn_market") or market_radar.get("cnMarket"))
    indices = _first_rows(cn_market.get("indices"))
    sectors = _first_rows(cn_market.get("sectors"))
    breadth = _copy_mapping(cn_market.get("breadth"))

    index_lines = [
        (
            f"- {row.get('name') or row.get('code')}: {_fmt(row.get('current'))}, "
            f"{row.get('change_pct', '未取得')}%, source={row.get('source', 'unknown')}, "
            f"time={row.get('data_date', 'unknown')}"
        )
        for row in indices
    ] or ["- 未取得A股指数"]
    sector_lines = [
        (
            f"- {row.get('name') or row.get('code')}: {_fmt(row.get('current'))}, "
            f"{row.get('change_pct', '未取得')}%, fund_flow={row.get('fund_flow', '未取得')}, "
            f"time={row.get('data_date', 'unknown')}"
        )
        for row in sectors
    ] or ["- 未取得重点板块/ETF"]

    return "\n".join(
        [
            "## A股市场雷达",
            *index_lines,
            "",
            f"- 成交额: {_fmt(breadth.get('total_amount'))}",
            f"- 主力资金估算: {_fmt(breadth.get('main_net_inflow'))}",
            f"- 数据状态: {cn_market.get('data_status', 'unknown')}",
            "",
            "## 科技线重点代理",
            *sector_lines,
        ]
    )


def _external_rows_markdown(market_radar: Mapping[str, Any]) -> str:
    external = _copy_mapping(market_radar.get("external_radar") or market_radar.get("externalRadar"))
    groups = external.get("groups") if isinstance(external.get("groups"), list) else []
    lines = [
        "## 外围影响雷达",
        "只作为 A股科技线风险偏好参考，不生成海外买卖建议。",
    ]
    if not groups:
        lines.append("- 外围数据未取得")
        return "\n".join(lines)
    for group in groups:
        if isinstance(group, Mapping):
            lines.append(f"- {group.get('title') or group.get('region')}: {group.get('impact', 'missing')}")
    return "\n".join(lines)


def infer_cn_session_status(generated_at: str) -> str:
    try:
        clock = datetime.fromisoformat(generated_at).time()
    except Exception:
        return "unknown"
    if clock.hour < 9 or (clock.hour == 9 and clock.minute < 30):
        return "pre_market"
    if clock.hour < 15 or (clock.hour == 15 and clock.minute <= 5):
        return "intraday"
    return "post_close"


def _session_status_label(status: str) -> str:
    return {
        "pre_market": "开盘前快照",
        "intraday": "盘中快照",
        "post_close": "收盘后快照",
    }.get(status, "未知时段快照")


def build_today_dashboard_artifact(
    *,
    trade_date: str,
    latest_snapshot: Optional[Mapping[str, Any]] = None,
    market_builder: Callable[..., dict[str, Any]] = build_market_radar_payload,
    generated_at: Optional[str] = None,
) -> TodayDashboardArtifact:
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    session_status = infer_cn_session_status(generated_at)
    latest_snapshot = latest_snapshot or {}
    reused = build_reused_inputs(latest_snapshot, trade_date=trade_date)
    market_radar = market_builder(
        date=trade_date,
        account=reused["account"],
        portfolio_matrix=reused["portfolio_matrix"],
        trade_timeline=reused["trade_timeline"],
        next_session_plan=reused["next_session_plan"],
        market_stats_timeout_seconds=45,
    )
    market_freshness, market_freshness_label = infer_market_freshness(market_radar, trade_date=trade_date)
    cn_market = market_radar.get("cn_market") if isinstance(market_radar, Mapping) else None
    if isinstance(cn_market, dict):
        cn_market.setdefault("session_status", session_status)
        cn_market.setdefault("session_status_label", _session_status_label(session_status))
        cn_market.setdefault("market_freshness", market_freshness)
        cn_market.setdefault("market_freshness_label", market_freshness_label)

    session_label = _session_status_label(session_status)
    if session_status == "post_close":
        purpose_text = "用途：收盘后先看当天收盘行情，晚上再用你的持仓和成交截图复盘。"
        one_sentence = "已重新联网抓取今天收盘后行情；持仓快照若非今天，只作参考，晚上用截图复盘。"
        trend_prediction = "收盘后雷达刷新"
        operation_advice = "等待收盘持仓截图校准后复盘"
        key_points = "在线收盘行情已刷新；旧持仓只作参考；晚上补截图后复盘。"
    elif session_status == "pre_market":
        purpose_text = "用途：开盘前先看最近可用行情和外围影响，开盘后再刷新 A股盘中数据。"
        one_sentence = "已联网抓取开盘前可用行情；持仓快照若非今天，只作参考，开盘后再校准。"
        trend_prediction = "开盘前雷达刷新"
        operation_advice = "等待开盘后行情确认再决策"
        key_points = "开盘前行情已刷新；外围只作风险偏好参考；开盘后再确认真实强弱。"
    else:
        purpose_text = "用途：盘中先看真实行情，晚上再用你的持仓和成交截图复盘。"
        one_sentence = "已重新联网抓取今天行情；持仓快照若非今天，只作参考，晚上用截图复盘。"
        trend_prediction = "盘中雷达刷新"
        operation_advice = "等待持仓截图校准后决策"
        key_points = "在线行情已刷新；旧持仓只作参考；晚上补截图后复盘。"

    markdown = "\n\n".join(
        [
            f"# {trade_date} A股持仓决策仪表盘",
            purpose_text,
            f"- 生成时间: {generated_at}",
            f"- 数据时段: {session_label}",
            (
                f"- 持仓来源: 最近一份已保存仪表盘快照 date="
                f"{reused['previous_snapshot_date'] or '未取得'}；若不是今天，请以晚上截图为准。"
            ),
            "- 在线行情: 已调用 market_radar_builder 抓取今天/最新 A股和外围影响数据；数据缺失处保持未取得。",
            "一句话：先让市场数据自己说话，再决定你的仓位动作；旧持仓只做参考，不冒充今天实盘。",
            _market_rows_markdown(market_radar),
            _external_rows_markdown(market_radar),
            (
                "## 晚上复盘需要你补充\n"
                "- 收盘持仓截图\n"
                "- 今日成交截图\n"
                "- 你当时的操作理由\n\n"
                "拿到这些后，report 会补齐操作时间线、纪律评分和明日三阶段计划。"
            ),
        ]
    )
    markdown = f"{markdown}\n\n- market_freshness: {market_freshness} / {market_freshness_label}"

    context_snapshot = {
        "market_radar": market_radar,
        "marketRadar": market_radar,
        "report_kind": "a_share_today_market_dashboard",
        "data_reliability": {
            "generated_at": generated_at,
            "session_status": session_status,
            "session_status_label": session_label,
            "online_market": "attempted",
            "market_freshness": market_freshness,
            "market_freshness_label": market_freshness_label,
            "portfolio_snapshot": "stale_from_previous_report"
            if reused["previous_snapshot_date"] != trade_date
            else "same_day",
            "previous_snapshot_date": reused["previous_snapshot_date"],
        },
    }

    dashboard = {
        "core_conclusion": {
            "one_sentence": one_sentence,
            "signal_type": "market_radar_refresh",
            "time_sensitivity": session_status,
            "position_advice": {
                "has_position": "先看 A股雷达和持仓矩阵，不根据旧截图盲动。",
                "no_position": "没有当天持仓截图时，不生成重仓买卖动作。",
            },
        },
        "intelligence": {
            "risk_alerts": [
                "账户和持仓若来自旧快照，需要晚上截图校准。",
                "外围只作为 A股科技线风险偏好参考。",
            ]
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "等待当天持仓/成交确认后给出。",
                "stop_loss": "等待当天持仓/成交确认后给出。",
                "take_profit": "等待当天持仓/成交确认后给出。",
            },
            "action_checklist": [
                "先确认 today market_radar 是否有 A股指数和重点ETF数据。",
                "晚上用收盘持仓和成交截图补齐交易时间线。",
            ],
        },
        "market_radar": market_radar,
    }

    result = AnalysisResult(
        code="PORTFOLIO",
        name="A股持仓组合",
        sentiment_score=50,
        trend_prediction=trend_prediction,
        operation_advice=operation_advice,
        decision_type="hold",
        confidence_level="中",
        report_language="zh",
        action="hold",
        action_label="观察",
        dashboard=dashboard,
        analysis_summary=one_sentence,
        key_points=key_points,
        risk_warning="缺少当天收盘持仓和成交截图时，不给确定性买卖结论。",
        data_sources="market_radar_builder online fetch + latest saved dashboard snapshot",
        search_performed=True,
        model_used="today-market-dashboard-generator",
        news_summary=markdown,
    )

    report_path = REPORT_DIR / f"report_{trade_date.replace('-', '')}_market_dashboard.md"
    return TodayDashboardArtifact(
        report_path=report_path,
        markdown=markdown,
        context_snapshot=context_snapshot,
        result=result,
    )


def save_today_market_dashboard(
    db: Any,
    *,
    trade_date: Optional[str] = None,
    market_builder: Callable[..., dict[str, Any]] = build_market_radar_payload,
    generated_at: Optional[str] = None,
) -> tuple[int, TodayDashboardArtifact]:
    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    latest_snapshot = load_latest_dashboard_snapshot(db)
    artifact = build_today_dashboard_artifact(
        trade_date=trade_date,
        latest_snapshot=latest_snapshot,
        market_builder=market_builder,
        generated_at=generated_at,
    )

    artifact.report_path.parent.mkdir(parents=True, exist_ok=True)
    artifact.report_path.write_text(artifact.markdown, encoding="utf-8")

    history_id = db.save_analysis_history(
        artifact.result,
        query_id=f"today_market_dashboard_{trade_date.replace('-', '')}",
        report_type="detailed",
        news_content=artifact.markdown,
        context_snapshot=artifact.context_snapshot,
        save_snapshot=True,
    )
    return int(history_id or 0), artifact
