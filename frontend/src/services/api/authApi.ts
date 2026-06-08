// ================================================
// DebugSQL - Auth API
//
// Current behavior:
// - GET /auth/me returns the active cookie-backed session user.
// - POST /auth/email/request-code sends or logs a short-lived verification code.
// - POST /auth/email/verify-code verifies the code and creates a cookie session.
// ================================================

import { apiGet, apiPost } from './client';

export interface CurrentUser {
  id: string;
  email: string;
  displayName?: string | null;
  avatarUrl?: string | null;
  authMode: string;
  isAdmin: boolean;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiGet<CurrentUser>('/auth/me');
}

export async function logout(): Promise<void> {
  return apiPost<void>('/auth/logout', {});
}

export interface EmailCodeRequestResult {
  email: string;
  expiresInSeconds: number;
  resendAfterSeconds: number;
  delivery: 'smtp' | 'dev_log';
  warning?: string;
}

export async function requestEmailCode(email: string): Promise<EmailCodeRequestResult> {
  return apiPost<EmailCodeRequestResult>('/auth/email/request-code', { email });
}

export async function verifyEmailCode(email: string, code: string): Promise<CurrentUser> {
  return apiPost<CurrentUser>('/auth/email/verify-code', { email, code });
}
