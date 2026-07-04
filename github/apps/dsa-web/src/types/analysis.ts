/**
 * Analysis-related type definitions.
 * Aligned with the API schema.
 */

// ============ Request Types ============

export type StockReportType = 'simple' | 'detailed' | 'full' | 'brief';
export type ReportType = StockReportType | 'market_review';
export type AnalysisPhase = 'auto' | 'premarket' | 'intraday' | 'postmarket';

export interface AnalysisRequest {
  stockCode?: string;
  stockCodes?: string[];
  reportType?: StockReportType;
  forceRefresh?: boolean;
  asyncMode?: boolean;
  analysisPhase?: AnalysisPhase;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: 'manual' | 'autocomplete' | 'import' | 'image';
  notify?: boolean;
  skills?: string[];
  reportLanguage?: ReportLanguage;
}

export interface MarketReviewRequest {
  sendNotification?: boolean;
  reportLanguage?: ReportLanguage;
}

export interface MarketReviewAccepted {
  status: 'accepted';
  message: string;
  sendNotification: boolean;
  traceId?: string;
  taskId?: string;
}

// ============ Report Types ============

export type ReportLanguage = 'zh' | 'en';

export type MarketPhaseValue =
  | 'premarket'
  | 'intraday'
  | 'lunch_break'
  | 'closing_auction'
  | 'postmarket'
  | 'non_trading'
  | 'unknown';

export interface MarketPhaseSummary {
  market?: string | null;
  phase: MarketPhaseValue;
  marketLocalTime?: string | null;
  sessionDate?: string | null;
  effectiveDailyBarDate?: string | null;
  isTradingDay?: boolean | null;
  isMarketOpenNow?: boolean | null;
  isPartialBar?: boolean | null;
  minutesToOpen?: number | null;
  minutesToClose?: number | null;
  triggerSource?: string | null;
  analysisIntent?: string | null;
  warnings: string[];
}

/** Report metadata */
export interface ReportMeta {
  id?: number;  // Analysis history record ID, present for persisted reports
  queryId: string;
  stockCode: string;
  stockName: string;
  reportType: ReportType;
  reportLanguage?: ReportLanguage;
  createdAt: string;
  currentPrice?: number;
  changePct?: number;
  modelUsed?: string;  // Display-only model snapshot from persisted history; not used for runtime model selection
  marketPhaseSummary?: MarketPhaseSummary | null;
}

/** Sentiment label */
export type SentimentLabel =
  | '极度悲观'
  | '悲观'
  | '中性'
  | '乐观'
  | '极度乐观'
  | 'Very Bearish'
  | 'Bearish'
  | 'Neutral'
  | 'Bullish'
  | 'Very Bullish';

export type DecisionAction = 'buy' | 'add' | 'hold' | 'reduce' | 'sell' | 'watch' | 'avoid' | 'alert';

/** Report summary section */
export interface ReportSummary {
  analysisSummary: string;
  operationAdvice: string;
  action?: DecisionAction | null;
  actionLabel?: string | null;
  trendPrediction: string;
  sentimentScore: number;
  sentimentLabel?: SentimentLabel;
}

/** Strategy section */
export interface ReportStrategy {
  idealBuy?: string;
  secondaryBuy?: string;
  stopLoss?: string;
  takeProfit?: string;
}

export interface ReportKlineBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  ma5?: number | null;
  ma10?: number | null;
  ma20?: number | null;
  bbi?: number | null;
}

export interface ReportKlineChartPayload {
  source?: string | null;
  dataDate?: string | null;
  data_date?: string | null;
  bars?: ReportKlineBar[];
  warnings?: string[];
}

export interface RelatedBoard {
  name: string;
  code?: string;
  type?: string;
}

export interface SectorRankingItem {
  name: string;
  changePct?: number;
}

export interface SectorRankings {
  top?: SectorRankingItem[];
  bottom?: SectorRankingItem[];
}

export interface MarketReviewPayloadSection {
  key?: string;
  title: string;
  markdown: string;
}

export interface MarketReviewIndex {
  code: string;
  name: string;
  current?: number;
  change?: number;
  changePct?: number;
  open?: number;
  high?: number;
  low?: number;
  volume?: number;
  amount?: number;
  amplitude?: number;
}

