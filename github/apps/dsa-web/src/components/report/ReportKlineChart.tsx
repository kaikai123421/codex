import React, { useMemo } from 'react';
import type {
  ReportDetails as ReportDetailsType,
  ReportKlineBar,
  ReportLanguage,
  ReportStrategy,
} from '../../types/analysis';
import { normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportKlineChartProps {
  details?: ReportDetailsType;
  strategy?: ReportStrategy;
  language?: ReportLanguage;
}

type LevelTone = 'buy' | 'secondary' | 'stop' | 'target';

interface StrategyLevel {
  key: keyof ReportStrategy;
  label: string;
  value: number;
  tone: LevelTone;
}

const TEXT = {
  zh: {
    eyebrow: '看图确认',
    title: 'K线决策图',
    subtitle: '先看首屏结论，再用K线、BBI和关键价位确认，不用图表替代纪律。',
    latest: '最新',
    source: '行情快照',
    dataDate: '数据日',
    focus: '注意重点',
    bbi: 'BBI',
    ma5: 'MA5',
    ma20: 'MA20',
    price: '价格',
    missing: 'K线数据未取得',
    missingHint: '重新分析并取得日K后，这里会显示K线、BBI和策略价位。',
    idealBuy: '理想买入',
    secondaryBuy: '二买',
    stopLoss: '止损',
    takeProfit: '目标',
    closeAboveBbi: '收盘在BBI上方，趋势线仍有支撑。',
    closeBelowBbi: '收盘在BBI下方，先看修复再谈加仓。',
    bbiMissing: 'BBI未取得，不能用趋势支撑做结论。',
  },
  en: {
    eyebrow: 'CHART CHECK',
    title: 'K-line Decision Chart',
    subtitle: 'Read the overview first, then verify with K-line, BBI, and key levels.',
    latest: 'Latest',
    source: 'Source',
    dataDate: 'Data date',
    focus: 'Focus',
    bbi: 'BBI',
    ma5: 'MA5',
    ma20: 'MA20',
    price: 'Price',
    missing: 'K-line data unavailable',
    missingHint: 'Regenerate with daily bars to show K-line, BBI, and strategy levels.',
    idealBuy: 'Ideal buy',
    secondaryBuy: 'Secondary',
    stopLoss: 'Stop',
    takeProfit: 'Target',
    closeAboveBbi: 'Close is above BBI; trend support is still present.',
    closeBelowBbi: 'Close is below BBI; wait for repair before adding.',
    bbiMissing: 'BBI unavailable; do not infer trend support.',
  },
} as const;

const STRATEGY_META: Record<keyof ReportStrategy, { tone: LevelTone; textKey: keyof typeof TEXT.zh }> = {
  idealBuy: { tone: 'buy', textKey: 'idealBuy' },
  secondaryBuy: { tone: 'secondary', textKey: 'secondaryBuy' },
  stopLoss: { tone: 'stop', textKey: 'stopLoss' },
  takeProfit: { tone: 'target', textKey: 'takeProfit' },
};

const TONE_STYLE: Record<LevelTone, { stroke: string; bg: string; text: string }> = {
  buy: { stroke: '#22c55e', bg: 'bg-emerald-500/10', text: 'text-emerald-300' },
  secondary: { stroke: '#06b6d4', bg: 'bg-cyan/10', text: 'text-cyan' },
  stop: { stroke: '#f43f5e', bg: 'bg-rose-500/10', text: 'text-rose-300' },
  target: { stroke: '#f59e0b', bg: 'bg-amber-500/10', text: 'text-amber-300' },
};

const isFiniteNumber = (value: unknown): value is number => (
  typeof value === 'number' && Number.isFinite(value)
);

const formatPrice = (value?: number | null, digits = 2): string => (
  isFiniteNumber(value) ? value.toFixed(digits) : '--'
);

const parseFirstPrice = (value?: string): number | null => {
  if (!value) return null;
  const match = value.match(/-?\d+(?:\.\d+)?/);
  if (!match) return null;
  const parsed = Number(match[0]);
  return Number.isFinite(parsed) ? parsed : null;
};

const normalizeBars = (bars?: ReportKlineBar[]): ReportKlineBar[] => (
  (bars || [])
    .filter((bar) => (
      bar.date
      && isFiniteNumber(bar.open)
      && isFiniteNumber(bar.high)
      && isFiniteNumber(bar.low)
      && isFiniteNumber(bar.close)
      && bar.high >= bar.low
    ))
    .slice(-48)
);

const buildPath = (
  bars: ReportKlineBar[],
  valueKey: keyof Pick<ReportKlineBar, 'ma5' | 'ma20' | 'bbi'>,
  xForIndex: (index: number) => number,
  yForValue: (value: number) => number,
): string => {
  const points = bars
    .map((bar, index) => {
      const value = bar[valueKey];
      return isFiniteNumber(value) ? `${xForIndex(index).toFixed(2)},${yForValue(value).toFixed(2)}` : null;
    })
    .filter((point): point is string => Boolean(point));
  return points.length >= 2 ? `M ${points.join(' L ')}` : '';
};

export const ReportKlineChart: React.FC<ReportKlineChartProps> = ({
  details,
  strategy,
  language = 'zh',
}) => {
  const reportLanguage = normalizeReportLanguage(language);
  const text = TEXT[reportLanguage];
  const payload = details?.klineChart ?? details?.kline_chart ?? null;
  const bars = useMemo(() => normalizeBars(payload?.bars), [payload?.bars]);

  if (!payload && bars.length === 0) {
    return null;
  }

  const levels = (Object.keys(STRATEGY_META) as Array<keyof ReportStrategy>)
    .map((key): StrategyLevel | null => {
      const value = parseFirstPrice(strategy?.[key]);
      if (!isFiniteNumber(value)) return null;
      const meta = STRATEGY_META[key];
      return {
        key,
        label: text[meta.textKey],
        value,
        tone: meta.tone,
      };
    })
    .filter((level): level is StrategyLevel => Boolean(level));

  const latest = bars[bars.length - 1];
  const dataDate = payload?.dataDate ?? payload?.data_date ?? latest?.date;

  const priceValues = bars.flatMap((bar) => [
    bar.high,
    bar.low,
    isFiniteNumber(bar.ma5) ? bar.ma5 : null,
    isFiniteNumber(bar.ma20) ? bar.ma20 : null,
    isFiniteNumber(bar.bbi) ? bar.bbi : null,
  ]).filter(isFiniteNumber);
  const levelValues = levels.map((level) => level.value);
  const allValues = [...priceValues, ...levelValues];
  const minValue = Math.min(...allValues);
  const maxValue = Math.max(...allValues);
  const range = Math.max(maxValue - minValue, 1);
  const padding = range * 0.12;
  const chartMin = minValue - padding;
  const chartMax = maxValue + padding;
  const chartRange = Math.max(chartMax - chartMin, 1);

  const width = 720;
  const height = 300;
  const plot = { left: 52, top: 22, right: 86, bottom: 46 };
  const plotWidth = width - plot.left - plot.right;
  const plotHeight = height - plot.top - plot.bottom;
  const step = bars.length > 1 ? plotWidth / (bars.length - 1) : plotWidth;
  const candleWidth = Math.max(5, Math.min(14, step * 0.48));
  const maxVolume = Math.max(...bars.map((bar) => bar.volume || 0), 1);

  const xForIndex = (index: number) => plot.left + index * step;
  const yForValue = (value: number) => plot.top + ((chartMax - value) / chartRange) * plotHeight;
  const ma5Path = buildPath(bars, 'ma5', xForIndex, yForValue);
  const ma20Path = buildPath(bars, 'ma20', xForIndex, yForValue);
  const bbiPath = buildPath(bars, 'bbi', xForIndex, yForValue);
  const latestBbi = latest && isFiniteNumber(latest.bbi) ? latest.bbi : null;
  const bbiStatus = latestBbi === null
    ? text.bbiMissing
    : latest.close >= latestBbi
      ? text.closeAboveBbi
      : text.closeBelowBbi;

  return (
    <section
      data-testid="report-kline-chart"
      className="home-panel-card rounded-2xl border border-cyan/20 bg-panel/80 p-5 text-left shadow-[0_18px_48px_rgba(0,0,0,0.22)]"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <span className="label-uppercase">{text.eyebrow}</span>
          <div className="mt-1 flex flex-wrap items-baseline gap-3">
            <h3 className="text-2xl font-bold text-foreground">{text.title}</h3>
            {latest ? (
              <span className="font-mono text-sm text-secondary-text">
                {text.latest} {formatPrice(latest.close)}
              </span>
            ) : null}
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-secondary-text">
            {text.subtitle}
          </p>
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-muted-text">
          {dataDate ? <span className="home-accent-chip px-2 py-0.5">{text.dataDate}: {dataDate}</span> : null}
        </div>
      </div>

      {bars.length >= 2 ? (
        <div className="mt-5 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1fr)_260px]">
          <div className="overflow-hidden rounded-2xl border border-white/10 bg-base/50 p-3">
            <svg role="img" aria-label={text.title} viewBox={`0 0 ${width} ${height}`} className="h-[320px] w-full">
              <rect x={plot.left} y={plot.top} width={plotWidth} height={plotHeight} rx="14" fill="rgba(15,23,42,0.42)" />
              {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
                const y = plot.top + ratio * plotHeight;
                const value = chartMax - ratio * chartRange;
                return (
                  <g key={ratio}>
                    <line x1={plot.left} x2={plot.left + plotWidth} y1={y} y2={y} stroke="rgba(148,163,184,0.14)" />
                    <text x={plot.left - 10} y={y + 4} textAnchor="end" className="fill-slate-400 text-[11px]">
                      {formatPrice(value)}
                    </text>
                  </g>
                );
              })}
              {levels.map((level) => {
                const y = yForValue(level.value);
                const tone = TONE_STYLE[level.tone];
                return (
                  <g key={level.key}>
                    <line
                      x1={plot.left}
                      x2={plot.left + plotWidth}
                      y1={y}
                      y2={y}
                      stroke={tone.stroke}
                      strokeDasharray="6 6"
                      strokeOpacity="0.72"
                    />
                    <text x={plot.left + plotWidth + 10} y={y + 4} className="fill-slate-200 text-[12px]">
                      {level.label} {formatPrice(level.value)}
                    </text>
                  </g>
                );
              })}
              {bars.map((bar, index) => {
                const x = xForIndex(index);
                const isUp = bar.close >= bar.open;
                const color = isUp ? '#ef4444' : '#22c55e';
                const yHigh = yForValue(bar.high);
                const yLow = yForValue(bar.low);
                const yOpen = yForValue(bar.open);
                const yClose = yForValue(bar.close);
                const bodyY = Math.min(yOpen, yClose);
                const bodyHeight = Math.max(Math.abs(yOpen - yClose), 2);
                const volumeHeight = ((bar.volume || 0) / maxVolume) * 28;

                return (
                  <g key={`${bar.date}-${index}`}>
                    <line x1={x} x2={x} y1={yHigh} y2={yLow} stroke={color} strokeWidth="1.5" />
                    <rect
                      x={x - candleWidth / 2}
                      y={bodyY}
                      width={candleWidth}
                      height={bodyHeight}
                      rx="2"
                      fill={isUp ? 'rgba(239,68,68,0.9)' : 'rgba(34,197,94,0.9)'}
                    />
                    <rect
                      x={x - candleWidth / 2}
                      y={height - plot.bottom + 18 - volumeHeight}
                      width={candleWidth}
                      height={volumeHeight}
                      rx="1.5"
                      fill={isUp ? 'rgba(239,68,68,0.32)' : 'rgba(34,197,94,0.32)'}
                    />
                  </g>
                );
              })}
              {ma20Path ? <path d={ma20Path} fill="none" stroke="#38bdf8" strokeWidth="2" strokeOpacity="0.8" /> : null}
              {ma5Path ? <path d={ma5Path} fill="none" stroke="#f59e0b" strokeWidth="2" strokeOpacity="0.86" /> : null}
              {bbiPath ? <path d={bbiPath} fill="none" stroke="#a78bfa" strokeWidth="2.6" strokeOpacity="0.95" /> : null}
              <line x1={plot.left} x2={plot.left + plotWidth} y1={height - plot.bottom + 18} y2={height - plot.bottom + 18} stroke="rgba(148,163,184,0.2)" />
            </svg>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-secondary-text">
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-amber-500" />{text.ma5}</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-sky-400" />{text.ma20}</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-violet-400" />{text.bbi}</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-rose-500" />A股红涨</span>
              <span className="inline-flex items-center gap-1.5"><span className="h-2 w-4 rounded-full bg-emerald-500" />绿跌</span>
            </div>
          </div>

          <aside className="rounded-2xl border border-white/10 bg-base/45 p-4">
            <span className="label-uppercase">{text.focus}</span>
            <div className="mt-3 space-y-3">
              <div className="rounded-xl border border-violet-400/20 bg-violet-500/10 p-3">
                <p className="text-sm font-semibold text-violet-200">{text.bbi}</p>
                <p className="mt-1 text-sm leading-6 text-secondary-text">{bbiStatus}</p>
              </div>
              {levels.map((level) => {
                const tone = TONE_STYLE[level.tone];
                return (
                  <div key={level.key} className={`rounded-xl border border-white/10 p-3 ${tone.bg}`}>
                    <p className={`text-sm font-semibold ${tone.text}`}>
                      {level.label} {formatPrice(level.value)}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-secondary-text">
                      {strategy?.[level.key]}
                    </p>
                  </div>
                );
              })}
            </div>
          </aside>
        </div>
      ) : (
        <div className="mt-5 rounded-2xl border border-dashed border-white/15 bg-base/40 p-6 text-center">
          <p className="text-base font-semibold text-foreground">{text.missing}</p>
          <p className="mt-2 text-sm text-secondary-text">{text.missingHint}</p>
        </div>
      )}
    </section>
  );
};
