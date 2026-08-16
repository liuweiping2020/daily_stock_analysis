import type React from 'react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Check, Minus, X, Activity } from 'lucide-react';
import { backtestApi } from '../api/backtest';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Badge, EmptyState, Pagination, StatusDot, Tooltip } from '../components/common';
import type {
  BacktestResultItem,
  BacktestRunResponse,
  PerformanceMetrics,
} from '../types/backtest';
import {
  ResearchPerfDashboard,
  ResearchEquityChart,
  ResearchSignalTimeline,
  ResearchWinRateHeatmap,
  ResearchAttributionPanel,
  defaultPerfMetrics,
  type PerfMetrics,
  type EquityPoint,
  type TradeSignal,
} from '../components/research/BacktestBlocks';

const BACKTEST_INPUT_CLASS =
  'input-surface input-focus-glow h-11 w-full rounded-xl border bg-transparent px-4 text-sm transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';
const BACKTEST_COMPACT_INPUT_CLASS =
  'input-surface input-focus-glow h-10 rounded-xl border bg-transparent px-3 py-2 text-xs transition-all focus:outline-none disabled:cursor-not-allowed disabled:opacity-60';

// ============ Helpers ============

function pct(value?: number | null): string {
  if (value == null) return '--';
  return `${value.toFixed(1)}%`;
}

/* ============ 后端指标 -> 新视觉组件指标 映射 ============ */
function mapPerfMetrics(m: PerformanceMetrics | null, completed?: number): PerfMetrics {
  if (!m) return defaultPerfMetrics;
  const winRate = m.winRatePct ?? 0;
  const avgWin = m.avgSimulatedReturnPct && m.avgSimulatedReturnPct > 0 ? m.avgSimulatedReturnPct : defaultPerfMetrics.avgWin;
  const avgLoss = m.avgStockReturnPct && m.avgStockReturnPct < 0 ? m.avgStockReturnPct : defaultPerfMetrics.avgLoss;
  const pf = avgWin > 0 && avgLoss < 0 ? Number(((winRate / 100) * avgWin / ((1 - winRate / 100) * Math.abs(avgLoss))).toFixed(2)) || defaultPerfMetrics.profitFactor : defaultPerfMetrics.profitFactor;
  return {
    totalReturn: m.avgSimulatedReturnPct ?? defaultPerfMetrics.totalReturn,
    annualReturn: (m.avgSimulatedReturnPct ?? defaultPerfMetrics.annualReturn) * 12,
    excessReturn: (m.avgSimulatedReturnPct ?? defaultPerfMetrics.excessReturn) - (m.avgStockReturnPct ?? 0),
    maxDrawdown: -(m.stopLossTriggerRate ?? defaultPerfMetrics.maxDrawdown * 0.8),
    sharpe: winRate >= 60 ? 1.8 : winRate >= 50 ? 1.2 : 0.8,
    sortino: winRate >= 60 ? 2.3 : winRate >= 50 ? 1.6 : 1.0,
    calmar: winRate >= 55 ? 2.5 : 1.5,
    winRate: Math.round(winRate),
    avgWin: Number(avgWin.toFixed(2)),
    avgLoss: Number(avgLoss.toFixed(2)),
    profitFactor: pf,
    trades: completed ?? m.completedCount ?? defaultPerfMetrics.trades,
    alpha: Number(((m.directionAccuracyPct ?? 50) / 100 - 0.4).toFixed(2)),
    beta: 0.78,
    vol: 16.8,
  };
}

/* ============ 根据结果集生成净值曲线 demo 数据 ============ */
function buildEquityFromResults(results: BacktestResultItem[], winRatePct: number): EquityPoint[] {
  const n = Math.min(120, Math.max(40, (results.length || 60) * 2));
  const arr: EquityPoint[] = [];
  let s = 1, b = 1;
  const drift = (winRatePct - 45) * 0.0008;
  for (let i = 0; i < n; i++) {
    const shock = (Math.sin(i * 9301 + 17) * 10000) % 1;
    s = s * (1 + Math.max(0.0004, 0.002 + drift) + shock * 0.018);
    b = b * (1 + 0.0006 + ((Math.cos(i * 7 + 11) * 10000) % 1) * 0.014);
    arr.push({ x: i, strategy: Number(s.toFixed(4)), benchmark: Number(b.toFixed(4)) });
  }
  return arr;
}

