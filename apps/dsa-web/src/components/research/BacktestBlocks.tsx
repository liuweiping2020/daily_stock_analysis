import React from 'react';
import {
  BarChart3,
  TrendingUp,
  Target,
  Layers,
  BadgeDollarSign,
  ShieldAlert,
  LineChart as LineChartIcon,
  Activity,
  Zap,
} from 'lucide-react';

export type PerfMetrics = {
  totalReturn: number;    // %
  annualReturn: number;   // %
  excessReturn: number;   // % vs 基准
  maxDrawdown: number;    // %
  sharpe: number;
  sortino: number;
  calmar: number;
  winRate: number;        // %
  avgWin: number;         // %
  avgLoss: number;        // %
  profitFactor: number;
  trades: number;
  alpha: number;
  beta: number;
  vol: number;            // 波动率%
};

export const defaultPerfMetrics: PerfMetrics = {
  totalReturn: 42.8,
  annualReturn: 28.4,
  excessReturn: 19.6,
  maxDrawdown: -11.2,
  sharpe: 1.84,
  sortino: 2.36,
  calmar: 2.54,
  winRate: 64,
  avgWin: 4.6,
  avgLoss: -2.1,
  profitFactor: 2.1,
  trades: 186,
  alpha: 0.18,
  beta: 0.78,
  vol: 16.8,
};

