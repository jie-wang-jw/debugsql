// ================================================
// DebugSQL - Benchmark API
//
// Dataset/database registry used by the frontend selector. The current backend
// exposes Spider metadata and leaves BIRD as a placeholder until downloaded.
// ================================================

import { apiGet } from './client';
import type { RequestOptions } from './client';

export interface BenchmarkInfo {
  id: string;
  label: string;
  status: 'ready' | 'missing' | 'placeholder' | string;
  databaseCount: number;
}

export interface BenchmarkDatabaseInfo {
  benchmark: string;
  dbId: string;
  label: string;
  hasSQLite: boolean;
  tableCount: number;
  sampleQuestions: Array<{
    question: string;
    query?: string;
  }>;
}

export async function getBenchmarks(options?: RequestOptions): Promise<BenchmarkInfo[]> {
  return apiGet<BenchmarkInfo[]>('/benchmarks', options);
}

export async function getBenchmarkDatabases(
  benchmark: string,
  options?: RequestOptions,
): Promise<BenchmarkDatabaseInfo[]> {
  return apiGet<BenchmarkDatabaseInfo[]>(`/benchmarks/${benchmark}/databases`, options);
}
