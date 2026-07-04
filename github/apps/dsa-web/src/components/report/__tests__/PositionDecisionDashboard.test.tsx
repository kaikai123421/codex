import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import type { AnalysisReport, MarketRadarPayload } from '../../../types/analysis';
import { PositionDecisionDashboard } from '../PositionDecisionDashboard';

const marketRadar: MarketRadarPayload = {
  version: 1,
  date: '2026-07-02',
  traderScope: 'a_share_only',
  account: {
    totalAssets: 50585.84,
    dayPnl: -508.1,
    dayPnlPct: -0.99,
    positionPct: 78.5,
    cash: 10896.04,
    riskLight: 'defense',
    posture: '防守确认',
  },
  cnMarket: {
    riskLight: 'defense',
    summary: 'A股科技线大分歧，主线仍在但短线需要等承接。',
    indices: [
      {
        code: 'TEST_STALE_INDEX',
        name: '测试指数',
        current: 4056.78,
        changePct: 0.69,
        dataStatus: 'stale',
        source: 'tencent_quote',
        dataDate: '2026-07-03 12:05:00',
      },
      { code: '000001', name: '上证指数', current: 4028.9, changePct: -2.03 },
      { code: '399001', name: '深证成指', current: 12890.2, changePct: -3.85 },
      { code: '399006', name: '创业板指', current: 2510.8, changePct: -5.71 },
      { code: '000688', name: '科创50', current: 1188.4, changePct: -7.7 },
    ],
    breadth: {
      upCount: 790,
      downCount: 4676,
      totalAmount: 35754,
      mainNetInflow: -1986.64,
    },
    sectors: [
      {
        name: '测试板块',
        strength: 'watch',
        changePct: 1.23,
        fundFlow: 2.34,
        dataStatus: 'stale',
        source: 'tencent_quote',
        dataDate: '2026-07-03 12:05:58',
      },
      { name: '通信设备', strength: 'weak', changePct: -8.2, fundFlow: -135.98 },
      { name: '消费电子', strength: 'watch', changePct: -7.26, fundFlow: 7.62 },
    ],
  },
  externalRadar: {
    scopeNote: '外围只用于判断A股科技线风险偏好，不生成海外买卖建议。',
    groups: [
      {
        region: 'us',
        title: '美股科技',
        impact: 'negative',
        items: [
          {
            code: 'IXIC',
            name: '纳指',
            changePct: -0.55,
            impact: 'negative',
            source: 'Yahoo Finance',
            dataDate: '2026-07-02',
          },
          { code: 'SOX', name: '费半/SOX', impact: 'missing', dataStatus: 'missing' },
        ],
      },
      {
        region: 'kr',
        title: '韩国科技',
        impact: 'neutral',
        items: [{ code: 'KOSPI', name: 'KOSPI', impact: 'neutral' }],
      },
    ],
  },
  portfolioMatrix: [
    {
      code: '000725',
      name: '京东方A',
      action: 'hold',
      actionLabel: '持有观察',
      role: '强势利润仓',
      strength: 'strong',
      bbiPosition: 'above_weekly_bbi',
      bbiDetails: {
        daily: { value: 8.21, status: 'ok' },
        weekly: { value: 7.94, status: 'ok' },
        source: 'db_cache',
      },
      fundDirection: 'inflow',
      keyLevels: ['8.75', '8.18', '9.44'],
      nextTrigger: '不跌破8.75继续持有，放量跌破减仓。',
    },
    {
      code: '515880',
      name: '通信ETF',
      action: 'watch',
      actionLabel: '观察承接',
      role: '主线底仓',
      strength: 'weak',
      bbiPosition: 'below_daily_bbi',
      fundDirection: 'outflow',
      keyLevels: ['1.576', '1.557', '1.714'],
      nextTrigger: '回到周BBI上方且缩量止跌再考虑加仓。',
    },
    {
      code: '515050',
      name: '5GETF',
      action: 'watch',
      actionLabel: '试仓观察',
      role: '补涨试仓',
      strength: 'weak',
      bbiPosition: 'above_weekly_bbi',
      fundDirection: 'outflow',
      keyLevels: ['1.222', '1.178', '1.270'],
      nextTrigger: '二次下探不破周BBI才允许补第二笔。',
    },
    {
      code: '601138',
      name: '工业富联',
      action: 'hold',
      actionLabel: '不追杀',
      role: '长期趋势观察仓',
      strength: 'weak',
      bbiPosition: 'below_weekly_bbi',
      bbiMissingReason: '未取得足够K线，不能计算BBI',
      fundDirection: 'outflow',
      keyLevels: ['64.02', '68.02', '71.47'],
      nextTrigger: '未收复周BBI前不加仓，只观察止跌。',
    },
  ],
  tradeTimeline: [
    {
      time: '09:34',
      code: '515880',
      name: '通信ETF',
      side: 'buy',
      price: 1.618,
      quantity: 2700,
      ruleMatch: 'partial',
      ruleNote: '补回偏急，但属于主线试仓。',
    },
    {
      time: '09:57',
      code: '515050',
      name: '5GETF',
      side: 'buy',
      price: 1.27,
      quantity: 3400,
      ruleMatch: 'partial',
      ruleNote: '第一笔试仓可以，后续需要确认。',
    },
  ],
  nextSessionPlan: [
    {
      stage: 'open_15m',
      title: '开盘15分钟',
      trigger: '科技线继续低开且资金未回流',
      action: '不加仓，等承接',
      ratio: '0%',
      invalidation: '放量站回昨日均价线',
    },
    {
      stage: '1030',
      title: '10:30确认',
      trigger: '通信/5G缩量止跌，京东方保持强于指数',
      action: '只加强不加弱',
      ratio: '单票5%-10%',
      invalidation: '创业板继续放量破低',
    },
    {
      stage: '1430',
      title: '14:30后',
      trigger: '尾盘资金回流科技主线',
      action: '保留底仓，弱仓不恋战',
      ratio: '减弱仓10%-20%',
      invalidation: '外围期货继续走弱',
    },
  ],
};