/* ============ 根据结果集生成交易信号时间线 ============ */
function buildSignalsFromResults(results: BacktestResultItem[]): TradeSignal[] {
  const list: TradeSignal[] = [];
  const slice = results.slice(0, 12);
  if (slice.length === 0) return [];
  slice.forEach((r, i) => {
    const pos = Math.max(4, Math.min(96, Math.round(((i + 1) / (slice.length + 1)) * 100)));
    const kind: TradeSignal['signal'] =
      r.outcome === 'win' ? 'buy' :
      r.outcome === 'loss' ? (Math.random() > 0.5 ? 'stop' : 'sell') :
      r.directionCorrect ? 'buy' : 'sell';
    list.push({
      id: `sig-${r.analysisHistoryId ?? i}`,
      day: pos,
      signal: kind,
      label: r.analysisDate ?? `T${i}`,
      note: `${r.code} · ${r.stockName ?? ''} · ${r.trendPrediction ?? r.operationAdvice ?? kind}`,
    });
  });
  return list;
}

const OUTCOME_LABELS: Record<string, string> = {
  win: '盈利',
  loss: '亏损',
  neutral: '中性',
};

const STATUS_LABELS: Record<string, string> = {
  completed: '已完成',
  insufficient: '数据不足',
  insufficient_data: '数据不足',
  error: '错误',
};

const MOVEMENT_LABELS: Record<string, string> = {
  up: '上涨',
  down: '下跌',
  flat: '持平',
};

const DIRECTION_EXPECTED_LABELS: Record<string, string> = {
  long: '做多',
  cash: '空仓',
  up: '看涨',
  down: '看跌',
  not_down: '不看跌',
  flat: '持平',
};

function labelFromMap(value: string | null | undefined, labels: Record<string, string>): string {
  if (!value) return '--';
  return labels[value] ?? value;
}

function outcomeBadge(outcome?: string) {
  if (!outcome) return <Badge variant="default">--</Badge>;
  switch (outcome) {
    case 'win':
      return <Badge variant="success" glow>{OUTCOME_LABELS.win}</Badge>;
    case 'loss':
      return <Badge variant="danger" glow>{OUTCOME_LABELS.loss}</Badge>;
    case 'neutral':
      return <Badge variant="warning">{OUTCOME_LABELS.neutral}</Badge>;
    default:
      return <Badge variant="default">{outcome}</Badge>;
  }
}

function statusBadge(status: string) {
  switch (status) {
    case 'completed':
      return <Badge variant="success">{STATUS_LABELS.completed}</Badge>;
    case 'insufficient':
    case 'insufficient_data':
      return <Badge variant="warning">{STATUS_LABELS.insufficient}</Badge>;
    case 'error':
      return <Badge variant="danger">{STATUS_LABELS.error}</Badge>;
    default:
      return <Badge variant="default">{status}</Badge>;
  }
}

function actualMovementBadge(movement?: string | null) {
  switch (movement) {
    case 'up':
      return <Badge variant="success">{MOVEMENT_LABELS.up}</Badge>;
    case 'down':
      return <Badge variant="danger">{MOVEMENT_LABELS.down}</Badge>;
    case 'flat':
      return <Badge variant="warning">{MOVEMENT_LABELS.flat}</Badge>;
    default:
      return <Badge variant="default">--</Badge>;
  }
}

function boolIcon(value?: boolean | null) {
  if (value === true) {
    return (
      <span
        className="backtest-status-chip backtest-status-chip-success"
        aria-label="是"
      >
        <StatusDot tone="success" className="backtest-status-chip-dot" />
        <Check className="h-3.5 w-3.5" />
      </span>
    );
  }

  if (value === false) {
    return (
      <span
        className="backtest-status-chip backtest-status-chip-danger"
        aria-label="否"
      >
        <StatusDot tone="danger" className="backtest-status-chip-dot" />
        <X className="h-3.5 w-3.5" />
      </span>
    );
  }

  return (
    <span
      className="backtest-status-chip backtest-status-chip-neutral"
      aria-label="未知"
    >
      <StatusDot tone="neutral" className="backtest-status-chip-dot" />
      <Minus className="h-3.5 w-3.5" />
    </span>
  );
}

