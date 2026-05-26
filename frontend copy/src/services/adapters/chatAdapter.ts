// ================================================
// DebugSQL – Chat Adapter  (Phase 7)
//
// Single injection point for the chat / AI query service.
// Components and contexts import ONLY from this file, never from mock
// services or API modules directly.
//
// To connect the real backend:
//   1. Set VITE_USE_MOCK_SERVICES=false in your .env
//   2. Uncomment the real API call below
//   3. Remove the mock branch
//
// TODO: Replace mock adapter with real backend API
// TODO: Integrate authentication/session handling — pass real sessionId
// TODO: Persist query history via backend session storage
// ================================================

import type { ChatQueryRequest, ChatQueryResponse } from '../api/chatApi';
import { getMockResponse } from '../mocks/mockChatService';

// ---------------------------------------------------------------------------
// Feature flag
// Defaults to true (mock) unless VITE_USE_MOCK_SERVICES is explicitly 'false'.
// ---------------------------------------------------------------------------

const USE_MOCK_SERVICES = import.meta.env.VITE_USE_MOCK_SERVICES !== 'false';

// ---------------------------------------------------------------------------
// Adapter
// ---------------------------------------------------------------------------

/**
 * Sends a natural-language message and returns the AI assistant's response.
 *
 * Currently routes to the mock chat service.
 * When the backend is ready, flip USE_MOCK_SERVICES and uncomment the real call.
 *
 * TODO: Replace mock adapter with postChatQuery() from chatApi.ts
 * TODO: Connect websocket/live execution updates for streaming responses
 * TODO: Extract planId from response and trigger query plan refresh
 */
export async function sendChatMessage(
  request: ChatQueryRequest,
  _signal?: AbortSignal,
): Promise<ChatQueryResponse> {
  if (USE_MOCK_SERVICES) {
    const content = await getMockResponse(request.message);
    return {
      content,
      // TODO: Backend will return a real planId linked to the generated query plan
      planId: `mock-plan-${Date.now()}`,
    };
  }

  // TODO: Replace with real API call:
  // const { postChatQuery } = await import('../api/chatApi');
  // return postChatQuery(request, { signal: _signal });
  throw new Error(
    '[chatAdapter] Real backend is not implemented yet. Set VITE_USE_MOCK_SERVICES=true.',
  );
}
