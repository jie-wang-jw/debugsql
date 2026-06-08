import { apiGet } from './client';
import type { DatasetContext } from './chatApi';
import type { ExecutionResultPreview } from '../../types/execution.types';

export interface AdminHistoryUser {
  id: string;
  email: string;
  displayName: string | null;
}

export interface AdminHistoryConversationSummary {
  id: string;
  sessionId: string;
  title: string | null;
  activePlanId: string | null;
  datasetContext?: DatasetContext | null;
  updatedAt: string;
  user: AdminHistoryUser;
}

export interface AdminHistorySummary {
  pagination: {
    limit: number;
    offset: number;
    totalConversations: number;
    hasMoreConversations: boolean;
  };
  conversations: AdminHistoryConversationSummary[];
}

export interface AdminHistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  planId?: string | null;
  sql?: string | null;
  datasetContext?: DatasetContext | null;
}

export interface AdminHistoryConversationDetail {
  id: string;
  sessionId: string;
  title: string | null;
  datasetContext?: DatasetContext | null;
  activePlanId?: string | null;
  latestExecutionRunId?: string | null;
  latestExecutionStatus?: string | null;
  latestExecutionResultPreview?: ExecutionResultPreview | null;
  updatedAt: string;
  user: AdminHistoryUser;
  messages: AdminHistoryMessage[];
  executionRuns: Array<{
    id: string;
    planId: string | null;
    runType: string;
    status: string;
    resultPreview?: ExecutionResultPreview | null;
    updatedAt: string;
  }>;
}

export function getAdminHistorySummary(params: { limit?: number; offset?: number } = {}) {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  return apiGet<AdminHistorySummary>(`/admin/history/summary${query ? `?${query}` : ''}`);
}

export function getAdminHistoryConversation(conversationId: string) {
  return apiGet<AdminHistoryConversationDetail>(`/admin/history/conversations/${conversationId}`);
}
