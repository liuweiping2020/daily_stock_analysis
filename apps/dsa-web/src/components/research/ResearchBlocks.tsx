import React from 'react';
import {
  TrendingUp,
  TrendingDown,
  Minus as DashIcon,
  Activity,
  TrendingUp as TrendingUpIcon,
  Flame,
  Target,
  Scroll,
  Sparkles,
  Clock,
  Shield,
  Rocket,
  Coins,
  Layers,
  Briefcase,
  CircleCheckBig,
  CircleAlert,
  Loader2,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';

export type MarketIndex = {
  code: string;
  name: string;
  market: 'A股' | '港股' | '美股';
  price: number;
  change: number;        // 点数变化
  changePct: number;     // 百分比变化
  turnover?: string;     // 成交额（人读）
  tone?: 'default' | 'gold' | 'success' | 'danger' | 'purple';
};

export const defaultMarketIndices: MarketIndex[] = [
  { code: '000001', name: '上证指数', market: 'A股', price: 3287.45, change: 42.83, changePct: 1.32, turnover: '5428亿', tone: 'gold' },
  { code: '399001', name: '深证成指', market: 'A股', price: 10234.18, change: 118.45, changePct: 1.17, turnover: '4218亿', tone: 'success' },
  { code: '399006', name: '创业板指', market: 'A股', price: 2045.73, change: 32.16, changePct: 1.60, turnover: '2156亿', tone: 'success' },
  { code: '000016', name: '上证50',   market: 'A股', price: 2652.88, change: -12.44, changePct: -0.47, turnover: '1204亿', tone: 'danger' },
  { code: 'HSI',    name: '恒生指数', market: '港股', price: 19824.33, change: 512.88, changePct: 2.65, turnover: '1685亿', tone: 'purple' },
  { code: 'HSCEI',  name: '国企指数', market: '港股', price: 6788.12, change: 134.55, changePct: 2.02, turnover: '952亿' },
  { code: 'SPX',    name: '标普500',  market: '美股', price: 5420.66, change: 55.32, changePct: 1.03, tone: 'gold' },
  { code: 'NDX',    name: '纳斯达克', market: '美股', price: 17985.24, change: 236.17, changePct: 1.33, tone: 'success' },
];

export type SentimentLevel = 'greed' | 'neutral' | 'fear';
export const getSentimentLevel = (score: number): SentimentLevel => {
  if (score >= 66) return 'greed';
  if (score >= 34) return 'neutral';
  return 'fear';
};
export const sentimentCn = (level: SentimentLevel): string =>
  level === 'greed' ? '贪婪' : level === 'fear' ? '恐惧' : '中性';

/* ========== 顶部KPI矩阵 ========== */
const KPICard: React.FC<{
  index: MarketIndex;
  className?: string;
  style?: React.CSSProperties;
}> = ({ index, className = '', style }) => {
  const delta = index.change;
  const sign: 'up' | 'down' | 'flat' =
    delta > 1e-6 ? 'up' : delta < -1e-6 ? 'down' : 'flat';
  const Arrow = sign === 'up' ? ArrowUpRight : sign === 'down' ? ArrowDownRight : DashIcon;
  const signLabel =
    sign === 'up' ? '+' : sign === 'down' ? '-' : '';

  return (
    <div className={`research-kpi-card animate-float-in ${className}`} data-tone={index.tone} style={style}>
      <div className="relative z-10 p-4">
        <div className="flex items-center justify-between">
          <span className="research-kpi-label">{index.market} · {index.code}</span>
          <span className="text-[11px] font-medium tracking-wide text-secondary-text/90">T+0</span>
        </div>
        <div className="mt-3 flex items-end justify-between gap-2">
          <div>
            <div className="research-kpi-value" style={{ fontSize: 24 }}>
              {index.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
            <div className="mt-2 text-[12px] font-semibold text-secondary-text/90">
              {index.name}
            </div>
          </div>
          <div className="research-kpi-delta" data-sign={sign}>
            <Arrow className="h-3.5 w-3.5" />
            <span>
              {signLabel}{Math.abs(index.change).toFixed(2)} · {signLabel}{Math.abs(index.changePct).toFixed(2)}%
            </span>
          </div>
        </div>
        {index.turnover ? (
          <div className="mt-3 flex items-center justify-between pt-2 border-t border-[hsl(var(--foreground)/0.06)]">
            <span className="text-[11px] text-secondary-text/90">成交额</span>
            <span className="text-[12px] font-semibold text-foreground font-mono">{index.turnover}</span>
          </div>
        ) : null}
      </div>
    </div>
  );
};

export const ResearchKPIMatrix: React.FC<{
  indices?: MarketIndex[];
  className?: string;
}> = ({ indices = defaultMarketIndices, className = '' }) => {
  return (
    <section className={`${className}`}>
      <div className="mb-4 flex items-end justify-between">
        <div>
          <div className="label-uppercase text-primary/90">
            <Activity className="h-3.5 w-3.5" />
            Market Matrix
          </div>
          <h2 className="mt-2 text-[22px] font-semibold leading-tight">
            大盘指数 <span className="title-gradient">实时驾驶舱</span>
          </h2>
        </div>
        <div className="hidden items-center gap-2 sm:flex">
          <span className="badge badge-cyan">A 股</span>
          <span className="badge badge-purple">港股</span>
          <span className="badge badge-success">美股</span>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {indices.map((it, idx) => (
          <KPICard key={it.code} index={it} style={{ animationDelay: `${idx * 40}ms` } as React.CSSProperties} />
        ))}
      </div>
    </section>
  );
};

/* ========== 情绪仪表卡 ========== */
export const ResearchSentimentPanel: React.FC<{
  score: number;
  updateAt?: string;
  signals?: Array<{ label: string; tone: 'up' | 'down' | 'flat' | 'warn'; hint?: string }>;
  className?: string;
}> = ({ score, updateAt = '2025-07-01 14:32', signals, className = '' }) => {
  const level = getSentimentLevel(score);
  const cn = sentimentCn(level);
  const pct = Math.max(0, Math.min(100, score));
  // StrokeDashArray based on 270deg arc
  const R = 56;
  const C = 2 * Math.PI * R;
  const dash = (pct / 100) * (C * 0.75);
  const strokeColor =
    level === 'greed' ? 'var(--sentiment-greed)' :
    level === 'fear'  ? 'var(--sentiment-fear)' : 'var(--sentiment-neutral)';
  const glow =
    level === 'greed' ? 'drop-shadow(0 0 10px var(--sentiment-greed-glow))' :
    level === 'fear'  ? 'drop-shadow(0 0 10px var(--sentiment-fear-glow))' : 'drop-shadow(0 0 10px var(--sentiment-neutral-glow))';

  return (
    <div className={`research-sentiment-wrap ${className}`}>
      <div className="relative z-10 p-5">
        <div className="flex items-center justify-between">
          <div className="label-uppercase text-purple/90">
            <Flame className="h-3.5 w-3.5" />
            Fear &amp; Greed
          </div>
          <span className="text-[11px] text-secondary-text/90 font-mono">{updateAt}</span>
        </div>

        <div className="mt-3 flex flex-col items-center">
          <div className="relative" style={{ width: 180, height: 160 }}>
            <svg viewBox="0 0 200 170" className="h-full w-full">
              {/* Track (270deg) */}
              <circle
                cx="100" cy="100" r={R}
                fill="none"
                stroke="hsl(var(--foreground) / 0.06)"
                strokeWidth="14"
                strokeLinecap="round"
                strokeDasharray={`${C * 0.75} ${C}`}
                transform="rotate(135 100 100)"
              />
              {/* Progress */}
              <circle
                cx="100" cy="100" r={R}
                fill="none"
                stroke={strokeColor}
                strokeWidth="14"
                strokeLinecap="round"
                strokeDasharray={`${dash} ${C}`}
                transform="rotate(135 100 100)"
                style={{ transition: 'stroke-dasharray .8s ease-out', filter: glow }}
              />
              {/* Tick marks */}
              {[0, 25, 50, 75, 100].map((t) => {
                const p = (t / 100) * 270 - 225;
                const a = (p * Math.PI) / 180;
                const r1 = R + 10;
                const r2 = R + 14;
                const x1 = 100 + r1 * Math.cos(a);
                const y1 = 100 + r1 * Math.sin(a);
                const x2 = 100 + r2 * Math.cos(a);
                const y2 = 100 + r2 * Math.sin(a);
                return (
                  <line key={t} x1={x1} y1={y1} x2={x2} y2={y2} stroke="hsl(var(--foreground)/0.25)" strokeWidth="2" strokeLinecap="round" />
                );
              })}
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ paddingBottom: 10 }}>
              <div className="text-[11px] uppercase tracking-[0.28em] text-secondary-text/90 font-semibold">
                Fear/Greed
              </div>
              <div
                data-sentiment={level}
                data-sentiment-text={level}
                className="mt-1 text-[44px] font-bold leading-none font-mono"
              >
                {score}
              </div>
              <div className="mt-2 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold"
                   style={{
                     borderColor: `${strokeColor}55`,
                     background: `${strokeColor}18`,
                     color: strokeColor,
                   }}>
                {cn}
              </div>
            </div>
          </div>

          {/* 区间图例 */}
          <div className="mt-4 w-full max-w-[240px] grid grid-cols-3 gap-2 text-[11px] font-semibold">
            <div className="text-center text-danger">0-34 恐惧</div>
            <div className="text-center text-purple">34-66 中性</div>
            <div className="text-center text-primary">66-100 贪婪</div>
          </div>
        </div>

        {/* 信号条 */}
        {signals && signals.length > 0 ? (
          <div className="mt-5 grid grid-cols-1 gap-2 border-t border-[hsl(var(--foreground)/0.06)] pt-4 sm:grid-cols-2">
            {signals.map((s, i) => {
              const isUp = s.tone === 'up';
              const isDown = s.tone === 'down';
              const isWarn = s.tone === 'warn';
              const color = isUp ? 'var(--home-strategy-buy)'
                         : isDown ? 'var(--home-strategy-stop)'
                         : isWarn ? 'hsl(37 92% 50%)' : 'var(--text-secondary-text)';
              const Icon = isUp ? TrendingUp : isDown ? TrendingDown : isWarn ? CircleAlert : Minus;
              return (
                <div key={i} className="flex items-center justify-between gap-3 rounded-[0.75rem] border border-[hsl(var(--foreground)/0.06)] bg-[hsl(var(--foreground)/0.02)] px-3 py-2">
                  <div className="flex items-center gap-2">
                    <div
                      className="flex h-7 w-7 items-center justify-center rounded-lg border"
                      style={{ borderColor: `${color}44`, background: `${color}14`, color }}
                    >
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    <div>
                      <div className="text-[12px] font-semibold">{s.label}</div>
                      {s.hint ? <div className="text-[11px] text-secondary-text/90">{s.hint}</div> : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
};

/* ========== 研究报告卡片 ========== */
export const ResearchReportCard: React.FC<{
  title: string;
  ticker?: string;
  summary: string;
  author?: string;
  date?: string;
  tags?: string[];
  rating?: '强烈推荐' | '推荐' | '持有' | '减持' | '卖出';
  confidence?: number;      // 0-100
  className?: string;
  onAction?: (label: string) => void;
}> = ({
  title, ticker = '600519.SH', summary, author = 'DSA Research', date = '2025-07-01',
  tags = ['白酒', '消费龙头', '估值修复'], rating = '推荐', confidence = 87,
  className = '', onAction,
}) => {
  const ratingColor = (() => {
    switch (rating) {
      case '强烈推荐': return 'var(--home-strategy-buy)';
      case '推荐':     return 'hsl(152 70% 44%)';
      case '持有':     return 'var(--color-gold)';
      case '减持':     return 'hsl(37 92% 50%)';
      case '卖出':     return 'var(--home-strategy-stop)';
      default:         return 'var(--text-secondary-text)';
    }
  })();

  return (
    <div className={`research-report-card ${className}`}>
      <div className="relative z-10 p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="research-report-ribbon">
              <Sparkles className="h-3.5 w-3.5" />
              研究报告 · Research
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1.5 rounded-[0.55rem] border px-2 py-1 text-[12px] font-bold font-mono text-primary/95"
                    style={{ borderColor: 'hsl(var(--primary)/0.28)', background: 'hsl(var(--primary)/0.10)' }}>
                <Briefcase className="h-3.5 w-3.5" />
                {ticker}
              </span>
              {tags.slice(0, 3).map((t) => (
                <span key={t} className="inline-flex items-center rounded-[0.55rem] border border-[hsl(var(--foreground)/0.08)] bg-[hsl(var(--foreground)/0.03)] px-2 py-1 text-[11px] text-secondary-text/95">
                  {t}
                </span>
              ))}
            </div>
          </div>
          <div
            className="inline-flex items-center gap-2 rounded-[0.8rem] border px-3 py-2 text-[13px] font-bold shadow-sm"
            style={{
              borderColor: `${ratingColor}55`,
              background: `${ratingColor}14`,
              color: ratingColor,
            }}
          >
            <Target className="h-4 w-4" />
            {rating}
          </div>
        </div>

        <h3 className="mt-4 text-[20px] font-semibold leading-snug">
          {title}
        </h3>
        <p className="mt-3 text-[13.5px] leading-relaxed text-secondary-text/95">
          {summary}
        </p>

        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-[hsl(var(--foreground)/0.08)] pt-4 sm:grid-cols-4">
          <div>
            <div className="label-xs">分析师</div>
            <div className="mt-1 text-[13px] font-semibold">{author}</div>
          </div>
          <div>
            <div className="label-xs">发布日期</div>
            <div className="mt-1 text-[13px] font-semibold font-mono">{date}</div>
          </div>
          <div>
            <div className="label-xs">信心度</div>
            <div className="mt-1 flex items-center gap-2">
              <div className="h-2 flex-1 rounded-full bg-[hsl(var(--foreground)/0.06)] overflow-hidden">
                <div
                  className="h-full rounded-full bg-primary-gradient"
                  style={{ width: `${Math.max(0, Math.min(100, confidence))}%` }}
                />
              </div>
              <span className="text-[12px] font-bold font-mono text-primary">{confidence}%</span>
            </div>
          </div>
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              className="btn-secondary !py-2 !px-3 text-[12.5px]"
              onClick={() => onAction?.('预览')}
            >
              <Scroll className="h-4 w-4" /> 预览
            </button>
            <button
              type="button"
              className="btn-primary !py-2 !px-3 text-[12.5px]"
              onClick={() => onAction?.('发布')}
            >
              <Rocket className="h-4 w-4" /> 发布
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ========== 策略快照（狙击点位）========== */
export const ResearchStrategyCard: React.FC<{
  ticker: string;
  name: string;
  rating: '买入' | '增持' | '持有' | '减仓' | '卖出';
  entry: number;           // 入场价
  target: number;          // 目标价
  stop: number;            // 止损价
  upside?: number;         // 百分比
  riskReward?: string;     // 盈亏比
  timeHorizon?: string;    // 周期
  className?: string;
}> = ({
  ticker, name, rating = '买入', entry, target, stop,
  upside = 18.4, riskReward = '3.2 : 1', timeHorizon = '3-6M',
  className = '',
}) => {
  const buy = rating === '买入' || rating === '增持';
  const danger = rating === '卖出' || rating === '减仓';

  return (
    <div className={`research-strategy-card p-5 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-[0.9rem] border bg-primary-gradient text-white shadow-glow-cyan">
            <Target className="h-5 w-5" />
          </div>
          <div>
            <div className="text-[15px] font-semibold leading-tight">{name}</div>
            <div className="mt-0.5 text-[12px] font-mono text-secondary-text/95">{ticker}</div>
          </div>
        </div>
        <span
          className="badge text-[12px]"
          style={{
            background: buy ? 'hsl(149 100% 38% / 0.12)' : danger ? 'hsl(0 86% 58% / 0.12)' : 'hsl(40 96% 52% / 0.12)',
            color: buy ? 'hsl(149 100% 38%)' : danger ? 'hsl(0 86% 58%)' : 'hsl(40 96% 52%)',
            borderColor: buy ? 'hsl(149 100% 38% / 0.26)' : danger ? 'hsl(0 86% 58% / 0.28)' : 'hsl(40 96% 52% / 0.28)',
          }}
        >
          {rating}
        </span>
      </div>

      <div className="mt-5 grid grid-cols-3 gap-3">
        <div className="rounded-[0.85rem] border border-[hsl(var(--foreground)/0.07)] bg-[hsl(var(--foreground)/0.02)] p-3">
          <div className="label-xs">入场价</div>
          <div className="mt-1 text-[17px] font-bold font-mono text-foreground">{entry.toFixed(2)}</div>
          <div className="mt-0.5 text-[11px] text-secondary-text/90">建议价格带</div>
        </div>
        <div className="rounded-[0.85rem] border p-3"
             style={{ borderColor: 'hsl(149 100% 38% / 0.24)', background: 'hsl(149 100% 38% / 0.08)' }}>
          <div className="label-xs text-[hsl(149 98% 30%)]">目标价</div>
          <div className="mt-1 text-[17px] font-bold font-mono" style={{ color: 'hsl(149 98% 36%)' }}>{target.toFixed(2)}</div>
          <div className="mt-0.5 text-[11px]">
            空间 <span className="font-bold" style={{ color: 'hsl(149 98% 36%)' }}>+{upside.toFixed(1)}%</span>
          </div>
        </div>
        <div className="rounded-[0.85rem] border p-3"
             style={{ borderColor: 'hsl(0 86% 58% / 0.24)', background: 'hsl(0 86% 58% / 0.08)' }}>
          <div className="label-xs text-[hsl(0 86% 48%)]">止损价</div>
          <div className="mt-1 text-[17px] font-bold font-mono" style={{ color: 'hsl(0 86% 58%)' }}>{stop.toFixed(2)}</div>
          <div className="mt-0.5 text-[11px]">
            盈亏比 <span className="font-bold" style={{ color: 'hsl(0 86% 58%)' }}>{riskReward}</span>
          </div>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between border-t border-[hsl(var(--foreground)/0.07)] pt-4">
        <div className="flex items-center gap-2 text-[12px] text-secondary-text/95">
          <Clock className="h-3.5 w-3.5" />
          周期 {timeHorizon}
        </div>
        <div className="flex items-center gap-2 text-[12px] text-secondary-text/95">
          <Shield className="h-3.5 w-3.5" />
          风控达标
        </div>
      </div>
    </div>
  );
};

/* ========== 任务轨道（流水线）========== */
export type TaskState = 'idle' | 'running' | 'success' | 'failed';
export type PipelineStage = {
  key: string;
  label: string;
  state: TaskState;
  duration?: string;
  detail?: string;
};

export const ResearchTaskTrack: React.FC<{
  title?: string;
  stages?: PipelineStage[];
  className?: string;
}> = ({
  title = '今日分析流水线',
  stages = [
    { key: 'grab',    label: '数据抓取',  state: 'success', duration: '18s' },
    { key: 'tech',    label: '技术分析',  state: 'success', duration: '22s' },
    { key: 'news',    label: '新闻检索',  state: 'success', duration: '10s' },
    { key: 'llm',     label: 'LLM 推理',  state: 'running', detail: '生成中 78%', duration: '42s' },
    { key: 'report',  label: '报告生成',  state: 'idle' },
    { key: 'push',    label: '通知推送',  state: 'idle' },
  ],
  className = '',
}) => {
  const IconForState: Record<TaskState, React.FC<{ className?: string }>> = {
    idle:    Layers,
    running: Loader2,
    success: CircleCheckBig,
    failed:  CircleAlert,
  };
  const StateLabel: Record<TaskState, string> = {
    idle: '等待中',
    running: '进行中',
    success: '已完成',
    failed: '失败',
  };

  return (
    <div className={`terminal-card terminal-card-hover ${className}`}>
      <div className="relative z-10 p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="label-uppercase text-purple/90">
              <Coins className="h-3.5 w-3.5" />
              Pipeline
            </div>
            <h3 className="mt-2 text-[17px] font-semibold">{title}</h3>
          </div>
          <span className="badge badge-cyan">今日 07/01</span>
        </div>

        <div className="mt-5 research-task-track">
          {stages.map((s) => {
            const I = IconForState[s.state];
            const spinning = s.state === 'running';
            const stateColor =
              s.state === 'success' ? 'hsl(149 100% 38%)' :
              s.state === 'running' ? 'hsl(var(--primary))' :
              s.state === 'failed'  ? 'hsl(0 86% 58%)' : 'var(--text-secondary-text)';
            return (
              <div key={s.key} className="research-task-chip" data-state={s.state}>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg border"
                       style={{ borderColor: `${stateColor}44`, background: `${stateColor}14`, color: stateColor }}>
                    <I className={`h-4 w-4 ${spinning ? 'animate-spin' : ''}`} />
                  </div>
                  <span className="text-[10.5px] font-semibold tracking-wide uppercase text-secondary-text/90">
                    {StateLabel[s.state]}
                  </span>
                </div>
                <div className="mt-3 text-[13px] font-semibold">{s.label}</div>
                <div className="mt-1 flex items-center justify-between text-[11px] text-secondary-text/90">
                  <span>{s.detail ?? ' '}</span>
                  {s.duration ? <span className="font-mono">{s.duration}</span> : <span>—</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

/* ========== 新闻/事件时间线 ========== */
export type NewsTone = 'positive' | 'negative' | 'policy' | 'default';
export type NewsEvent = {
  key: string;
  time: string;
  title: string;
  source?: string;
  tone: NewsTone;
  summary?: string;
  link?: string;
};

export const ResearchNewsTimeline: React.FC<{
  title?: string;
  items?: NewsEvent[];
  className?: string;
}> = ({
  title = '市场关键事件',
  items = [
    { key: 'n1', time: '14:02', tone: 'positive', title: '贵州茅台：公告 7 月提高出厂价约 20%', source: '公司公告', summary: '市场预期全年 EPS 上调 6-8%。' },
    { key: 'n2', time: '11:45', tone: 'policy',   title: '央行：今日开展 8000 亿 MLF 净投放 2000 亿', source: '央行公开市场', summary: '维护银行体系流动性合理充裕。' },
    { key: 'n3', time: '10:18', tone: 'negative', title: '港股内房板块：龙头跌幅超 5%', source: '路透', summary: '月度销售数据同比不及预期。' },
    { key: 'n4', time: '09:30', tone: 'default',  title: '大盘开盘：两市竞价成交额较昨日+12%', source: '交易所' },
    { key: 'n5', time: '08:00', tone: 'positive', title: '国务院：发布进一步支持新能源汽车下乡若干措施', source: '新华社', summary: '行业补贴延续并覆盖乡村充电桩网络。' },
  ] as NewsEvent[],
  className = '',
}) => {
  return (
    <div className={`glass-card ${className}`}>
      <div className="relative z-10 p-5">
        <div className="flex items-center justify-between">
          <div>
            <div className="label-uppercase text-purple/90">
              <TrendingUpIcon className="h-3.5 w-3.5" />
              Event Timeline
            </div>
            <h3 className="mt-2 text-[17px] font-semibold">{title}</h3>
          </div>
          <button type="button" className="btn-secondary !py-1.5 !px-3 text-[12px]">
            查看全部
          </button>
        </div>

        <div className="mt-4 research-timeline">
          {items.map((n) => (
            <div key={n.key} className="research-timeline-item" data-tone={n.tone === 'default' ? undefined : n.tone}>
              <div className="flex items-center justify-between gap-3">
                <div className="text-[11px] font-bold font-mono tracking-wide text-secondary-text/95">{n.time}</div>
                {n.source ? (
                  <span className="inline-flex items-center rounded-full border border-[hsl(var(--foreground)/0.08)] bg-[hsl(var(--foreground)/0.03)] px-2 py-0.5 text-[10.5px] text-secondary-text/95">
                    {n.source}
                  </span>
                ) : null}
              </div>
              <div className="mt-1.5 text-[13.5px] font-semibold leading-snug">{n.title}</div>
              {n.summary ? (
                <div className="mt-1 text-[12.5px] leading-relaxed text-secondary-text/95">{n.summary}</div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

const Minus: React.FC<{ className?: string }> = ({ className }) => <DashIcon className={className} />;
