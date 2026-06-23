import { apiGet, apiPost } from './client';
import type { RequestOptions } from './client';
import type { DatasetContext } from './chatApi';

export type DbType = 'sqlite_benchmark' | 'postgres';

export interface ConnectorCapabilities {
  dbType: DbType;
  label: string;
  supportsExplain: boolean;
  supportsSampleRows: boolean;
  supportsRelationships: boolean;
  readOnly: boolean;
  maxRows: number;
  maxSampleRows: number;
}

export interface ToolDefinition {
  name: string;
  label: string;
  description: string;
  requiresApproval: boolean;
  parameters: Record<string, string>;
}

export interface CapabilityExample {
  id: string;
  kind: 'prompt' | 'sql';
  label: string;
  content: string;
}

export interface CapabilitiesResponse {
  context: DatasetContext & { dbType?: DbType };
  connector: ConnectorCapabilities;
  tools: ToolDefinition[];
  schemaPreview: Record<string, unknown>;
  policies: Record<string, unknown>;
  examples: CapabilityExample[];
}

export interface ToolExecuteRequest {
  tool: string;
  toolCallId?: string;
  arguments: Record<string, unknown>;
  context: DatasetContext & { dbType?: DbType };
  approved?: boolean;
  sessionId?: string;
}

export interface ToolResult {
  toolCallId: string;
  tool: string;
  success: boolean;
  data: Record<string, unknown>;
  error?: string | null;
}

export async function getCapabilities(
  params: Partial<DatasetContext & { dbType: DbType }>,
  options?: RequestOptions,
): Promise<CapabilitiesResponse> {
  const search = new URLSearchParams();
  if (params.dbType) search.set('dbType', params.dbType);
  if (params.benchmark) search.set('benchmark', params.benchmark);
  if (params.dbId) search.set('dbId', params.dbId);
  const query = search.toString();
  return apiGet<CapabilitiesResponse>(`/capabilities${query ? `?${query}` : ''}`, options);
}

export async function executeTool(
  body: ToolExecuteRequest,
  options?: RequestOptions,
): Promise<ToolResult> {
  return apiPost<ToolResult>('/tools/execute', body, options);
}