const report: AnalysisReport = {
  meta: {
    queryId: 'position-20260702',
    stockCode: 'PORTFOLIO',
    stockName: 'A股持仓',
    reportType: 'full',
    reportLanguage: 'zh',
    createdAt: '2026-07-02T18:30:00+08:00',
  },
  summary: {
    analysisSummary: '组合复盘',
    operationAdvice: '防守确认',
    trendPrediction: '等待确认',
    sentimentScore: 45,
  },
  details: {
    contextSnapshot: {
      marketRadar,
    },
  },
};

describe('PositionDecisionDashboard', () => {
  it('renders the A-share decision dashboard without giving external trading advice', () => {
    render(<PositionDecisionDashboard report={report} />);

    expect(screen.getByText('A股持仓决策仪表盘')).toBeInTheDocument();
    expect(screen.getByText('总资产')).toBeInTheDocument();
    expect(screen.getByText('50,585.84')).toBeInTheDocument();
    expect(screen.getByText('防守确认')).toBeInTheDocument();

    expect(screen.getByText('A股市场雷达')).toBeInTheDocument();
    expect(screen.getByText('上证指数')).toBeInTheDocument();
    expect(screen.getByText('科创50')).toBeInTheDocument();
    expect(screen.getByText('主力资金')).toBeInTheDocument();
    expect(screen.getByText('报告快照')).toBeInTheDocument();
    expect(screen.getByText('报告时间 2026-07-02 18:30')).toBeInTheDocument();
    expect(screen.getByText(/当前显示的是所选报告生成时的大盘快照/)).toBeInTheDocument();

    const externalSection = screen.getByLabelText('外围影响雷达');
    expect(within(externalSection).getByText('美股科技')).toBeInTheDocument();
    expect(within(externalSection).getByText('韩国科技')).toBeInTheDocument();
    expect(within(externalSection).getByText('利空')).toBeInTheDocument();
    expect(within(externalSection).getByText('数据缺失')).toBeInTheDocument();
    expect(within(externalSection).getByText('数据时间 2026-07-02')).toBeInTheDocument();
    expect(within(externalSection).queryByText(/Yahoo Finance/)).not.toBeInTheDocument();
    expect(within(externalSection).queryByText(/proxy|cached|tencent_quote|eastmoney|yahoo/i)).not.toBeInTheDocument();
    expect(within(externalSection).queryByText(/买入|卖出|加仓|减仓/)).not.toBeInTheDocument();

    const matrixSection = screen.getByLabelText('持仓决策矩阵');
    expect(within(matrixSection).getByText('持仓决策矩阵')).toBeInTheDocument();
    expect(within(matrixSection).getByText('京东方A')).toBeInTheDocument();
    expect(within(matrixSection).getByText('通信ETF')).toBeInTheDocument();
    expect(within(matrixSection).getByText('5GETF')).toBeInTheDocument();
    expect(within(matrixSection).getByText('工业富联')).toBeInTheDocument();
    expect(within(matrixSection).getByText('日BBI 8.210 · 周BBI 7.940')).toBeInTheDocument();
    expect(within(matrixSection).getByText('未取得足够K线，不能计算BBI')).toBeInTheDocument();
    expect(within(matrixSection).getByText('未收复周BBI前不加仓，只观察止跌。')).toBeInTheDocument();

    expect(screen.getByText('今日操作时间线')).toBeInTheDocument();
    expect(screen.getByText('09:34')).toBeInTheDocument();
    expect(screen.getByText('09:57')).toBeInTheDocument();
    expect(screen.getByText('数据时间 2026-07-03 12:05:00 · 今日滞后')).toBeInTheDocument();
    expect(screen.queryByText(/tencent_quote|eastmoney|yahoo|proxy|cached/i)).not.toBeInTheDocument();

    const marketSection = screen.getByLabelText('A股市场雷达');
    const sectorChip = within(marketSection).getByTestId('market-sector-chip-测试板块');
    expect(sectorChip).toHaveTextContent('测试板块');
    expect(sectorChip).toHaveTextContent('+1.23%');
    expect(sectorChip).toHaveTextContent('+2.34亿');
    expect(sectorChip).toHaveTextContent('观察');
    expect(sectorChip).not.toHaveTextContent('tencent_quote');
    expect(sectorChip).not.toHaveTextContent('2026-07-03');
    expect(sectorChip).not.toHaveTextContent('今日滞后');

    expect(screen.getByText('明日三阶段执行')).toBeInTheDocument();
    expect(screen.getByText('开盘15分钟')).toBeInTheDocument();
    expect(screen.getByText('10:30确认')).toBeInTheDocument();
    expect(screen.getByText('14:30后')).toBeInTheDocument();
  });

  it('shows a visible fallback for legacy reports without dashboard payload', () => {
    render(
      <PositionDecisionDashboard
        report={{
          ...report,
          details: {
            contextSnapshot: {},
          },
        }}
      />,
    );

    expect(screen.getByText('结构化仪表盘未生成')).toBeInTheDocument();
    expect(screen.getByText(/重新生成 report 后会显示/)).toBeInTheDocument();
  });
});
