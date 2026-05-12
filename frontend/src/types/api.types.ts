// ================================================
// DebugSQL – Shared API & async types  (Phase 7)
//
// These types describe the contract between the frontend and the backend.
// Used by services/api/*.ts (real API calls) and services/adapters/*.ts.
// ================================================

// ---- Generic API envelope ----

/** Standard envelope wrapping every backend response body. */
export interface ApiResponse<T> {
  data:     T;
  success:  boolean;
  message?: string;
}

/** Error shape returned by the backend on 4xx / 5xx responses. */
export interface ApiError {
  code:     string;
  message:  string;
  details?: Record<string, unknown>;
}

// ---- Async state ----

/**
 * Reusable loading / error / data state for any async resource.
 *
 * Replaces ad-hoc isLoading + error + data triples in component state.
 */
export interface AsyncState<T> {
  data:      T | null;
  isLoading: boolean;
  error:     string | null;
}

/** Returns a blank AsyncState — convenient default value. */
export function createAsyncState<T>(): AsyncState<T> {
  return { data: null, isLoading: false, error: null };
}

// ---- Pagination ----

export interface PaginationMeta {
  page:       number;
  pageSize:   number;
  totalCount: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  meta:  PaginationMeta;
}

// ---- Session ----

/** Opaque session identifier passed with every authenticated API request. */
export type SessionId = string;
