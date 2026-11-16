/**
 * Bring-your-own-key storage. The user's OpenAI key lives only in this browser and is sent to
 * our server per request (X-OpenAI-Key), which uses it once and never stores it.
 *
 * sessionStorage (default): cleared when the tab closes.
 * localStorage ("Remember on this device"): persists, but any XSS bug could read it — opt-in.
 */

const STORAGE_KEY = 'hubspot-importer.openai-key';

export function getOpenAIKey(): string | null {
  return sessionStorage.getItem(STORAGE_KEY) ?? localStorage.getItem(STORAGE_KEY);
}

export function setOpenAIKey(key: string, { remember }: { remember: boolean }): void {
  clearOpenAIKey();
  (remember ? localStorage : sessionStorage).setItem(STORAGE_KEY, key.trim());
}

export function clearOpenAIKey(): void {
  sessionStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(STORAGE_KEY);
}

export function isOpenAIKeyRemembered(): boolean {
  return localStorage.getItem(STORAGE_KEY) !== null;
}

/** "sk-proj-abc…wxyz" -> "sk-…wxyz". Never render the full key. */
export function maskKey(key: string): string {
  return key.length <= 8 ? '••••' : `${key.slice(0, 3)}…${key.slice(-4)}`;
}
