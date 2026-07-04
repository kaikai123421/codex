import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { historyApi } from '../../../api/history';
import type { AnalysisContextPackOverview, AnalysisReport, AnalysisResult } from '../../../types/analysis';
import { AnalysisContextSummary } from '../AnalysisContextSummary';
import { ReportSummary } from '../ReportSummary';

vi.mock('../../../api/history', () => ({
  historyApi: {
    getDiagnostics: vi.fn(),
    getNews: vi.fn(),
  },
}));

const overview: AnalysisContextPackOverview = {
  packVersion: '1.0',
  createdAt: '2026-04-10T08:30:00+00:00',
  subject: {
    code: '600519',
    stockName: '贵州茅台',
    market: 'cn',
  },
  blocks: [
    {
      key: 'quote',
      label: '行情',
      status: 'available',
      source: 'mock_quote',
      warnings: [],
      missingReasons: [],
    },
    {
      key: 'news',
      label: '新闻',
      status: 'missing',
      source: null,
      warnings: ['news_provider_timeout'],
      missingReasons: ['news_context_missing'],
    },
    {
      key: 'fundamentals',
      label: '基本面',
      status: 'fetch_failed',
      source: 'fundamental_pipeline',
      warnings: [],
      missingReasons: ['fundamental_pipeline_failed'],
    },
  ],
  counts: {
    available: 1,
    missing: 1,
    notSupported: 0,
    fallback: 0,
    stale: 0,
    estimated: 0,
    partial: 0,
    fetchFailed: 1,
  },
  dataQuality: {
    overallScore: 82,
    level: 'usable',
    blockScores: {
      quote: 100,
      daily_bars: 100,
      technical: 100,
      news: 35,
      fundamentals: 25,
      chip: 100,
    },
    limitations: ['fundamentals: fetch_failed'],
  },
  warnings: ['intraday_realtime_overlay'],
  metadata: {
    triggerSource: 'api',
    newsResultCount: 3,
  },
};

