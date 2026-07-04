import type React from 'react';
import type { ReportLanguage, ReportStrategy as ReportStrategyType } from '../../types/analysis';
import { Card } from '../common';
import { DashboardPanelHeader } from '../dashboard';
import { getReportText, normalizeReportLanguage } from '../../utils/reportLanguage';

interface ReportStrategyProps {
  strategy?: ReportStrategyType;
  language?: ReportLanguage;
}

interface StrategyItemProps {
  label: string;
  displayLabel: string;
  value?: string;
  tone: string;
  tag: string;
}

const parseStrategyValue = (value?: string): { price: string; condition?: string } => {
  const normalized = (value || '').trim();
  if (!normalized) {
    return { price: '—' };
  }

  const match = normalized.match(/^(.+?)[（(](.+)[）)]$/);
  if (!match) {
    return { price: normalized };
  }

  return {
    price: match[1].trim(),
    condition: match[2].trim(),
  };
};

const StrategyItem: React.FC<StrategyItemProps> = ({
  label,
  displayLabel,
  value,
  tone,
  tag,
}) => {
  const parsed = parseStrategyValue(value);

  return (
    <li
      className="home-subpanel home-strategy-card relative overflow-hidden px-3.5 py-3"
      style={{ ['--home-strategy-tone' as string]: `var(${tone})` }}
      aria-label={displayLabel}
    >
      <div
        className="absolute inset-y-3 left-0 w-1 rounded-r-full"
        style={{ background: `var(${tone})` }}
        aria-hidden="true"
      />
      <div className="grid gap-3 pl-2 md:grid-cols-[0.85fr_0.9fr_1.35fr] md:items-center">
        <div className="min-w-0">
          <span
            className="inline-flex rounded-full border px-2 py-0.5 text-[11px] font-semibold"
            style={{ borderColor: `color-mix(in srgb, var(${tone}) 45%, transparent)`, color: `var(${tone})` }}
          >
            {tag}
          </span>
          <h4 className="mt-1.5 truncate text-sm font-semibold text-foreground">{displayLabel}</h4>
          <span className="home-strategy-label mt-0.5 block text-[11px]">{label}</span>
        </div>

        <div className="min-w-0">
          <p className="text-[11px] text-muted-text">价格</p>
          <div
            className="mt-1 truncate font-mono text-lg font-bold leading-tight"
            style={!value ? { color: 'var(--text-muted-text)' } : { color: `var(${tone})` }}
          >
            {parsed.price}
          </div>
        </div>

        <div className="min-w-0">
          <p className="text-[11px] text-muted-text">触发条件</p>
          {parsed.condition ? (
            <p className="mt-1 text-sm leading-6 text-secondary-text">{parsed.condition}</p>
          ) : (
            <p className="mt-1 text-sm leading-6 text-muted-text">等待数据确认</p>
          )}
        </div>
      </div>
      <div
        className="absolute bottom-0 left-0 right-0 h-0.5"
        style={{ background: `linear-gradient(90deg, transparent, var(${tone}), transparent)` }}
      />
    </li>
  );
};

/**
 * 策略点位区组件 - 终端风格
 */
export const ReportStrategy: React.FC<ReportStrategyProps> = ({ strategy, language = 'zh' }) => {
  if (!strategy) {
    return null;
  }

  const reportLanguage = normalizeReportLanguage(language);
  const text = getReportText(reportLanguage);

  const strategyItems = [
    {
      label: text.idealBuy,
      displayLabel: reportLanguage === 'en' ? 'Ideal entry point' : '理想买入点',
      value: strategy.idealBuy,
      tone: '--home-strategy-buy',
      tag: reportLanguage === 'en' ? 'Primary' : '主买点',
    },
    {
      label: text.secondaryBuy,
      displayLabel: reportLanguage === 'en' ? 'Secondary entry point' : '次优买入点',
      value: strategy.secondaryBuy,
      tone: '--home-strategy-secondary',
      tag: reportLanguage === 'en' ? 'Confirm' : '确认点',
    },
    {
      label: text.stopLoss,
      displayLabel: text.stopLoss,
      value: strategy.stopLoss,
      tone: '--home-strategy-stop',
      tag: reportLanguage === 'en' ? 'Risk line' : '风险线',
    },
    {
      label: text.takeProfit,
      displayLabel: text.takeProfit,
      value: strategy.takeProfit,
      tone: '--home-strategy-take',
      tag: reportLanguage === 'en' ? 'Target' : '目标',
    },
  ];

  return (
    <Card variant="bordered" padding="md" className="home-panel-card">
      <DashboardPanelHeader
        eyebrow={text.strategyPoints}
        title={text.sniperLevels}
        className="mb-3"
      />
      <ul className="grid grid-cols-1 gap-2" aria-label={text.sniperLevels}>
        {strategyItems.map((item) => (
          <StrategyItem key={item.label} {...item} />
        ))}
      </ul>
    </Card>
  );
};
