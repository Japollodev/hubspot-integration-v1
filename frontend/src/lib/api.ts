/** Typed fetch wrapper. All backend calls go through here so errors are handled uniformly. */

export const API_BASE = import.meta.env.VITE_API_BASE ?? '/api';

export interface ApiErrorBody {
  code: string;
  message: string;
  details?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details?: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.details = body.details;
  }
}

function isErrorEnvelope(value: unknown): value is { error: ApiErrorBody } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as { error: unknown }).error === 'object'
  );
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { Accept: 'application/json', ...init?.headers },
  });

  const contentType = res.headers.get('content-type') ?? '';
  const body: unknown = contentType.includes('application/json') ? await res.json() : null;

  if (!res.ok) {
    throw new ApiError(
      res.status,
      isErrorEnvelope(body) ? body.error : { code: 'http_error', message: res.statusText },
    );
  }
  return body as T;
}

export interface HealthResponse {
  status: 'ok';
  version: string;
}

export const getHealth = (signal?: AbortSignal) => apiFetch<HealthResponse>('/health', { signal });

/** Mirrors backend/app/schemas/uploads.py. */
export type HubSpotStatus = 'pending' | 'uploaded' | 'failed' | 'skipped';

export type Legibility = 'clear' | 'partial' | 'unreadable' | 'absent';

/** What the extractor saw for one field, kept for review. */
export interface FieldEvidence {
  legibility: Legibility;
  source_text: string | null;
  note: string | null;
}

export type ContactFieldName = 'first_name' | 'last_name' | 'email' | 'phone' | 'job_title';

/** Extracted contact. null = absent or unreadable on the card (see `evidence` for why). */
export interface ContactFields {
  extractor: string;
  status: 'succeeded' | 'failed';
  model: string | null;
  error_code: string | null;
  error: string | null;
  evidence: Partial<Record<ContactFieldName, FieldEvidence>>;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  job_title: string | null;
}

export interface UploadResponse {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  hubspot: {
    status: HubSpotStatus;
    file_id: string | null;
    url: string | null;
    error: string | null;
  };
  contact: ContactFields | null;
}

/** GET /api/uploads/:id — the stored upload and contact, read back from Postgres. */
export const getUpload = (id: string, signal?: AbortSignal) =>
  apiFetch<UploadResponse>(`/uploads/${encodeURIComponent(id)}`, { signal });

/** Header carrying the user's own OpenAI key (bring-your-own-key). */
export const OPENAI_KEY_HEADER = 'X-OpenAI-Key';

/** Error codes meaning "the user must (re-)enter their OpenAI key". */
export const OPENAI_KEY_ERRORS = new Set(['openai_key_missing', 'openai_key_invalid']);

/**
 * POST /api/uploads. No Content-Type header: the browser adds the multipart boundary.
 * `openaiKey` is the user's key; omit it only when the server has a dev fallback key.
 */
export function uploadPhoto(file: File, signal?: AbortSignal, openaiKey?: string | null) {
  const body = new FormData();
  body.append('file', file);
  const headers: Record<string, string> = openaiKey ? { [OPENAI_KEY_HEADER]: openaiKey } : {};
  return apiFetch<UploadResponse>('/uploads', { method: 'POST', body, signal, headers });
}

export interface OpenAIStatus {
  /** True when the server has a dev-only key it will use if the browser sends none. */
  server_key_available: boolean;
  model: string;
}

export const getOpenAIStatus = (signal?: AbortSignal) =>
  apiFetch<OpenAIStatus>('/openai/status', { signal });

export interface VerifyResult {
  valid: boolean;
  message: string | null;
}

/** POST /api/openai/verify — checks the key can authenticate and use the configured model. */
export const verifyOpenAIKey = (key: string, signal?: AbortSignal) =>
  apiFetch<VerifyResult>('/openai/verify', {
    method: 'POST',
    headers: { [OPENAI_KEY_HEADER]: key },
    signal,
  });
