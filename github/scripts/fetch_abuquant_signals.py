#!/usr/bin/env python
"""Fetch AbuQuant public report signals for report generation.

The script only reads public report pages and extracts compact signals that are
useful inside stock_analyzer reports. It does not execute trades or make a
standalone recommendation.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.request
from dataclasses import asdict, dataclass
from typing import Iterable


BASE_URL = "https://abuquant.com/abu_context/output_gi_week3/report"


@dataclass
class StrategyCount:
    name: str
    total: int
    active: int
    ratio: str


@dataclass
class IndicatorSignal:
    indicator: str
    values: str
    comment: str
    score: str
    bias: str


@dataclass
class AbuQuantSignal:
    code: str
    report_url: str
    indicator_url: str
    title: str | None
    last_modified: str | None
    last_price: str | None
    long_score: str | None
    short_score: str | None
    buy_sell_conclusion: str | None
    strategy_counts: list[StrategyCount]
    pattern_status: str | None
    pattern_direction: str | None
    pattern_bias: str | None
    pattern_time: str | None
    indicator_signals: list[IndicatorSignal]
    errors: list[str]


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
            )
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def clean_text(raw: str) -> str:
    raw = re.sub(r"<script[\s\S]*?</script>", " ", raw, flags=re.I)
    raw = re.sub(r"<style[\s\S]*?</style>", " ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", "|", raw)
    raw = html.unescape(raw)
    raw = raw.replace("\xa0", " ")
    raw = re.sub(r"\|+", "|", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return raw.strip("| \n\r\t")


def first_match(pattern: str, text: str, group: int = 1) -> str | None:
    found = re.search(pattern, text, flags=re.S)
    if not found:
        return None
    return found.group(group).strip()


def extract_strategy_counts(text: str) -> list[StrategyCount]:
    names = ["趋势跟踪", "均值回复", "止损风控", "止盈利保"]
    counts: list[StrategyCount] = []
    for name in names:
        pattern = rf"{name}\|?\s*总数:\s*(\d+)，激活:\s*(\d+)，占比:\s*([\d.]+%)"
        found = re.search(pattern, text)
        if found:
            counts.append(
                StrategyCount(
                    name=name,
                    total=int(found.group(1)),
                    active=int(found.group(2)),
                    ratio=found.group(3),
                )
            )
    return counts


def extract_indicator_rows(indicator_html: str) -> list[IndicatorSignal]:
    rows: list[IndicatorSignal] = []
    for row in re.findall(r"<tr[\s\S]*?</tr>", indicator_html, flags=re.I):
        row_text = clean_text(row)
        if not any(key in row_text for key in ["KDJ(", "MACD(", "BOLL(", "RSI(", "CCI("]):
            continue

        parts = [part.strip() for part in row_text.split("|") if part.strip()]
        start = next(
            (
                i
                for i, part in enumerate(parts)
                if any(part.startswith(key) for key in ["KDJ(", "MACD(", "BOLL(", "RSI(", "CCI("])
            ),
            None,
        )
        if start is None or len(parts) < start + 4:
            continue

        score_part = parts[start + 3].strip("(|（） ")
        bias = ""
        if start + 4 < len(parts) and parts[start + 4] in {"偏多", "偏空", "中性"}:
            bias = parts[start + 4]
        else:
            bias_match = re.search(r"(偏多|偏空|中性)", parts[start + 3])
            bias = bias_match.group(1) if bias_match else ""

        rows.append(
            IndicatorSignal(
                indicator=parts[start],
                values=parts[start + 1],
                comment=parts[start + 2],
                score=score_part,
                bias=bias,
            )
        )
    return rows


def extract_signal(code: str) -> AbuQuantSignal:
    code = code.strip()
    report_url = f"{BASE_URL}/{code}/pc.html"
    indicator_url = f"{BASE_URL}/{code}/pc_mc.html"
    errors: list[str] = []

    report_html = ""
    indicator_html = ""
    try:
        report_html = fetch(report_url)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pc.html fetch failed: {exc}")
    try:
        indicator_html = fetch(indicator_url)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"pc_mc.html fetch failed: {exc}")

    report_text = clean_text(report_html) if report_html else ""
    indicator_text = clean_text(indicator_html) if indicator_html else ""

    title = first_match(r"<title>(.*?)</title>", report_html) or first_match(
        r"<title>(.*?)</title>", indicator_html
    )
    last_modified = first_match(r'<meta\s+content="?([^">]+)"?\s+name=last-modified', report_html)
    if not last_modified:
        last_modified = first_match(r'<meta\s+content="?([^">]+)"?\s+name=last-modified', indicator_html)

    buy_sell = first_match(r"买入卖出信号量化结论[:：]\s*\|?\s*([^|<\s]+)", report_text)
    last_price = first_match(r"生成报告时最后交易价格\s*([0-9.]+)", report_text)
    long_score = first_match(r"多方[:：]\s*([0-9.]+)", report_text)
    short_score = first_match(r"空方[:：]\s*([0-9.]+)", report_text)

    pattern_status = first_match(r"指标形态[:：]\s*\|?\s*([^|]+)", indicator_text)
    direction_match = re.search(
        r"形态方向[:：]\s*([^|]+)(?:\|+\s*(看多|看空|中性|偏多|偏空))?",
        indicator_text,
        flags=re.S,
    )
    direction_text = direction_match.group(1).strip() if direction_match else None
    pattern_bias = direction_match.group(2).strip() if direction_match and direction_match.group(2) else None
    pattern_time = first_match(r"价格走势在\s*([^|]+?形成[^|]+)", indicator_text)

    return AbuQuantSignal(
        code=code,
        report_url=report_url,
        indicator_url=indicator_url,
        title=title,
        last_modified=last_modified,
        last_price=last_price,
        long_score=long_score,
        short_score=short_score,
        buy_sell_conclusion=buy_sell,
        strategy_counts=extract_strategy_counts(report_text),
        pattern_status=pattern_status,
        pattern_direction=direction_text,
        pattern_bias=pattern_bias,
        pattern_time=pattern_time,
        indicator_signals=extract_indicator_rows(indicator_html),
        errors=errors,
    )


def render_markdown(signals: Iterable[AbuQuantSignal]) -> str:
    chunks: list[str] = ["## 阿布量化策略信号\n"]
    for signal in signals:
        chunks.append(f"### {signal.code}\n")
        if signal.title:
            chunks.append(f"- 页面：{signal.title}")
        chunks.append(f"- 完整研报：{signal.report_url}")
        chunks.append(f"- 指标页：{signal.indicator_url}")
        if signal.last_modified:
            chunks.append(f"- 页面更新时间：{signal.last_modified}")
        if signal.last_price:
            chunks.append(f"- 报告最后价格：{signal.last_price}")
        if signal.long_score or signal.short_score:
            chunks.append(f"- 多空评分：多方 {signal.long_score or '-'} / 空方 {signal.short_score or '-'}")
        if signal.buy_sell_conclusion:
            chunks.append(f"- 买入卖出AI信号：{signal.buy_sell_conclusion}")
        if signal.pattern_status:
            chunks.append(
                f"- 指标形态：{signal.pattern_status}"
                + (f"；方向：{signal.pattern_direction}" if signal.pattern_direction else "")
                + (f"；形态偏向：{signal.pattern_bias}" if signal.pattern_bias else "")
            )
        if signal.pattern_time:
            chunks.append(f"- 形态时间：{signal.pattern_time}")
        if signal.strategy_counts:
            chunks.append("- 策略激活：")
            for item in signal.strategy_counts:
                chunks.append(f"  - {item.name}：总数 {item.total}，激活 {item.active}，占比 {item.ratio}")
        if signal.indicator_signals:
            chunks.append("- 指标摘要：")
            for item in signal.indicator_signals[:6]:
                chunks.append(
                    f"  - {item.indicator}：{item.comment}；评分 {item.score}"
                    + (f"（{item.bias}）" if item.bias else "")
                )
        if signal.errors:
            chunks.append("- 抓取问题：" + "；".join(signal.errors))
        chunks.append("")
    return "\n".join(chunks).strip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch AbuQuant public strategy signals.")
    parser.add_argument("codes", nargs="+", help="Codes such as 000001, 399006, 515880")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    signals = [extract_signal(code) for code in args.codes]
    if args.format == "json":
        print(json.dumps([asdict(signal) for signal in signals], ensure_ascii=False, indent=2))
    else:
        print(render_markdown(signals))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
