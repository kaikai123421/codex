import type React from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  Globe2,
  ListChecks,
  ShieldAlert,
  WalletCards,
} from 'lucide-react';
import type {
  AnalysisReport,
  MarketRadarExternalGroup,
  MarketRadarImpact,
  MarketRadarPayload,
  NextSessionPlanItem,
  PortfolioMatrixItem,
  TradeTimelineItem,
} from '../../types/analysis';

interface PositionDecisionDashboardProps {
  report: AnalysisReport;
}

const cn = (...classes: Array<string | false | null | undefined>): string =>
  classes.filter(Boolean).join(' ');

const subtlePillTone = 'border-border/70 bg-muted/70 text-secondary-text';
const subtleCardClass = 'border-border/70 bg-elevated/80';
const subtleChipClass = 'border-border/70 bg-muted/70';

const getMarketRadar = (report: AnalysisReport): MarketRadarPayload | null => {
  const snapshot = report.details?.contextSnapshot;
  const candidate = snapshot?.marketRadar ?? snapshot?.market_radar;
  if (!candidate || typeof candidate !== 'object') {
    return null;
  }
  return candidate as MarketRadarPayload;
};

const formatNumber = (value?: number | null, digits = 2): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '未取得';
  }
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits,
  }).format(value);
};

const formatSignedPct = (value?: number | null): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '未取得';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
};

