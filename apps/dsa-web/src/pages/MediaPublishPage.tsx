import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  BadgeCheck,
  BellRing,
  BookOpen,
  Copy,
  Eye,
  Hash,
  Megaphone,
  MousePointerClick,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  Sparkles,
  SquarePen,
  Trash2,
  Users2,
  XCircle,
} from 'lucide-react';
import {
  ApiErrorAlert,
  Badge,
  Button,
  EmptyState,
  Input,
  Select,
  StatusDot,
  Tooltip,
} from '../components/common';
import { mediaPublishApi } from '../api/mediaPublish';
import { getParsedApiError, type ParsedApiError } from '../api/error';
import type {
  CreateTasksRequest,
  PlatformRow,
  PlatformSpec,
  PublishTaskRow,
  TaskStatus,
  UpsertPlatformRequest,
} from '../types/mediaPublish';

const TASK_STATUS_STYLE: Record<
  TaskStatus,
  { tone: 'success' | 'danger' | 'warning' | 'info' | 'default'; label: string }
> = {
  pending: { tone: 'default', label: '待执行' },
  queued: { tone: 'info', label: '已排队' },
  running: { tone: 'info', label: '执行中' },
  published: { tone: 'success', label: '已发布' },
  failed: { tone: 'danger', label: '失败' },
  retried: { tone: 'warning', label: '待重试' },
  cancelled: { tone: 'default', label: '已取消' },
};

const INPUT_CLS =
  'input-surface input-focus-glow h-10 w-full rounded-xl border bg-transparent px-3 text-sm transition-all focus:outline-none disabled:opacity-60';

function toast(text: string) {
  try {
    const el = document.createElement('div');
    el.textContent = text;
    el.className =
      'fixed z-[100] left-1/2 top-6 -translate-x-1/2 rounded-2xl border border-border bg-card px-4 py-2 text-sm shadow-xl';
    document.body.appendChild(el);
    window.setTimeout(() => el.remove(), 2000);
  } catch {
    /* ignore */
  }
}

async function copyToClipboard(value: string) {
  try {
    await navigator.clipboard.writeText(value);
    toast('已复制到剪贴板');
    return true;
  } catch {
    toast('复制失败，请手动复制');
    return false;
  }
}

function TaskStatusBadge({ status }: { status: TaskStatus }) {
  const s = TASK_STATUS_STYLE[status] ?? { tone: 'default' as const, label: status };
  return <Badge variant={s.tone}>{s.label}</Badge>;
}

