import { apiGet } from './client';
import type { DatasetContext } from './chatApi';
import type { RequestOptions } from './client';

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

export interface HistoryMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  planId?: string | null;
  sql?: string | null;
  datasetContext?: DatasetContext | null;
}

export interface HistoryConversationDetail {
  id: string;
  sessionId: string;
  title: string | null;
  datasetContext?: DatasetContext | null;
  activePlanId?: string | null;
  updatedAt: string;
  messages: HistoryMessage[];
  executionRuns: Array<{
    id: string;
    planId: string | null;
    runType: string;
    status: string;
    resultPreview?: unknown;
    updatedAt: string;
  }>;
}

export function getHistorySummary(options?: RequestOptions): Promise<HistorySummary> {
  return apiGet<HistorySummary>('/history/summary', options);
}

export function getHistoryConversation(
  conversationId: string,
  options?: RequestOptions,
): Promise<HistoryConversationDetail> {
  return apiGet<HistoryConversationDetail>(`/history/conversations/${conversationId}`, options);
}
