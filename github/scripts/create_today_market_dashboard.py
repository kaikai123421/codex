from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analyzer import AnalysisResult
from src.storage import DatabaseManager
from src.services.market_radar_builder import build_market_radar_payload


REPORT_DIR = ROOT / "reports"


@dataclass
class TodayDashboardArtifact:
    report_path: Path
    markdown: str
    context_snapshot: dict[str, Any]
    result: AnalysisResult


def _parse_context_snapshot(raw_snapshot: Any) -> dict[str, Any]:
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


def _load_latest_dashboard_snapshot(db: Any, *, limit: int = 50) -> dict[str, Any]:
    records, _total = db.get_analysis_history_paginated(offset=0, limit=limit)
    for record in records:
        snapshot = _parse_context_snapshot(getattr(record, "context_snapshot", None))
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


def _build_reused_inputs(latest_snapshot: Mapping[str, Any], *, trade_date: str) -> dict[str, Any]:
    radar = latest_snapshot.get("market_radar") or latest_snapshot.get("marketRadar") or {}
    radar = radar if isinstance(radar, Mapping) else {}
    previous_date = str(radar.get("date") or "")

    account = _copy_mapping(radar.get("account"))
    if account:
        account["data_status"] = "stale_from_previous_report"
        account["source_note"] = f"latest saved dashboard snapshot date={previous_date or 'unknown'}; refresh with user screenshots after close"

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


def _market_rows_markdown(market_radar: Mapping[str, Any]) -> str:
    cn_market = _copy_mapping(market_radar.get("cn_market") or market_radar.get("cnMarket"))
    indices = _first_rows(cn_market.get("indices"))
    sectors = _first_rows(cn_market.get("sectors"))
    breadth = _copy_mapping(cn_market.get("breadth"))

    index_lines = [
        f"- {row.get('name') or row.get('code')}: {_fmt(row.get('current'))}, {row.get('change_pct', '未取得')}%, source={row.get('source', 'unknown')}, time={row.get('data_date', 'unknown')}"
        for row in indices
    ] or ["- 未取得 A股指数"]
    sector_lines = [
        f"- {row.get('name') or row.get('code')}: {_fmt(row.get('current'))}, {row.get('change_pct', '未取得')}%, fund_flow={row.get('fund_flow', '未取得')}, time={row.get('data_date', 'unknown')}"
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
    lines = ["## 外围影响雷达", "只作为 A股科技线风险偏好参考，不生成海外买卖建议。"]
    if not groups:
        lines.append("- 外围数据未取得")
        return "\n".join(lines)
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        lines.append(f"- {group.get('title') or group.get('region')}: {group.get('impact', 'missing')}")
    return "\n".join(lines)


def build_today_dashboard_artifact(
    *,
    trade_date: str,
    latest_snapshot: Optional[Mapping[str, Any]] = None,
    market_builder: Callable[..., dict[str, Any]] = build_market_radar_payload,
    generated_at: Optional[str] = None,
) -> TodayDashboardArtifact:
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    latest_snapshot = latest_snapshot or {}
    reused = _build_reused_inputs(latest_snapshot, trade_date=trade_date)
    market_radar = market_builder(
        date=trade_date,
        account=reused["account"],
        portfolio_matrix=reused["portfolio_matrix"],
        trade_timeline=reused["trade_timeline"],
        next_session_plan=reused["next_session_plan"],
    )

    markdown = "\n\n".join(
        [
            f"# {trade_date} A股持仓决策仪表盘",
            "用途：盘中先看真实行情，晚上再用你的持仓和成交截图复盘。",
            f"- 生成时间: {generated_at}",
            f"- 持仓来源: 最近一份已保存仪表盘快照 date={reused['previous_snapshot_date'] or '未取得'}；若不是今天，请以晚上截图为准。",
            "- 在线行情: 已调用 market_radar_builder 抓取今天/最新 A股和外围影响数据；数据缺失处保持未取得。",
            "一句话：先让市场数据自己说话，再决定你的仓位动作；旧持仓只做参考，不冒充今天实盘。",
            _market_rows_markdown(market_radar),
            _external_rows_markdown(market_radar),
            "## 晚上复盘需要你补充\n- 收盘持仓截图\n- 今日成交截图\n- 你当时的操作理由\n\n拿到这些后，report 会补齐操作时间线、纪律评分和明日三阶段计划。",
        ]
    )

    context_snapshot = {
        "market_radar": market_radar,
        "marketRadar": market_radar,
        "report_kind": "a_share_today_market_dashboard",
        "data_reliability": {
            "generated_at": generated_at,
            "online_market": "attempted",
            "portfolio_snapshot": "stale_from_previous_report" if reused["previous_snapshot_date"] != trade_date else "same_day",
            "previous_snapshot_date": reused["previous_snapshot_date"],
        },
    }

    one_sentence = "已重新联网抓取今天行情；持仓快照若非今天，只作参考，晚上用截图复盘。"
    dashboard = {
        "core_conclusion": {
            "one_sentence": one_sentence,
            "signal_type": "market_radar_refresh",
            "time_sensitivity": "intraday",
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
        trend_prediction="盘中雷达刷新",
        operation_advice="等待持仓截图校准后决策",
        decision_type="hold",
        confidence_level="中",
        report_language="zh",
        action="hold",
        action_label="观察",
        dashboard=dashboard,
        analysis_summary=one_sentence,
        key_points="在线行情已刷新；旧持仓只作参考；晚上补截图后复盘。",
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


def main() -> None:
    trade_date = datetime.now().strftime("%Y-%m-%d")
    db = DatabaseManager.get_instance()
    latest_snapshot = _load_latest_dashboard_snapshot(db)
    artifact = build_today_dashboard_artifact(trade_date=trade_date, latest_snapshot=latest_snapshot)

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

    print(f"report_path={artifact.report_path}")
    print(f"history_id={history_id}")


from src.services.today_market_dashboard_service import (
    REPORT_DIR as _SERVICE_REPORT_DIR,
    TodayDashboardArtifact as _ServiceTodayDashboardArtifact,
    build_reused_inputs as _service_build_reused_inputs,
    build_today_dashboard_artifact as _service_build_today_dashboard_artifact,
    load_latest_dashboard_snapshot as _service_load_latest_dashboard_snapshot,
    parse_context_snapshot as _service_parse_context_snapshot,
    save_today_market_dashboard as _service_save_today_market_dashboard,
)

REPORT_DIR = _SERVICE_REPORT_DIR
TodayDashboardArtifact = _ServiceTodayDashboardArtifact
_parse_context_snapshot = _service_parse_context_snapshot
_load_latest_dashboard_snapshot = _service_load_latest_dashboard_snapshot
_build_reused_inputs = _service_build_reused_inputs
build_today_dashboard_artifact = _service_build_today_dashboard_artifact


def main() -> None:
    trade_date = datetime.now().strftime("%Y-%m-%d")
    db = DatabaseManager.get_instance()
    history_id, artifact = _service_save_today_market_dashboard(db, trade_date=trade_date)

    print(f"report_path={artifact.report_path}")
    print(f"history_id={history_id}")


if __name__ == "__main__":
    main()