const MediaPublishPage: React.FC = () => {
  useEffect(() => {
    document.title = '多平台发布 - DSA';
  }, []);

  // ===== 通用状态 =====
  const [tab, setTab] = useState<'tasks' | 'platforms' | 'export'>('tasks');
  const [pageError, setPageError] = useState<ParsedApiError | null>(null);

  // ===== 平台状态 =====
  const [specs, setSpecs] = useState<PlatformSpec[]>([]);
  const [platforms, setPlatforms] = useState<PlatformRow[]>([]);
  const [platformsLoading, setPlatformsLoading] = useState(false);
  const [platformForm, setPlatformForm] = useState<UpsertPlatformRequest>({
    platformCode: 'clipboard_export',
    displayName: '',
    enabled: true,
  });
  const [credentialFields, setCredentialFields] = useState<Array<{ key: string; value: string }>>([]);

  // ===== 任务状态 =====
  const [tasks, setTasks] = useState<PublishTaskRow[]>([]);
  const [tasksLoading, setTasksLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<TaskStatus | ''>('');
  const [platformFilter, setPlatformFilter] = useState('');
  const [taskForm, setTaskForm] = useState<CreateTasksRequest>({
    sourceType: 'manual',
    sourceDisplayName: '即时发布',
    title: '',
    summary: '',
    contentMarkdown: '',
    tags: [],
    originalAuthor: '',
    maxRetries: 2,
  });
  const [selectedPlatformIds, setSelectedPlatformIds] = useState<number[]>([]);

  // ===== 即时导出 =====
  const [exportTitle, setExportTitle] = useState('A股日报');
  const [exportMd, setExportMd] = useState(
    '# 大盘复盘\n\n今日**沪深300**上涨 *1.2%*。\n\n- 600519 茅台：MA5>MA10 多头\n- 300750 宁德：放量突破\n',
  );
  const [exportSummary, setExportSummary] = useState('AI 每日投研复盘摘要');
  const [exportTags, setExportTags] = useState('A股,复盘,智能分析');
  const [exportOutput, setExportOutput] = useState<{
    markdown: string;
    html: string;
    coseJson: string;
  } | null>(null);
  const [exportRunning, setExportRunning] = useState(false);

  // ===== 加载辅助 =====
  const refreshSpecs = async () => {
    try {
      const data = await mediaPublishApi.listSpecs();
      setSpecs(data);
      return data;
    } catch (e) {
      setPageError(getParsedApiError(e));
      return [];
    }
  };

  const refreshPlatforms = async () => {
    setPlatformsLoading(true);
    try {
      const data = await mediaPublishApi.listPlatforms(false);
      setPlatforms(data);
      return data;
    } catch (e) {
      setPageError(getParsedApiError(e));
      return [];
    } finally {
      setPlatformsLoading(false);
    }
  };

  const refreshTasks = async () => {
    setTasksLoading(true);
    try {
      const data = await mediaPublishApi.listTasks({
        status: statusFilter || undefined,
        platformCode: platformFilter || undefined,
        limit: 50,
      });
      setTasks(data);
    } catch (e) {
      setPageError(getParsedApiError(e));
    } finally {
      setTasksLoading(false);
    }
  };

  useEffect(() => {
    const init = async () => {
      const sp = await refreshSpecs();
      const pl = await refreshPlatforms();
      if (sp.length && !platformForm.displayName) {
        setPlatformForm((f) => ({ ...f, displayName: sp[0].platformName + '（默认）' }));
        setCredentialFields(
          sp[0].requiredCredentialKeys.map((k) => ({ key: k, value: '' })),
        );
      }
      if (pl.length && !selectedPlatformIds.length) {
        setSelectedPlatformIds(pl.slice(0, 1).map((p) => p.id));
      }
      refreshTasks();
    };
    void init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    void refreshTasks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, platformFilter]);

  // ===== 平台操作 =====
  const currentSpec = specs.find((s) => s.platformCode === platformForm.platformCode);
  useEffect(() => {
    if (currentSpec) {
      setCredentialFields(
        currentSpec.requiredCredentialKeys.map((k) => ({ key: k, value: '' })),
      );
    }
  }, [currentSpec?.platformCode]);

  const handleUpsertPlatform = async () => {
    try {
      const credentials: Record<string, unknown> = {};
      credentialFields.forEach(({ key, value }) => {
        if (key.trim()) credentials[key.trim()] = value;
      });
      await mediaPublishApi.upsertPlatform({
        ...platformForm,
        credentials: Object.keys(credentials).length ? credentials : undefined,
      });
      toast('平台已保存');
      await refreshPlatforms();
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const handleToggleEnabled = async (p: PlatformRow) => {
    try {
      await mediaPublishApi.setEnabled(p.id, !p.enabled);
      toast(p.enabled ? '已禁用' : '已启用');
      await refreshPlatforms();
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const handleDeletePlatform = async (p: PlatformRow) => {
    if (!window.confirm(`确认删除平台「${p.displayName}」？发布任务记录会保留。`)) return;
    try {
      await mediaPublishApi.deletePlatform(p.id);
      toast('已删除平台');
      await refreshPlatforms();
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  // ===== 任务操作 =====
  const handleCreateTasks = async () => {
    if (!taskForm.title) {
      toast('请输入标题');
      return;
    }
    if (!selectedPlatformIds.length) {
      toast('请至少选择一个发布目标平台');
      return;
    }
    try {
      const created = await mediaPublishApi.createTasks({
        ...taskForm,
        platformIds: selectedPlatformIds,
      });
      toast(`已创建 ${created.length} 条发布任务`);
      setTab('tasks');
      void refreshTasks();
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const handleRunTask = async (t: PublishTaskRow, force = false) => {
    try {
      const updated = await mediaPublishApi.runTask(t.id, force);
      setTasks((prev) => prev.map((x) => (x.id === t.id ? updated : x)));
      toast(`任务 ${updated.status}`);
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const handleRetryTask = async (t: PublishTaskRow) => {
    try {
      const updated = await mediaPublishApi.retryTask(t.id);
      setTasks((prev) => prev.map((x) => (x.id === t.id ? updated : x)));
      toast('已重置为待执行');
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const handleCancelTask = async (t: PublishTaskRow) => {
    try {
      const updated = await mediaPublishApi.cancelTask(t.id);
      setTasks((prev) => prev.map((x) => (x.id === t.id ? updated : x)));
      toast('已取消');
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const handleRunBatch = async () => {
    try {
      const r = await mediaPublishApi.runBatch(20, true);
      toast(`批量执行：发布 ${r.published} / 失败 ${r.failed} / 总计 ${r.total}`);
      void refreshTasks();
    } catch (e) {
      setPageError(getParsedApiError(e));
    }
  };

  const toggleSelectPlatform = (id: number) => {
    setSelectedPlatformIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  // ===== 导出 =====
  const handleExport = async () => {
    setExportRunning(true);
    setPageError(null);
    try {
      const res = await mediaPublishApi.exportNow({
        title: exportTitle,
        contentMarkdown: exportMd,
        summary: exportSummary,
        tags: exportTags.split(',').map((s) => s.trim()).filter(Boolean),
        targetPlatformCodes: ['clipboard_export'],
      });
      const front = res.export?.extra?.frontends;
      if (front) {
        setExportOutput({
          markdown: front.copyMarkdown ?? '',
          html: front.copyHtml ?? '',
          coseJson: front.copyCoseJson ?? '',
        });
      }
      toast('导出完成，可一键复制');
    } catch (e) {
      setPageError(getParsedApiError(e));
    } finally {
      setExportRunning(false);
    }
  };

  const statusOptions = useMemo(
    () => [
      { value: '', label: '全部状态' },
      ...Object.entries(TASK_STATUS_STYLE).map(([v, { label }]) => ({
        value: v,
        label,
      })),
    ],
    [],
  );

  // ====== 发布概览 KPI ======
  const publishKpis = useMemo(() => {
    const total = tasks.length;
    const published = tasks.filter((t) => t.status === 'published').length;
    const failed = tasks.filter((t) => t.status === 'failed').length;
    const rate = total > 0 ? Math.round((published / total) * 100) : 0;
    const enabledPlat = platforms.filter((p) => p.enabled).length;
    return { total, published, failed, rate, enabledPlat, platCount: platforms.length };
  }, [tasks, platforms]);

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      {/* ====== Header ====== */}
      <header className="research-page-head">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl border border-primary/30 bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-[0_12px_28px_var(--nav-brand-shadow)]">
              <Megaphone className="h-5 w-5" />
            </div>
            <span className="absolute -right-1 -top-1 flex h-3 w-3 items-center justify-center">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success/40" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
            </span>
          </div>
          <div className="flex flex-col">
            <h1 className="text-base font-semibold">
              多平台发布 <span className="title-gradient">· 智能投研分发</span>
            </h1>
            <p className="text-xs text-muted-text">
              公众号草稿 / 知乎 / 雪球 / 微博 / 头条 &amp; 通用剪贴板（COSE 兼容）
            </p>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-1 rounded-2xl border border-[hsl(var(--foreground)/0.08)] bg-[hsl(var(--card)/0.6)] p-1 backdrop-blur">
            {([
              { key: 'tasks', label: '发布任务', icon: SquarePen },
              { key: 'platforms', label: '平台管理', icon: ShieldAlert },
              { key: 'export', label: '即时导出', icon: Copy },
            ] as const).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                className={
                  'relative flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs transition-all ' +
                  (tab === key
                    ? 'bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-lg shadow-primary/20'
                    : 'text-secondary-text hover:text-foreground hover:bg-[hsl(var(--foreground)/0.04)]')
                }
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* KPI 矩阵 */}
        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <PublishKpiCell
            icon={<Send className="h-3.5 w-3.5" />}
            label="发布任务"
            value={String(publishKpis.total)}
            tone="primary"
          />
          <PublishKpiCell
            icon={<BadgeCheck className="h-3.5 w-3.5" />}
            label="已发布"
            value={String(publishKpis.published)}
            tone="success"
          />
          <PublishKpiCell
            icon={<XCircle className="h-3.5 w-3.5" />}
            label="失败数"
            value={String(publishKpis.failed)}
            tone="danger"
          />
          <PublishKpiCell
            icon={<Sparkles className="h-3.5 w-3.5" />}
            label="成功率"
            value={`${publishKpis.rate}%`}
            tone="purple"
          />
          <PublishKpiCell
            icon={<Users2 className="h-3.5 w-3.5" />}
            label="启用平台"
            value={`${publishKpis.enabledPlat} / ${publishKpis.platCount}`}
            tone="warning"
          />
        </div>

        {pageError ? (
          <ApiErrorAlert
            error={pageError}
            onDismiss={() => setPageError(null)}
            dismissLabel="关闭"
            className="mt-3"
          />
        ) : null}
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto p-3 pb-10 sm:p-5">
        {tab === 'tasks' && (
          <TasksPanel
            tasks={tasks}
            tasksLoading={tasksLoading}
            statusOptions={statusOptions}
            statusFilter={statusFilter}
            setStatusFilter={setStatusFilter}
            platforms={platforms}
            platformFilter={platformFilter}
            setPlatformFilter={setPlatformFilter}
            taskForm={taskForm}
            setTaskForm={setTaskForm}
            selectedPlatformIds={selectedPlatformIds}
            toggleSelectPlatform={toggleSelectPlatform}
            onCreateTasks={handleCreateTasks}
            onRunTask={handleRunTask}
            onRetryTask={handleRetryTask}
            onCancelTask={handleCancelTask}
            onRunBatch={handleRunBatch}
            onRefresh={refreshTasks}
          />
        )}

        {tab === 'platforms' && (
          <PlatformsPanel
            specs={specs}
            platforms={platforms}
            platformsLoading={platformsLoading}
            platformForm={platformForm}
            setPlatformForm={setPlatformForm}
            credentialFields={credentialFields}
            setCredentialFields={setCredentialFields}
            onUpsert={handleUpsertPlatform}
            onToggleEnabled={handleToggleEnabled}
            onDelete={handleDeletePlatform}
            onRefresh={refreshPlatforms}
          />
        )}

        {tab === 'export' && (
          <ExportPanel
            title={exportTitle}
            setTitle={setExportTitle}
            md={exportMd}
            setMd={setExportMd}
            summary={exportSummary}
            setSummary={setExportSummary}
            tagsInput={exportTags}
            setTagsInput={setExportTags}
            output={exportOutput}
            running={exportRunning}
            onExport={handleExport}
          />
        )}
      </main>
    </div>
  );
};

/* ============ 发布页 KPI 单元格 ============ */
const PublishKpiCell: React.FC<{
  icon: React.ReactNode;
  label: string;
  value: string;
  tone: 'primary' | 'success' | 'danger' | 'warning' | 'purple';
}> = ({ icon, label, value, tone }) => {
  const toneMap: Record<string, { border: string; txt: string; bg: string; raw: string }> = {
    primary: {
      border: 'hsl(var(--primary) / 0.3)',
      txt: 'text-primary',
      bg: 'hsl(var(--primary) / 0.12)',
      raw: 'hsl(var(--primary))',
    },
    success: {
      border: 'hsl(149 100% 38% / 0.3)',
      txt: 'text-success',
      bg: 'hsl(149 100% 38% / 0.12)',
      raw: 'hsl(149 100% 38%)',
    },
    danger: {
      border: 'hsl(0 86% 58% / 0.3)',
      txt: 'text-danger',
      bg: 'hsl(0 86% 58% / 0.12)',
      raw: 'hsl(0 86% 58%)',
    },
    warning: {
      border: 'hsl(37 92% 50% / 0.3)',
      txt: 'text-warning',
      bg: 'hsl(37 92% 50% / 0.12)',
      raw: 'hsl(37 92% 50%)',
    },
    purple: {
      border: 'hsl(245 85% 65% / 0.3)',
      txt: 'text-purple',
      bg: 'hsl(245 85% 65% / 0.12)',
      raw: 'hsl(245 85% 65%)',
    },
  };
  const t = toneMap[tone] ?? toneMap.primary;
  return (
    <div
      className="relative overflow-hidden rounded-[0.85rem] border px-3 py-2.5"
      style={{ borderColor: t.border, background: `linear-gradient(180deg, ${t.bg}, transparent 70%)` }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="label-xs text-secondary-text/90">{label}</span>
        <span
          className={`flex h-6 w-6 items-center justify-center rounded-md border ${t.txt}`}
          style={{ borderColor: t.border, color: t.raw }}
        >
          {icon}
        </span>
      </div>
      <div className={`mt-1 font-mono text-[18px] font-bold leading-none ${t.txt}`} style={{ color: t.raw }}>
        {value}
      </div>
    </div>
  );
};

/* ============ 研究报告预览卡片（封面 + 摘要 + 标签） ============ */
const ResearchCoverPreview: React.FC<{
  title?: string;
  summary?: string;
  content?: string;
  tags?: string[];
  author?: string;
  className?: string;
}> = ({ title = '未命名研究报告', summary, content, tags = [], author = 'AI 智能投研', className = '' }) => {
  const previewText = summary
    || (content ? content.replace(/[#*`>\-]/g, '').slice(0, 120) : '本报告基于多因子模型与 LLM 语义分析，覆盖大盘复盘、板块轮动与重点标的。')
    + '...';
  const dateStr = new Date().toISOString().slice(0, 10);

  return (
    <div className={`research-cover-card ${className}`}>
      <div className="relative z-10 p-[1px]">
        {/* 封面画布 */}
        <div className="relative overflow-hidden rounded-[1.35rem]">
          {/* 渐变背景 + 网格 */}
          <div
            className="absolute inset-0"
            style={{
              background:
                'radial-gradient(800px 220px at 10% 0%, hsl(var(--primary) / 0.35), transparent 60%),' +
                'radial-gradient(600px 200px at 90% 100%, hsl(245 85% 65% / 0.3), transparent 60%),' +
                'linear-gradient(160deg, hsl(222 47% 12%), hsl(222 47% 6%))',
            }}
          />
          <div
            className="absolute inset-0 opacity-40"
            style={{
              backgroundImage:
                'linear-gradient(hsl(var(--foreground) / 0.06) 1px, transparent 1px),' +
                'linear-gradient(90deg, hsl(var(--foreground) / 0.06) 1px, transparent 1px)',
              backgroundSize: '24px 24px',
              maskImage: 'radial-gradient(closest-side at 50% 50%, #000, transparent 80%)',
              WebkitMaskImage: 'radial-gradient(closest-side at 50% 50%, #000, transparent 80%)',
            }}
          />
          {/* 内容区 */}
          <div className="relative z-10 p-5 sm:p-6 text-white">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full border border-white/15 bg-white/5 px-2.5 py-1 text-[10.5px] backdrop-blur">
                <Sparkles className="h-3 w-3 text-primary" />
                AI Research
              </span>
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10.5px] backdrop-blur text-white/70">
                {dateStr}
              </span>
              <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10.5px] backdrop-blur text-white/70">
                DSA · 智能投研
              </span>
            </div>

            <h3 className="mt-4 text-[22px] font-bold leading-[1.3] tracking-tight">
              {title || '未命名研究报告'}
            </h3>

            <p className="mt-3 text-[13px] leading-[1.75] text-white/78 line-clamp-3">
              {previewText}
            </p>

            <div className="mt-4 flex flex-wrap gap-1.5">
              {(tags.length ? tags : ['A股', '智能分析', '量化复盘']).map((t) => (
                <span
                  key={t}
                  className="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 px-2 py-0.5 text-[11px] text-white/80 backdrop-blur"
                >
                  <Hash className="h-2.5 w-2.5 opacity-60" />
                  {t}
                </span>
              ))}
            </div>

            <div className="mt-5 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-7 w-7 items-center justify-center rounded-full bg-primary-gradient text-[11px] font-bold text-white shadow-lg">
                  AI
                </div>
                <div className="flex flex-col">
                  <span className="text-[11.5px] font-semibold">{author}</span>
                  <span className="text-[10px] text-white/50">智能投研系统</span>
                </div>
              </div>
              <div className="flex items-center gap-1 text-[10.5px] text-white/60">
                <Eye className="h-3 w-3" />
                <BookOpen className="h-3 w-3 ml-1" />
                <span className="ml-1">Report Preview</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== 子组件：任务 ====================
const TasksPanel: React.FC<{
  tasks: PublishTaskRow[];
  tasksLoading: boolean;
  statusOptions: { value: string; label: string }[];
  statusFilter: TaskStatus | '';
  setStatusFilter: (v: TaskStatus | '') => void;
  platforms: PlatformRow[];
  platformFilter: string;
  setPlatformFilter: (v: string) => void;
  taskForm: CreateTasksRequest;
  setTaskForm: React.Dispatch<React.SetStateAction<CreateTasksRequest>>;
  selectedPlatformIds: number[];
  toggleSelectPlatform: (id: number) => void;
  onCreateTasks: () => void;
  onRunTask: (t: PublishTaskRow, force?: boolean) => void;
  onRetryTask: (t: PublishTaskRow) => void;
  onCancelTask: (t: PublishTaskRow) => void;
  onRunBatch: () => void;
  onRefresh: () => void;
}> = (props) => {
  const {
    tasks, tasksLoading, statusOptions, statusFilter, setStatusFilter,
    platforms, platformFilter, setPlatformFilter,
    taskForm, setTaskForm, selectedPlatformIds, toggleSelectPlatform,
    onCreateTasks, onRunTask, onRetryTask, onCancelTask, onRunBatch, onRefresh,
  } = props;

  return (
    <div className="space-y-4 animate-fade-in">
      {/* ====== 顶部：研究封面预览 + 创建发布任务表单 ====== */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* 左：封面预览 */}
        <div className="lg:col-span-2">
          <ResearchCoverPreview
            title={taskForm.title || undefined}
            summary={taskForm.summary || undefined}
            content={taskForm.contentMarkdown || undefined}
            tags={taskForm.tags || []}
            author={taskForm.originalAuthor || undefined}
          />
        </div>

        {/* 右：任务创建表单 */}
        <div className="terminal-card terminal-card-hover lg:col-span-3 overflow-hidden">
          <div className="p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <div>
                <div className="label-uppercase text-primary/90">
                  <SquarePen className="h-3.5 w-3.5" />
                  Publishing Desk
                </div>
                <h3 className="mt-1.5 text-[17px] font-semibold">
                  创建<span className="title-gradient"> 发布任务</span>
                </h3>
              </div>
              <div className="ml-auto flex flex-wrap gap-1.5">
                <Button size="sm" variant="secondary" onClick={onRefresh}>
                  <RefreshCw className="h-3.5 w-3.5" />
                  刷新
                </Button>
                <Button size="sm" variant="primary" onClick={onRunBatch}>
                  <Play className="h-3.5 w-3.5" />
                  批量执行
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              <div>
                <label className="label-xs mb-1 block">来源类型</label>
                <Select
                  value={taskForm.sourceType}
                  onChange={(v) =>
                    setTaskForm((f) => ({ ...f, sourceType: v as CreateTasksRequest['sourceType'] }))
                  }
                  options={[
                    { value: 'manual', label: '手工 / 即时' },
                    { value: 'analysis', label: '分析历史' },
                    { value: 'market_review', label: '大盘复盘' },
                  ]}
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">来源名称（可选）</label>
                <Input
                  value={taskForm.sourceDisplayName || ''}
                  onChange={(e) =>
                    setTaskForm((f) => ({ ...f, sourceDisplayName: e.target.value }))
                  }
                  placeholder="例如：8 月 16 日复盘"
                  className={INPUT_CLS}
                />
              </div>
              <div className="md:col-span-2">
                <label className="label-xs mb-1 block">标题 *</label>
                <Input
                  value={taskForm.title}
                  onChange={(e) => setTaskForm((f) => ({ ...f, title: e.target.value }))}
                  placeholder="发布标题（必填，将显示在封面上）"
                  className={INPUT_CLS}
                />
              </div>
              <div className="md:col-span-2">
                <label className="label-xs mb-1 block">摘要</label>
                <Input
                  value={taskForm.summary || ''}
                  onChange={(e) => setTaskForm((f) => ({ ...f, summary: e.target.value }))}
                  placeholder="不填会自动截取 Markdown 前 180 字"
                  className={INPUT_CLS}
                />
              </div>
              <div className="md:col-span-2">
                <label className="label-xs mb-1 block">正文（Markdown）</label>
                <textarea
                  rows={7}
                  value={taskForm.contentMarkdown || ''}
                  onChange={(e) =>
                    setTaskForm((f) => ({ ...f, contentMarkdown: e.target.value }))
                  }
                  className={
                    'resize-none rounded-xl border bg-transparent px-3 py-2 text-sm transition-all focus:outline-none ' +
                    INPUT_CLS
                  }
                  placeholder="# 大盘复盘\n\n今日 **沪深300** 上涨 *1.2%* …"
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">标签（英文逗号分隔）</label>
                <Input
                  value={(taskForm.tags || []).join(',')}
                  onChange={(e) =>
                    setTaskForm((f) => ({
                      ...f,
                      tags: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                    }))
                  }
                  placeholder="A股,复盘,智能分析"
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">作者</label>
                <Input
                  value={taskForm.originalAuthor || ''}
                  onChange={(e) =>
                    setTaskForm((f) => ({ ...f, originalAuthor: e.target.value }))
                  }
                  placeholder="留空跟随平台配置"
                  className={INPUT_CLS}
                />
              </div>
              <div className="md:col-span-2">
                <label className="label-xs mb-1 block">
                  发布目标平台（选中 {selectedPlatformIds.length} 个）
                </label>
                <div className="flex flex-wrap gap-2">
                  {platforms.length === 0 ? (
                    <span className="text-xs text-muted-text">
                      尚未注册平台，先去「平台管理」添加。
                    </span>
                  ) : (
                    platforms.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => toggleSelectPlatform(p.id)}
                        className={
                          'relative flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs transition-all ' +
                          (selectedPlatformIds.includes(p.id)
                            ? 'border-primary/50 bg-primary/10 text-primary shadow-[0_0_0_3px_hsl(var(--primary)/0.1)]'
                            : 'border-[hsl(var(--foreground)/0.08)] text-secondary-text hover:text-foreground hover:bg-[hsl(var(--foreground)/0.03)]')
                        }
                      >
                        {p.enabled ? (
                          <StatusDot tone="success" />
                        ) : (
                          <StatusDot tone="neutral" />
                        )}
                        {p.displayName}
                        <span className="text-[10px] text-muted-text">({p.platformCode})</span>
                      </button>
                    ))
                  )}
                </div>
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-2">
              <div className="text-[11.5px] text-secondary-text/95">
                <MousePointerClick className="mr-1 inline h-3 w-3 opacity-70" />
                选好平台后点「创建」，任务会进入下方队列等待执行。
              </div>
              <Button variant="primary" onClick={onCreateTasks}>
                <Plus className="h-3.5 w-3.5" />
                创建发布任务
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* ====== 下方：任务列表 ====== */}
      <div className="terminal-card terminal-card-hover overflow-hidden">
        <div className="p-5">
          <div className="mb-4 flex flex-wrap items-center gap-2">
            <div>
              <div className="label-uppercase text-success/90">
                <Send className="h-3.5 w-3.5" />
                Task Queue
              </div>
              <h3 className="mt-1.5 text-[17px] font-semibold">发布任务队列</h3>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              <Select
                value={platformFilter}
                onChange={setPlatformFilter}
                options={[
                  { value: '', label: '全部平台' },
                  ...platforms.map((p) => ({ value: p.platformCode, label: p.displayName })),
                ]}
                className={INPUT_CLS + ' h-9 w-36 !px-2'}
              />
              <Select
                value={statusFilter}
                onChange={(v) => setStatusFilter(v as TaskStatus | '')}
                options={statusOptions}
                className={INPUT_CLS + ' h-9 w-32 !px-2'}
              />
            </div>
          </div>

          {tasksLoading ? (
            <EmptyState
              title="加载中"
              description="获取任务列表"
              className="min-h-[10rem] border-dashed bg-card/45 shadow-none"
            />
          ) : tasks.length === 0 ? (
            <EmptyState
              title="暂无任务"
              description="先在上方创建一条任务，或选择「即时导出」。"
              className="min-h-[10rem] border-dashed bg-card/45 shadow-none"
            />
          ) : (
            <div className="max-h-[65vh] space-y-2 overflow-y-auto pr-1">
              {tasks.map((t) => (
                <div
                  key={t.id}
                  className="flex flex-col gap-2 rounded-2xl border border-[hsl(var(--foreground)/0.06)] bg-[hsl(var(--card)/0.55)] p-3 text-sm hover:border-[hsl(var(--foreground)/0.12)] transition-colors"
                >
                  <div className="flex flex-wrap items-start gap-2">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground truncate">{t.title}</span>
                        <TaskStatusBadge status={t.status} />
                      </div>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-text">
                        <span>#{t.id}</span>
                        <span>·</span>
                        <span>{t.platformCode}</span>
                        {t.sourceDisplayName ? (
                          <>
                            <span>·</span>
                            <span className="truncate">{t.sourceDisplayName}</span>
                          </>
                        ) : null}
                        {t.remoteUrl ? (
                          <>
                            <span>·</span>
                            <a
                              href={t.remoteUrl}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary underline"
                            >
                              打开
                            </a>
                          </>
                        ) : null}
                        {t.errorCode ? (
                          <Tooltip
                            content={`${t.errorCode}: ${t.errorMessage || ''}`}
                            focusable
                          >
                            <Badge variant="danger" className="cursor-help">
                              {t.errorCode}
                            </Badge>
                          </Tooltip>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex flex-wrap justify-end gap-1">
                      {['pending', 'retried', 'failed'].includes(t.status) && (
                        <Button size="sm" variant="primary" onClick={() => onRunTask(t)}>
                          <Play className="h-3 w-3" />
                          执行
                        </Button>
                      )}
                      {t.status === 'failed' && (
                        <Button size="sm" variant="secondary" onClick={() => onRetryTask(t)}>
                          <RotateCcw className="h-3 w-3" />
                          重试
                        </Button>
                      )}
                      {['pending', 'retried', 'queued'].includes(t.status) && (
                        <Button size="sm" variant="secondary" onClick={() => onCancelTask(t)}>
                          <XCircle className="h-3 w-3" />
                          取消
                        </Button>
                      )}
                      <Button size="sm" variant="ghost" onClick={() => onRunTask(t, true)}>
                        <RefreshCw className="h-3 w-3" />
                        强制
                      </Button>
                    </div>
                  </div>
                  {t.summary ? (
                    <p className="line-clamp-2 text-xs text-secondary-text">{t.summary}</p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ==================== 子组件：平台管理 ====================
const PlatformsPanel: React.FC<{
  specs: PlatformSpec[];
  platforms: PlatformRow[];
  platformsLoading: boolean;
  platformForm: UpsertPlatformRequest;
  setPlatformForm: React.Dispatch<React.SetStateAction<UpsertPlatformRequest>>;
  credentialFields: Array<{ key: string; value: string }>;
  setCredentialFields: React.Dispatch<
    React.SetStateAction<Array<{ key: string; value: string }>>
  >;
  onUpsert: () => void;
  onToggleEnabled: (p: PlatformRow) => void;
  onDelete: (p: PlatformRow) => void;
  onRefresh: () => void;
}> = ({
  specs, platforms, platformsLoading, platformForm, setPlatformForm,
  credentialFields, setCredentialFields, onUpsert, onToggleEnabled, onDelete, onRefresh,
}) => {
  // 平台渠道矩阵配色映射
  const toneOf = (code: string): 'primary' | 'success' | 'danger' | 'warning' | 'purple' => {
    if (code.includes('wechat') || code.includes('mp')) return 'success';
    if (code.includes('zhihu')) return 'primary';
    if (code.includes('xigua') || code.includes('toutiao')) return 'danger';
    if (code.includes('weibo')) return 'warning';
    if (code.includes('clipboard') || code.includes('export')) return 'purple';
    return 'primary';
  };

  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* 左：平台注册表单 */}
        <div className="terminal-card terminal-card-hover lg:col-span-2 overflow-hidden">
          <div className="p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <div>
                <div className="label-uppercase text-warning/90">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  Platform Registry
                </div>
                <h3 className="mt-1.5 text-[17px] font-semibold">
                  注册<span className="title-gradient"> 平台凭据</span>
                </h3>
              </div>
              <div className="ml-auto">
                <Button size="sm" variant="secondary" onClick={onRefresh}>
                  <RefreshCw className="h-3.5 w-3.5" />
                  刷新
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-1 gap-3">
              <div>
                <label className="label-xs mb-1 block">平台类型</label>
                <Select
                  value={platformForm.platformCode}
                  onChange={(v) => setPlatformForm((f) => ({ ...f, platformCode: v }))}
                  options={specs.map((s) => ({ value: s.platformCode, label: s.platformName }))}
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">显示名称</label>
                <Input
                  value={platformForm.displayName}
                  onChange={(e) =>
                    setPlatformForm((f) => ({ ...f, displayName: e.target.value }))
                  }
                  placeholder="例如：XX 投资研究公众号"
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">账号 ID（可选，去重用）</label>
                <Input
                  value={platformForm.accountId || ''}
                  onChange={(e) =>
                    setPlatformForm((f) => ({ ...f, accountId: e.target.value }))
                  }
                  placeholder="例如：gh_xxx / 专栏 id"
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">默认目标（专栏 / 分类 / 草稿箱）</label>
                <Input
                  value={platformForm.defaultTarget || ''}
                  onChange={(e) =>
                    setPlatformForm((f) => ({ ...f, defaultTarget: e.target.value }))
                  }
                  placeholder="可留空"
                  className={INPUT_CLS}
                />
              </div>
              <div>
                <label className="label-xs mb-1 block">凭据字段</label>
                {credentialFields.length === 0 ? (
                  <p className="text-xs text-muted-text rounded-xl border border-dashed border-[hsl(var(--foreground)/0.08)] px-3 py-2">
                    该平台无需凭据（例如「通用导出」）。
                  </p>
                ) : (
                  <div className="flex flex-col gap-2">
                    {credentialFields.map((f, idx) => (
                      <div key={f.key || idx} className="flex items-center gap-2">
                        <Input
                          value={f.key}
                          onChange={(e) => {
                            const next = [...credentialFields];
                            next[idx] = { ...f, key: e.target.value };
                            setCredentialFields(next);
                          }}
                          placeholder="字段名"
                          className={INPUT_CLS + ' flex-1'}
                        />
                        <Input
                          value={f.value}
                          onChange={(e) => {
                            const next = [...credentialFields];
                            next[idx] = { ...f, value: e.target.value };
                            setCredentialFields(next);
                          }}
                          type="password"
                          placeholder="对应值（脱敏存储与回传）"
                          className={INPUT_CLS + ' flex-[2]'}
                        />
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            setCredentialFields((prev) => prev.filter((_, i) => i !== idx))
                          }
                        >
                          删除
                        </Button>
                      </div>
                    ))}
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() =>
                        setCredentialFields((prev) => [...prev, { key: '', value: '' }])
                      }
                    >
                      新增字段
                    </Button>
                  </div>
                )}
              </div>
            </div>

            <div className="mt-4 flex items-center justify-between gap-2">
              <label className="flex items-center gap-2 text-xs text-secondary-text">
                <input
                  type="checkbox"
                  checked={!!platformForm.enabled}
                  onChange={(e) =>
                    setPlatformForm((f) => ({ ...f, enabled: e.target.checked }))
                  }
                />
                启用该平台
              </label>
              <Button variant="primary" onClick={onUpsert}>
                <Plus className="h-3.5 w-3.5" />
                保存
              </Button>
            </div>
          </div>
        </div>

        {/* 右：平台渠道矩阵 */}
        <div className="glass-card lg:col-span-3 overflow-hidden">
          <div className="relative z-10 p-5">
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <div>
                <div className="label-uppercase text-purple/90">
                  <Users2 className="h-3.5 w-3.5" />
                  Channel Matrix
                </div>
                <h3 className="mt-1.5 text-[17px] font-semibold">
                  平台渠道矩阵（{platforms.length}）
                </h3>
              </div>
            </div>

            {platformsLoading ? (
              <EmptyState title="加载中" description="获取平台列表" className="min-h-[10rem] border-dashed bg-card/45 shadow-none" />
            ) : platforms.length === 0 ? (
              <EmptyState
                title="尚未注册"
                description="建议先注册一个「通用导出」平台，作为任何情况下的保底发布出口。"
                className="min-h-[14rem] border-dashed bg-card/45 shadow-none"
              />
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {platforms.map((p) => {
                  const tone = toneOf(p.platformCode);
                  const toneMap: Record<string, { border: string; bg: string; raw: string }> = {
                    primary: { border: 'hsl(var(--primary) / 0.3)', bg: 'hsl(var(--primary) / 0.12)', raw: 'hsl(var(--primary))' },
                    success: { border: 'hsl(149 100% 38% / 0.3)', bg: 'hsl(149 100% 38% / 0.12)', raw: 'hsl(149 100% 38%)' },
                    danger:  { border: 'hsl(0 86% 58% / 0.3)',   bg: 'hsl(0 86% 58% / 0.12)',   raw: 'hsl(0 86% 58%)' },
                    warning: { border: 'hsl(37 92% 50% / 0.3)',  bg: 'hsl(37 92% 50% / 0.12)',  raw: 'hsl(37 92% 50%)' },
                    purple:  { border: 'hsl(245 85% 65% / 0.3)', bg: 'hsl(245 85% 65% / 0.12)', raw: 'hsl(245 85% 65%)' },
                  };
                  const t = toneMap[tone] ?? toneMap.primary;
                  const hints = Array.isArray(p.credentialsKeyHints)
                    ? p.credentialsKeyHints
                    : (typeof p.credentialsKeyHints === 'object' && p.credentialsKeyHints)
                      ? Object.keys(p.credentialsKeyHints as Record<string, unknown>)
                      : [];
                  return (
                    <div
                      key={p.id}
                      className="relative overflow-hidden rounded-[1rem] border p-3 transition-all hover:-translate-y-0.5"
                      style={{
                        borderColor: p.enabled ? t.border : 'hsl(var(--foreground)/0.08)',
                        background: `linear-gradient(160deg, ${p.enabled ? t.bg : 'hsl(var(--foreground)/0.02)'}, hsl(var(--card)/0.6))`,
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <div
                              className="flex h-7 w-7 items-center justify-center rounded-lg border text-[10.5px] font-bold"
                              style={{ borderColor: t.border, color: t.raw, background: t.bg }}
                            >
                              {p.displayName.slice(0, 2) || 'P'}
                            </div>
                            <span className="font-semibold truncate">{p.displayName}</span>
                          </div>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {p.enabled ? (
                              <Badge variant="success">
                                <BadgeCheck className="mr-0.5 h-3 w-3 inline" />
                                启用
                              </Badge>
                            ) : (
                              <Badge variant="default">已禁用</Badge>
                            )}
                            <Badge variant="default">{p.platformCode}</Badge>
                          </div>
                        </div>
                      </div>
                      <div className="mt-2.5 space-y-1 text-[11px] text-secondary-text/95">
                        <div className="flex items-center gap-1">
                          <span className="text-muted-text">ID</span>
                          <span className="font-mono">#{p.id}</span>
                          {p.accountId ? (
                            <>
                              <span className="text-muted-text">· 账号</span>
                              <span className="font-mono truncate">{p.accountId}</span>
                            </>
                          ) : null}
                        </div>
                        {hints.length ? (
                          <div className="flex flex-wrap items-center gap-1">
                            <span className="text-muted-text">凭据</span>
                            {hints.slice(0, 4).map((k) => (
                              <span key={k} className="rounded border border-[hsl(var(--foreground)/0.08)] px-1.5 py-0.5 font-mono text-[10px]">
                                {k}
                              </span>
                            ))}
                            {hints.length > 4 && (
                              <span className="text-muted-text">+{hints.length - 4}</span>
                            )}
                          </div>
                        ) : null}
                        {p.defaultTarget ? (
                          <div className="flex items-center gap-1">
                            <span className="text-muted-text">目标</span>
                            <span className="truncate">{p.defaultTarget}</span>
                          </div>
                        ) : null}
                      </div>
                      <div className="mt-3 flex items-center justify-end gap-1">
                        <Button
                          size="sm"
                          variant={p.enabled ? 'secondary' : 'primary'}
                          onClick={() => onToggleEnabled(p)}
                        >
                          <BellRing className="h-3 w-3" />
                          {p.enabled ? '禁用' : '启用'}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => onDelete(p)}>
                          <Trash2 className="h-3 w-3" />
                          删除
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// ==================== 子组件：即时导出 ====================
const ExportPanel: React.FC<{
  title: string; setTitle: (v: string) => void;
  md: string; setMd: (v: string) => void;
  summary: string; setSummary: (v: string) => void;
  tagsInput: string; setTagsInput: (v: string) => void;
  output: { markdown: string; html: string; coseJson: string } | null;
  running: boolean;
  onExport: () => void;
}> = ({ title, setTitle, md, setMd, summary, setSummary, tagsInput, setTagsInput, output, running, onExport }) => {
  const tagList = tagsInput.split(',').map((s) => s.trim()).filter(Boolean);
  return (
    <div className="space-y-4 animate-fade-in">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        {/* 左：封面画布预览 */}
        <div className="lg:col-span-2">
          <ResearchCoverPreview
            title={title || undefined}
            summary={summary || undefined}
            content={md || undefined}
            tags={tagList}
          />
          <p className="mt-3 px-1 text-[11.5px] leading-relaxed text-secondary-text/95">
            左侧为研究报告发布时的「封面画布」效果。填写标题、摘要、正文和标签后，会同步呈现。
            正式在公众号 / 知乎等平台发布时，可将该封面作为首图或题图粘贴。
          </p>
        </div>

        {/* 右：表单 + 输出 */}
        <div className="space-y-4 lg:col-span-3">
          {/* 表单 */}
          <div className="terminal-card terminal-card-hover overflow-hidden">
            <div className="p-5">
              <div className="mb-4 flex flex-wrap items-center gap-2">
                <div>
                  <div className="label-uppercase text-purple/90">
                    <Copy className="h-3.5 w-3.5" />
                    Instant Export
                  </div>
                  <h3 className="mt-1.5 text-[17px] font-semibold">
                    即时<span className="title-gradient"> 导出</span>（无需平台凭据）
                  </h3>
                </div>
                <div className="ml-auto">
                  <Button variant="primary" disabled={running || !title} onClick={onExport}>
                    {running ? '导出中…' : (
                      <>
                        <Sparkles className="h-3.5 w-3.5" />
                        生成 &amp; 导出
                      </>
                    )}
                  </Button>
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                <div className="md:col-span-2">
                  <label className="label-xs mb-1 block">标题</label>
                  <Input value={title} onChange={(e) => setTitle(e.target.value)} className={INPUT_CLS} />
                </div>
                <div>
                  <label className="label-xs mb-1 block">摘要</label>
                  <Input value={summary} onChange={(e) => setSummary(e.target.value)} className={INPUT_CLS} />
                </div>
                <div>
                  <label className="label-xs mb-1 block">标签（逗号分隔）</label>
                  <Input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} className={INPUT_CLS} />
                </div>
                <div className="md:col-span-2">
                  <label className="label-xs mb-1 block">正文 Markdown</label>
                  <textarea
                    rows={12}
                    value={md}
                    onChange={(e) => setMd(e.target.value)}
                    className={
                      'resize-none rounded-xl border bg-transparent px-3 py-2 text-sm transition-all focus:outline-none ' +
                      INPUT_CLS
                    }
                  />
                </div>
              </div>
            </div>
          </div>

          {/* 输出 */}
          <div className="glass-card overflow-hidden">
            <div className="relative z-10 p-5">
              <div className="mb-3 flex items-center gap-2">
                <div>
                  <div className="label-uppercase text-primary/90">
                    <Send className="h-3.5 w-3.5" />
                    Export Output
                  </div>
                  <h3 className="mt-1 text-[15px] font-semibold">
                    导出输出（可复制或粘贴到浏览器扩展发布）
                  </h3>
                </div>
              </div>
              {!output ? (
                <EmptyState
                  title="暂无输出"
                  description="点击「生成 &amp; 导出」即可得到 Markdown / HTML / COSE 兼容 JSON 三份内容。"
                  className="min-h-[10rem] border-dashed bg-card/45 shadow-none"
                />
              ) : (
                <div className="flex flex-col gap-3">
                  <ExportBlock title="Markdown" value={output.markdown} />
                  <ExportBlock title="HTML" value={output.html} />
                  <ExportBlock
                    title="COSE 兼容 JSON（推荐用于浏览器扩展）"
                    value={output.coseJson}
                    mono
                  />
                  <p className="text-xs text-muted-text">
                    说明：也可把任意任务的目标平台设置为「通用导出」，在任务列表中直接执行即可获得同样输出。
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ExportBlock: React.FC<{ title: string; value: string; mono?: boolean }> = ({
  title,
  value,
  mono,
}) => (
  <div className="rounded-2xl border border-border/70 bg-card/60 p-3">
    <div className="mb-2 flex items-center justify-between gap-2">
      <span className="text-xs font-medium text-secondary-text">{title}</span>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => void copyToClipboard(value)}
      >
        <Copy className="h-3 w-3" />
        复制
      </Button>
    </div>
    <pre
      className={
        'max-h-56 overflow-auto rounded-xl bg-[var(--code-bg)] p-3 text-xs leading-6 text-foreground/90 ' +
        (mono ? 'font-mono whitespace-pre-wrap break-all' : 'whitespace-pre-wrap break-words')
      }
    >
      {value || '—'}
    </pre>
  </div>
);

export default MediaPublishPage;
