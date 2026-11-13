import { useEffect, useRef, useState, type FormEvent } from 'react';
import { ApiError, uploadPhoto, type HubSpotStatus, type UploadResponse } from '../../lib/api';
import { formatBytes } from '../../lib/format';

/** Keep in sync with MAX_UPLOAD_MB on the server; the server check is authoritative. */
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const ACCEPT = 'image/jpeg,image/png,image/webp,image/heic,image/heif';

type State =
  | { kind: 'idle' }
  | { kind: 'uploading' }
  | { kind: 'done'; result: UploadResponse }
  | { kind: 'error'; message: string };

const hubspotLabel: Record<HubSpotStatus, { text: string; className: string }> = {
  uploaded: { text: 'Saved to HubSpot', className: 'bg-emerald-100 text-emerald-800' },
  skipped: { text: 'HubSpot skipped (no token)', className: 'bg-slate-100 text-slate-700' },
  failed: { text: 'HubSpot upload failed', className: 'bg-amber-100 text-amber-800' },
  pending: { text: 'HubSpot pending', className: 'bg-slate-100 text-slate-700' },
};

export function UploadForm() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [state, setState] = useState<State>({ kind: 'idle' });
  const abortRef = useRef<AbortController | null>(null);
  const previewRef = useRef<string | null>(null);

  // On unmount: cancel any in-flight upload and free the preview object URL.
  useEffect(
    () => () => {
      abortRef.current?.abort();
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    },
    [],
  );

  function replacePreview(next: File | null) {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = next ? URL.createObjectURL(next) : null;
    setPreviewUrl(previewRef.current);
  }

  function onFileChange(selected: File | null) {
    setState({ kind: 'idle' });
    if (selected && selected.size > MAX_UPLOAD_BYTES) {
      setFile(null);
      replacePreview(null);
      setState({
        kind: 'error',
        message: `File is larger than the ${MAX_UPLOAD_BYTES / 1024 / 1024} MB limit.`,
      });
      return;
    }
    setFile(selected);
    replacePreview(selected);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState({ kind: 'uploading' });
    try {
      const result = await uploadPhoto(file, controller.signal);
      setState({ kind: 'done', result });
    } catch (err) {
      if (controller.signal.aborted) return;
      const message =
        err instanceof ApiError ? err.message : 'Upload failed. Check your connection.';
      setState({ kind: 'error', message });
    }
  }

  const uploading = state.kind === 'uploading';

  return (
    <section className="space-y-6">
      <form
        onSubmit={onSubmit}
        className="space-y-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <div>
          <label htmlFor="photo" className="block text-sm font-medium">
            Business card photo
          </label>
          <p className="text-xs text-slate-500">JPEG, PNG, WebP or HEIC, up to 10 MB.</p>
        </div>
        <input
          id="photo"
          name="file"
          type="file"
          accept={ACCEPT}
          disabled={uploading}
          onChange={(e) => onFileChange(e.target.files?.[0] ?? null)}
          className="block w-full text-sm file:mr-4 file:rounded-md file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200"
        />
        {previewUrl && (
          <img
            src={previewUrl}
            alt="Selected photo preview"
            className="max-h-64 rounded-md border border-slate-200 object-contain"
          />
        )}
        <button
          type="submit"
          disabled={!file || uploading}
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {uploading ? 'Uploading…' : 'Upload'}
        </button>
      </form>

      {state.kind === 'error' && (
        <p role="alert" className="rounded-md bg-red-50 px-4 py-3 text-sm text-red-800">
          {state.message}
        </p>
      )}

      {state.kind === 'done' && <UploadResult result={state.result} />}
    </section>
  );
}

function UploadResult({ result }: { result: UploadResponse }) {
  const hs = hubspotLabel[result.hubspot.status];
  return (
    <div
      aria-label="Upload result"
      className="space-y-3 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-emerald-700">Upload complete</h2>
      <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        <dt className="text-slate-500">Filename</dt>
        <dd className="font-medium break-all">{result.filename}</dd>
        <dt className="text-slate-500">Size</dt>
        <dd className="font-medium">
          {formatBytes(result.size_bytes)}{' '}
          <span className="text-slate-500">({result.size_bytes.toLocaleString()} bytes)</span>
        </dd>
        <dt className="text-slate-500">Type</dt>
        <dd>{result.content_type}</dd>
        <dt className="text-slate-500">HubSpot</dt>
        <dd>
          <span
            className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${hs.className}`}
          >
            {hs.text}
          </span>
          {result.hubspot.file_id && (
            <span className="ml-2 text-xs text-slate-500">file #{result.hubspot.file_id}</span>
          )}
          {result.hubspot.error && (
            <p className="mt-1 text-xs text-amber-800">{result.hubspot.error}</p>
          )}
        </dd>
      </dl>
    </div>
  );
}
