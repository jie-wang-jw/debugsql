// ================================================
// DebugSQL - Chat Adapter
//
// Single injection point for the chat / AI query service.
// Components and contexts import only from this file.
//
// Default mode calls the real backend API. Set VITE_USE_MOCK_SERVICES=true
// only when intentionally running isolated frontend mock services.
//
// TODO: Integrate authentication/session handling and pass a real sessionId.
// TODO: Persist query history via backend session storage.
// ================================================

import type { ChatQueryRequest, ChatQueryResponse } from '../api/chatApi';
import { getMockResponse } from '../mocks/mockChatService';

const USE_MOCK_SERVICES = import.meta.env.VITE_USE_MOCK_SERVICES === 'true';

/**
 * Sends a natural-language message and returns the assistant response.
 *
 * The real backend returns the assistant text plus a planId. The mock branch
 * is kept only for frontend-only development and visual testing.
 */
export async function sendChatMessage(
  request: ChatQueryRequest,
  _signal?: AbortSignal,
): Promise<ChatQueryResponse> {
  if (USE_MOCK_SERVICES) {
    const content = await getMockResponse(request.message);
    return {
      content,
      planId: `mock-plan-${Date.now()}`,
    };
  }

  const { postChatQuery } = await import('../api/chatApi');
  return postChatQuery(request, { signal: _signal });
}
