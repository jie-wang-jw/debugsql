import { apiGet } from './client';
import type { DatasetContext } from './chatApi';
import type { ProposedToolAction } from './chatApi';
import type { RequestOptions } from './client';
import type { ExecutionResultPreview } from '../../types/execution.types';

export interface HistoryConversationSummary {
  id: string;
  sessionId: string;
  title: string | null;
  activePlanId: string | null;
  updatedAt: string;
}

export interface HistorySummary {
  user: {
    id: string;
    email: string;
    displayName: string | null;
  };
  pagination?: {
    limit: number;
    offset: number;
    totalConversations: number;
    hasMoreConversations: boolean;
  };
  conversations: HistoryConversationSummary[];
  queryPlans: Array<{
    id: string;
    benchmark: string | null;
    dbId: string | null;
    template: string | null;
    updatedAt: string;
  }>;
  executionRuns: Array<{
    id: string;
    planId: string | null;
    runType: string;
    status: string;
    updatedAt: string;
  }>;
}

export interface HistorySummaryParams {
  limit?: number;
  offset?: number;
}

export interface HistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  planId?: string | null;
  sql?: string | null;
  datasetContext?: DatasetContext | null;
  proposedActions?: ProposedToolAction[];
  requiresApproval?: boolean | null;
  confidence?: number | null;
  assumptions?: string[];
  tablesUsed?: string[];
  explanation?: string | null;
}

export interface HistoryConversationDetail {
  id: string;
  sessionId: string;
  title: string | null;
  datasetContext?: DatasetContext | null;
  activePlanId?: string | null;
  latestExecutionRunId?: string | null;
  latestExecutionStatus?: string | null;
  latestExecutionResultPreview?: ExecutionResultPreview | null;
  updatedAt: string;
  messages: HistoryMessage[];
  executionRuns: Array<{
    id: string;
    planId: string | null;
    runType: string;
    status: string;
    resultPreview?: ExecutionResultPreview | null;
    updatedAt: string;
  }>;
}

export function getHistorySummary(
  params: HistorySummaryParams = {},
  options?: RequestOptions,
): Promise<HistorySummary> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) search.set('limit', String(params.limit));
  if (params.offset !== undefined) search.set('offset', String(params.offset));
  const query = search.toString();
  return apiGet<HistorySummary>(`/history/summary${query ? `?${query}` : ''}`, options);
}

export function getHistoryConversation(
  conversationId: string,
  options?: RequestOptions,
): Promise<HistoryConversationDetail> {
  return apiGet<HistoryConversationDetail>(`/history/conversations/${conversationId}`, options);
}
