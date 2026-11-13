import { useEffect, useState } from 'react';
import { getHealth } from '../lib/api';

type Status = { kind: 'loading' } | { kind: 'ok'; version: string } | { kind: 'error' };

const styles: Record<Status['kind'], string> = {
  loading: 'bg-slate-100 text-slate-600',
  ok: 'bg-emerald-100 text-emerald-800',
  error: 'bg-red-100 text-red-800',
};

export function BackendStatus() {
  const [status, setStatus] = useState<Status>({ kind: 'loading' });

  useEffect(() => {
    const controller = new AbortController();
    getHealth(controller.signal)
      .then((h) => setStatus({ kind: h.status, version: h.version }))
      .catch(() => {
        if (!controller.signal.aborted) setStatus({ kind: 'error' });
      });
    return () => controller.abort();
  }, []);

  const label =
    status.kind === 'loading'
      ? 'Backend: checking…'
      : status.kind === 'ok'
        ? `Backend: ok (v${status.version})`
        : 'Backend: unreachable';

  return (
    <span
      role="status"
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${styles[status.kind]}`}
    >
      {label}
    </span>
  );
}