export interface MarketReviewBreadth {
  upCount?: number;
  downCount?: number;
  flatCount?: number;
  limitUpCount?: number;
  limitDownCount?: number;
  totalAmount?: number;
  turnoverUnit?: string;
}

export interface MarketReviewPayload {
  version?: number;
  kind?: 'market_review' | string;
  region?: string;
  language?: ReportLanguage | string;
  title?: string;
  rootTitle?: string;
  generatedAt?: string;
  date?: string;
  marketScope?: string;
  marketLight?: Record<string, unknown>;
  breadth?: MarketReviewBreadth;
  indices?: MarketReviewIndex[];
  sectors?: SectorRankings;
  news?: Array<Record<string, unknown>>;
  sections?: MarketReviewPayloadSection[];
  markets?: Record<string, MarketReviewPayload>;
  markdownReport?: string;
}

export type MarketRadarRiskLight = 'attack' | 'balanced' | 'defense' | 'danger' | 'unknown';
export type MarketRadarImpact = 'positive' | 'neutral' | 'negative' | 'missing';
export type MarketRadarStrength = 'strong' | 'watch' | 'weak' | 'unknown';
export type MarketRadarFundDirection = 'inflow' | 'flat' | 'outflow' | 'missing';
export type MarketRadarRuleMatch = 'yes' | 'partial' | 'no' | 'unknown';

export interface MarketRadarAccount {
  totalAssets?: number | null;
  dayPnl?: number | null;
  dayPnlPct?: number | null;
  positionPct?: number | null;
  cash?: number | null;
  riskLight?: MarketRadarRiskLight | string | null;
  posture?: string | null;
}

export interface MarketRadarIndex {
  code?: string;
  name: string;
  current?: number | null;
  changePct?: number | null;
  change_pct?: number | null;
  change?: number | null;
  amount?: number | null;
  dataStatus?: 'ok' | 'stale' | 'cached' | 'missing' | string | null;
  data_status?: 'ok' | 'stale' | 'cached' | 'missing' | string | null;
  source?: string | null;
  dataDate?: string | null;
  data_date?: string | null;
}

export interface MarketRadarBreadth {
  upCount?: number | null;
  up_count?: number | null;
  downCount?: number | null;
  down_count?: number | null;
  flatCount?: number | null;
  flat_count?: number | null;
  limitUpCount?: number | null;
  limit_up_count?: number | null;
  limitDownCount?: number | null;
  limit_down_count?: number | null;
  totalAmount?: number | null;
  total_amount?: number | null;
  mainNetInflow?: number | null;
  main_net_inflow?: number | null;
  fundFlowStatus?: string | null;
  fund_flow_status?: string | null;
  fundFlowMissingReason?: string | null;
  fund_flow_missing_reason?: string | null;
  fundFlowNote?: string | null;
  fund_flow_note?: string | null;
  dataStatus?: 'ok' | 'stale' | 'cached' | 'missing' | string | null;
  data_status?: 'ok' | 'stale' | 'cached' | 'missing' | string | null;
  source?: string | null;
  dataDate?: string | null;
  data_date?: string | null;
}

export interface MarketRadarSector {
  name: string;
  strength?: MarketRadarStrength | string | null;
  changePct?: number | null;
  change_pct?: number | null;
  fundFlow?: number | null;
  fund_flow?: number | null;
  current?: number | null;
  volume?: number | null;
  dataStatus?: 'ok' | 'stale' | 'cached' | 'missing' | string | null;
  data_status?: 'ok' | 'stale' | 'cached' | 'missing' | string | null;
  source?: string | null;
  dataDate?: string | null;
  data_date?: string | null;
  proxyNote?: string | null;
  proxy_note?: string | null;
}

export interface MarketRadarCnMarket {
  riskLight?: MarketRadarRiskLight | string | null;
  summary?: string | null;
  indices?: MarketRadarIndex[];
  breadth?: MarketRadarBreadth | null;
  sectors?: MarketRadarSector[];
  dataStatus?: 'ok' | 'partial' | 'missing' | string | null;
  data_status?: 'ok' | 'partial' | 'missing' | string | null;
  marketFreshness?: 'same_day_current' | 'same_day_stale' | 'stale_other_day' | 'missing' | string | null;
  market_freshness?: 'same_day_current' | 'same_day_stale' | 'stale_other_day' | 'missing' | string | null;
  marketFreshnessLabel?: string | null;
  market_freshness_label?: string | null;
  sessionStatus?: string | null;
  session_status?: string | null;
  sessionStatusLabel?: string | null;
  session_status_label?: string | null;
  source?: string | null;
}

