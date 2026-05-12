// ================================================
// DebugSQL – Auth API  (Phase 7)
//
// Typed request/response models and API functions for authentication.
// These functions are NOT called yet — auth is not implemented yet.
//
// Target endpoints:
//   POST /api/auth/login   → authenticate and receive a session token
//   GET  /api/auth/me      → load current user profile
//   POST /api/auth/logout  → invalidate the session
//
// TODO: Integrate authentication/session handling
// TODO: Persist session token in localStorage or httpOnly cookie
// TODO: Add token refresh flow for long-lived sessions
// ================================================

import { apiGet, apiPost } from './client';
import type { RequestOptions } from './client';

// ---- Types ----

export interface LoginRequest {
  email:    string;
  password: string;
}

export interface AuthSession {
  sessionId:    string;
  accessToken:  string;
  /** ISO 8601 expiry timestamp. */
  expiresAt:    string;
}

export interface UserProfile {
  id:    string;
  email: string;
  name:  string;
  /** Access level determining which features are visible. */
  role:  'admin' | 'analyst' | 'viewer';
}

// ---- API functions ----

/**
 * POST /api/auth/login
 *
 * Authenticates the user and returns a session token.
 *
 * TODO: Integrate authentication/session handling
 * TODO: Store accessToken and pass it in the Authorization header via client.ts
 */
export async function postLogin(
  body:     LoginRequest,
  options?: RequestOptions,
): Promise<AuthSession> {
  return apiPost<AuthSession>('/auth/login', body, options);
}

/**
 * GET /api/auth/me
 *
 * Returns the current user's profile for the active session.
 *
 * TODO: Call on app startup to initialize user context
 */
export async function getMe(options?: RequestOptions): Promise<UserProfile> {
  return apiGet<UserProfile>('/auth/me', options);
}

/**
 * POST /api/auth/logout
 *
 * Invalidates the current session on the backend.
 *
 * TODO: Clear local auth state and redirect to login on logout
 */
export async function postLogout(options?: RequestOptions): Promise<void> {
  return apiPost<void>('/auth/logout', {}, options);
}
