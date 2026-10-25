/** UI contract v1. Contains no secrets, process addresses, command lines or authority grants. */
export type RuntimeState = 'idle' | 'checking' | 'ready' | 'running' | 'stopping' | 'stopped' | 'fault';
export type DemoScenario = 'ready' | 'no-game' | 'stale' | 'failure';
export interface RuntimeProfile { id: string; name: string; revision: number }
export interface RuntimeSession { id: string; map: string; playerName: string; faction: string }
export interface RuntimeReason { code: string; message: string; action: string }
export interface RuntimeCapability { id: string; label: string; status: 'demo' | 'unavailable' | 'planned'; detail: string }
export interface RuntimeTask { id: string; title: string; stage: string; detail: string }
export interface RuntimeLog { id: string; at: number; level: 'info' | 'warning' | 'error'; message: string }
export interface RuntimeSnapshot {
  schemaVersion: 1;
  mode: 'demo' | 'native';
  adapterConnected: boolean;
  state: RuntimeState;
  revision: number;
  profile: RuntimeProfile;
  session: RuntimeSession | null;
  readiness: { token: string; expiresAt: number } | null;
  observing: boolean;
  reason: RuntimeReason | null;
  capabilities: readonly RuntimeCapability[];
  tasks: readonly RuntimeTask[];
  logs: readonly RuntimeLog[];
  metrics: { decisions: number; completed: number; elapsedSeconds: number };
}
export interface RuntimeRequest { requestId: string; profileId: string; profileRevision: number }
export interface SessionRequest extends RuntimeRequest { sessionId: string }
export interface StartRequest extends SessionRequest { readyToken: string }
export interface OperationResult { ok: boolean; code: string; message: string }
export interface DesktopRuntime {
  getSnapshot(): RuntimeSnapshot;
  subscribe(listener: () => void): () => void;
  selectProfile(profile: RuntimeProfile): OperationResult;
  setScenario(scenario: DemoScenario): OperationResult;
  check(request: RuntimeRequest, signal?: AbortSignal): Promise<OperationResult>;
  start(request: StartRequest): Promise<OperationResult>;
  stop(request: SessionRequest): Promise<OperationResult>;
  detach(): void;
  attach(): void;
  dispose(): void;
}