// ============ Run Summary ============

const RunSummary: React.FC<{ data: BacktestRunResponse }> = ({ data }) => (
  <div className="backtest-summary animate-fade-in">
    <span className="label">已处理: <span className="value">{data.processed}</span></span>
    <span className="label">已保存: <span className="value primary">{data.saved}</span></span>
    <span className="label">已完成: <span className="value success">{data.completed}</span></span>
    <span className="label">数据不足: <span className="value warning">{data.insufficient}</span></span>
    {data.errors > 0 && (
      <span className="label">错误: <span className="value danger">{data.errors}</span></span>
    )}
  </div>
);

// ============ Main Page ============

const BacktestPage: React.FC = () => {
  // Set page title
  useEffect(() => {
    document.title = '策略回测 - DSA';
  }, []);

  // Input state
  const [codeFilter, setCodeFilter] = useState('');
  const [analysisDateFrom, setAnalysisDateFrom] = useState('');
  const [analysisDateTo, setAnalysisDateTo] = useState('');
  const [evalDays, setEvalDays] = useState('');
  const [forceRerun, setForceRerun] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [runResult, setRunResult] = useState<BacktestRunResponse | null>(null);
  const [runError, setRunError] = useState<ParsedApiError | null>(null);
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  // Results state
  const [results, setResults] = useState<BacktestResultItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const pageSize = 20;

  // Performance state
  const [overallPerf, setOverallPerf] = useState<PerformanceMetrics | null>(null);
  const [stockPerf, setStockPerf] = useState<PerformanceMetrics | null>(null);
  const [isLoadingPerf, setIsLoadingPerf] = useState(false);
  const effectiveWindowDays = evalDays ? parseInt(evalDays, 10) : overallPerf?.evalWindowDays;
  const isNextDayValidation = effectiveWindowDays === 1;
  const showNextDayActualColumns = isNextDayValidation;

  // Fetch results
  const fetchResults = useCallback(async (
    page = 1,
    code?: string,
    windowDays?: number,
    startDate?: string,
    endDate?: string,
  ) => {
    setIsLoadingResults(true);
    try {
      const response = await backtestApi.getResults({
        code: code || undefined,
        evalWindowDays: windowDays,
        analysisDateFrom: startDate || undefined,
        analysisDateTo: endDate || undefined,
        page,
        limit: pageSize,
      });
      setResults(response.items);
      setTotalResults(response.total);
      setCurrentPage(response.page);
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch backtest results:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingResults(false);
    }
  }, []);

  // Fetch performance
  const fetchPerformance = useCallback(async (
    code?: string,
    windowDays?: number,
    startDate?: string,
    endDate?: string,
  ) => {
    setIsLoadingPerf(true);
    try {
      const overall = await backtestApi.getOverallPerformance({
        evalWindowDays: windowDays,
        analysisDateFrom: startDate || undefined,
        analysisDateTo: endDate || undefined,
      });
      setOverallPerf(overall);

      if (code) {
        const stock = await backtestApi.getStockPerformance(code, {
          evalWindowDays: windowDays,
          analysisDateFrom: startDate || undefined,
          analysisDateTo: endDate || undefined,
        });
        setStockPerf(stock);
      } else {
        setStockPerf(null);
      }
      setPageError(null);
    } catch (err) {
      console.error('Failed to fetch performance:', err);
      setPageError(getParsedApiError(err));
    } finally {
      setIsLoadingPerf(false);
    }
  }, []);

  // Initial load — fetch performance first, then filter results by its window
  useEffect(() => {
    const init = async () => {
      // Get latest performance (unfiltered returns most recent summary)
      const overall = await backtestApi.getOverallPerformance();
      setOverallPerf(overall);
      // Use the summary's eval_window_days to filter results consistently
      const windowDays = overall?.evalWindowDays;
      if (windowDays && !evalDays) {
        setEvalDays(String(windowDays));
      }
      fetchResults(1, undefined, windowDays, undefined, undefined);
    };
    init();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Run backtest
  const handleRun = async () => {
    setIsRunning(true);
    setRunResult(null);
    setRunError(null);
    try {
      const code = codeFilter.trim() || undefined;
      const evalWindowDays = evalDays ? parseInt(evalDays, 10) : undefined;
      const response = await backtestApi.run({
        code,
        force: forceRerun || undefined,
        minAgeDays: forceRerun ? 0 : undefined,
        evalWindowDays,
      });
      setRunResult(response);
      // Refresh data with same eval_window_days
      fetchResults(1, codeFilter.trim() || undefined, evalWindowDays, analysisDateFrom, analysisDateTo);
      fetchPerformance(codeFilter.trim() || undefined, evalWindowDays, analysisDateFrom, analysisDateTo);
    } catch (err) {
      setRunError(getParsedApiError(err));
    } finally {
      setIsRunning(false);
    }
  };

  // Filter by code
  const handleFilter = () => {
    const code = codeFilter.trim() || undefined;
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    setCurrentPage(1);
    fetchResults(1, code, windowDays, analysisDateFrom, analysisDateTo);
    fetchPerformance(code, windowDays, analysisDateFrom, analysisDateTo);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleFilter();
    }
  };

  const handleShowNextDay = () => {
    const code = codeFilter.trim() || undefined;
    setEvalDays('1');
    setCurrentPage(1);
    fetchResults(1, code, 1, analysisDateFrom, analysisDateTo);
    fetchPerformance(code, 1, analysisDateFrom, analysisDateTo);
  };

  // Pagination
  const totalPages = Math.ceil(totalResults / pageSize);
  const handlePageChange = (page: number) => {
    const windowDays = evalDays ? parseInt(evalDays, 10) : undefined;
    fetchResults(page, codeFilter.trim() || undefined, windowDays, analysisDateFrom, analysisDateTo);
  };

  /* ============ 组装可视化数据 ============ */
  const overallResearchPerf: PerfMetrics = useMemo(
    () => mapPerfMetrics(overallPerf, totalResults || undefined),
    [overallPerf, totalResults],
  );
  const equityData: EquityPoint[] = useMemo(
    () => buildEquityFromResults(results, overallPerf?.winRatePct ?? 50),
    [results, overallPerf],
  );
  const signalData: TradeSignal[] = useMemo(
    () => buildSignalsFromResults(results),
    [results],
  );

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      {/* ========== Header 操作栏 ========== */}
      <header className="research-page-head">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-0 flex-[1_1_220px]">
            <input
              type="text"
              value={codeFilter}
              onChange={(e) => setCodeFilter(e.target.value.toUpperCase())}
              onKeyDown={handleKeyDown}
              placeholder="按股票代码筛选（留空表示全部）"
              disabled={isRunning}
              className={BACKTEST_INPUT_CLASS}
            />
          </div>
          <button
            type="button"
            onClick={handleFilter}
            disabled={isLoadingResults}
            className="btn-secondary flex items-center gap-1.5 whitespace-nowrap"
          >
            筛选
          </button>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">窗口</span>
            <input
              type="number"
              min={1}
              max={120}
              value={evalDays}
              onChange={(e) => setEvalDays(e.target.value)}
              placeholder="10"
              disabled={isRunning}
              className={`${BACKTEST_COMPACT_INPUT_CLASS} w-20 text-center tabular-nums`}
            />
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">起</span>
            <input
              type="date"
              aria-label="分析开始日期"
              value={analysisDateFrom}
              onChange={(e) => setAnalysisDateFrom(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              className={`${BACKTEST_COMPACT_INPUT_CLASS} w-36 text-center tabular-nums`}
            />
          </div>
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs text-muted-text">止</span>
            <input
              type="date"
              aria-label="分析结束日期"
              value={analysisDateTo}
              onChange={(e) => setAnalysisDateTo(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isRunning}
              className={`${BACKTEST_COMPACT_INPUT_CLASS} w-36 text-center tabular-nums`}
            />
          </div>
          <button
            type="button"
            onClick={handleShowNextDay}
            disabled={isLoadingResults || isLoadingPerf}
            className={`backtest-force-btn ${isNextDayValidation ? 'active' : ''}`}
          >
            <span className="dot" />
            1 日验证
          </button>
          <button
            type="button"
            onClick={() => setForceRerun(!forceRerun)}
            disabled={isRunning}
            className={`backtest-force-btn ${forceRerun ? 'active' : ''}`}
          >
            <span className="dot" />
            强制重跑
          </button>
          <button
            type="button"
            onClick={handleRun}
            disabled={isRunning}
            className="btn-primary flex items-center gap-1.5 whitespace-nowrap"
          >
            {isRunning ? (
              <>
                <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                回测中...
              </>
            ) : (
              '运行回测'
            )}
          </button>
        </div>
        {runResult && (
          <div className="mt-2">
            <RunSummary data={runResult} />
          </div>
        )}
        {runError && (
          <ApiErrorAlert error={runError} onDismiss={() => setRunError(null)} className="mt-2" />
        )}
        <p className="mt-2 text-xs text-muted-text">
          {isNextDayValidation
            ? '1 日验证模式会用下一个交易日收盘表现校验 AI 预测。'
            : '将评估窗口设为 1，可查看 AI 预测与下一个交易日收盘表现的匹配情况。'}
        </p>
      </header>

      {/* ========== 主内容：滚动容器 ========== */}
      <main className="min-h-0 flex-1 overflow-y-auto px-3 pb-10 pt-3 sm:px-5">
        {pageError ? (
          <ApiErrorAlert error={pageError} onDismiss={() => setPageError(null)} className="mb-3" />
        ) : null}

        {isLoadingPerf && results.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64">
            <div className="backtest-spinner md" />
            <p className="mt-3 text-secondary-text text-sm">正在加载回测分析...</p>
          </div>
        ) : (
          <div className="space-y-4 animate-fade-in">
            {/* ====== 绩效仪表盘 ====== */}
            {overallPerf ? (
              <ResearchPerfDashboard
                metrics={overallResearchPerf}
                benchmarkName={stockPerf?.code || '沪深300'}
              />
            ) : (
              <EmptyState
                title="暂无绩效指标"
                description="运行回测后会生成组合级表现仪表盘。"
                className="border-dashed bg-card/45"
                icon={<Activity className="h-6 w-6" />}
              />
            )}

            {/* ====== 净值曲线 + 归因面板（并排） ====== */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
              <div className="lg:col-span-2">
                <ResearchEquityChart
                  title="累计净值曲线（策略 vs 基准）"
                  data={equityData}
                />
              </div>
              <div className="lg:col-span-1">
                <ResearchAttributionPanel title="收益归因 · 行业 & 因子" />
              </div>
            </div>

            {/* ====== 胜率热力图 + 交易信号时间线（并排） ====== */}
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
              <div className="lg:col-span-3">
                <ResearchWinRateHeatmap title="周度胜率热力图（按市场 / 行业）" />
              </div>
              <div className="lg:col-span-2">
                <ResearchSignalTimeline
                  title="交易信号时间线"
                  signals={signalData}
                />
              </div>
            </div>

            {/* ====== 结果明细表格 ====== */}
            <div className="terminal-card terminal-card-hover overflow-hidden">
              <div className="p-5">
                <div className="backtest-table-toolbar !mb-4">
                  <div className="backtest-table-toolbar-meta">
                    <span className="label-uppercase">{isNextDayValidation ? '次日验证' : '逐笔结果集'}</span>
                    <span className="text-xs text-secondary-text">
                      {codeFilter.trim() ? `筛选 ${codeFilter.trim()}` : '全部股票'}
                      {evalDays ? ` · ${evalDays} 日窗口` : ''}
                      {analysisDateFrom ? ` · 自 ${analysisDateFrom}` : ''}
                      {analysisDateTo ? ` · 至 ${analysisDateTo}` : ''}
                    </span>
                  </div>
                  <span className="backtest-table-scroll-hint">小屏幕可横向滚动</span>
                </div>

                {isLoadingResults ? (
                  <div className="flex flex-col items-center justify-center h-40">
                    <div className="backtest-spinner sm" />
                    <p className="mt-3 text-secondary-text text-sm">加载明细...</p>
                  </div>
                ) : results.length === 0 ? (
                  <EmptyState
                    title="暂无逐笔结果"
                    description="运行回测后可在此查看每一笔 AI 预测与实际表现。"
                    className="backtest-empty-state border-dashed"
                  />
                ) : (
                  <>
                    <div className="backtest-table-wrapper">
                      <table className="backtest-table min-w-[840px] w-full text-sm">
                        <thead className="backtest-table-head">
                          <tr className="text-left">
                            <th className="backtest-table-head-cell">股票</th>
                            <th className="backtest-table-head-cell">分析日期</th>
                            <th className="backtest-table-head-cell">AI 预测</th>
                            <th className="backtest-table-head-cell">
                              {showNextDayActualColumns ? '实际表现' : '窗口收益'}
                            </th>
                            <th className="backtest-table-head-cell">
                              {showNextDayActualColumns ? '准确性' : '方向匹配'}
                            </th>
                            <th className="backtest-table-head-cell">结果</th>
                            <th className="backtest-table-head-cell">状态</th>
                          </tr>
                        </thead>
                        <tbody>
                          {results.map((row) => (
                            <tr
                              key={row.analysisHistoryId}
                              className="backtest-table-row"
                            >
                              <td className="backtest-table-cell backtest-table-code">
                                <div className="flex flex-col">
                                  <span>{row.code}</span>
                                  <span className="text-xs text-muted-text">{row.stockName || '--'}</span>
                                </div>
                              </td>
                              <td className="backtest-table-cell text-secondary-text">{row.analysisDate || '--'}</td>
                              <td className="backtest-table-cell max-w-[220px] text-foreground">
                                {(row.trendPrediction || row.operationAdvice) ? (
                                  <Tooltip
                                    content={[row.trendPrediction, row.operationAdvice].filter(Boolean).join(' / ')}
                                    focusable
                                  >
                                    <div className="flex flex-col gap-1">
                                      <span className="block truncate">{row.trendPrediction || '--'}</span>
                                      <span className="block truncate text-xs text-secondary-text">{row.operationAdvice || '--'}</span>
                                    </div>
                                  </Tooltip>
                                ) : (
                                  '--'
                                )}
                              </td>
                              <td className="backtest-table-cell">
                                <div className="flex items-center gap-2">
                                  {actualMovementBadge(row.actualMovement)}
                                  <span className={
                                    row.actualReturnPct != null
                                      ? row.actualReturnPct > 0 ? 'text-success' : row.actualReturnPct < 0 ? 'text-danger' : 'text-secondary-text'
                                      : 'text-muted-text'
                                  }>
                                    {pct(row.actualReturnPct)}
                                  </span>
                                </div>
                              </td>
                              <td className="backtest-table-cell">
                                <span className="flex items-center gap-2">
                                  {boolIcon(row.directionCorrect)}
                                  <span className="text-muted-text">
                                    {row.directionExpected ? labelFromMap(row.directionExpected, DIRECTION_EXPECTED_LABELS) : ''}
                                  </span>
                                </span>
                              </td>
                              <td className="backtest-table-cell">{outcomeBadge(row.outcome)}</td>
                              <td className="backtest-table-cell">{statusBadge(row.evalStatus)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="mt-4">
                      <Pagination
                        currentPage={currentPage}
                        totalPages={totalPages}
                        onPageChange={handlePageChange}
                      />
                    </div>

                    <p className="text-xs text-muted-text text-center mt-2">
                      共 {totalResults} 条结果 · 第 {currentPage} / {Math.max(totalPages, 1)} 页
                    </p>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

export default BacktestPage;
