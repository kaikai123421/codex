# -*- coding: utf-8 -*-
"""
===================================
分析服务层
===================================

职责：
1. 封装股票分析逻辑
2. 调用 analyzer 和 pipeline 执行分析
3. 保存分析结果到数据库
"""

import logging
import copy
import json
import os
import urllib.request
import uuid
from typing import Optional, Dict, Any, Callable, List

from src.repositories.analysis_repo import AnalysisRepository
from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.market_phase_summary import extract_market_phase_summary
from src.schemas.decision_action import build_action_fields
from src.services.run_diagnostics import (
    activate_run_diagnostic_context,
    build_run_diagnostic_summary,
    get_current_diagnostic_context,
    reset_run_diagnostic_context,
)

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    分析服务
    
    封装股票分析相关的业务逻辑
    """
    
    def __init__(self):
        """初始化分析服务"""
        self.repo = AnalysisRepository()
        self.last_error: Optional[str] = None
    
    def analyze_stock(
        self,
        stock_code: str,
        report_type: str = "detailed",
        force_refresh: bool = False,
        query_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        send_notification: bool = True,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        skills: Optional[List[str]] = None,
        analysis_phase: str = "auto",
        query_source: str = "api",
        portfolio_context: Optional[Dict[str, Any]] = None,
        report_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        执行股票分析
        
        Args:
            stock_code: 股票代码
            report_type: 报告类型 (simple/detailed)
            force_refresh: 是否强制刷新
            query_id: 查询 ID（可选）
            send_notification: 是否发送通知（API 触发默认发送）
            analysis_phase: 请求的分析阶段覆盖（auto/premarket/intraday/postmarket）
            
        Returns:
            分析结果字典，包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - report: 分析报告
        """
        try:
            self.last_error = None
            # 导入分析相关模块
            from src.config import get_config
            from src.enums import ReportType
            
            # 生成 query_id
            if query_id is None:
                query_id = uuid.uuid4().hex
            effective_trace_id = trace_id or query_id
            diag_token = None
            if get_current_diagnostic_context() is None:
                diag_token = activate_run_diagnostic_context(
                    trace_id=effective_trace_id,
                    query_id=query_id,
                    stock_code=stock_code,
                    trigger_source=query_source or "api",
                )
            
            # 获取配置
            config = get_config()
            normalized_report_language = normalize_report_language(report_language, default="")
            if normalized_report_language:
                config = copy.copy(config)
                config.report_language = normalized_report_language

            rt = ReportType.from_str(report_type)
            if self._render_light_mode_enabled():
                if progress_callback:
                    progress_callback(35, "云端轻量模式：正在读取行情")
                result = self._build_lightweight_result(
                    stock_code=stock_code,
                    query_id=query_id,
                    report_language=normalized_report_language or "zh",
                )
                if progress_callback:
                    progress_callback(95, "云端轻量模式：生成基础判断")
                return self._build_analysis_response(result, query_id, report_type=rt.value)
            
            # 创建分析流水线
            from src.core.pipeline import StockAnalysisPipeline

            pipeline = StockAnalysisPipeline(
                config=config,
                query_id=query_id,
                trace_id=effective_trace_id,
                query_source=query_source or "api",
                progress_callback=progress_callback,
                analysis_skills=skills,
                analysis_phase=analysis_phase,
                portfolio_context=portfolio_context,
            )
            
            # 确定报告类型 (API: simple/detailed/full/brief -> ReportType)
            rt = ReportType.from_str(report_type)
            
            # 执行分析
            result = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=send_notification,
                report_type=rt,
            )
            
            if result is None:
                logger.warning(f"分析股票 {stock_code} 返回空结果")
                self.last_error = self.last_error or f"分析股票 {stock_code} 返回空结果"
                return None

            if not getattr(result, "success", True):
                self.last_error = getattr(result, "error_message", None) or f"分析股票 {stock_code} 失败"
                logger.warning(f"分析股票 {stock_code} 未成功完成: {self.last_error}")
                return None
            
            # 构建响应
            return self._build_analysis_response(result, query_id, report_type=rt.value)
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"分析股票 {stock_code} 失败: {e}", exc_info=True)
            return None
        finally:
            reset_run_diagnostic_context(locals().get("diag_token"))

    def _render_light_mode_enabled(self) -> bool:
        value = os.getenv("RENDER_ANALYSIS_LIGHT_MODE")
        if value is not None:
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return os.getenv("RENDER", "").strip().lower() == "true" or bool(os.getenv("RENDER_SERVICE_ID"))

    def analyze_stock_lightweight(
        self,
        stock_code: str,
        report_type: str = "brief",
        query_id: Optional[str] = None,
        report_language: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Run the dependency-light quote analysis used by cloud chat fallback."""
        try:
            self.last_error = None
            if query_id is None:
                query_id = uuid.uuid4().hex
            normalized_report_language = normalize_report_language(report_language, default="zh") or "zh"
            result = self._build_lightweight_result(
                stock_code=stock_code,
                query_id=query_id,
                report_language=normalized_report_language,
            )
            return self._build_analysis_response(result, query_id, report_type=report_type)
        except Exception as exc:
            self.last_error = str(exc)
            logger.error("轻量分析股票 %s 失败: %s", stock_code, exc, exc_info=True)
            return None

    def _eastmoney_secid(self, stock_code: str) -> str:
        code = str(stock_code).strip()
        if code.startswith(("5", "6", "9")):
            return f"1.{code}"
        return f"0.{code}"

    def _tencent_symbol(self, stock_code: str) -> str:
        code = str(stock_code).strip()
        prefix = "sh" if code.startswith(("5", "6", "9")) else "sz"
        return f"{prefix}{code}"

    def _safe_float(self, value: Any) -> Optional[float]:
        try:
            if value is None or value == "-":
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _fetch_light_quote(self, stock_code: str) -> Dict[str, Any]:
        fields = "f12,f14,f2,f3,f4,f5,f6,f8,f10,f15,f16,f17,f18,f62"
        url = (
            "https://push2.eastmoney.com/api/qt/ulist.np/get"
            f"?fltt=2&invt=2&fields={fields}&secids={self._eastmoney_secid(stock_code)}"
        )
        timeout = float(os.getenv("LIGHT_ANALYSIS_QUOTE_TIMEOUT", "5") or "5")
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 DSA-LightMode/1.0",
                    "Referer": "https://quote.eastmoney.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            rows = ((payload or {}).get("data") or {}).get("diff") or []
            if not rows:
                fallback = self._fetch_tencent_light_quote(stock_code)
                if fallback.get("ok"):
                    fallback["fallback_from"] = "eastmoney_empty"
                    return fallback
                return {"ok": False, "error": "empty quote response", "source": "eastmoney_push2"}
            row = rows[0]
            return {
                "ok": True,
                "source": "eastmoney_push2",
                "code": str(row.get("f12") or stock_code),
                "name": row.get("f14") or f"股票{stock_code}",
                "price": self._safe_float(row.get("f2")),
                "change_pct": self._safe_float(row.get("f3")),
                "change": self._safe_float(row.get("f4")),
                "volume": self._safe_float(row.get("f5")),
                "amount": self._safe_float(row.get("f6")),
                "turnover": self._safe_float(row.get("f8")),
                "volume_ratio": self._safe_float(row.get("f10")),
                "high": self._safe_float(row.get("f15")),
                "low": self._safe_float(row.get("f16")),
                "open": self._safe_float(row.get("f17")),
                "prev_close": self._safe_float(row.get("f18")),
                "main_fund": self._safe_float(row.get("f62")),
            }
        except Exception as exc:
            logger.warning("light quote fetch failed for %s: %s", stock_code, exc)
            fallback = self._fetch_tencent_light_quote(stock_code)
            if fallback.get("ok"):
                fallback["fallback_from"] = f"eastmoney_error:{type(exc).__name__}"
                return fallback
            return {"ok": False, "error": str(exc), "source": "eastmoney_push2"}

    def _fetch_tencent_light_quote(self, stock_code: str) -> Dict[str, Any]:
        symbol = self._tencent_symbol(stock_code)
        url = f"https://qt.gtimg.cn/q={symbol}"
        timeout = float(os.getenv("LIGHT_ANALYSIS_QUOTE_TIMEOUT", "5") or "5")
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 DSA-LightMode/1.0",
                    "Referer": "https://gu.qq.com/",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("gbk", errors="replace")
            _, _, quoted = text.partition('="')
            raw = quoted.rsplit('"', 1)[0] if quoted else ""
            parts = raw.split("~")
            if len(parts) < 39 or not parts[2]:
                return {"ok": False, "error": "empty tencent quote response", "source": "tencent_gtimg"}

            amount_wan = self._safe_float(parts[37] if len(parts) > 37 else None)
            return {
                "ok": True,
                "source": "tencent_gtimg",
                "code": parts[2] or stock_code,
                "name": parts[1] or f"\u80a1\u7968{stock_code}",
                "price": self._safe_float(parts[3]),
                "change_pct": self._safe_float(parts[32] if len(parts) > 32 else None),
                "change": self._safe_float(parts[31] if len(parts) > 31 else None),
                "volume": self._safe_float(parts[36] if len(parts) > 36 else None),
                "amount": amount_wan * 10000 if amount_wan is not None else None,
                "turnover": self._safe_float(parts[38] if len(parts) > 38 else None),
                "volume_ratio": self._safe_float(parts[49] if len(parts) > 49 else None),
                "high": self._safe_float(parts[33] if len(parts) > 33 else None),
                "low": self._safe_float(parts[34] if len(parts) > 34 else None),
                "open": self._safe_float(parts[5] if len(parts) > 5 else None),
                "prev_close": self._safe_float(parts[4] if len(parts) > 4 else None),
                "main_fund": None,
            }
        except Exception as exc:
            logger.warning("tencent light quote fetch failed for %s: %s", stock_code, exc)
            return {"ok": False, "error": str(exc), "source": "tencent_gtimg"}

    def _build_lightweight_result(
        self,
        stock_code: str,
        query_id: Optional[str],
        report_language: str = "zh",
    ) -> Any:
        from src.analyzer import AnalysisResult

        quote = self._fetch_light_quote(stock_code)
        source_name = quote.get("source") or "unknown"
        if quote.get("fallback_from"):
            source_name = f"{source_name} (fallback: {quote.get('fallback_from')})"
        price = quote.get("price") if quote.get("ok") else None
        change_pct = quote.get("change_pct") if quote.get("ok") else None
        name = quote.get("name") if quote.get("ok") else f"股票{stock_code}"
        score = 50
        trend = "震荡"
        if isinstance(change_pct, (int, float)):
            if change_pct >= 3:
                score, trend = 58, "偏强震荡"
            elif change_pct <= -3:
                score, trend = 42, "偏弱震荡"
            elif change_pct > 0:
                score, trend = 53, "小幅修复"
            elif change_pct < 0:
                score, trend = 47, "小幅承压"

        if quote.get("ok"):
            quote_line = (
                f"{name}({stock_code}) 现价 {price if price is not None else '未取得'}，"
                f"涨跌幅 {change_pct if change_pct is not None else '未取得'}%。"
            )
            data_line = (
                f"成交额 {quote.get('amount') if quote.get('amount') is not None else '未取得'}，"
                f"换手 {quote.get('turnover') if quote.get('turnover') is not None else '未取得'}，"
                f"主力资金 {quote.get('main_fund') if quote.get('main_fund') is not None else '未取得'}。"
            )
        else:
            quote_line = f"{name}({stock_code}) 云端未能取得实时行情。"
            data_line = f"行情接口失败：{quote.get('error') or 'unknown error'}。"

        summary = (
            f"云端轻量模式：{quote_line} 当前线上环境为了避免 Render 免费实例被完整分析链路拖成 502，"
            "本次只输出行情驱动的基础判断。完整 report 仍应以 BBI、日线/周线、资金流、持仓矩阵和你的交易纪律综合确认。"
        )
        technical = (
            f"{quote_line} {data_line} BBI：轻量模式不编造 BBI，未取得日线序列时不做 BBI 结论；"
            "正式交易判断必须等待 BBI/均线结构和量价确认。"
        )
        dashboard = {
            "core_conclusion": {
                "one_sentence": summary,
                "position_advice": {
                    "has_position": "先观望，不因轻量行情结果追涨杀跌；等 BBI 和资金确认。",
                    "no_position": "未持仓先等确认，不在数据不完整时重仓试错。",
                },
            },
            "battle_plan": {
                "sniper_points": {
                    "ideal_buy": "需完整 BBI/量价确认",
                    "secondary_buy": "回踩不破关键均线且资金回流",
                    "stop_loss": "跌破 BBI 或放量破位时重新评估",
                    "take_profit": "大涨后按计划取利润，不临盘情绪化",
                },
                "action_checklist": [
                    "确认 BBI 位置",
                    "确认量价是否背离",
                    "确认主力资金方向",
                    "确认是否符合先试仓、确认后加仓",
                ],
            },
        }
        risk = (
            "这是云端稳定优先的基础结果，不构成投资建议。若页面显示数据缺失，按未验证处理；"
            "你的规则仍然优先：先试仓，确认后加仓，买强不买弱，做错不加仓。"
        )
        return AnalysisResult(
            code=str(stock_code),
            name=str(name),
            sentiment_score=score,
            trend_prediction=trend,
            operation_advice="观望",
            decision_type="hold",
            confidence_level="低",
            report_language=report_language,
            action="watch",
            dashboard=dashboard,
            technical_analysis=technical,
            ma_analysis="云端轻量模式未运行完整均线/BBI计算。",
            volume_analysis=data_line,
            fundamental_analysis="云端轻量模式未运行基本面链路。",
            news_summary="云端轻量模式未抓取新闻，避免外部依赖导致 502。",
            analysis_summary=summary,
            key_points="轻量模式只用于保证线上可用；深度判断必须回到 BBI、资金、量价和持仓纪律。",
            risk_warning=risk,
            buy_reason="数据不完整时不主动给买入结论。",
            market_snapshot=quote,
            search_performed=False,
            data_sources=f"{source_name}; render_light_mode",
            success=True,
            current_price=price,
            change_pct=change_pct,
            model_used="render-lightweight-safe-mode",
            query_id=query_id,
        )
    
    def _build_analysis_response(
        self, 
        result: Any, 
        query_id: str,
        report_type: str = "detailed",
    ) -> Dict[str, Any]:
        """
        构建分析响应
        
        Args:
            result: AnalysisResult 对象
            query_id: 查询 ID
            report_type: 归一化后的报告类型
            
        Returns:
            格式化的响应字典
        """
        # 获取狙击点位
        sniper_points = {}
        if hasattr(result, 'get_sniper_points'):
            sniper_points = result.get_sniper_points() or {}
        
        # 计算情绪标签
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        sentiment_label = get_sentiment_label(result.sentiment_score, report_language)
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        action_fields = build_action_fields(
            operation_advice=getattr(result, "operation_advice", None),
            explicit_action=getattr(result, "action", None),
            report_type=report_type,
            report_language=report_language,
        )
        diagnostic_context = get_current_diagnostic_context()
        trace_id = diagnostic_context.trace_id if diagnostic_context is not None else query_id
        diagnostic_snapshot = diagnostic_context.snapshot() if diagnostic_context is not None else None
        diagnostic_context_snapshot = getattr(result, "diagnostic_context_snapshot", None)
        market_phase_summary = extract_market_phase_summary(diagnostic_context_snapshot)
        if isinstance(diagnostic_context_snapshot, dict):
            context_snapshot = dict(diagnostic_context_snapshot)
            if diagnostic_snapshot is not None:
                context_snapshot["diagnostics"] = diagnostic_snapshot
        elif diagnostic_snapshot is not None:
            context_snapshot = {"diagnostics": diagnostic_snapshot}
        else:
            context_snapshot = None
        diagnostic_summary = build_run_diagnostic_summary(
            context_snapshot=context_snapshot,
            raw_result=result.to_dict() if hasattr(result, "to_dict") else None,
            report_saved=True,
            query_id=query_id,
            stock_code=result.code,
        )
        
        # 构建报告结构
        report = {
            "meta": {
                "query_id": query_id,
                "trace_id": trace_id,
                "stock_code": result.code,
                "stock_name": stock_name,
                "report_type": report_type,
                "report_language": report_language,
                "current_price": result.current_price,
                "change_pct": result.change_pct,
                "model_used": getattr(result, "model_used", None),
                "market_phase_summary": market_phase_summary,
            },
            "summary": {
                "analysis_summary": result.analysis_summary,
                "operation_advice": localize_operation_advice(result.operation_advice, report_language),
                "action": action_fields["action"],
                "action_label": action_fields["action_label"],
                "trend_prediction": localize_trend_prediction(result.trend_prediction, report_language),
                "sentiment_score": result.sentiment_score,
                "sentiment_label": sentiment_label,
            },
            "strategy": {
                "ideal_buy": sniper_points.get("ideal_buy"),
                "secondary_buy": sniper_points.get("secondary_buy"),
                "stop_loss": sniper_points.get("stop_loss"),
                "take_profit": sniper_points.get("take_profit"),
            },
            "details": {
                "news_summary": result.news_summary,
                "technical_analysis": result.technical_analysis,
                "fundamental_analysis": result.fundamental_analysis,
                "risk_warning": result.risk_warning,
            }
        }
        
        return {
            "query_id": query_id,
            "trace_id": trace_id,
            "stock_code": result.code,
            "stock_name": stock_name,
            "report": report,
            "diagnostic_summary": diagnostic_summary,
        }