/* ========== 绩效仪表盘（终端质感） ========== */
export const ResearchPerfDashboard: React.FC<{
  metrics?: PerfMetrics;
  benchmarkName?: string;
  className?: string;
}> = ({ metrics = defaultPerfMetrics, benchmarkName = '沪深300', className = '' }) => {
  const cells: Array<{
    label: string;
    value: string;
    accent?: 'primary' | 'success' | 'danger' | 'warning' | 'purple';
  }> = [
    { label: '累计收益率', value: `${metrics.totalReturn.toFixed(2)}%`, accent: 'success' },
    { label: '年化收益率', value: `${metrics.annualReturn.toFixed(2)}%`, accent: 'primary' },
    { label: `超额(${benchmarkName})`, value: `+${metrics.excessReturn.toFixed(2)}%`, accent: 'purple' },
    { label: '最大回撤',   value: `${metrics.maxDrawdown.toFixed(2)}%`, accent: 'danger' },
    { label: '夏普比率',   value: metrics.sharpe.toFixed(2), accent: 'primary' },
    { label: '索提诺比率', value: metrics.sortino.toFixed(2), accent: 'success' },
    { label: '卡玛比率',   value: metrics.calmar.toFixed(2), accent: 'purple' },
    { label: '胜率',       value: `${metrics.winRate}%`, accent: 'success' },
    { label: '平均盈利',   value: `+${metrics.avgWin.toFixed(2)}%`, accent: 'success' },
    { label: '平均亏损',   value: `${metrics.avgLoss.toFixed(2)}%`, accent: 'danger' },
    { label: '盈亏比',     value: metrics.profitFactor.toFixed(2), accent: 'primary' },
    { label: '交易次数',   value: String(metrics.trades), accent: 'warning' },
    { label: 'Alpha',      value: metrics.alpha.toFixed(2), accent: 'purple' },
    { label: 'Beta',       value: metrics.beta.toFixed(2), accent: 'warning' },
    { label: '年化波动率', value: `${metrics.vol.toFixed(2)}%`, accent: 'danger' },
    { label: '评价',       value: metrics.sharpe >= 1.5 ? '优秀' : metrics.sharpe >= 1 ? '良好' : '待优化', accent: metrics.sharpe >= 1.5 ? 'success' : metrics.sharpe >= 1 ? 'primary' : 'warning' },
  ];

  return (
    <div className={`research-performance-card ${className}`}>
      <div className="research-performance-inner p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="label-uppercase text-primary/90">
              <BarChart3 className="h-3.5 w-3.5" />
              Performance Dashboard
            </div>
            <h2 className="mt-2 text-[20px] font-semibold">
              策略绩效 <span className="title-gradient">归因总览</span>
            </h2>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="badge badge-cyan">区间：1Y</span>
            <span className="badge badge-purple">基准：{benchmarkName}</span>
            <span className="badge badge-success">资金曲线</span>
          </div>
        </div>

        {/* 头部 4 个强调指标卡 */}
        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <HighlightCell
            icon={<BadgeDollarSign className="h-4 w-4" />}
            label="累计收益"
            value={`${metrics.totalReturn > 0 ? '+' : ''}${metrics.totalReturn.toFixed(2)}%`}
            hint="近 252 交易日"
            tone="success"
          />
          <HighlightCell
            icon={<Activity className="h-4 w-4" />}
            label="夏普比率"
            value={metrics.sharpe.toFixed(2)}
            hint="无风险利率 2.5%"
            tone="primary"
          />
          <HighlightCell
            icon={<ShieldAlert className="h-4 w-4" />}
            label="最大回撤"
            value={`${metrics.maxDrawdown.toFixed(2)}%`}
            hint="控制在 15% 以内"
            tone="danger"
          />
          <HighlightCell
            icon={<Layers className="h-4 w-4" />}
            label="超额收益"
            value={`+${metrics.excessReturn.toFixed(2)}%`}
            hint={`相对 ${benchmarkName}`}
            tone="purple"
          />
        </div>

        {/* 详细指标网格 */}
        <div className="mt-5 research-perf-grid sm:grid-cols-4">
          {cells.map((c, idx) => (
            <div key={idx} className="research-perf-cell">
              <div className="research-perf-label">{c.label}</div>
              <div className="research-perf-value" data-accent={c.accent}>{c.value}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const HighlightCell: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
  tone: 'success' | 'primary' | 'danger' | 'purple';
}> = ({ icon, label, value, hint, tone }) => {
  const border =
    tone === 'success' ? 'hsl(149 100% 38% / 0.26)' :
    tone === 'danger'  ? 'hsl(0 86% 58% / 0.28)' :
    tone === 'purple'  ? 'hsl(245 85% 65% / 0.28)' : 'hsl(var(--primary) / 0.3)';
  const txt =
    tone === 'success' ? 'text-success' :
    tone === 'danger'  ? 'text-danger' :
    tone === 'purple'  ? 'text-purple' : 'text-primary';
  const bg =
    tone === 'success' ? 'hsl(149 100% 38% / 0.1)' :
    tone === 'danger'  ? 'hsl(0 86% 58% / 0.1)' :
    tone === 'purple'  ? 'hsl(245 85% 65% / 0.1)' : 'hsl(var(--primary) / 0.12)';

  return (
    <div className="relative overflow-hidden rounded-[0.95rem] border p-4"
         style={{ borderColor: border, background: `linear-gradient(180deg, ${bg}, transparent 60%), hsl(var(--card)/0.94)` }}>
      <div className="flex items-center justify-between">
        <span className="label-uppercase text-secondary-text/90">{label}</span>
        <div className={`${txt} flex h-8 w-8 items-center justify-center rounded-lg border`}
             style={{ borderColor: border, background: `${bg}`, color:
               tone === 'success' ? 'hsl(149 100% 38%)' :
               tone === 'danger'  ? 'hsl(0 86% 58%)' :
               tone === 'purple'  ? 'hsl(245 85% 65%)' : 'hsl(var(--primary))'
             }}>
          {icon}
        </div>
      </div>
      <div className={`mt-2 text-[24px] font-bold font-mono leading-none ${txt}`}>
        {value}
      </div>
      {hint ? <div className="mt-1.5 text-[11.5px] text-secondary-text/95">{hint}</div> : null}
    </div>
  );
};

/* ========== 净值曲线：终端极简 SVG ========== */
export type EquityPoint = { x: number; strategy: number; benchmark: number; };

export const ResearchEquityChart: React.FC<{
  title?: string;
  data?: EquityPoint[];
  className?: string;
}> = ({
  title = '累计净值曲线（策略 vs 基准）',
  data = generateDemoEquity(120),
  className = '',
}) => {
  const w = 800;
  const h = 280;
  const padL = 44, padR = 16, padT = 18, padB = 28;
  const maxX = Math.max(...data.map((d) => d.x));
  const maxY = Math.max(...data.flatMap((d) => [d.strategy, d.benchmark])) * 1.05;
  const minY = Math.min(...data.flatMap((d) => [d.strategy, d.benchmark])) * 0.98;
  const xOf = (x: number) => padL + ((x - 0) / maxX) * (w - padL - padR);
  const yOf = (y: number) => padT + (1 - (y - minY) / (maxY - minY)) * (h - padT - padB);
  const toPath = (key: 'strategy' | 'benchmark') =>
    data.map((d, i) => `${i === 0 ? 'M' : 'L'}${xOf(d.x).toFixed(2)},${yOf(d[key]).toFixed(2)}`).join(' ');

  const yTicks = 5;
  const ticks = Array.from({ length: yTicks + 1 }, (_, i) => minY + ((maxY - minY) * i) / yTicks);
  const xTickLabels = ['T0', '30D', '60D', '90D', '120D', '1Y'];

  return (
    <div className={`terminal-card terminal-card-hover ${className}`}>
      <div className="relative z-10 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="label-uppercase text-purple/90">
              <LineChartIcon className="h-3.5 w-3.5" />
              Equity Curve
            </div>
            <h3 className="mt-2 text-[18px] font-semibold">{title}</h3>
          </div>
          <div className="flex items-center gap-4 text-[12px]">
            <LegendDot color="hsl(var(--primary))" label="策略净值" />
            <LegendDot color="hsl(var(--muted-text))" label="基准（沪深300）" dashed />
            <LegendDot color="hsl(0 86% 58%)" label="回撤参考" />
          </div>
        </div>

        <div className="mt-4 rounded-[1rem] border border-[hsl(var(--foreground)/0.06)] bg-[hsl(var(--foreground)/0.015)] p-3">
          <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-[280px]">
            {/* 背景网格 */}
            {ticks.map((t, i) => {
              const y = yOf(t);
              return (
                <g key={i}>
                  <line x1={padL} x2={w - padR} y1={y} y2={y}
                        stroke="hsl(var(--foreground) / 0.07)" strokeDasharray="4 4" />
                  <text x={padL - 8} y={y + 3.5}
                        textAnchor="end"
                        className="fill-secondary-text/90" fontSize="10" fontFamily="ui-monospace,Menlo,monospace">
                    {t.toFixed(2)}
                  </text>
                </g>
              );
            })}
            {/* x 轴刻度 */}
            {xTickLabels.map((lbl, i) => {
              const x = padL + ((w - padL - padR) * i) / (xTickLabels.length - 1);
              return (
                <text key={lbl} x={x} y={h - 10}
                      textAnchor="middle"
                      className="fill-secondary-text/90" fontSize="10" fontFamily="ui-monospace,Menlo,monospace">
                  {lbl}
                </text>
              );
            })}
            {/* 净值 fill（策略） */}
            <defs>
              <linearGradient id="stratFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%"  stopColor="hsl(var(--primary))" stopOpacity="0.28" />
                <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="benchFill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%"  stopColor="hsl(var(--muted-text))" stopOpacity="0.14" />
                <stop offset="100%" stopColor="hsl(var(--muted-text))" stopOpacity="0" />
              </linearGradient>
            </defs>
            <path d={`${toPath('strategy')} L${xOf(maxX)},${yOf(minY)} L${xOf(0)},${yOf(minY)} Z`}
                  fill="url(#stratFill)" opacity={0.9} />
            <path d={`${toPath('benchmark')} L${xOf(maxX)},${yOf(minY)} L${xOf(0)},${yOf(minY)} Z`}
                  fill="url(#benchFill)" opacity={0.6} />
            {/* 线 */}
            <path d={toPath('benchmark')}
                  stroke="hsl(var(--muted-text))" strokeWidth="2" fill="none"
                  strokeDasharray="6 6" />
            <path d={toPath('strategy')}
                  stroke="hsl(var(--primary))" strokeWidth="2.6" fill="none"
                  strokeLinecap="round" strokeLinejoin="round"
                  style={{ filter: 'drop-shadow(0 0 6px hsl(var(--primary)/0.45))' }} />
            {/* 最大回撤锚点示意：最低点 & 起点 */}
            {(() => {
              let peak = -Infinity, maxDD = Infinity, mddIdx = 0, peakIdx = 0;
              data.forEach((d, i) => {
                if (d.strategy > peak) { peak = d.strategy; peakIdx = i; }
                const dd = d.strategy - peak;
                if (dd < maxDD) { maxDD = dd; mddIdx = i; }
              });
              const p = data[peakIdx], t = data[mddIdx];
              return (
                <>
                  <line x1={xOf(p.x)} y1={yOf(p.strategy)} x2={xOf(t.x)} y2={yOf(t.strategy)}
                        stroke="hsl(0 86% 58%)" strokeWidth="1.8" strokeDasharray="4 4" />
                  <circle cx={xOf(p.x)} cy={yOf(p.strategy)} r="5"
                          fill="#fff" stroke="hsl(0 86% 58%)" strokeWidth="2" />
                  <circle cx={xOf(t.x)} cy={yOf(t.strategy)} r="5"
                          fill="#fff" stroke="hsl(0 86% 58%)" strokeWidth="2" />
                  <text x={xOf(t.x)} y={yOf(t.strategy) - 10}
                        textAnchor="middle" fontSize="10" className="fill-danger font-mono font-semibold">
                    MDD {(maxDD).toFixed(2)}
                  </text>
                </>
              );
            })()}
          </svg>
        </div>
      </div>
    </div>
  );
};

const LegendDot: React.FC<{ color: string; label: string; dashed?: boolean }> = ({ color, label, dashed }) => (
  <div className="inline-flex items-center gap-2 text-secondary-text/95">
    <span
      className="inline-block h-2.5 w-6 rounded-full"
      style={{
        background: dashed
          ? `repeating-linear-gradient(90deg, ${color} 0 4px, transparent 4px 8px)`
          : color,
      }}
    />
    <span className="font-semibold">{label}</span>
  </div>
);

function generateDemoEquity(n: number): EquityPoint[] {
  const arr: EquityPoint[] = [];
  let s = 1, b = 1;
  const seed = 42;
  const rnd = (i: number) => {
    const x = Math.sin(i * 9301 + seed) * 10000;
    return x - Math.floor(x);
  };
  for (let i = 0; i < n; i++) {
    // 策略：带一点 drift 与回撤
    const drift = 0.0025;
    const vol = 0.013;
    const shock = (rnd(i) - 0.5) * vol * 2;
    s = s * (1 + drift + shock);
    // 基准：更低 drift，更高相关
    b = b * (1 + 0.0006 + (rnd(i + 7) - 0.5) * 0.014);
    arr.push({ x: i, strategy: Number(s.toFixed(4)), benchmark: Number(b.toFixed(4)) });
  }
  return arr;
}

/* ========== 交易信号时间条 ========== */
export type TradeSignal = {
  id: string;
  day: number;     // 0-100（百分比位置）
  signal: 'buy' | 'sell' | 'stop';
  label: string;   // 如 2025-02-12
  note?: string;
};

export const ResearchSignalTimeline: React.FC<{
  signals?: TradeSignal[];
  title?: string;
  className?: string;
}> = ({
  signals = [
    { id: 's1', day: 8,  signal: 'buy',  label: '2025-01-10', note: '首次建仓 60%' },
    { id: 's2', day: 22, signal: 'buy',  label: '2025-02-05', note: '加仓至 85%' },
    { id: 's3', day: 34, signal: 'stop', label: '2025-02-24', note: '止损保护触发' },
    { id: 's4', day: 48, signal: 'buy',  label: '2025-03-18', note: '趋势重启介入' },
    { id: 's5', day: 62, signal: 'sell', label: '2025-04-09', note: '部分止盈 40%' },
    { id: 's6', day: 75, signal: 'sell', label: '2025-04-29', note: '止盈减持至 25%' },
    { id: 's7', day: 90, signal: 'buy',  label: '2025-05-19', note: '回踩均线加仓' },
  ],
  title = '交易信号时间线',
  className = '',
}) => {
  return (
    <div className={`glass-card ${className}`}>
      <div className="relative z-10 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="label-uppercase text-success/90">
              <Zap className="h-3.5 w-3.5" />
              Signals
            </div>
            <h3 className="mt-2 text-[18px] font-semibold">{title}</h3>
          </div>
          <div className="flex items-center gap-3 text-[11.5px]">
            <LegendDot color="hsl(149 100% 38%)" label="买入" />
            <LegendDot color="hsl(0 86% 58%)"    label="卖出" />
            <LegendDot color="hsl(37 92% 50%)"    label="止损" />
          </div>
        </div>

        <div className="mt-5 research-signal-track">
          {signals.map((s) => (
            <div
              key={s.id}
              className="research-signal-dot group"
              data-signal={s.signal}
              style={{ left: `${Math.max(2, Math.min(98, s.day))}%` }}
              title={`${s.label} · ${s.note ?? s.signal}`}
            >
              <div className="pointer-events-none absolute bottom-[120%] left-1/2 z-20 hidden -translate-x-1/2 whitespace-nowrap rounded-lg border border-[hsl(var(--foreground)/0.1)] bg-[hsl(var(--card)/0.98)] px-2 py-1 text-[11px] shadow-lg backdrop-blur group-hover:block">
                <div className="font-semibold">{s.label}</div>
                <div className="text-secondary-text/95">{s.note ?? s.signal}</div>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-4 grid grid-cols-3 gap-3 text-[12px] sm:grid-cols-7">
          {['T0', '30D', '60D', '90D', '120D', '150D', '1Y'].map((t) => (
            <div key={t} className="rounded-lg border border-[hsl(var(--foreground)/0.06)] bg-[hsl(var(--foreground)/0.02)] px-2 py-1 text-center text-secondary-text/95 font-mono">
              {t}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

/* ========== 胜率热力图（按周×标的） ========== */
export const ResearchWinRateHeatmap: React.FC<{
  title?: string;
  weekCount?: number;       // 周数
  className?: string;
}> = ({ title = '周度胜率热力图', weekCount = 28, className = '' }) => {
  const rows = [
    { key: 'cn', name: 'A 股' },
    { key: 'hk', name: '港股' },
    { key: 'us', name: '美股' },
    { key: 'sec', label: true, name: '—' } as const,
    { key: 'tech', name: '科技' },
    { key: 'consume', name: '消费' },
    { key: 'fin', name: '金融' },
  ] as const;
  type RowName = typeof rows[number]['key'];

  // 伪数据生成：稳定且视觉层次分明
  const cell = (r: RowName, i: number): { pct: number; tone: 'good' | 'mid' | 'bad' | 'neutral' } => {
    const base =
      r === 'cn' ? 64 : r === 'hk' ? 58 : r === 'us' ? 60 :
      r === 'tech' ? 66 : r === 'consume' ? 62 : r === 'fin' ? 55 : 50;
    const jitter = (Math.sin(i * 17 + String(r).length * 13) * 0.5 + 0.5) * 32 - 16;
    const pct = Math.max(0, Math.min(100, base + jitter));
    const tone: 'good' | 'mid' | 'bad' | 'neutral' =
      pct >= 62 ? 'good' : pct >= 50 ? 'mid' : pct >= 38 ? 'bad' : 'neutral';
    return { pct, tone };
  };

  const bg = (t: ReturnType<typeof cell>['tone'], pct: number): string => {
    if (t === 'good') return `hsl(149 86% ${38 - pct * 0.12}% / ${0.28 + pct * 0.005})`;
    if (t === 'mid')  return `hsl(192 100% ${48 - pct * 0.1}%  / ${0.22 + pct * 0.003})`;
    if (t === 'bad')  return `hsl(37 92% ${44 - pct * 0.1}%  / ${0.22 + (100 - pct) * 0.002})`;
    return 'hsl(0 86% 58% / 0.28)';
  };

  return (
    <div className={`glass-card ${className}`}>
      <div className="relative z-10 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="label-uppercase text-warning/90">
              <Target className="h-3.5 w-3.5" />
              Win Rate Heatmap
            </div>
            <h3 className="mt-2 text-[18px] font-semibold">{title}</h3>
          </div>
          <div className="flex items-center gap-2 text-[11.5px] text-secondary-text/95">
            <span>Loss</span>
            <div className="flex items-center">
              {['bad', 'mid', 'good'].map((t) => (
                <span key={t}
                      className="inline-block h-3.5 w-7 first:rounded-l-md last:rounded-r-md"
                      style={{
                        background:
                          t === 'good' ? 'hsl(149 86% 38%)' :
                          t === 'mid'  ? 'hsl(192 100% 48%)' : 'hsl(37 92% 50%)',
                      }}
                />
              ))}
            </div>
            <span>Win</span>
          </div>
        </div>

        <div className="mt-4 overflow-x-auto">
          <div className="min-w-[960px] space-y-2">
            {rows.map((r) => {
              if (r.key === 'sec') {
                return (
                  <div key={r.key} className="mt-4 border-t border-[hsl(var(--foreground)/0.06)] pt-4" />
                );
              }
              return (
                <div key={r.key} className="flex items-center gap-3">
                  <div className="w-[70px] shrink-0 text-[12px] font-semibold text-secondary-text/95">
                    {r.name}
                  </div>
                  <div className="research-heatmap flex-1" style={{ gridTemplateColumns: `repeat(${weekCount}, minmax(0,1fr))` }}>
                    {Array.from({ length: weekCount }).map((_, i) => {
                      const v = cell(r.key as RowName, i);
                      return (
                        <div
                          key={i}
                          className="research-heatmap-cell"
                          style={{ background: bg(v.tone, v.pct), color: v.pct > 60 ? '#fff' : 'hsl(222 47% 12%)' }}
                          title={`${r.name} · 第${i + 1}周 · 胜率 ${v.pct.toFixed(0)}%`}
                        >
                          {i % 4 === 0 ? v.pct.toFixed(0) : ''}
                        </div>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4 text-[12.5px]">
          <AttrCell label="平均周胜率" value="61.4%" tone="primary" />
          <AttrCell label="连续盈利周" value="6"    tone="success" />
          <AttrCell label="最大连亏周" value="2"    tone="danger" />
          <AttrCell label="周收益偏度" value="+0.42" tone="purple" />
        </div>
      </div>
    </div>
  );
};

const AttrCell: React.FC<{ label: string; value: string; tone: 'primary' | 'success' | 'danger' | 'purple' }> = ({ label, value, tone }) => {
  const cls =
    tone === 'primary' ? 'text-primary' :
    tone === 'success' ? 'text-success' :
    tone === 'danger'  ? 'text-danger' : 'text-purple';
  return (
    <div className="rounded-[0.8rem] border border-[hsl(var(--foreground)/0.06)] bg-[hsl(var(--foreground)/0.02)] px-3 py-2">
      <div className="label-xs">{label}</div>
      <div className={`mt-0.5 text-[16px] font-bold font-mono leading-none ${cls}`}>{value}</div>
    </div>
  );
};

/* ========== 回测归因：行业/因子 贡献柱状图（极简 SVG） ========== */
export type AttributionRow = { key: string; name: string; pct: number; tone?: 'primary' | 'success' | 'danger' | 'warning' | 'purple'; };

export const ResearchAttributionPanel: React.FC<{
  title?: string;
  rows?: AttributionRow[];
  className?: string;
}> = ({
  title = '收益归因 · 行业 & 因子',
  rows = [
    { key: 'a',  name: '白酒',         pct: 38, tone: 'success' },
    { key: 'b',  name: '新能源电池',   pct: 26, tone: 'primary' },
    { key: 'c',  name: '互联网平台',   pct: 19, tone: 'purple'  },
    { key: 'd',  name: '银行保险',     pct: 10, tone: 'warning' },
    { key: 'e',  name: '医药生物',     pct: -3, tone: 'danger'  },
    { key: 'f',  name: '地产链',       pct: -8, tone: 'danger'  },
    { key: 'g',  name: '因子动量',     pct: 15, tone: 'primary' },
    { key: 'h',  name: '因子价值',     pct: 9,  tone: 'success' },
    { key: 'i',  name: '因子质量',     pct: 5,  tone: 'warning' },
    { key: 'j',  name: '因子残差',     pct: -2, tone: 'danger'  },
  ],
  className = '',
}) => {
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.pct)), 1);
  return (
    <div className={`glass-card ${className}`}>
      <div className="relative z-10 p-5">
        <div>
          <div className="label-uppercase text-purple/90">
            <TrendingUp className="h-3.5 w-3.5" />
            Attribution
          </div>
          <h3 className="mt-2 text-[18px] font-semibold">{title}</h3>
        </div>

        <div className="mt-4 space-y-2.5">
          {rows.map((r) => {
            const color =
              r.tone === 'success' ? 'hsl(149 100% 38%)' :
              r.tone === 'danger'  ? 'hsl(0 86% 58%)' :
              r.tone === 'warning' ? 'hsl(37 92% 50%)' :
              r.tone === 'purple'  ? 'hsl(245 85% 65%)' : 'hsl(var(--primary))';
            const w = (Math.abs(r.pct) / maxAbs) * 100;
            const right = r.pct >= 0;
            return (
              <div key={r.key} className="flex items-center gap-3">
                <div className="w-[86px] shrink-0 text-[12.5px] font-semibold text-secondary-text/95">{r.name}</div>
                <div className="relative h-7 flex-1 overflow-hidden rounded-lg bg-[hsl(var(--foreground)/0.03)] border border-[hsl(var(--foreground)/0.05)]">
                  <div
                    className="absolute top-0 bottom-0 rounded-[6px]"
                    style={{
                      width: `${Math.max(2, w * 0.5)}%`,
                      background: `linear-gradient(90deg, ${color}26, ${color}cc)`,
                      ...(right ? { left: '50%' } : { right: '50%', transform: 'scaleX(-1)' }),
                      boxShadow: `0 0 0 1px ${color}22 inset, 0 0 10px ${color}44`,
                    }}
                  />
                  {/* 中线 */}
                  <div className="absolute inset-y-0 left-1/2 w-px bg-[hsl(var(--foreground)/0.08)]" />
                </div>
                <div className="w-[60px] shrink-0 text-right font-mono text-[12px] font-bold" style={{ color }}>
                  {r.pct > 0 ? '+' : ''}{r.pct}%
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
