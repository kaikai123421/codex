from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analyzer import AnalysisResult
from src.storage import DatabaseManager
from src.services.market_radar_builder import build_market_radar_payload


REPORT_DATE = "2026-07-02"
REPORT_PATH = ROOT / "reports" / "report_20260702_close_dashboard.md"


def _has_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _build_data_reliability_summary(market_radar: dict) -> dict[str, list[str]]:
    cn_market = market_radar.get("cn_market") or {}
    indices = cn_market.get("indices") or []
    breadth = cn_market.get("breadth") or {}
    sectors = cn_market.get("sectors") or []

    verified = ["用户持仓截图", "用户成交截图", "账户仓位与现金"]
    missing = ["逐笔盘口", "暗盘资金", "精确BBI/周K", "阿布量化当日页"]

    if any(_has_number(item.get("current")) and _has_number(item.get("change_pct")) for item in indices):
        verified.append("A股指数收盘价/涨跌幅")
    else:
        missing.append("A股指数收盘价/涨跌幅")

    if _has_number(breadth.get("up_count")) and _has_number(breadth.get("down_count")):
        verified.append("涨跌家数")
    else:
        missing.append("涨跌家数")

    if _has_number(breadth.get("total_amount")):
        verified.append("成交额")
    else:
        missing.append("成交额")

    if _has_number(breadth.get("main_net_inflow")) or breadth.get("fund_flow_status") == "ok":
        verified.append("主力资金净流入")
    else:
        missing.append("主力/超大单/大单净流入")

    if any(_has_number(item.get("current")) and _has_number(item.get("change_pct")) for item in sectors):
        verified.append("科技相关板块价格/涨跌幅")
    else:
        missing.append("科技相关板块强弱")

    return {"verified": verified, "missing": missing}


