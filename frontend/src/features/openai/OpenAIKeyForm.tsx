import { useState, type FormEvent } from 'react';
import { ApiError, verifyOpenAIKey } from '../../lib/api';
import { setOpenAIKey } from '../../lib/openaiKey';

interface Props {
  /** Why the form is shown (e.g. the server's "key missing/invalid" message). */
  message?: string | null;
  onSaved: (key: string) => void;
  onCancel?: () => void;
}

/**
 * Bring-your-own-key entry. The key is verified with OpenAI (via our server, no tokens billed),
 * then stored only in this browser.
 */
export function OpenAIKeyForm({ message, onSaved, onCancel }: Props) {
  const [key, setKey] = useState('');
  const [remember, setRemember] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = key.trim();
    if (!trimmed) return;
    setVerifying(true);
    setError(null);
    try {
      const result = await verifyOpenAIKey(trimmed);
      if (!result.valid) {
        setError(result.message ?? 'OpenAI rejected this API key.');
        return;
      }
      setOpenAIKey(trimmed, { remember });
      setKey('');
      onSaved(trimmed);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not check the key. Try again.');
    } finally {
      setVerifying(false);
    }
  }

  return (
    <form
      onSubmit={onSubmit}
      aria-label="OpenAI API key"
      className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-6"
    >
      <div>
        <h2 className="text-sm font-semibold">Add your OpenAI API key</h2>
        {message && (
          <p role="alert" className="mt-1 text-sm text-amber-900">
            {message}
          </p>
        )}
        <p className="mt-1 text-xs text-slate-600">
          Contacts are read from your photo using your own OpenAI account, and usage is billed to
          it. The key stays in this browser and is sent only with your uploads — it is never saved
          on our server.{' '}
          <a
            href="https://platform.openai.com/api-keys"
            target="_blank"
            rel="noreferrer"
            className="text-brand underline"
          >
            Get a key
          </a>
        </p>
      </div>
      <label htmlFor="openai-key" className="sr-only">
        OpenAI API key
      </label>
      <input
        id="openai-key"
        type="password"
        autoComplete="off"
        spellCheck={false}
        placeholder="sk-..."
        value={key}
        disabled={verifying}
        onChange={(e) => setKey(e.target.value)}
        className="block w-full rounded-md border border-slate-300 bg-white px-3 py-2 font-mono text-sm"
      />
      <label className="flex items-center gap-2 text-xs text-slate-700">
        <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
        Remember on this device (otherwise it is forgotten when you close the tab)
      </label>
      {error && <p className="text-sm text-red-700">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!key.trim() || verifying}
          className="rounded-md bg-brand px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
        >
          {verifying ? 'Verifying…' : 'Verify & save'}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}
