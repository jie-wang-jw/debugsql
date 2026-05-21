// ================================================
// DebugSQL - Auth API
//
// Current MVP behavior:
// - GET /auth/me returns the dev auto-login user when DEBUGSQL_AUTO_LOGIN=1.
// - POST /auth/logout is a stable placeholder until real sessions are added.
// - GitHub OAuth will later be mounted at /auth/github/login.
// ================================================

import { apiGet, apiPost, API_BASE_URL } from './client';

export interface CurrentUser {
  id: string;
  email: string;
  displayName?: string | null;
  avatarUrl?: string | null;
  authMode: string;
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiGet<CurrentUser>('/auth/me');
}

export async function logout(): Promise<void> {
  return apiPost<void>('/auth/logout', {});
}

export function githubLoginUrl(): string {
  return `${API_BASE_URL}/auth/github/login`;
}

export function googleLoginUrl(): string {
  return `${API_BASE_URL}/auth/google/login`;
}
