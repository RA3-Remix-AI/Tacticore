import {HostError} from './nativeRpc';
import {parseDecisionRecords, type DecisionStreamRecord} from './decisions';
import {decisionFixtureRecords} from './decisionFixtures';
import type {DecisionSource} from './features';

/** Host operation name; the Python backend method is `run_decisions`. */
export const DECISIONS_OPERATION = 'run.decisions';

export type DecisionPage =
  | {state: 'ok'; records: DecisionStreamRecord[]; source: DecisionSource}
  | {state: 'unavailable'; code: string}
  | {state: 'error'; code: string};

type Rpc = (operation: typeof DECISIONS_OPERATION, args: object) => Promise<object>;

/** Codes that mean "this backend has no decision records" rather than a transient fault. */
/** Host pages are bounded (about 48 KB); a long review is read in at most this many pages. */
const MAX_PAGES = 50;

const unsupported = new Set(['operation_unsupported', 'request_invalid', 'decisions_unavailable', 'run_decisions_unavailable']);

export function createDecisionClient(options: {rpc: Rpc; source: DecisionSource; now?: () => number; revealEveryMs?: number}) {
  const now = options.now ?? Date.now;
  const firstSeen = new Map<string, number>();
  const openSeq = new Map<string, number>();
  return async function fetchDecisions(runId: string, sinceSeq?: number, complete = false): Promise<DecisionPage> {
    if (options.source === 'mock') {
      // Fixtures appear progressively during a live run; a review shows the whole match.
      const started = firstSeen.get(runId) ?? now();
      firstSeen.set(runId, started);
      const all = decisionFixtureRecords(runId);
      const visible = complete ? all.length : Math.min(all.length, 2 + Math.floor((now() - started) / (options.revealEveryMs ?? 4000)));
      const shown = all.slice(0, visible).filter(row => 'kind' in row || sinceSeq === undefined || row.seq > sinceSeq);
      return {state: 'ok', records: shown, source: 'mock'};
    }
    try {
      // The newest decision can still gain observed effects (host `final=false`); re-read it from open_seq - 1.
      const open = openSeq.get(runId);
      let since = complete ? 0 : Math.max(0, Math.min(sinceSeq ?? 0, open === undefined ? Infinity : open - 1));
      const records: DecisionStreamRecord[] = [];
      for (let page = 0; page < MAX_PAGES; page += 1) {
        const value = await options.rpc(DECISIONS_OPERATION, since === 0 ? {run_id: runId} : {run_id: runId, since_seq: since});
        records.push(...parseDecisionRecords(value));
        const body = value as {open_seq?: unknown; has_more?: unknown; next_since_seq?: unknown};
        if (typeof body.open_seq === 'number') openSeq.set(runId, body.open_seq);
        else openSeq.delete(runId);
        const next = body.next_since_seq;
        if (body.has_more !== true || typeof next !== 'number' || next <= since) break;
        since = next;
      }
      return {state: 'ok', records, source: 'backend'};
    } catch (error) {
      const code = error instanceof HostError ? error.code : 'delivery_unknown';
      return unsupported.has(code) ? {state: 'unavailable', code} : {state: 'error', code};
    }
  };
}