describe('AnalysisContextSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a collapsed summary and expands overview details on demand', () => {
    render(<AnalysisContextSummary overview={overview} />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(panel).not.toHaveAttribute('open');
    expect(within(panel).getAllByText('输入数据块')[0]).toBeVisible();
    expect(screen.getAllByText('可用 1')[0]).toBeVisible();
    expect(screen.getAllByText('缺失 1')[0]).toBeVisible();
    expect(screen.getAllByText('抓取失败 1')[0]).toBeVisible();
    expect(screen.getAllByText('质量分 82/100 可用')[0]).toBeVisible();
    expect(screen.getByText('触发来源: api')).toBeVisible();
    expect(screen.getByText('来源: mock_quote')).not.toBeVisible();

    fireEvent.click(within(panel).getAllByText('输入数据块')[0]);

    expect(panel).toHaveAttribute('open');
    expect(screen.getByText('行情')).toBeInTheDocument();
    expect(screen.getByText('来源: mock_quote')).toBeVisible();
    expect(screen.getByText('告警:')).toBeInTheDocument();
    expect(screen.getByText(/intraday_realtime_overlay/)).toBeInTheDocument();
    expect(screen.getByText('数据限制:')).toBeInTheDocument();
    expect(screen.getByText(/基本面：抓取失败/)).toBeInTheDocument();
    expect(screen.getByText(/news_provider_timeout/)).toBeInTheDocument();
    expect(screen.getByText(/未进入分析输入 \(news_context_missing\)/)).toBeInTheDocument();
    expect(screen.getByText(/fundamental_pipeline_failed/)).toBeInTheDocument();
    expect(screen.getAllByText('新闻结果数: 3').some((item) => item.textContent === '新闻结果数: 3')).toBe(true);
    expect(screen.getAllByText('本次分析输入')[0]).toBeVisible();
  });

  it('localizes the collapsed summary for english reports', () => {
    render(<AnalysisContextSummary overview={overview} language="en" />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(panel).not.toHaveAttribute('open');
    expect(screen.getAllByText('Input Blocks')[0]).toBeVisible();
    expect(screen.getByText('Shows inputs included in this LLM run, not provider run success')).toBeVisible();
    expect(screen.getAllByText('Available 1')[0]).toBeVisible();
    expect(screen.getAllByText('Missing 1')[0]).toBeVisible();
    expect(screen.getAllByText('Fetch failed 1')[0]).toBeVisible();
    expect(screen.getAllByText('Quality 82/100 Usable')[0]).toBeVisible();
    expect(screen.getByText('Trigger: api')).toBeVisible();

    fireEvent.click(within(panel).getAllByText('Input Blocks')[0]);

    expect(screen.getByText('Data Limitations:')).toBeInTheDocument();
    expect(screen.getByText(/fundamentals: Fetch failed/)).toBeInTheDocument();
  });

  it('labels unsupported ETF chip data as not applicable instead of missing', () => {
    const etfOverview: AnalysisContextPackOverview = {
      ...overview,
      subject: {
        code: '515880',
        stockName: '通信ETF国泰',
        market: 'cn',
      },
      blocks: [
        {
          key: 'chip',
          label: '筹码',
          status: 'not_supported',
          source: null,
          warnings: [],
          missingReasons: ['chip_not_supported'],
        },
      ],
      counts: {
        available: 0,
        missing: 0,
        notSupported: 1,
        fallback: 0,
        stale: 0,
        estimated: 0,
        partial: 0,
        fetchFailed: 0,
      },
    };

    render(<AnalysisContextSummary overview={etfOverview} language="en" />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(within(panel).queryByText('Missing 1')).not.toBeInTheDocument();
    expect(within(panel).getAllByText('Not supported 1')[0]).toBeVisible();

    fireEvent.click(within(panel).getAllByText('Input Blocks')[0]);

    expect(screen.getByText(/ETF\/index chip distribution is not applicable/)).toBeInTheDocument();
  });

  it('surfaces degraded non-zero states in the collapsed summary', () => {
    const degradedOverview: AnalysisContextPackOverview = {
      ...overview,
      blocks: [
        {
          key: 'quote',
          label: '行情',
          status: 'fallback',
          source: 'cached_quote',
          warnings: ['quote_fallback'],
          missingReasons: [],
        },
        {
          key: 'fundamental',
          label: '基本面',
          status: 'stale',
          source: 'fundamental_cache',
          warnings: ['stale_fundamental'],
          missingReasons: [],
        },
      ],
      counts: {
        available: 0,
        missing: 0,
        notSupported: 0,
        fallback: 1,
        stale: 1,
        estimated: 0,
        partial: 0,
        fetchFailed: 0,
      },
    };

    render(<AnalysisContextSummary overview={degradedOverview} />);

    const panel = screen.getByTestId('analysis-context-summary');
    expect(panel).not.toHaveAttribute('open');
    expect(within(panel).getByText('可用 0')).toBeVisible();
    expect(within(panel).getByText('缺失 0')).toBeVisible();
    expect(within(panel).getAllByText('降级 1')[0]).toBeVisible();
    expect(within(panel).getAllByText('过期 1')[0]).toBeVisible();
  });

  it('does not render without an overview', () => {
    const { container } = render(<AnalysisContextSummary overview={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('does not render raw values or unexpected sensitive fields', () => {
    const unsafeOverview = {
      ...overview,
      value: 'raw trend payload',
      content: '完整新闻正文不应出现',
      apiKey: 'secret-key',
      blocks: [
        {
          ...overview.blocks[0],
          items: {
            price: {
              value: 1880,
              apiKey: 'secret-key',
            },
          },
        },
      ],
    } as unknown as AnalysisContextPackOverview;

    render(<AnalysisContextSummary overview={unsafeOverview} />);

    fireEvent.click(screen.getAllByText('输入数据块')[0]);

    expect(screen.queryByText('raw trend payload')).not.toBeInTheDocument();
    expect(screen.queryByText('完整新闻正文不应出现')).not.toBeInTheDocument();
    expect(screen.queryByText('secret-key')).not.toBeInTheDocument();
  });
});

describe('ReportSummary analysis context placement', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(historyApi.getDiagnostics).mockResolvedValue({
      status: 'normal',
      statusLabel: '正常',
      reason: '运行正常',
      components: {},
      copyText: '',
    });
  });

  it('renders strategy and news before context, diagnostics and traceability', async () => {
    vi.mocked(historyApi.getNews).mockResolvedValue({
      total: 0,
      items: [],
    });

    const report: AnalysisReport = {
      meta: {
        id: 1,
        queryId: 'q1',
        stockCode: '600519',
        stockName: '贵州茅台',
        reportType: 'detailed',
        reportLanguage: 'zh',
        createdAt: '2026-04-10T12:00:00',
        marketPhaseSummary: {
          market: 'cn',
          phase: 'intraday',
          marketLocalTime: '2026-04-10T10:30:00+08:00',
          sessionDate: '2026-04-10',
          effectiveDailyBarDate: '2026-04-09',
          isTradingDay: true,
          isMarketOpenNow: true,
          isPartialBar: true,
          minutesToOpen: null,
          minutesToClose: 150,
          triggerSource: 'api',
          analysisIntent: 'auto',
          warnings: [],
        },
      },
      summary: {
        analysisSummary: 'summary',
        operationAdvice: '持有',
        trendPrediction: '震荡',
        sentimentScore: 70,
      },
      strategy: {
        idealBuy: '120',
      },
      details: {
        analysisContextPackOverview: overview,
      },
    };
    const result: AnalysisResult = {
      queryId: 'q1',
      stockCode: '600519',
      stockName: '贵州茅台',
      report,
      diagnosticSummary: {
        status: 'normal',
        statusLabel: '正常',
        reason: '运行正常',
        components: {},
        copyText: '',
      },
      createdAt: '2026-04-10T12:00:00',
    };

    render(<ReportSummary data={result} />);

    await waitFor(() => {
      expect(screen.getByTestId('run-diagnostics')).toBeInTheDocument();
    });

    expect(screen.getByText('市场阶段: CN · 盘中')).toBeInTheDocument();
    expect(screen.getByText('日线未完成')).toBeInTheDocument();
    expect(screen.getAllByText('质量分 82/100 可用')[0]).toBeInTheDocument();

    const strategy = screen.getByText('狙击点位');
    const diagnostics = screen.getByTestId('run-diagnostics');
    const contextSummary = screen.getByTestId('analysis-context-summary');
    expect(contextSummary).not.toHaveAttribute('open');
    expect(diagnostics).not.toHaveAttribute('open');
    const traceability = screen.getByText('数据追溯');

    expect(strategy.compareDocumentPosition(contextSummary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(contextSummary.compareDocumentPosition(diagnostics) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(diagnostics.compareDocumentPosition(traceability) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText('AI 建议 / 决策信号')).not.toBeInTheDocument();
  });

  it('does not mount stock-only sections for portfolio dashboard reports', async () => {
    const report: AnalysisReport = {
      meta: {
        id: 88,
        queryId: 'today_market_dashboard_20260703',
        stockCode: 'PORTFOLIO',
        stockName: 'Portfolio Dashboard',
        reportType: 'full',
        reportLanguage: 'zh',
        createdAt: '2026-07-03T17:08:00',
      },
      summary: {
        analysisSummary: 'portfolio decision dashboard',
        operationAdvice: 'defense',
        trendPrediction: 'wait for confirmation',
        sentimentScore: 50,
      },
      strategy: {
        idealBuy: 'should not render',
      },
      details: {
        klineChart: {
          source: 'unit_test_daily_bars',
          dataDate: '2026-07-03',
          bars: [
            { date: '2026-07-02', open: 1, high: 2, low: 1, close: 2 },
            { date: '2026-07-03', open: 2, high: 3, low: 2, close: 3 },
          ],
        },
        contextSnapshot: {
          marketRadar: {
            version: 1,
            date: '2026-07-03',
            traderScope: 'a_share_only',
            account: {
              totalAssets: 50585.84,
              dayPnl: -508.1,
              dayPnlPct: -0.99,
              positionPct: 78.5,
              cash: 10896.04,
              riskLight: 'defense',
            },
          },
        },
      },
    };

    render(<ReportSummary data={report} />);

    await waitFor(() => {
      expect(historyApi.getDiagnostics).toHaveBeenCalledTimes(1);
    });

    expect(historyApi.getNews).not.toHaveBeenCalled();
    expect(screen.queryByTestId('report-kline-chart')).not.toBeInTheDocument();
    expect(screen.queryByText('should not render')).not.toBeInTheDocument();
  });

  it('keeps the stock overview first and renders the K-line decision chart before strategy points', async () => {
    vi.mocked(historyApi.getNews).mockResolvedValue({
      total: 0,
      items: [],
    });

    const report: AnalysisReport = {
      meta: {
        id: 2,
        queryId: 'q2',
        stockCode: '300502',
        stockName: '新易盛',
        reportType: 'detailed',
        reportLanguage: 'zh',
        createdAt: '2026-07-03T16:23:00',
        currentPrice: 526,
        changePct: 3.34,
      },
      summary: {
        analysisSummary: '新易盛今日收涨，但仍需要先看概览结论。',
        operationAdvice: '观望',
        trendPrediction: '看空',
        sentimentScore: 30,
      },
      strategy: {
        idealBuy: '554.9元（MA5上方站稳且放量）',
        secondaryBuy: '553.1元（MA20附近支撑确认）',
        stopLoss: '505.8元（今日最低点，跌破则离场）',
        takeProfit: '580元（前期高点区间）',
      },
      details: {
        klineChart: {
          source: 'unit_test_daily_bars',
          dataDate: '2026-07-03',
          bars: [
            { date: '2026-06-29', open: 510, high: 526, low: 505, close: 520, volume: 1200, ma5: 518, ma20: 512, bbi: 515 },
            { date: '2026-06-30', open: 520, high: 535, low: 516, close: 531, volume: 1500, ma5: 522, ma20: 515, bbi: 520 },
            { date: '2026-07-01', open: 531, high: 540, low: 520, close: 524, volume: 1800, ma5: 526, ma20: 518, bbi: 522 },
            { date: '2026-07-02', open: 524, high: 532, low: 510, close: 518, volume: 1600, ma5: 524, ma20: 520, bbi: 521 },
            { date: '2026-07-03', open: 518, high: 529, low: 506, close: 526, volume: 1900, ma5: 523, ma20: 522, bbi: 524 },
          ],
        },
        analysisContextPackOverview: overview,
      },
    };

    const result: AnalysisResult = {
      queryId: 'q2',
      stockCode: '300502',
      stockName: '新易盛',
      report,
      createdAt: '2026-07-03T16:23:00',
    };

    render(<ReportSummary data={result} />);

    await waitFor(() => {
      expect(screen.getByTestId('run-diagnostics')).toBeInTheDocument();
    });

    const overviewText = screen.getByText('新易盛今日收涨，但仍需要先看概览结论。');
    const klineChart = screen.getByTestId('report-kline-chart');
    const strategy = screen.getByText('狙击点位');

    expect(overviewText.compareDocumentPosition(klineChart) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(klineChart.compareDocumentPosition(strategy) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(klineChart).getByText('K线决策图')).toBeInTheDocument();
    expect(within(klineChart).getAllByText('BBI').length).toBeGreaterThan(0);
    expect(within(klineChart).getAllByText('止损 505.80').length).toBeGreaterThan(0);
    expect(within(klineChart).getAllByText('目标 580.00').length).toBeGreaterThan(0);
    expect(within(klineChart).queryByText(/unit_test_daily_bars/)).not.toBeInTheDocument();
  });
});
