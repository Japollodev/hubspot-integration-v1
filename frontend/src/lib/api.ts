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
}

/** POST /api/uploads. No Content-Type header: the browser adds the multipart boundary. */
export function uploadPhoto(file: File, signal?: AbortSignal) {
  const body = new FormData();
  body.append('file', file);
  return apiFetch<UploadResponse>('/uploads', { method: 'POST', body, signal });
}