export interface MarketRadarExternalItem {
  code?: string;
  name: string;
  current?: number | null;
  changePct?: number | null;
  change_pct?: number | null;
  impact?: MarketRadarImpact | string | null;
  dataStatus?: 'ok' | 'stale' | 'missing' | string | null;
  data_status?: 'ok' | 'stale' | 'missing' | string | null;
  source?: string | null;
  dataDate?: string | null;
  data_date?: string | null;
  missingReason?: string | null;
  missing_reason?: string | null;
  proxyNote?: string | null;
  proxy_note?: string | null;
}

export interface MarketRadarExternalGroup {
  region: 'us' | 'kr' | 'jp' | string;
  title: string;
  impact: MarketRadarImpact | string;
  items?: MarketRadarExternalItem[];
  note?: string | null;
}

export interface PortfolioMatrixItem {
  code: string;
  name: string;
  action: DecisionAction | string;
  actionLabel: string;
  role?: string | null;
  positionRole?: string | null;
  position_role?: string | null;
  strength?: MarketRadarStrength | string | null;
  bbiPosition?: string | null;
  bbi_position?: string | null;
  bbiDetails?: {
    current?: number | null;
    daily?: { value?: number | null; status?: string | null; missingReason?: string | null; missing_reason?: string | null };
    weekly?: { value?: number | null; status?: string | null; missingReason?: string | null; missing_reason?: string | null };
    source?: string | null;
    missingReason?: string | null;
    missing_reason?: string | null;
  } | null;
  bbi_details?: PortfolioMatrixItem['bbiDetails'];
  bbiMissingReason?: string | null;
  bbi_missing_reason?: string | null;
  fundDirection?: MarketRadarFundDirection | string | null;
  keyLevels?: string[];
  key_levels?: string[];
  nextTrigger?: string | null;
}

export interface TradeTimelineItem {
  time: string;
  code?: string;
  name?: string;
  target?: string | null;
  side?: 'buy' | 'sell' | 'deposit' | 'withdraw' | string;
  action?: string | null;
  price?: number | null;
  quantity?: number | null;
  ruleMatch?: MarketRadarRuleMatch | string | null;
  rule_match?: MarketRadarRuleMatch | string | null;
  discipline?: MarketRadarRuleMatch | string | null;
  ruleNote?: string | null;
  rule_note?: string | null;
  review?: string | null;
}

export interface NextSessionPlanItem {
  stage: 'open_15m' | '1030' | '1430' | string;
  title: string;
  trigger: string;
  action: string;
  ratio?: string | null;
  invalidation?: string | null;
}

export interface MarketRadarPayload {
  version?: number;
  date?: string;
  generatedAt?: string | null;
  generated_at?: string | null;
  traderScope?: 'a_share_only' | string;
  account?: MarketRadarAccount | null;
  cnMarket?: MarketRadarCnMarket | null;
  cn_market?: MarketRadarCnMarket | null;
  externalRadar?: {
    scopeNote?: string | null;
    groups?: MarketRadarExternalGroup[];
  } | null;
  external_radar?: {
    scopeNote?: string | null;
    groups?: MarketRadarExternalGroup[];
  } | null;
  portfolioMatrix?: PortfolioMatrixItem[];
  portfolio_matrix?: PortfolioMatrixItem[];
  tradeTimeline?: TradeTimelineItem[];
  trade_timeline?: TradeTimelineItem[];
  nextSessionPlan?: NextSessionPlanItem[];
  next_session_plan?: NextSessionPlanItem[];
}

export type AnalysisContextPackBlockStatus =
  | 'available'
  | 'missing'
  | 'not_supported'
  | 'fallback'
  | 'stale'
  | 'estimated'
  | 'partial'
  | 'fetch_failed';

export interface AnalysisContextPackOverviewSubject {
  code: string;
  stockName?: string | null;
  market?: string | null;
}

export interface AnalysisContextPackOverviewBlock {
  key: string;
  label: string;
  status: AnalysisContextPackBlockStatus;
  source?: string | null;
  warnings: string[];
  missingReasons: string[];
}

