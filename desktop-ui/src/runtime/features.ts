/**
 * Feature flags for UI that is built ahead of its backend.
 *
 * decisions:
 *   'backend' (default) - call `run.decisions`; an older backend that does not
 *                         know it is shown as "not available in this version".
 *   'mock'              - serve realistic fixture records (UI development and
 *                         demos only; never mixed with backend data).
 * Enable mock with VITE_TACTICORE_DECISIONS=mock at build/dev time, or at run
 * time with localStorage['tacticore.flags.decisions'] = 'mock'.
 */
export type DecisionSource = 'backend' | 'mock';
export const decisionFlagKey = 'tacticore.flags.decisions';

type Env = Record<string, string | boolean | undefined>;
type Storage = Pick<globalThis.Storage, 'getItem'>;

function viteEnv(): Env {
  return ((import.meta as unknown as {env?: Env}).env) ?? {};
}

function browserStorage(): Storage | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage;
  } catch {
    return null;
  }
}

export function decisionSource(env: Env = viteEnv(), storage: Storage | null = browserStorage()): DecisionSource {
  if (env.VITE_TACTICORE_DECISIONS === 'mock') return 'mock';
  try {
    if (storage?.getItem(decisionFlagKey) === 'mock') return 'mock';
  } catch {
    // Storage may be blocked; the backend source is the safe default.
  }
  return 'backend';
}
