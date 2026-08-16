import type React from 'react';
import { useEffect, useMemo, useState } from 'react';
import {
  BadgeCheck,
  BellRing,
  Copy,
  Megaphone,
  Play,
  Plus,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  SquarePen,
  Trash2,
  XCircle,
} from 'lucide-react';
import {
  ApiErrorAlert,
  Badge,
  Button,
  Card,
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

  return (
    <div className="min-h-full flex flex-col rounded-[1.5rem] bg-transparent">
      <header className="flex-shrink-0 border-b border-white/5 px-3 py-3 sm:px-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-primary-gradient text-[hsl(var(--primary-foreground))] shadow-[0_12px_28px_var(--nav-brand-shadow)]">
            <Megaphone className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <h1 className="text-base font-semibold">多平台发布</h1>
            <p className="text-xs text-muted-text">
              公众号草稿 / 知乎 / 雪球 / 微博 / 头条 & 通用剪贴板（COSE 兼容）
            </p>
          </div>
          <div className="ml-auto flex flex-wrap items-center gap-1 rounded-2xl border border-border bg-card/50 p-1">
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
                  'flex items-center gap-1.5 rounded-xl px-3 py-1.5 text-xs transition-all ' +
                  (tab === key
                    ? 'bg-primary text-[hsl(var(--primary-foreground))] shadow'
                    : 'text-secondary-text hover:text-foreground')
                }
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>
        </div>
        {pageError ? (
          <ApiErrorAlert
            error={pageError}
            onDismiss={() => setPageError(null)}
            dismissLabel="关闭"
            className="mt-2"
          />
        ) : null}
      </header>

      <main className="min-h-0 flex-1 flex-col gap-3 overflow-y-auto p-3 sm:p-4">
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
    <div className="flex flex-col gap-3 lg:flex-row">
      <Card variant="bordered" padding="md" className="flex-1">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="label-uppercase">创建发布任务</span>
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
              placeholder="发布标题（必填）"
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
              rows={8}
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
            <label className="label-xs mb-1 block">标签（用英文逗号分隔）</label>
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
              发布目标平台 *（选中 {selectedPlatformIds.length} 个）
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
                      'flex items-center gap-1.5 rounded-2xl border px-3 py-1.5 text-xs transition-all ' +
                      (selectedPlatformIds.includes(p.id)
                        ? 'border-primary/60 bg-primary/10 text-primary'
                        : 'border-border text-secondary-text hover:text-foreground')
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
        <div className="mt-3 flex items-center justify-end gap-2">
          <Button variant="primary" onClick={onCreateTasks}>
            <Plus className="h-3.5 w-3.5" />
            创建发布任务
          </Button>
        </div>
      </Card>

      <Card variant="bordered" padding="md" className="flex-1 lg:min-w-[560px]">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="label-uppercase">任务列表</span>
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
            description="先在左侧创建一条任务，或选择即时导出。"
            className="min-h-[10rem] border-dashed bg-card/45 shadow-none"
          />
        ) : (
          <div className="max-h-[65vh] space-y-2 overflow-y-auto pr-1">
            {tasks.map((t) => (
              <div
                key={t.id}
                className="flex flex-col gap-2 rounded-2xl border border-border/70 bg-card/50 p-3 text-sm"
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
      </Card>
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
}) => (
  <div className="flex flex-col gap-3 lg:flex-row">
    <Card variant="bordered" padding="md" className="flex-1">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="label-uppercase">注册 / 更新平台凭据</span>
        <Button size="sm" variant="secondary" onClick={onRefresh}>
          <RefreshCw className="h-3.5 w-3.5" />
          刷新
        </Button>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
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
        <div className="md:col-span-2">
          <label className="label-xs mb-1 block">凭据字段</label>
          {credentialFields.length === 0 ? (
            <p className="text-xs text-muted-text">
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
                    placeholder="对应值（不显示明文，API 端也脱敏回传）"
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
      <div className="mt-3 flex items-center justify-between gap-2">
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
    </Card>

    <Card variant="bordered" padding="md" className="flex-1 lg:min-w-[520px]">
      <div className="mb-3 flex items-center gap-2">
        <span className="label-uppercase">已注册平台（{platforms.length}）</span>
      </div>
      {platformsLoading ? (
        <EmptyState title="加载中" description="获取平台列表" className="min-h-[10rem] border-dashed bg-card/45 shadow-none" />
      ) : platforms.length === 0 ? (
        <EmptyState
          title="尚未注册"
          description="建议先注册一个「通用导出」平台，作为任何情况下的保底发布出口。"
          className="min-h-[10rem] border-dashed bg-card/45 shadow-none"
        />
      ) : (
        <div className="max-h-[65vh] space-y-2 overflow-y-auto pr-1">
          {platforms.map((p) => (
            <div
              key={p.id}
              className="rounded-2xl border border-border/70 bg-card/50 p-3 text-sm"
            >
              <div className="flex flex-wrap items-start gap-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{p.displayName}</span>
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
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-text">
                    <span>ID: {p.id}</span>
                    {p.accountId ? (
                      <>
                        <span>·</span>
                        <span>账号: {p.accountId}</span>
                      </>
                    ) : null}
                    {Array.isArray(p.credentialsKeyHints) && p.credentialsKeyHints.length ? (
                      <>
                        <span>·</span>
                        <span>
                          凭据键: {p.credentialsKeyHints.join(', ')}
                        </span>
                      </>
                    ) : null}
                    {typeof p.credentialsKeyHints === 'object' && p.credentialsKeyHints && !Array.isArray(p.credentialsKeyHints) ? (
                      <>
                        <span>·</span>
                        <span>
                          凭据: {Object.keys(p.credentialsKeyHints as Record<string, unknown>).join(', ')}
                        </span>
                      </>
                    ) : null}
                    {p.defaultTarget ? (
                      <>
                        <span>·</span>
                        <span>目标: {p.defaultTarget}</span>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="flex flex-wrap justify-end gap-1">
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
            </div>
          ))}
        </div>
      )}
    </Card>
  </div>
);

// ==================== 子组件：即时导出 ====================
const ExportPanel: React.FC<{
  title: string; setTitle: (v: string) => void;
  md: string; setMd: (v: string) => void;
  summary: string; setSummary: (v: string) => void;
  tagsInput: string; setTagsInput: (v: string) => void;
  output: { markdown: string; html: string; coseJson: string } | null;
  running: boolean;
  onExport: () => void;
}> = ({ title, setTitle, md, setMd, summary, setSummary, tagsInput, setTagsInput, output, running, onExport }) => (
  <div className="flex flex-col gap-3 lg:flex-row">
    <Card variant="bordered" padding="md" className="flex-1">
      <div className="mb-3 flex items-center gap-2">
        <span className="label-uppercase">即时导出（无需平台凭据）</span>
        <div className="ml-auto">
          <Button variant="primary" disabled={running || !title} onClick={onExport}>
            {running ? '导出中…' : (
              <>
                <Copy className="h-3.5 w-3.5" />
                生成 & 导出
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
            rows={14}
            value={md}
            onChange={(e) => setMd(e.target.value)}
            className={
              'resize-none rounded-xl border bg-transparent px-3 py-2 text-sm transition-all focus:outline-none ' +
              INPUT_CLS
            }
          />
        </div>
      </div>
    </Card>

    <Card variant="bordered" padding="md" className="flex-1 lg:min-w-[520px]">
      <div className="mb-3 flex items-center gap-2">
        <span className="label-uppercase">导出输出（可复制或粘贴到浏览器扩展发布）</span>
      </div>
      {!output ? (
        <EmptyState
          title="暂无输出"
          description="点击「生成 & 导出」即可得到 Markdown / HTML / COSE 兼容 JSON 三份内容。"
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
    </Card>
  </div>
);

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