const formatSignedAmount = (value?: number | null, suffix = ''): string => {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '未取得';
  }
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatNumber(value)}${suffix}`;
};

const toneByValue = (value?: number | null): string => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value === 0) {
    return 'text-secondary-text';
  }
  return value > 0 ? 'text-[var(--home-price-up)]' : 'text-[var(--home-price-down)]';
};

const riskLabelMap: Record<string, string> = {
  attack: '进攻',
  balanced: '均衡',
  defense: '防守',
  danger: '强防守',
  unknown: '未取得',
};

const riskToneMap: Record<string, string> = {
  attack: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200',
  balanced: 'border-sky-400/40 bg-sky-400/10 text-sky-200',
  defense: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
  danger: 'border-rose-400/40 bg-rose-400/10 text-rose-200',
  unknown: subtlePillTone,
};

const impactLabelMap: Record<MarketRadarImpact | string, string> = {
  positive: '利多',
  neutral: '中性',
  negative: '利空',
  missing: '数据缺失',
};

const impactToneMap: Record<string, string> = {
  positive: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200',
  neutral: subtlePillTone,
  negative: 'border-rose-400/40 bg-rose-400/10 text-rose-200',
  missing: subtlePillTone,
};

const strengthLabelMap: Record<string, string> = {
  strong: '强',
  watch: '观察',
  weak: '弱',
  unknown: '未取得',
};

const fundDirectionLabelMap: Record<string, string> = {
  inflow: '流入',
  flat: '持平',
  outflow: '流出',
  missing: '未取得',
};

const ruleMatchLabelMap: Record<string, string> = {
  yes: '符合',
  partial: '部分符合',
  no: '不符合',
  unknown: '待确认',
};

const getRiskLabel = (risk?: string | null): string => riskLabelMap[risk || 'unknown'] ?? risk ?? '未取得';
const getImpactLabel = (impact?: string | null): string => impactLabelMap[impact || 'missing'] ?? '数据缺失';
const getStrengthLabel = (strength?: string | null): string => strengthLabelMap[strength || 'unknown'] ?? strength ?? '未取得';
const getFundDirectionLabel = (direction?: string | null): string =>
  fundDirectionLabelMap[direction || 'missing'] ?? direction ?? '未取得';
const getRuleMatchLabel = (rule?: string | null): string => ruleMatchLabelMap[rule || 'unknown'] ?? rule ?? '待确认';

const firstText = (...values: Array<string | null | undefined>): string | null => {
  const found = values.find((value) => typeof value === 'string' && value.trim().length > 0);
  return found ? found.trim() : null;
};

const dataStatusLabelMap: Record<string, string> = {
  ok: '今日在线',
  partial: '部分取得',
  stale: '今日滞后',
  cached: '缓存',
  missing: '未取得',
};

const marketFreshnessToneMap: Record<string, string> = {
  same_day_current: 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200',
  same_day_stale: 'border-amber-400/40 bg-amber-400/10 text-amber-200',
  stale_other_day: 'border-rose-400/40 bg-rose-400/10 text-rose-200',
  missing: subtlePillTone,
};

const getDataStatusLabel = (status?: string | null): string | null => {
  if (!status) {
    return null;
  }
  return dataStatusLabelMap[status] ?? status;
};

const getSourceTimeStatus = (
  _source?: string | null,
  dataDate?: string | null,
  dataStatus?: string | null,
): string | null => {
  const statusLabel = getDataStatusLabel(dataStatus);
  const dataTime = firstText(dataDate);
  const parts = [dataTime ? `数据时间 ${dataTime}` : null, dataStatus === 'missing' ? null : statusLabel].filter(Boolean);
  return parts.length ? parts.join(' · ') : null;
};

const formatSnapshotTime = (value?: string | null): string | null => {
  const raw = firstText(value);
  if (!raw) {
    return null;
  }
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/);
  if (!match) {
    return raw;
  }
  return `${match[1]}-${match[2]}-${match[3]} ${match[4]}:${match[5]}`;
};

const LegacyDashboardFallback: React.FC = () => (
  <section
    className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-4"
    aria-label="结构化仪表盘未生成"
  >
    <div className="flex items-start gap-3">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
      <div>
        <h2 className="text-base font-semibold text-amber-100">结构化仪表盘未生成</h2>
        <p className="mt-1 text-sm leading-6 text-amber-100/85">
          这份旧报告没有 market_radar 数据。重新生成 report 后会显示 A股雷达、外围雷达、持仓矩阵和操作时间线。
        </p>
      </div>
    </div>
  </section>
);

const StatusPill: React.FC<{ label: string; tone?: string; className?: string }> = ({
  label,
  tone = subtlePillTone,
  className,
}) => (
  <span className={cn('inline-flex shrink-0 items-center rounded-full border px-2.5 py-1 text-xs font-semibold', tone, className)}>
    {label}
  </span>
);

const SectionHeader: React.FC<{
  icon: React.ReactNode;
  title: string;
  caption?: string;
  meta?: React.ReactNode;
}> = ({ icon, title, caption, meta }) => (
  <div className="mb-3 flex items-center justify-between gap-3">
    <div className="flex items-center gap-2">
      <span className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border text-secondary-text', subtleChipClass)}>
        {icon}
      </span>
      <div>
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        {caption ? <p className="mt-0.5 text-xs text-muted-text">{caption}</p> : null}
      </div>
    </div>
    {meta ? <div className="flex shrink-0 flex-wrap justify-end gap-2">{meta}</div> : null}
  </div>
);

const Metric: React.FC<{ label: string; value: string; valueClassName?: string }> = ({
  label,
  value,
  valueClassName,
}) => (
  <div className="min-w-0 border-l border-border/70 pl-3">
    <p className="text-xs text-muted-text">{label}</p>
    <p className={cn('mt-1 truncate font-mono text-lg font-semibold text-foreground', valueClassName)}>
      {value}
    </p>
  </div>
);

const renderBbiLabel = (value?: string | null): string => {
  const map: Record<string, string> = {
    above_daily_bbi: '日BBI上方',
    below_daily_bbi: '日BBI下方',
    above_weekly_bbi: '周BBI上方',
    below_weekly_bbi: '周BBI下方',
    near_bbi: '贴近BBI',
    missing: '未取得',
  };
  return map[value || ''] ?? value ?? '未取得';
};

const finiteNumber = (value: unknown): number | null =>
  typeof value === 'number' && Number.isFinite(value) ? value : null;

const renderBbiDetailLine = (item: PortfolioMatrixItem): string | null => {
  const details = item.bbiDetails ?? item.bbi_details;
  const dailyValue = finiteNumber(details?.daily?.value);
  const weeklyValue = finiteNumber(details?.weekly?.value);
  const parts: string[] = [];
  if (dailyValue !== null) {
    parts.push(`日BBI ${dailyValue.toFixed(3)}`);
  }
  if (weeklyValue !== null) {
    parts.push(`周BBI ${weeklyValue.toFixed(3)}`);
  }
  if (parts.length) {
    return parts.join(' · ');
  }
  return firstText(
    item.bbiMissingReason,
    item.bbi_missing_reason,
    details?.missingReason,
    details?.missing_reason,
    details?.daily?.missingReason,
    details?.daily?.missing_reason,
    details?.weekly?.missingReason,
    details?.weekly?.missing_reason,
  );
};

const getPortfolioRole = (item: PortfolioMatrixItem): string | null =>
  firstText(item.role, item.positionRole, item.position_role);

const getTradeName = (item: TradeTimelineItem): string =>
  firstText(item.name, item.target) ?? item.code ?? '未命名操作';

const getTradeRuleMatch = (item: TradeTimelineItem): string | null =>
  firstText(item.ruleMatch, item.rule_match, item.discipline);

const getTradeRuleNote = (item: TradeTimelineItem): string | null =>
  firstText(item.ruleNote, item.rule_note, item.review);

const getTradeDisplayPriceQty = (item: TradeTimelineItem): string => {
  const action = firstText(item.action);
  const parsed = action?.match(/(\d+(?:\.\d+)?)\s*@\s*(\d+(?:\.\d+)?)/);
  const quantity = item.quantity ?? (parsed ? Number(parsed[1]) : null);
  const price = item.price ?? (parsed ? Number(parsed[2]) : null);
  const priceText = typeof price === 'number' && Number.isFinite(price) ? `${price}` : '--';
  const quantityText = typeof quantity === 'number' && Number.isFinite(quantity) ? `${quantity}` : '--';
  return `${priceText} / ${quantityText}`;
};

const PortfolioRow: React.FC<{ item: PortfolioMatrixItem }> = ({ item }) => {
  const bbiDetailLine = renderBbiDetailLine(item);
  return (
    <div className="grid gap-3 border-t border-border/70 py-3 first:border-t-0 md:grid-cols-[1.1fr_0.95fr_1.4fr] md:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-foreground">{item.name}</span>
          <span className="font-mono text-xs text-muted-text">{item.code}</span>
          <StatusPill label={item.actionLabel || item.action} tone="border-sky-400/40 bg-sky-400/10 text-sky-200" />
        </div>
        <p className="mt-1 text-xs text-muted-text">{getPortfolioRole(item) || '仓位角色未取得'}</p>
      </div>

      <div className="grid grid-cols-3 gap-2 text-xs">
        <div>
          <p className="text-muted-text">强弱</p>
          <p className="mt-1 font-semibold text-foreground">{getStrengthLabel(item.strength)}</p>
        </div>
        <div className="col-span-1">
          <p className="text-muted-text">BBI</p>
          <p className="mt-1 font-semibold text-foreground">{renderBbiLabel(item.bbiPosition ?? item.bbi_position)}</p>
          {bbiDetailLine ? <p className="mt-1 leading-4 text-muted-text">{bbiDetailLine}</p> : null}
        </div>
        <div>
          <p className="text-muted-text">资金</p>
          <p className="mt-1 font-semibold text-foreground">{getFundDirectionLabel(item.fundDirection)}</p>
        </div>
      </div>

      <div className="min-w-0">
        <div className="flex flex-wrap gap-1.5">
          {((item.keyLevels?.length ? item.keyLevels : item.key_levels) ?? ['未取得']).map((level) => (
            <span
              key={`${item.code}-${level}`}
              className={cn('rounded-md border px-2 py-1 font-mono text-xs text-secondary-text', subtleChipClass)}
            >
              {level}
            </span>
          ))}
        </div>
        <p className="mt-2 text-sm leading-6 text-secondary-text">{item.nextTrigger || '明日触发动作未取得'}</p>
      </div>
    </div>
  );
};

const ExternalGroup: React.FC<{ group: MarketRadarExternalGroup }> = ({ group }) => {
  const impact = group.impact || 'missing';
  return (
    <div className={cn('rounded-lg border p-3', subtleCardClass)}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="font-semibold text-foreground">{group.title}</span>
        <StatusPill label={getImpactLabel(impact)} tone={impactToneMap[impact] ?? impactToneMap.missing} />
      </div>
      <div className="space-y-1.5">
        {(group.items?.length ? group.items : [{ name: '数据未取得', impact: 'missing' }]).map((item) => {
          const dataStatus = item.dataStatus ?? item.data_status;
          const changePct = item.changePct ?? item.change_pct;
          const dataDate = firstText(item.dataDate, item.data_date);
          const source = firstText(item.source);
          const sourceTimeStatus = getSourceTimeStatus(source, dataDate, dataStatus);
          return (
            <div key={`${group.region}-${item.code || item.name}`} className="text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="min-w-0 truncate text-secondary-text">{item.name}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {dataStatus === 'missing' || item.impact === 'missing' ? (
                    <span className={cn('rounded-full border px-1.5 py-0.5 text-[11px]', subtlePillTone)}>
                      数据缺失
                    </span>
                  ) : null}
                  <span className={cn('font-mono', toneByValue(changePct))}>
                    {dataStatus === 'missing' ? '未取得' : formatSignedPct(changePct)}
                  </span>
                </span>
              </div>
              {sourceTimeStatus ? (
                <p className="mt-0.5 truncate text-[11px] text-muted-text">
                  {sourceTimeStatus}
                </p>
              ) : null}
              {item.proxyNote || item.proxy_note || item.missingReason || item.missing_reason ? (
                <p className="mt-0.5 text-[11px] leading-4 text-muted-text">
                  {firstText(item.proxyNote, item.proxy_note, item.missingReason, item.missing_reason)}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
      {group.note ? <p className="mt-2 text-xs leading-5 text-muted-text">{group.note}</p> : null}
    </div>
  );
};

const TradeTimelineRow: React.FC<{ item: TradeTimelineItem }> = ({ item }) => {
  const action = firstText(item.action);
  const side = firstText(item.side);
  const isSell = side === 'sell' || Boolean(action?.includes('卖出'));
  const isBuy = side === 'buy' || Boolean(action?.includes('买入'));
  const sideLabel = side === 'buy' ? '买入' : side === 'sell' ? '卖出' : action || side || '操作';
  const ruleMatch = getTradeRuleMatch(item);
  const ruleNote = getTradeRuleNote(item);
  const tradeName = getTradeName(item);
  const priceQty = getTradeDisplayPriceQty(item);
  const sideTone = isBuy
    ? 'border-rose-400/40 bg-rose-400/10 text-rose-200'
    : isSell
      ? 'border-sky-400/40 bg-sky-400/10 text-sky-200'
      : subtlePillTone;
  return (
    <div className="grid gap-2 border-t border-border/70 py-3 first:border-t-0 sm:grid-cols-[4rem_1fr_auto] sm:items-center">
      <span className="font-mono text-sm text-muted-text">{item.time}</span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-semibold text-foreground">{tradeName}</span>
          <StatusPill
            label={sideLabel}
            tone={sideTone}
          />
          <StatusPill
            label={getRuleMatchLabel(ruleMatch)}
            tone={
              ruleMatch === 'yes'
                ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200'
                : ruleMatch === 'no'
                  ? 'border-rose-400/40 bg-rose-400/10 text-rose-200'
                  : 'border-amber-400/40 bg-amber-400/10 text-amber-200'
            }
          />
        </div>
        <p className="mt-1 text-sm leading-6 text-secondary-text">{ruleNote || '规则备注未取得'}</p>
      </div>
      <div className="font-mono text-sm text-secondary-text">
        {priceQty}
      </div>
    </div>
  );
};

const PlanItem: React.FC<{ item: NextSessionPlanItem }> = ({ item }) => (
  <div className={cn('rounded-lg border p-3', subtleCardClass)}>
    <div className="mb-2 flex items-center justify-between gap-2">
      <span className="font-semibold text-foreground">{item.title}</span>
      {item.ratio ? <StatusPill label={item.ratio} tone="border-cyan-400/40 bg-cyan-400/10 text-cyan-200" /> : null}
    </div>
    <p className="text-xs text-muted-text">触发</p>
    <p className="mt-1 text-sm leading-6 text-secondary-text">{item.trigger}</p>
    <p className="mt-2 text-xs text-muted-text">动作</p>
    <p className="mt-1 text-sm font-semibold leading-6 text-foreground">{item.action}</p>
    {item.invalidation ? (
      <p className="mt-2 text-xs leading-5 text-amber-200/90">失效：{item.invalidation}</p>
    ) : null}
  </div>
);

export const PositionDecisionDashboard: React.FC<PositionDecisionDashboardProps> = ({ report }) => {
  const radar = getMarketRadar(report);
  if (!radar) {
    return <LegacyDashboardFallback />;
  }

  const account = radar.account;
  const cnMarket = radar.cnMarket ?? radar.cn_market;
  const externalRadar = radar.externalRadar ?? radar.external_radar;
  const portfolioMatrix = radar.portfolioMatrix ?? radar.portfolio_matrix ?? [];
  const tradeTimeline = radar.tradeTimeline ?? radar.trade_timeline ?? [];
  const nextSessionPlan = radar.nextSessionPlan ?? radar.next_session_plan ?? [];
  const accountRisk = account?.riskLight || cnMarket?.riskLight || 'unknown';
  const breadth = cnMarket?.breadth;
  const upCount = breadth?.upCount ?? breadth?.up_count;
  const downCount = breadth?.downCount ?? breadth?.down_count;
  const totalAmount = breadth?.totalAmount ?? breadth?.total_amount;
  const mainNetInflow = breadth?.mainNetInflow ?? breadth?.main_net_inflow;
  const marketFreshness = firstText(cnMarket?.marketFreshness, cnMarket?.market_freshness);
  const marketFreshnessLabel = firstText(cnMarket?.marketFreshnessLabel, cnMarket?.market_freshness_label);
  const sessionStatusLabel = firstText(cnMarket?.sessionStatusLabel, cnMarket?.session_status_label);
  const fundFlowNote = firstText(
    breadth?.fundFlowNote,
    breadth?.fund_flow_note,
    breadth?.fundFlowMissingReason,
    breadth?.fund_flow_missing_reason,
  );
  const radarSnapshotTime = formatSnapshotTime(firstText(radar.generatedAt, radar.generated_at, report.meta?.createdAt));
  const marketCaption = [
    '当前显示的是所选报告生成时的大盘快照；不同个股报告生成时间不同，指数值可能不同。',
    cnMarket?.summary,
  ].filter(Boolean).join(' ');

  return (
    <section className="space-y-5" aria-label="A股持仓决策仪表盘">
      <div className="overflow-hidden rounded-xl border border-border/70 bg-elevated/90 shadow-soft-card">
        <div className="border-b border-border/70 px-4 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="flex items-center gap-2 text-xl font-bold text-foreground">
                <WalletCards className="h-5 w-5 text-cyan-300" />
                A股持仓决策仪表盘
              </h2>
              <p className="mt-1 text-sm text-muted-text">
                只服务A股交易；外围市场只做风险偏好参考。
              </p>
            </div>
            <StatusPill
              label={account?.posture || getRiskLabel(accountRisk)}
              tone={riskToneMap[accountRisk] ?? riskToneMap.unknown}
              className="text-sm"
            />
          </div>
        </div>

        <div className="grid gap-4 px-4 py-4 sm:grid-cols-2 lg:grid-cols-5">
          <Metric label="总资产" value={formatNumber(account?.totalAssets)} />
          <Metric label="当日盈亏" value={formatSignedAmount(account?.dayPnl)} valueClassName={toneByValue(account?.dayPnl)} />
          <Metric label="当日涨跌" value={formatSignedPct(account?.dayPnlPct)} valueClassName={toneByValue(account?.dayPnlPct)} />
          <Metric label="仓位" value={typeof account?.positionPct === 'number' ? `${account.positionPct.toFixed(1)}%` : '未取得'} />
          <Metric label="现金" value={formatNumber(account?.cash)} />
        </div>
      </div>

      <section className="rounded-xl border border-border/70 bg-surface/70 p-4" aria-label="A股市场雷达">
        <SectionHeader
          icon={<BarChart3 className="h-4 w-4" />}
          title="A股市场雷达"
          caption={marketCaption}
          meta={
            <>
              <StatusPill label="报告快照" tone="border-cyan-400/40 bg-cyan-400/10 text-cyan-200" />
              {radarSnapshotTime ? (
                <StatusPill
                  label={`报告时间 ${radarSnapshotTime}`}
                  tone={subtlePillTone}
                />
              ) : null}
            </>
          }
        />
        {marketFreshnessLabel || sessionStatusLabel ? (
          <div className="mb-3 flex flex-wrap gap-2">
            {marketFreshnessLabel ? (
              <StatusPill
                label={marketFreshnessLabel}
                tone={marketFreshnessToneMap[marketFreshness || ''] ?? marketFreshnessToneMap.missing}
              />
            ) : null}
            {sessionStatusLabel ? (
              <StatusPill label={sessionStatusLabel} tone={subtlePillTone} />
            ) : null}
          </div>
        ) : null}
        <div className="grid gap-3 md:grid-cols-4">
          {(cnMarket?.indices?.length ? cnMarket.indices : [{ name: '指数未取得' }]).map((index) => {
            const changePct = index.changePct ?? index.change_pct;
            const sourceTimeStatus = getSourceTimeStatus(
              index.source,
              firstText(index.dataDate, index.data_date),
              index.dataStatus ?? index.data_status,
            );
            return (
              <div key={`${index.code || index.name}`} className={cn('rounded-lg border p-3', subtleCardClass)}>
                <p className="truncate text-sm font-semibold text-foreground">{index.name}</p>
                <div className="mt-2 flex items-end justify-between gap-2">
                  <span className="font-mono text-lg text-secondary-text">
                    {typeof index.current === 'number' ? formatNumber(index.current) : '未取得'}
                  </span>
                  <span className={cn('font-mono text-sm font-semibold', toneByValue(changePct))}>
                    {formatSignedPct(changePct)}
                  </span>
                </div>
                {sourceTimeStatus ? (
                  <p className="mt-1 truncate text-[11px] text-muted-text">{sourceTimeStatus}</p>
                ) : null}
              </div>
            );
          })}
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-4">
          <Metric
            label="涨跌家数"
            value={`${upCount ?? '未取得'} / ${downCount ?? '未取得'}`}
          />
          <Metric label="成交额" value={formatSignedAmount(totalAmount, '亿')} />
          <Metric label="主力资金" value={formatSignedAmount(mainNetInflow, '亿')} valueClassName={toneByValue(mainNetInflow)} />
          <Metric label="风险灯" value={getRiskLabel(cnMarket?.riskLight)} />
        </div>
        {fundFlowNote ? (
          <p className="mt-3 rounded-lg border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-100/90">
            {fundFlowNote}
          </p>
        ) : null}
        {cnMarket?.sectors?.length ? (
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {cnMarket.sectors.map((sector) => (
              <div
                key={sector.name}
                data-testid={`market-sector-chip-${sector.name}`}
                className={cn('rounded-lg border px-3 py-2.5', subtleCardClass)}
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="min-w-0 truncate text-sm font-semibold text-foreground">{sector.name}</span>
                  <StatusPill
                    label={getStrengthLabel(sector.strength)}
                    tone={
                      sector.strength === 'strong'
                        ? 'border-emerald-400/40 bg-emerald-400/10 text-emerald-200'
                        : sector.strength === 'weak'
                          ? 'border-rose-400/40 bg-rose-400/10 text-rose-200'
                          : 'border-amber-400/40 bg-amber-400/10 text-amber-200'
                    }
                  />
                </div>
                <div className="mt-2 flex items-end justify-between gap-3">
                  <span className={cn('font-mono text-base font-semibold', toneByValue(sector.changePct ?? sector.change_pct))}>
                    {formatSignedPct(sector.changePct ?? sector.change_pct)}
                  </span>
                  <span className={cn('font-mono text-sm', toneByValue(sector.fundFlow ?? sector.fund_flow))}>
                    {formatSignedAmount(sector.fundFlow ?? sector.fund_flow, '亿')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="rounded-xl border border-border/70 bg-surface/70 p-4" aria-label="外围影响雷达">
        <SectionHeader
          icon={<Globe2 className="h-4 w-4" />}
          title="外围影响雷达"
          caption={externalRadar?.scopeNote || '美股、韩国、日本只判断A股科技线风险偏好。'}
        />
        <div className="grid gap-3 md:grid-cols-3">
          {(externalRadar?.groups?.length ? externalRadar.groups : [{ region: 'missing', title: '外围数据', impact: 'missing' }]).map((group) => (
            <ExternalGroup key={`${group.region}-${group.title}`} group={group} />
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-border/70 bg-surface/70 p-4" aria-label="持仓决策矩阵">
        <SectionHeader
          icon={<ListChecks className="h-4 w-4" />}
          title="持仓决策矩阵"
          caption="买强不买弱，去弱留强；长期趋势票重点看周K和BBI。"
        />
        <div>
          {portfolioMatrix.length ? (
            portfolioMatrix.map((item) => <PortfolioRow key={item.code} item={item} />)
          ) : (
            <p className="py-4 text-sm text-muted-text">持仓矩阵未取得。</p>
          )}
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[1fr_1.15fr]">
        <section className="rounded-xl border border-border/70 bg-surface/70 p-4" aria-label="今日操作时间线">
          <SectionHeader
            icon={<Clock3 className="h-4 w-4" />}
            title="今日操作时间线"
            caption="按时间检查是否符合先试仓、确认后加仓、做错不加仓。"
          />
          <div>
            {tradeTimeline.length ? (
              tradeTimeline.map((item, index) => <TradeTimelineRow key={`${item.time}-${item.code || item.name}-${index}`} item={item} />)
            ) : (
              <p className="py-4 text-sm text-muted-text">今日操作未取得；未操作的持仓不会被判定为操作错误。</p>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-border/70 bg-surface/70 p-4" aria-label="明日三阶段执行">
          <SectionHeader
            icon={<Activity className="h-4 w-4" />}
            title="明日三阶段执行"
            caption="先定触发条件，再定动作比例，盘中少拍脑袋。"
          />
          <div className="grid gap-3 lg:grid-cols-3">
            {nextSessionPlan.length ? (
              nextSessionPlan.map((item) => <PlanItem key={`${item.stage}-${item.title}`} item={item} />)
            ) : (
              <div className={cn('rounded-lg border p-3 text-sm text-muted-text', subtleCardClass)}>
                明日计划未取得。
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="rounded-xl border border-amber-400/20 bg-amber-400/[0.06] p-4" aria-label="纪律提醒">
        <div className="flex items-start gap-3">
          <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-200" />
          <div>
            <h3 className="text-sm font-semibold text-amber-100">纪律提醒</h3>
            <p className="mt-1 text-sm leading-6 text-amber-100/85">
              理性是情绪的对手盘：先试仓，确认后加仓；做对了拿住，做错了不加仓，等回本或纪律位处理。
            </p>
          </div>
          <CheckCircle2 className="ml-auto hidden h-5 w-5 text-emerald-200 sm:block" />
          <AlertTriangle className="hidden" aria-hidden="true" />
        </div>
      </section>
    </section>
  );
};