def main() -> None:
    account = {
        "total_assets": 50585.84,
        "market_value": 39689.80,
        "cash": 10896.04,
        "position_pct": 78.5,
        "day_pnl": -508.10,
        "day_pnl_pct": -0.99,
        "total_pnl": 5338.18,
        "risk_light": "defense",
        "stance": "防守确认",
        "source": "用户收盘持仓截图，截图时间 2026-07-02 18:25",
    }

    cn_market = {
        "risk_light": "defense",
        "summary": "A股当日回撤，用户对账单显示7月账户跑输上证；科技线进入分化修复期，明日优先确认承接，不继续情绪化进攻。",
        "indices": [
            {
                "code": "000001",
                "name": "上证指数",
                "change_pct": -1.60,
                "source": "用户对账单截图显示7月上证 -1.60%",
                "data_date": REPORT_DATE,
            },
            {"code": "399001", "name": "深证成指", "data_status": "missing", "missing_reason": "本次未取得可核验收盘数值"},
            {"code": "399006", "name": "创业板指", "data_status": "missing", "missing_reason": "本次未取得可核验收盘数值"},
            {"code": "000688", "name": "科创50", "data_status": "missing", "missing_reason": "本次未取得可核验收盘数值"},
        ],
        "breadth": {
            "data_status": "missing",
            "missing_reason": "涨跌家数、成交额、主力净流入未从可靠接口完整取得",
        },
        "sectors": [
            {"name": "通信/5G", "strength": "弱修复观察", "impact": "negative"},
            {"name": "面板/京东方链", "strength": "相对强", "impact": "positive"},
            {"name": "AI服务器/工业富联", "strength": "弱于主线", "impact": "negative"},
        ],
        "data_status": "partial",
        "source": "用户截图 + 本地/公开行情尝试；缺失项已标注",
    }

    portfolio_matrix = [
        {
            "code": "515880",
            "name": "通信ETF",
            "action": "持有观察，弱则先减可用仓",
            "position_role": "核心利润仓 + 今日回补仓",
            "strength": "中性偏弱",
            "bbi_position": "未取得精确BBI；按现价1.576低于昨日卖出价1.714/1.716，短线仍在修复验证",
            "fund_direction": "主力/超大单数据未取得；用分批回补后仍浮盈65.23%作为仓位安全垫",
            "key_levels": ["1.576现价", "1.607/1.618今日回补区", "1.55短线防守", "1.50风险线"],
            "next_trigger": "10:30仍站不回1.57且板块继续弱，优先减可用3200中的1500-2500；收回1.60并放量修复则持有。",
        },
        {
            "code": "159994",
            "name": "5GETF",
            "action": "只验证，不追加",
            "position_role": "试错仓",
            "strength": "弱",
            "bbi_position": "未取得精确BBI；当前1.222低于两笔买入均价1.255，试仓未确认成功",
            "fund_direction": "主力资金未取得；现阶段以价格是否收回1.24作为替代观察",
            "key_levels": ["1.222现价", "1.240/1.270买入区", "1.20心理防守"],
            "next_trigger": "跌破1.20且10:30收不回，减1000-2000；收回1.24并强于通信ETF，才允许继续观察。",
        },
        {
            "code": "000725",
            "name": "京东方A",
            "action": "保留600股利润底仓，不追高",
            "position_role": "强势利润仓",
            "strength": "强",
            "bbi_position": "未取得精确BBI；从截图看仍是相对强势标的，已兑现大部分利润",
            "fund_direction": "主力资金未取得；今日高位卖出1500股锁定利润，动作优秀",
            "key_levels": ["9.10收盘持仓价", "9.44今日卖出价", "8.75前卖出价", "8.80-9.00承接区"],
            "next_trigger": "高开冲高但量价不跟时可再减200-300；若强于大盘且回踩不破8.80，600底仓继续拿。",
        },
        {
            "code": "601138",
            "name": "工业富联",
            "action": "不加仓，等修复；不是今日操作错误",
            "position_role": "弱势观察仓",
            "strength": "弱",
            "bbi_position": "未取得精确BBI；当前64.02，低于75.571成本，短线弱于科技主线",
            "fund_direction": "主力资金未取得；以价格修复能力作为替代判断",
            "key_levels": ["64.02现价", "68-70修复确认区", "75.571成本区"],
            "next_trigger": "未收回68-70前不补；若跌破63且通信/5G也弱，考虑减100股防守；放量收回70再重新评估。",
        },
    ]

    trade_timeline = [
        {
            "time": "09:34",
            "target": "通信ETF",
            "action": "买入2700 @1.618",
            "discipline": "部分符合",
            "review": "属于回补核心利润仓，但在下跌日确认不足，偏早；明天要用1.57/1.60验证。",
        },
        {
            "time": "09:37",
            "target": "京东方A",
            "action": "买入600 @8.180",
            "discipline": "符合",
            "review": "低位试仓强势标的，后续能在9.44卖出大部分，执行质量高。",
        },
        {
            "time": "09:57",
            "target": "5GETF",
            "action": "买入3400 @1.270",
            "discipline": "部分符合",
            "review": "作为试仓可以，但当天整体弱，第一笔数量略大。",
        },
        {
            "time": "13:15",
            "target": "京东方A",
            "action": "卖出1500 @9.440",
            "discipline": "符合",
            "review": "高位兑现强势票利润，是今天最干净的一笔。",
        },
        {
            "time": "13:20",
            "target": "通信ETF",
            "action": "买入2500 @1.607",
            "discipline": "待验证",
            "review": "回补第二笔后仓位升到78.5%，明天不能继续无条件加。",
        },
        {
            "time": "13:31",
            "target": "5GETF",
            "action": "买入3300 @1.240",
            "discipline": "待验证",
            "review": "分批低吸思路成立，但试仓未盈利前禁止继续扩大。",
        },
    ]

    next_session_plan = [
        {
            "phase": "开盘15分钟",
            "trigger": "通信ETF不破1.55、5GETF不破1.20，京东方不出现放量高开低走",
            "action": "不追、不补、不急卖；只看承接",
            "ratio": "0%",
            "invalid_if": "通信/5G开盘直接跌破防守位且科技板块同步弱",
        },
        {
            "phase": "10:30",
            "trigger": "通信ETF站不回1.57或5GETF站不回1.22，且指数/板块无修复",
            "action": "优先减弱仓，通信ETF可减1500-2500，5GETF可减1000-2000",
            "ratio": "总仓降到65%-72%",
            "invalid_if": "通信ETF收回1.60、5GETF收回1.24且板块资金回流",
        },
        {
            "phase": "14:30后",
            "trigger": "尾盘继续跳水或跌破关键位",
            "action": "保留京东方底仓，优先处理通信/5G新增仓；工业富联只有破63才考虑减100",
            "ratio": "按弱势仓1/3处理",
            "invalid_if": "尾盘资金回流，科技线收回上午失地",
        },
    ]

    market_radar = build_market_radar_payload(
        date=REPORT_DATE,
        account=account,
        cn_market=cn_market,
        portfolio_matrix=portfolio_matrix,
        trade_timeline=trade_timeline,
        next_session_plan=next_session_plan,
    )
    reliability_summary = _build_data_reliability_summary(market_radar)
    verified_line = "、".join(reliability_summary["verified"])
    missing_line = "、".join(reliability_summary["missing"])

    one_sentence = (
        "今天不是失败，京东方兑现很漂亮；真正要管住的是通信/5G回补后仓位回到78.5%，"
        "明天先确认止跌，再决定留强去弱。"
    )

    markdown = f"""# 2026-07-02 收盘持仓复盘与明日应对报告

用途：复盘今日操作、校准持仓纪律、制定明日三阶段动作。

风险提示：本报告仅用于交易复盘和纪律辅助，不构成投资建议；真实下单以你的风险承受能力和券商实时行情为准。

## 数据可靠性

- 用户截图时间：持仓截图 2026-07-02 18:25；对账单截图 2026-07-02 18:28。
- 已核验截图数据：总资产 50,585.84；仓位 78.5%；现金 10,896.04；当日参考盈亏 -508.10（-0.99%）；持仓包含 5GETF、京东方A、工业富联、通信ETF。
- 已核验成交：07-02 买入通信ETF 2700@1.618、2500@1.607；买入5GETF 3400@1.270、3300@1.240；买入京东方A 600@8.180；卖出京东方A 1500@9.440。
- 已接入行情数据：{verified_line}。
- 未完全取得数据：{missing_line}。缺失项不编数字。
- 外围数据：本版只作为 A股科技线风险偏好雷达；不生成美股、韩国、日本买卖建议。

## 一句话结论

{one_sentence}

## 当前账户状态

| 项目 | 数值 |
| --- | ---: |
| 总资产 | 50,585.84 |
| 总市值 | 39,689.80 |
| 现金 | 10,896.04 |
| 仓位 | 78.5% |
| 当日参考盈亏 | -508.10 / -0.99% |
| 总盈亏 | +5,338.18 |
| 风险灯 | 防守确认 |

解释：你现在不是空仓恐慌状态，也不是满仓梭哈状态。78.5%仓位在分化日偏高，明天的任务不是证明自己今天一定对，而是看通信/5G是否止跌，把现金安全垫维持住。

## 收盘持仓矩阵

| 标的 | 持仓/现价 | 盈亏 | 角色 | 当前动作 | 明日触发 |
| --- | --- | --- | --- | --- | --- |
| 5GETF | 6700 / 1.222 | -223.80（-2.66%） | 试错仓 | 只验证，不追加 | 跌破1.20且10:30收不回，减1000-2000；收回1.24再观察 |
| 京东方A | 600 / 9.100 | +2645.91（+94.02%） | 强势利润底仓 | 持有，不追高 | 高开放量滞涨可再减200-300；回踩8.80-9.00不破可拿 |
| 工业富联 | 200 / 64.020 | -2310.26（-15.29%） | 弱势观察仓 | 未操作，不算今日错误 | 未收回68-70不补；跌破63且科技线继续弱，考虑减100 |
| 通信ETF | 8400 / 1.576 | +5226.33（+65.23%） | 核心利润仓+今日回补仓 | 持有观察，弱则先减可用仓 | 10:30站不回1.57，优先减可用3200中的1500-2500；收回1.60则持有 |

## 今日操作复盘

| 时间 | 操作 | 纪律评分 | 复盘 |
| --- | --- | --- | --- |
| 09:34 | 买入通信ETF 2700 @1.618 | 6/10 | 回补核心利润仓可以理解，但确认不足，偏早。 |
| 09:37 | 买入京东方A 600 @8.180 | 8/10 | 低位试仓强势标的，后面高位兑现，质量高。 |
| 09:57 | 买入5GETF 3400 @1.270 | 5.5/10 | 试仓可以，但当天弱势，第一笔略大。 |
| 13:15 | 卖出京东方A 1500 @9.440 | 9/10 | 今天最漂亮的一笔：强势兑现利润，不恋战。 |
| 13:20 | 买入通信ETF 2500 @1.607 | 5.5/10 | 第二笔回补后仓位抬高，明天必须验证。 |
| 13:31 | 买入5GETF 3300 @1.240 | 6/10 | 分批低吸思路成立，但试错仓未盈利前禁止继续扩大。 |

总评：今天不是追涨杀跌型灾难，主要问题是“卖强成功后，又把仓位快速打回通信/5G”。这不是大错，但明天必须用规则锁住手。

## 个人规则复核

- 先试仓、确认后加仓：京东方符合；5GETF和通信ETF更像“先回补再等确认”，明天不允许继续扩大。
- 买强不买弱、去弱留强：京东方明显强；工业富联明显弱；通信ETF是长期利润仓但短线走弱；5GETF是试错仓。
- 长期趋势票看BBI/周K：本次未取得精确BBI，不能编。明天若能拿到日线/周线图，应重点看通信ETF和工业富联是否回到各自BBI上方。
- 做对了拿着，做错了不加仓：京东方做对了保留底仓；5GETF做错与否还没确认，所以不加；工业富联未修复，不补。

## 明日三阶段执行

### 开盘15分钟

只看承接，不追涨不补仓。通信ETF守1.55、5GETF守1.20、京东方不出现高开低走，就先不动。工业富联如果低开弱反，不急着砍，但也不补。

### 10:30

如果通信ETF站不回1.57，且5GETF站不回1.22，同时科技板块没有修复，优先减弱仓：通信ETF可减1500-2500，5GETF可减1000-2000，把总仓位降到65%-72%。如果通信ETF收回1.60、5GETF收回1.24，说明回补没有立刻失败，可以持有观察。

### 14:30后

尾盘如果资金回流，持有强仓，不乱砍；如果尾盘继续跳水，优先处理今日新增的通信/5G仓。京东方保留600股利润底仓；工业富联只有跌破63且科技线同步弱，才考虑减100股防守。

## 禁止操作

- 不在5GETF试仓未确认前继续补。
- 不因为工业富联亏损难受就情绪化补仓。
- 不把京东方卖飞焦虑迁移到通信/5G上。
- 不因为朋友回撤10个点就改变自己的仓位纪律。朋友的回撤是参考，不是你的交易系统。

## 后验检查

明天收盘后用三件事验证本报告：通信ETF是否收回1.60；5GETF是否收回1.24；工业富联是否收回68-70。若三项都失败，今天的回补就按“试错失败”处理，优先降仓；若通信/5G修复、京东方继续强，则保留核心仓。
"""

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(markdown, encoding="utf-8")

    dashboard = {
        "core_conclusion": {
            "one_sentence": one_sentence,
            "signal_type": "防守确认",
            "time_sensitivity": "明日开盘至10:30",
            "position_advice": {
                "has_position": "持有为主，弱势确认后减仓，不新增加仓。",
                "no_position": "不追高，等待通信/5G止跌确认。",
            },
        },
        "intelligence": {
            "risk_alerts": [
                "仓位78.5%，在分化日偏高。",
                "通信/5G今日回补后尚未确认成功。",
                "工业富联弱于主线，未收回68-70前不补。",
            ]
        },
        "battle_plan": {
            "sniper_points": {
                "ideal_buy": "无新增买点；先确认通信ETF 1.60、5GETF 1.24",
                "stop_loss": "通信ETF 1.55/5GETF 1.20/工业富联63",
                "take_profit": "京东方高开量价背离可减200-300",
            },
            "action_checklist": [
                "开盘15分钟不追不补",
                "10:30检查通信ETF 1.57/1.60",
                "14:30检查尾盘资金是否回流",
            ],
        },
        "market_radar": market_radar,
    }

    context_snapshot = {
        "marketRadar": market_radar,
        "market_radar": market_radar,
        "report_kind": "a_share_portfolio_decision_dashboard",
        "source_screenshots": [
            "8739a8ffb1aec28eb69d1d16eff728eb.jpg",
            "50f102e73e1108a251f10ea8974bda0d.jpg",
        ],
        "data_reliability": {
            "verified": reliability_summary["verified"],
            "missing": reliability_summary["missing"],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
    }

    result = AnalysisResult(
        code="PORTFOLIO",
        name="A股持仓组合",
        sentiment_score=48,
        trend_prediction="防守确认",
        operation_advice="持有为主，弱势确认后减仓，不新增加仓",
        decision_type="hold",
        confidence_level="中",
        report_language="zh",
        action="hold",
        action_label="防守持有",
        dashboard=dashboard,
        trend_analysis="A股科技线分化，通信/5G回补后尚未确认止跌；京东方相对强，工业富联弱于主线。",
        short_term_outlook="明日重点看10:30前通信ETF能否收回1.57/1.60、5GETF能否收回1.24。",
        medium_term_outlook="保留强势利润仓，弱势仓不补，等待BBI/周K与资金共振确认。",
        technical_analysis="精确BBI未取得，本报告按截图价格、成交和关键价位制定条件。",
        volume_analysis="逐笔资金与主力净流入未取得，使用成交时间线与收盘持仓作为替代证据。",
        pattern_analysis="今日交易体现先卖强后回补通信/5G，明日若回补仓不修复需降仓。",
        analysis_summary=one_sentence,
        key_points="京东方卖点优秀；通信/5G回补后需验证；工业富联未动不算今日错误；仓位78.5%要求明日偏防守。",
        risk_warning="风险来自仓位偏高、科技线继续杀跌、通信/5G回补未确认、工业富联弱势未修复。",
        buy_reason="本报告不建议新增买入；只建议确认已有回补仓是否成立。",
        news_summary=markdown,
        market_sentiment="防守确认",
        hot_topics="A股科技线、通信ETF、5GETF、京东方A、工业富联",
        data_sources="用户截图；本地market_radar；外部数据仅作风险标签，缺失项已标注。",
        search_performed=True,
        model_used="manual-stock-analyzer-dashboard",
    )

    db = DatabaseManager.get_instance()
    history_id = db.save_analysis_history(
        result,
        query_id="manual_report_20260702_close_dashboard",
        report_type="detailed",
        news_content=markdown,
        context_snapshot=context_snapshot,
        save_snapshot=True,
    )

    print(f"report_path={REPORT_PATH}")
    print(f"history_id={history_id}")


if __name__ == "__main__":
    main()
