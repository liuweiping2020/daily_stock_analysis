import apiClient from './index';
import { toCamelCase } from './utils';
import type {
  PlatformSpec,
  PlatformRow,
  PublishTaskRow,
  UpsertPlatformRequest,
  CreateTasksRequest,
  ExportNowRequest,
  ExportNowResponse,
  BatchRunResponse,
  TaskStatus,
} from '../types/mediaPublish';

function snakeBody<T extends Record<string, unknown>>(payload: T): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(payload)) {
    const snake = key.replace(/[A-Z]/g, (m) => `_${m.toLowerCase()}`);
    out[snake] = value;
  }
  return out;
}

export const mediaPublishApi = {
  // ---- Platforms ----
  listSpecs: async (): Promise<PlatformSpec[]> => {
    const res = await apiClient.get<unknown[]>('/api/v1/media/platforms/specs');
    return (res.data || []).map((d) => toCamelCase<PlatformSpec>(d));
  },

  listPlatforms: async (onlyEnabled = false): Promise<PlatformRow[]> => {
    const res = await apiClient.get<unknown[]>('/api/v1/media/platforms', {
      params: { only_enabled: onlyEnabled },
    });
    return (res.data || []).map((d) => toCamelCase<PlatformRow>(d));
  },

  getPlatform: async (id: number): Promise<PlatformRow> => {
    const res = await apiClient.get<Record<string, unknown>>(`/api/v1/media/platforms/${id}`);
    return toCamelCase<PlatformRow>(res.data);
  },

  upsertPlatform: async (body: UpsertPlatformRequest): Promise<PlatformRow> => {
    const res = await apiClient.post<Record<string, unknown>>(
      '/api/v1/media/platforms',
      snakeBody(body as unknown as Record<string, unknown>),
    );
    return toCamelCase<PlatformRow>(res.data);
  },

  setEnabled: async (id: number, enabled: boolean): Promise<void> => {
    await apiClient.patch(`/api/v1/media/platforms/${id}/enabled`, { enabled });
  },

  deletePlatform: async (id: number): Promise<void> => {
    await apiClient.delete(`/api/v1/media/platforms/${id}`);
  },

  // ---- Tasks ----
  createTasks: async (body: CreateTasksRequest): Promise<PublishTaskRow[]> => {
    const res = await apiClient.post<unknown[]>(
      '/api/v1/media/tasks',
      snakeBody(body as unknown as Record<string, unknown>),
    );
    return (res.data || []).map((d) => toCamelCase<PublishTaskRow>(d));
  },

  listTasks: async (params?: {
    sourceType?: string;
    sourceRefId?: number;
    platformCode?: string;
    status?: TaskStatus | string;
    limit?: number;
    offset?: number;
  }): Promise<PublishTaskRow[]> => {
    const query: Record<string, unknown> = {};
    if (params?.sourceType) query.source_type = params.sourceType;
    if (params?.sourceRefId != null) query.source_ref_id = params.sourceRefId;
    if (params?.platformCode) query.platform_code = params.platformCode;
    if (params?.status) query.status = params.status;
    if (params?.limit != null) query.limit = params.limit;
    if (params?.offset != null) query.offset = params.offset;
    const res = await apiClient.get<unknown[]>('/api/v1/media/tasks', { params: query });
    return (res.data || []).map((d) => toCamelCase<PublishTaskRow>(d));
  },

  getTask: async (id: number): Promise<PublishTaskRow> => {
    const res = await apiClient.get<Record<string, unknown>>(`/api/v1/media/tasks/${id}`);
    return toCamelCase<PublishTaskRow>(res.data);
  },

  runTask: async (id: number, force = false): Promise<PublishTaskRow> => {
    const res = await apiClient.post<Record<string, unknown>>(
      `/api/v1/media/tasks/${id}/run`,
      null,
      { params: { force } },
    );
    return toCamelCase<PublishTaskRow>(res.data);
  },

  runBatch: async (limit = 20, includeScheduled = true): Promise<BatchRunResponse> => {
    const res = await apiClient.post<Record<string, unknown>>(
      '/api/v1/media/tasks/run-batch',
      null,
      { params: { limit, include_scheduled: includeScheduled } },
    );
    return toCamelCase<BatchRunResponse>(res.data);
  },

  retryTask: async (id: number): Promise<PublishTaskRow> => {
    const res = await apiClient.post<Record<string, unknown>>(
      `/api/v1/media/tasks/${id}/retry`,
    );
    return toCamelCase<PublishTaskRow>(res.data);
  },

  cancelTask: async (id: number): Promise<PublishTaskRow> => {
    const res = await apiClient.post<Record<string, unknown>>(
      `/api/v1/media/tasks/${id}/cancel`,
    );
    return toCamelCase<PublishTaskRow>(res.data);
  },

  // ---- One-shot export ----
  exportNow: async (body: ExportNowRequest): Promise<ExportNowResponse> => {
    const res = await apiClient.post<Record<string, unknown>>(
      '/api/v1/media/export/now',
      snakeBody(body as unknown as Record<string, unknown>),
    );
    return toCamelCase<ExportNowResponse>(res.data);
  },
};