export interface AnalysisContextPackOverviewCounts {
  available: number;
  missing: number;
  notSupported: number;
  fallback: number;
  stale: number;
  estimated: number;
  partial: number;
  fetchFailed: number;
}

export interface AnalysisContextPackOverviewMetadata {
  triggerSource?: string | null;
  newsResultCount?: number | null;
}

export type AnalysisContextPackDataQualityLevel = 'good' | 'usable' | 'limited' | 'poor';

export interface AnalysisContextPackOverviewDataQuality {
  overallScore?: number | null;
  level?: AnalysisContextPackDataQualityLevel | null;
  blockScores: Record<string, number>;
  limitations: string[];
}

export interface AnalysisContextPackOverview {
  packVersion: string;
  createdAt?: string | null;
  subject: AnalysisContextPackOverviewSubject;
  blocks: AnalysisContextPackOverviewBlock[];
  counts: AnalysisContextPackOverviewCounts;
  dataQuality?: AnalysisContextPackOverviewDataQuality | null;
  warnings: string[];
  metadata: AnalysisContextPackOverviewMetadata;
}

/** Details section */
export interface ReportDetails {
  newsContent?: string;
  rawResult?: Record<string, unknown>;
  contextSnapshot?: Record<string, unknown> & {
    marketReviewPayload?: MarketReviewPayload;
    market_review_payload?: MarketReviewPayload;
    marketRadar?: MarketRadarPayload;
    market_radar?: MarketRadarPayload;
  };
  analysisContextPackOverview?: AnalysisContextPackOverview | null;
  financialReport?: Record<string, unknown>;
  dividendMetrics?: Record<string, unknown>;
  klineChart?: ReportKlineChartPayload | null;
  kline_chart?: ReportKlineChartPayload | null;
  belongBoards?: RelatedBoard[];
  sectorRankings?: SectorRankings;
}

/** Full analysis report */
export interface AnalysisReport {
  meta: ReportMeta;
  summary: ReportSummary;
  strategy?: ReportStrategy;
  details?: ReportDetails;
}

// ============ Analysis Result Types ============

export type RunDiagnosticStatus = 'normal' | 'degraded' | 'failed' | 'unknown';

export type RunDiagnosticComponentStatus =
  | 'ok'
  | 'degraded'
  | 'failed'
  | 'unknown'
  | 'not_configured'
  | 'skipped';

export interface RunDiagnosticComponent {
  key: string;
  label: string;
  status: RunDiagnosticComponentStatus;
  message: string;
  details?: Record<string, unknown>;
}

export interface RunDiagnosticSummary {
  traceId?: string;
  taskId?: string;
  queryId?: string;
  stockCode?: string;
  triggerSource?: string;
  status: RunDiagnosticStatus;
  statusLabel: string;
  reason: string;
  components: Record<string, RunDiagnosticComponent>;
  copyText: string;
}

/** Sync analysis response */
export interface AnalysisResult {
  queryId: string;
  traceId?: string;
  stockCode: string;
  stockName: string;
  report: AnalysisReport;
  diagnosticSummary?: RunDiagnosticSummary;
  createdAt: string;
}

/** Async task accepted response */
export interface TaskAccepted {
  taskId: string;
  traceId?: string;
  status: 'pending' | 'processing';
  message?: string;
  analysisPhase?: AnalysisPhase;
}

export interface BatchTaskAcceptedItem {
  taskId: string;
  traceId?: string;
  stockCode: string;
  status: 'pending' | 'processing';
  message?: string;
  analysisPhase?: AnalysisPhase;
}

export interface BatchDuplicateTaskItem {
  stockCode: string;
  existingTaskId: string;
  message: string;
}

export interface BatchTaskAcceptedResponse {
  accepted: BatchTaskAcceptedItem[];
  duplicates: BatchDuplicateTaskItem[];
  message: string;
}

export type AnalyzeAsyncResponse = TaskAccepted | BatchTaskAcceptedResponse;

export type AnalyzeResponse = AnalysisResult | AnalyzeAsyncResponse;

