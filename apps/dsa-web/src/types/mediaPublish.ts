export type PlatformSpec = {
  platformCode: string;
  platformName: string;
  requiredCredentialKeys: string[];
};

export type PlatformRow = {
  id: number;
  platformCode: string;
  displayName: string;
  accountId?: string | null;
  credentialsKeyHints: string[] | Record<string, unknown>;
  enabled: boolean;
  defaultTarget?: string | null;
  extra?: Record<string, unknown> | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type TaskStatus =
  | 'pending'
  | 'queued'
  | 'running'
  | 'published'
  | 'failed'
  | 'retried'
  | 'cancelled';

export type PublishTaskRow = {
  id: number;
  sourceType: 'analysis' | 'market_review' | 'manual';
  sourceRefId?: number | null;
  sourceDisplayName?: string | null;
  title: string;
  summary?: string | null;
  platformId: number;
  platformCode: string;
  targetLocation?: string | null;
  status: TaskStatus;
  scheduleAt?: string | null;
  executeStartedAt?: string | null;
  executedAt?: string | null;
  retryCount: number;
  maxRetries: number;
  remoteArticleId?: string | null;
  remoteUrl?: string | null;
  errorCode?: string | null;
  errorMessage?: string | null;
  tags: string[];
  extra?: Record<string, unknown> | null;
  createdAt?: string | null;
  updatedAt?: string | null;
};

export type UpsertPlatformRequest = {
  platformCode: string;
  displayName: string;
  accountId?: string;
  credentials?: Record<string, unknown>;
  extra?: Record<string, unknown>;
  enabled?: boolean;
  defaultTarget?: string;
};

export type CreateTasksRequest = {
  sourceType: 'analysis' | 'market_review' | 'manual';
  sourceRefId?: number;
  sourceDisplayName?: string;
  title?: string;
  contentMarkdown?: string;
  contentHtml?: string;
  summary?: string;
  coverUrl?: string;
  tags?: string[];
  originalAuthor?: string;
  platformIds?: number[];
  platformCodes?: string[];
  scheduleAt?: string;
  maxRetries?: number;
};

export type ExportNowRequest = {
  title: string;
  contentMarkdown?: string;
  contentHtml?: string;
  summary?: string;
  tags?: string[];
  coverUrl?: string;
  originalAuthor?: string;
  referenceDate?: string;
  targetPlatformCodes?: string[];
};

export type ExportNowResponse = {
  export: {
    ok: boolean;
    articleId?: string | null;
    extra?: Record<string, unknown> & {
      frontends?: {
        copyMarkdown: string;
        copyHtml: string;
        copyCoseJson: string;
      };
    };
  };
  tasksCreated: PublishTaskRow[];
};

export type BatchRunResponse = {
  total: number;
  published: number;
  failed: number;
  items: Array<{
    id: number;
    status: TaskStatus;
    errorCode?: string | null;
  }>;
};
