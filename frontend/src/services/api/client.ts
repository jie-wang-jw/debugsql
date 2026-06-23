// ================================================
// DebugSQL – Centralized API Client  (Phase 7)
//
// Single HTTP client used by every real API function in api/*.ts.
// Mock services bypass this client entirely — they are routed by the
// adapter layer (services/adapters/*.ts).
//
// TODO: Add request retry logic with exponential back-off
// TODO: Integrate with global toast/notification system for API errors
// TODO: Add request/response interceptors for logging and telemetry
// ================================================

import type { ApiError, ApiResponse } from '../../types/api.types';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Backend base URL — injected from the Vite environment at build time.
 *
 * Development default : /api  (proxied by Vite or Docker Compose)
 * Production          : set VITE_API_BASE_URL in your deployment environment
 *
 * TODO: Add environment-specific configuration (dev / staging / prod)
 */
export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? '/api';

/** Default request timeout in milliseconds. */
export const DEFAULT_TIMEOUT_MS = 30_000;

// ---------------------------------------------------------------------------
// Request options
// ---------------------------------------------------------------------------

export interface RequestOptions {
  /** Caller-provided AbortSignal for manual cancellation. */
  signal?:  AbortSignal;
  /** Override the default timeout (ms). */
  timeout?: number;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

/** Thrown by the API client when the backend returns a non-2xx status. */
export class ApiClientError extends Error {
  constructor(
    message:                     string,
    public readonly statusCode:  number,
    public readonly apiError?:   ApiError,
  ) {
    super(message);
    this.name = 'ApiClientError';
  }
}

// ---------------------------------------------------------------------------
// Core request function
// ---------------------------------------------------------------------------

async function request<T>(
  method:  'GET' | 'POST' | 'PATCH' | 'DELETE',
  path:    string,
  body?:   unknown,
  options: RequestOptions = {},
): Promise<T> {
  const { signal, timeout = DEFAULT_TIMEOUT_MS } = options;

  // Combine caller signal with a timeout signal
  const timeoutSignal  = AbortSignal.timeout(timeout);
  const effectiveSignal = signal
    ? AbortSignal.any([signal, timeoutSignal])
    : timeoutSignal;

  const url = `${API_BASE_URL}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        // Auth uses the httpOnly debugsql_session cookie via credentials: 'include'.
      },
      body:   body !== undefined ? JSON.stringify(body) : undefined,
      signal: effectiveSignal,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'request failed';
    throw new Error(`${method} ${url}: ${message}`);
  }

  if (!response.ok) {
    let apiError: ApiError | undefined;
    let detail: string | undefined;
    try {
      const errBody = await response.json() as { detail?: string; error?: ApiError };
      apiError = errBody.error;
      detail = typeof errBody.detail === 'string' ? errBody.detail : undefined;
    } catch {
      // Response body was not valid JSON — ignore and use status text.
    }
    throw new ApiClientError(
      `${method} ${url}: ${
        apiError?.message ?? detail ?? `HTTP ${response.status} ${response.statusText}`
      }`,
      response.status,
      apiError,
    );
  }

  const envelope = await response.json() as ApiResponse<T>;
  return envelope.data;
}

// ---------------------------------------------------------------------------
// Method helpers — imported by api/*.ts files
// ---------------------------------------------------------------------------

export const apiGet = <T>(
  path: string,
  options?: RequestOptions,
): Promise<T> => request<T>('GET', path, undefined, options);

export const apiPost = <T>(
  path:    string,
  body:    unknown,
  options?: RequestOptions,
): Promise<T> => request<T>('POST', path, body, options);

export const apiPatch = <T>(
  path:    string,
  body:    unknown,
  options?: RequestOptions,
): Promise<T> => request<T>('PATCH', path, body, options);

export const apiDelete = <T>(
  path: string,
  options?: RequestOptions,
): Promise<T> => request<T>('DELETE', path, undefined, options);
