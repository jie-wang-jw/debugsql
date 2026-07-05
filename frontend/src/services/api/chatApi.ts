// ================================================
// DebugSQL - Chat / AI Query API
//
// Typed request/response models and API functions for the live backend chat
// endpoint. The active adapter calls these functions unless mock mode is
// explicitly enabled.
//
// Backend endpoints:
//   POST /api/query
//   GET  /api/sessions/:id/messages
// ================================================

import { apiGet, apiPost } from './client';
import type { RequestOptions } from './client';

export interface ChatQueryRequest {
  /** The natural-language message typed by the user. */
  message: string;
  /** Active session ID for conversation continuity. */
  sessionId: string;
  /** Optional benchmark/database selection for schema-aware planning. */
  datasetContext?: DatasetContext;
}

export interface SessionMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  planId?: string;
}

export interface DatasetContext {
  dbType?: 'sqlite_benchmark' | 'postgres' | 'multimodal_demo';
  benchmark?: string;
  dbId?: string;
}

export interface ProposedToolAction {
  id: string;
  tool: string;
  label: string;
  description?: string;
  arguments: Record<string, unknown>;
  requiresApproval: boolean;
}

export interface ChatQueryResponse {
  /** The assistant's markdown response text. */
  content: string;
  /** Classified backend intent for routing/debugging. */
  intentType?: 'help' | 'benchmark_query' | 'edit_plan' | 'unsupported' | 'error';
  /** Whether the backend created a query plan for this response. */
  requiresPlan?: boolean;
  /** Whether the frontend should trigger execution after loading the plan. */
  requiresExecution?: boolean;
  /** Backend-generated query plan ID used to fetch the full plan graph. */
  planId?: string | null;
  /** Generated SQL, if the backend exposes it directly. */
  sql?: string;
  /** Human-readable explanation of the plan choices. */
  explanation?: string;
  proposedActions?: ProposedToolAction[];
  requiresApproval?: boolean;
  confidence?: number | null;
  assumptions?: string[];
  tablesUsed?: string[];
  usedContext?: boolean;
  conversationMode?: 'new_query' | 'refine_query' | 'schema_answer' | 'clarify' | null;
  workingStateRevision?: number | null;
  mediaMatches?: Array<Record<string, unknown>>;
  mediaPredicate?: string | null;
  mediaType?: string | null;
  mediaLimit?: number | null;
}

/**
 * Sends a natural-language query to the backend AI/demo pipeline.
 * Returns the assistant response and planId for QueryPlan loading.
 */
export async function postChatQuery(
  body: ChatQueryRequest,
  options?: RequestOptions,
): Promise<ChatQueryResponse> {
  return apiPost<ChatQueryResponse>('/query', body, options);
}

/**
 * Loads persisted chat history for a session.
 * TODO: Implement backend persistence and auth-aware session handling.
 */
export async function getSessionMessages(
  sessionId: string,
  options?: RequestOptions,
): Promise<SessionMessage[]> {
  return apiGet<SessionMessage[]>(`/sessions/${sessionId}/messages`, options);
}