/** Task status */
export interface TaskStatus {
  taskId: string;
  traceId?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancel_requested' | 'cancelled';
  progress?: number;
  result?: AnalysisResult;
  marketReviewReport?: string;
  marketReviewPayload?: MarketReviewPayload;
  error?: string;
  stockName?: string;
  originalQuery?: string;
  selectionSource?: string;
  analysisPhase?: AnalysisPhase | null;
  skills?: string[];
}

/** Task details used by task list and SSE events */
export interface TaskInfo {
  taskId: string;
  traceId?: string;
  stockCode: string;
  stockName?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'cancel_requested' | 'cancelled';
  progress: number;
  message?: string;
  reportType: string;
  createdAt: string;
  startedAt?: string;
  completedAt?: string;
  error?: string;
  originalQuery?: string;
  selectionSource?: string;
  analysisPhase?: AnalysisPhase;
  skills?: string[];
}

/** Task list response */
export interface TaskListResponse {
  total: number;
  pending: number;
  processing: number;
  tasks: TaskInfo[];
}

/** Duplicate task error response */
export interface DuplicateTaskError {
  error: 'duplicate_task';
  message: string;
  stockCode: string;
  existingTaskId: string;
}

// ============ History Types ============

/** History item summary */
export interface HistoryItem {
  id: number;  // Record primary key ID, always present for persisted history items
  queryId: string;  // Linked analysis query ID
  stockCode: string;
  stockName?: string;
  reportType?: ReportType;
  trendPrediction?: string;
  analysisSummary?: string;
  sentimentScore?: number;
  operationAdvice?: string;
  action?: DecisionAction | null;
  actionLabel?: string | null;
  currentPrice?: number;
  changePct?: number;
  volumeRatio?: number;
  turnoverRate?: number;
  hasMarketRadar?: boolean;
  modelUsed?: string;  // Display-only model snapshot from persisted history; runtime provider/model/base URL still come from analyzer configuration
  marketPhaseSummary?: MarketPhaseSummary | null;
  createdAt: string;
}

export type StockHistoryRange = 'all' | '30d' | '90d';

export interface StockHistoryFilters {
  range: StockHistoryRange;
  model: string;
  sort: 'desc' | 'asc';
}

/** History list response */
export interface HistoryListResponse {
  total: number;
  page: number;
  limit: number;
  items: HistoryItem[];
}

/** News item */
export interface NewsIntelItem {
  title: string;
  snippet: string;
  url: string;
}

/** News response */
export interface NewsIntelResponse {
  total: number;
  items: NewsIntelItem[];
}

/** History filter parameters */
export interface HistoryFilters {
  stockCode?: string;
  reportType?: ReportType;
  startDate?: string;
  endDate?: string;
}

/** History pagination parameters */
export interface HistoryPagination {
  page: number;
  limit: number;
}

// ============ Stock Bar Types ============

export interface StockBarItem {
  id: number;
  stockCode: string;
  stockName?: string;
  reportType?: string;
  sentimentScore?: number;
  operationAdvice?: string;
  action?: DecisionAction | null;
  actionLabel?: string | null;
  analysisCount: number;
  lastAnalysisTime?: string;
  modelUsed?: string;
  marketPhaseSummary?: MarketPhaseSummary | null;
}

export interface StockBarResponse {
  total: number;
  items: StockBarItem[];
}

// ============ Error Types ============

export interface ApiError {
  error: string;
  message: string;
  detail?: Record<string, unknown>;
}

// ============ Helper Functions ============

/** Get sentiment label by score */
export const getSentimentLabel = (score: number, language: ReportLanguage = 'zh'): SentimentLabel => {
  if (language === 'en') {
    if (score <= 20) return 'Very Bearish';
    if (score <= 40) return 'Bearish';
    if (score <= 60) return 'Neutral';
    if (score <= 80) return 'Bullish';
    return 'Very Bullish';
  }
  if (score <= 20) return '极度悲观';
  if (score <= 40) return '悲观';
  if (score <= 60) return '中性';
  if (score <= 80) return '乐观';
  return '极度乐观';
};

/** Get sentiment color by score */
export const getSentimentColor = (score: number): string => {
  if (score <= 20) return '#ef4444'; // red-500
  if (score <= 40) return '#f97316'; // orange-500
  if (score <= 60) return '#eab308'; // yellow-500
  if (score <= 80) return '#22c55e'; // green-500
  return '#10b981'; // emerald-500
};
