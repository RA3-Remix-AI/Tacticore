import { useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { Circuitry, Crosshair, ClockCounterClockwise, GearSix, Stop } from '@phosphor-icons/react';
import { Button } from './components/ui';
import { hostRpc, HostError } from './runtime/nativeRpc';
import { macroStrategyView } from './runtime/macroStrategyView';
import { strategicCommandView, strategicPreflightView } from './runtime/strategicCommandView';
import { strategicReevaluationView } from './runtime/strategicReevaluationView';
import { modelCallView } from './runtime/modelCallView';
import { strategicUnifiedFeedbackV5 } from './runtime/strategicUnifiedFeedbackV5';
import { strategicLifecycleView } from './runtime/strategicLifecycleView';
import { sessionDisplay } from './runtime/sessionDisplay';
import { startAtOpening, discoveredOpeningCheck, type DiscoveredSession, type SessionDiscoveryResult } from './runtime/openingStart';
import { applicationView } from './runtime/applicationView';
import { createDiagnosticsDownload, saveDiagnosticFile } from './runtime/diagnosticsDownload';
import { preservePendingStart, runLocksControls, sameRun } from './runtime/nativeProcess';
import type { ConnectionConfigurationState } from './runtime/connectionConfigurationStateV1';
import type { Connection, Draft, Profile, Ready, Run, Session } from './runtime/hostTypes';
import { APP_VERSION, errorText, reasonText } from './runtime/copy';
import { matchControl, type ControlAction } from './runtime/matchControl';
import { parseScenario, type MatchScenario } from './runtime/scenario';
import { loadSetupPreferences, playModes, saveSetupPreferences, type PlayMode, type SetupPreferences } from './runtime/playMode';
import { firstIncompleteStep, showWizard, type WizardInput } from './runtime/wizard';
import { decisionSource } from './runtime/features';
import { createDecisionClient, type DecisionPage } from './runtime/decisionClient';
import { lastSeq, mergeDecisionRecords, type DecisionStreamRecord } from './runtime/decisions';
import { ConnectionConfigPanelV1 } from './ConnectionConfigPanelV1';
import { BetaSetupPanel, type BetaSetupResult } from './BetaSetupPanel';
import { SetupFlow, type SetupTab } from './ui/SetupFlow';
import { ModeStep, LobbyInstructions } from './ui/ModeStep';
import { StylePanel } from './ui/StylePanel';
import { MatchCard, boundView } from './ui/MatchCard';
import { MatchControlPanel } from './ui/MatchControlPanel';
import { DecisionFeed, type FeedState } from './ui/DecisionFeed';
import { CommanderAvatar } from './ui/CommanderAvatar';
import { commanderBadge, commanderProfile, commanderSupported, mergeCommanders, profileSaveDraft } from './runtime/commanders';
import { ReviewPage } from './ui/ReviewPage';
import { DetailsPanel } from './ui/DetailsPanel';
import './native.css';
import './native-workspace.css';
import './app.css';

type View = 'match' | 'review' | 'settings';
type Feed = {runId: string | null; records: DecisionStreamRecord[]; state: FeedState};

const views: {id: View; label: string; icon: typeof Crosshair}[] = [
  {id: 'match', label: '对局', icon: Crosshair},
  {id: 'review', label: '复盘', icon: ClockCounterClockwise},
  {id: 'settings', label: '设置', icon: GearSix},
];

const lastRunKey = 'tacticore.desktop.native.last-run.v1';
const publicId = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** Only identifiers and the (non-secret) match scenario are kept across restarts. */
function lastRun(): {run: Run; scenario: MatchScenario | null} | null {
  try {
    const value = JSON.parse(localStorage.getItem(lastRunKey) ?? 'null');
    if (!value || !publicId.test(value.run_id) || !publicId.test(value.session_id)) return null;
    const profileId = publicId.test(value.profile_id ?? '') ? value.profile_id : undefined;
    return {
      run: {run_id: value.run_id, session_id: value.session_id, profile_id: profileId, state: 'uncertain'},
      scenario: parseScenario(value.scenario),
    };
  } catch {
    return null;
  }
}

function rememberRun(value: Run, scenario: MatchScenario | null) {
  try {
    localStorage.setItem(lastRunKey, JSON.stringify({
      run_id: value.run_id, session_id: value.session_id, profile_id: value.profile_id, scenario,
    }));
  } catch {
    // Persistence is a convenience; the host's run.resume is authoritative.
  }
}

function browserStorage() {
  try { return localStorage; } catch { return null; }
}

const downloadDiagnostics = createDiagnosticsDownload((operation, args) => hostRpc(operation, args), invoke, saveDiagnosticFile);
const source = decisionSource();
const fetchDecisions = createDecisionClient({rpc: (operation, args) => hostRpc(operation, args), source});

export default function NativeApp() {
  // ----- navigation and first-run setup -----
  const [view, setView] = useState<View>('match');
  const [setupTab, setSetupTab] = useState<SetupTab>('game');
  const [setupPrefs, setSetupPrefs] = useState<SetupPreferences>(() => loadSetupPreferences(browserStorage()));
  const [setupState, setSetupState] = useState<BetaSetupResult>({});
  const main = useRef<HTMLElement>(null);
  // Read once at mount (not at module load), like the previous client.
  const [initialRun] = useState(lastRun);

  // ----- host state (unchanged semantics from the previous client) -----
  const [profiles, setProfiles] = useState<Profile[]>([]);
  // `commanders` from profiles.list; undefined on an older backend (built-in metadata is used then).
  const [commanderList, setCommanderList] = useState<unknown>(undefined);
  const [connections, setConnections] = useState<Connection[]>([]);
  const [selected, setSelected] = useState('');
  const [draft, setDraft] = useState<Draft | null>(null);
  const [dirty, setDirty] = useState(false);
  const [ready, setReady] = useState<Ready | null>(null);
  const [run, setRun] = useState<Run | null>(() => initialRun?.run ?? null);
  const [session, setSession] = useState<Session | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [clock, setClock] = useState(Date.now());
  const [candidates, setCandidates] = useState<DiscoveredSession[]>([]);
  const [candidateId, setCandidateId] = useState('');
  const [observedAt, setObservedAt] = useState<number | null>(null);
  const preparationRequests = useRef(new Map<string, string>());
  const [openingWaiting, setOpeningWaiting] = useState(false);
  const openingAbort = useRef<AbortController | null>(null);
  const [configurationState, setConfigurationState] = useState<ConnectionConfigurationState>('unverified');
  const configurationGate = useRef<{state: ConnectionConfigurationState; generation: number}>({state: 'unverified', generation: 0});
  const pending = useRef(false);

  // ----- match scenario bound to a run, and the decision feed -----
  const boundScenario = useRef<{runId: string | null; scenario: MatchScenario | null}>(
    {runId: initialRun?.run.run_id ?? null, scenario: initialRun?.scenario ?? null});
  const [scenarioRecord, setScenarioRecord] = useState(boundScenario.current);
  const pendingScenario = useRef<MatchScenario | null>(null);
  const [feed, setFeed] = useState<Feed>({runId: null, records: [], state: 'idle'});
  const feedRef = useRef(feed);
  feedRef.current = feed;

  const configurationReady = configurationState === 'ready';
  const profile = profiles.find(p => p.profile_id === selected);
  const commanders = mergeCommanders(commanderList);
  const commanderSupport = commanderSupported(profile?.draft, commanderList);
  // The saved profile's commander (what the next or current run uses), not the unsaved draft.
  const activeCommander = commanderSupport && profile
    ? commanderBadge(commanderProfile(profile.draft).commander_id, commanders) : null;
  const locked = runLocksControls(run?.state, run?.native_release_verified);
  const display = sessionDisplay<Session, Run, Ready>(run, session, ready?.ready && ready.expires_at > clock ? ready : null);
  const currentRun = display.current;
  const validReady = !!display.readiness;
  const wizard = showWizard({completed: setupPrefs.completed, runHoldsGame: locked});
  const activeView: View | 'wizard' = wizard ? 'wizard' : view;

  function configurationChanged(state: ConnectionConfigurationState) {
    configurationGate.current = {state, generation: configurationGate.current.generation + 1};
    setConfigurationState(state); setReady(null);
    openingAbort.current?.abort(); setOpeningWaiting(false);
  }
  function configurationCurrent(generation = configurationGate.current.generation) {
    return configurationGate.current.state === 'ready' && configurationGate.current.generation === generation;
  }
  function bindScenario(runId: string | null, scenario: MatchScenario | null) {
    boundScenario.current = {runId, scenario};
    setScenarioRecord(boundScenario.current);
  }
  function updateRun(value: Run) {
    const scenario = boundScenario.current.runId === value.run_id ? boundScenario.current.scenario : null;
    if (boundScenario.current.runId !== value.run_id) bindScenario(value.run_id, null);
    rememberRun(value, scenario); setRun(value); setObservedAt(Date.now());
  }
  async function perform(work: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true; setBusy(true);
    try { await work(); } catch (error) { setNotice(errorText(error)); } finally { pending.current = false; setBusy(false); }
  }
  function updateSetupPrefs(next: SetupPreferences) {
    setSetupPrefs(next); saveSetupPreferences(browserStorage(), next);
  }

  // ----- host operations -----
  async function load() {
    const [p, c, resumed] = await Promise.all([
      hostRpc<{profiles: Profile[]; commanders?: unknown}>('profiles.list', {}),
      hostRpc<{connections: Connection[]}>('connections.list', {}),
      hostRpc<{run: Run | null; observation_only: true; other_unreleased_runs: number}>('run.resume', {}),
    ]);
    setProfiles(p.profiles); setCommanderList(p.commanders); setConnections(c.connections);
    if (resumed.run) updateRun(resumed.run);
    const next = p.profiles.find(value => value.profile_id === (resumed.run?.profile_id ?? run?.profile_id ?? selected)) ?? p.profiles[0];
    if (next) { setSelected(next.profile_id); setDraft(structuredClone(next.draft)); }
    setDirty(false); setReady(null);
    if (resumed.other_unreleased_runs) setNotice('还有其他没有确认结束的对局，请在「详细信息与诊断」中查看。确认前不能开始新的对局。');
    else if (resumed.run && runLocksControls(resumed.run.state, resumed.run.native_release_verified)) setNotice('已重新连接到进行中的对局。');
    else setNotice(null);
  }
  useEffect(() => { void perform(load); }, []);
  useEffect(() => () => openingAbort.current?.abort(), []);
  useEffect(() => {
    main.current?.focus({preventScroll: true});
    window.scrollTo({top: 0, left: 0, behavior: 'instant'});
  }, [activeView]);

  // Status polling while a run holds the game. Never overlaps a user action.
  useEffect(() => {
    if (!run || !locked) return;
    let cancelled = false, inflight = false;
    const query = async () => {
      if (inflight || pending.current) return;
      inflight = true;
      try {
        const value = await hostRpc<Run>('run.status', {run_id: run.run_id});
        if (!sameRun(run, value)) throw new HostError('delivery_unknown', run.run_id);
        if (!cancelled) updateRun(value);
      } catch (error) {
        if (!cancelled) setNotice(errorText(error));
      } finally { inflight = false; }
    };
    const timer = setInterval(() => { void query(); }, 2000);
    void query();
    return () => { cancelled = true; clearInterval(timer); };
  }, [run?.run_id, locked]);

  useEffect(() => {
    if (!ready?.ready) return;
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [ready]);

  useEffect(() => {
    if (locked && run?.profile_id && run.profile_id !== selected) {
      const next = profiles.find(value => value.profile_id === run.profile_id);
      if (next) { setSelected(next.profile_id); setDraft(structuredClone(next.draft)); setDirty(false); setReady(null); }
    }
  }, [run?.profile_id, profiles, locked]);

  // ----- decision feed -----
  function applyPage(runId: string, page: DecisionPage) {
    setFeed(previous => {
      const known = previous.runId === runId ? previous.records : [];
      if (page.state !== 'ok') return {runId, records: known, state: page.state};
      return {runId, records: mergeDecisionRecords(known, page.records), state: 'ok'};
    });
  }
  async function refreshDecisions(runId: string, complete: boolean) {
    const known = feedRef.current.runId === runId ? feedRef.current.records : [];
    if (!known.length) setFeed({runId, records: [], state: 'loading'});
    applyPage(runId, await fetchDecisions(runId, complete ? undefined : lastSeq(known), complete));
  }
  useEffect(() => {
    if (!run || !locked) return;
    let cancelled = false, inflight = false;
    const tick = async () => {
      if (inflight || pending.current || cancelled) return;
      inflight = true;
      try { await refreshDecisions(run.run_id, false); } finally { inflight = false; }
    };
    const timer = setInterval(() => { void tick(); }, 3000);
    void tick();
    return () => { cancelled = true; clearInterval(timer); };
  }, [run?.run_id, locked]);
  useEffect(() => {
    if (activeView === 'review' && run && !locked) void refreshDecisions(run.run_id, true);
  }, [activeView, run?.run_id, locked]);

  // ----- style (commander profile) -----
  function edit(patch: Partial<Draft>) {
    if (draft) { setDraft({...draft, ...patch}); setDirty(true); setReady(null); }
  }
  function choose(id: string) {
    const next = profiles.find(p => p.profile_id === id);
    if (next) { setSelected(id); setDraft(structuredClone(next.draft)); setDirty(false); setReady(null); setSession(null); }
  }
  async function save() {
    if (!draft || !profile) return;
    const result = await hostRpc<{profile: Profile; state: string; host_applied: false}>('profiles.save',
      {draft: {...profileSaveDraft(draft, commanderSupport), revision: profile.revision}, expected_revision: profile.revision});
    setProfiles(values => values.map(p => (p.profile_id === result.profile.profile_id ? result.profile : p)));
    setDraft(structuredClone(result.profile.draft)); setDirty(false); setReady(null);
    setNotice('指挥官设置已保存，下一局开始时生效。');
  }

  // ----- finding, checking and starting a match -----
  async function discover() {
    setReady(null);
    const result = await hostRpc<SessionDiscoveryResult>('session.discover', {});
    setCandidates(result.candidates);
    setCandidateId(current => (result.candidates.some(value => value.candidate_id === current) ? current
      : result.candidates.length === 1 ? result.candidates[0].candidate_id : ''));
    setNotice(result.candidates.length ? null
      : result.issues[0] ? reasonText(result.issues[0]) : '没有找到对局。请确认已经在游戏里进入对局，再点击「查找对局」。');
  }
  async function prepareCandidate(id: string = candidateId) {
    if (!id) throw new HostError('session_selection_required', 'session-prepare');
    // The same candidate always reuses its request id, so a retry is idempotent.
    const requestId = preparationRequests.current.get(id) ?? crypto.randomUUID();
    preparationRequests.current.set(id, requestId);
    const result = await hostRpc<{registered: boolean; requires_preflight: true; session: Session}>('session.prepare', {candidate_id: id}, requestId);
    setSession(result.session); setReady(null); setCandidates([]); setCandidateId('');
  }
  async function resume() {
    const result = await hostRpc<{run: Run | null; observation_only: true; other_unreleased_runs: number}>('run.resume', {});
    if (result.run) updateRun(result.run);
    setNotice(result.run ? '已重新连接到已有对局，没有开始新的指挥。' : '没有找到已有的对局记录。');
  }
  /** Read-only admission check. Returns the result, or null when configuration changed meanwhile. */
  async function check(generation = configurationGate.current.generation): Promise<Ready | null> {
    if (!configurationCurrent(generation) || !profile) return null;
    setReady(null); setSession(null);
    const result = await hostRpc<Ready>('run.check',
      {profile_id: profile.profile_id, profile_revision: profile.revision, effective_hash: profile.effective?.effective_hash});
    if (!configurationCurrent(generation)) return null;
    setReady(result); setClock(Date.now());
    if (result.session) setSession(result.session);
    else {
      const inspected = await hostRpc<{session: Session | null}>('session.inspect', {profile_id: profile.profile_id});
      if (!configurationCurrent(generation)) return null;
      setSession(inspected.session);
    }
    if (!result.ready) setNotice(reasonText(result.reason_code ?? 'session_not_ready'));
    return result;
  }
  /** Submits run.start at most once. An uncertain start is kept and observed, never repeated. */
  async function start(admission: Ready | null = ready, generation = configurationGate.current.generation) {
    if (!configurationCurrent(generation)) return;
    if (!profile || !admission?.ready || admission.expires_at <= Date.now()) {
      setReady(null); setNotice(reasonText('readiness_expired')); return;
    }
    const requestId = crypto.randomUUID();
    const pendingRun: Run = {run_id: requestId, session_id: admission.session_id, profile_id: profile.profile_id, state: 'uncertain'};
    bindScenario(requestId, pendingScenario.current);
    updateRun(pendingRun);
    try {
      const value = await hostRpc<Run>('run.start', {
        profile_id: profile.profile_id, profile_revision: profile.revision, effective_hash: profile.effective?.effective_hash,
        session_id: admission.session_id, ready_token: admission.ready_token,
      }, requestId);
      if (!sameRun(pendingRun, value)) throw new HostError('delivery_unknown', requestId);
      updateRun(value);
      setNotice(value.no_native_execution_started ? '开始前已取消，弈核 AI 没有接手。' : null);
    } catch (error) {
      if (error instanceof HostError && !preservePendingStart(error.code)) {
        setRun(null); bindScenario(null, null);
        try { localStorage.removeItem(lastRunKey); } catch { /* ignore */ }
      }
      throw error;
    } finally { setReady(null); }
  }
  /** The single Start: prepare the chosen match if needed, check it, then start. */
  async function startMatch() {
    if (!configurationCurrent() || !profile || dirty || locked) return;
    const generation = configurationGate.current.generation;
    let admission: Ready | null = validReady ? ready : null;
    if (!admission) {
      if (candidates.length) {
        const id = candidateId || (candidates.length === 1 ? candidates[0].candidate_id : '');
        const chosen = candidates.find(row => row.candidate_id === id);
        await prepareCandidate(id);
        pendingScenario.current = parseScenario(chosen?.scenario);
      }
      admission = await check(generation);
      if (!admission?.ready) return;
    }
    await start(admission, generation);
  }
  async function openingStart() {
    if (!configurationCurrent() || !profile || dirty || locked) return;
    const generation = configurationGate.current.generation;
    const controller = new AbortController();
    const seen = new Map<string, DiscoveredSession>();
    openingAbort.current = controller; setOpeningWaiting(true); setReady(null); setNotice(null);
    try {
      const result = await startAtOpening({
        signal: controller.signal,
        check: () => discoveredOpeningCheck({
          signal: controller.signal, candidateId: candidateId || undefined,
          check: () => {
            if (!configurationCurrent(generation)) throw new HostError('connection_config_recovery_required', 'configuration');
            return hostRpc<Ready>('run.check',
              {profile_id: profile.profile_id, profile_revision: profile.revision, effective_hash: profile.effective?.effective_hash});
          },
          discover: async () => {
            const found = await hostRpc<SessionDiscoveryResult>('session.discover', {});
            for (const row of found.candidates) seen.set(row.candidate_id, row);
            return found;
          },
          prepare: async id => {
            await prepareCandidate(id);
            pendingScenario.current = parseScenario(seen.get(id)?.scenario);
          },
        }),
        start: async admission => {
          if (!configurationCurrent(generation)) return;
          setOpeningWaiting(false);
          if (admission.session) setSession(admission.session);
          await start(admission, generation);
        },
      });
      if (result === 'cancelled') setNotice('已取消等待。');
    } finally { openingAbort.current = null; setOpeningWaiting(false); }
  }
  async function query() {
    if (!run) return;
    const value = await hostRpc<Run>('run.status', {run_id: run.run_id});
    if (!sameRun(run, value)) throw new HostError('delivery_unknown', run.run_id);
    updateRun(value);
  }
  async function stop() {
    if (!run) return;
    const value = await hostRpc<Run>('run.stop', {run_id: run.run_id, session_id: run.session_id});
    if (!sameRun(run, value)) throw new HostError('delivery_unknown', run.run_id);
    updateRun(value);
    setNotice('已请求停止。确认游戏控制已交还后才算完全结束。');
  }
  async function download() {
    if (!run) return;
    const receipt = await downloadDiagnostics(run);
    setNotice(`诊断文件已生成并开始下载（${receipt.exported_event_count} / ${receipt.event_count} 条事件${receipt.truncated ? '，只包含最近的记录' : ''}）。`);
  }

  // ----- derived views -----
  const freshSession = session && session.id !== run?.session_id ? session : null;
  const profileIssue = dirty ? 'dirty' : !profile?.validation.ok ? 'invalid' : null;
  // A debug build cannot run game setup (beta_release_required); it relies on existing registrations.
  const gamePrepared = setupState.prepared === true ? true : setupState.error === 'beta_release_required' ? null : false;
  const control = matchControl({
    gamePrepared, configuration: configurationState, profileIssue,
    waiting: openingWaiting, busy, run, runHoldsGame: locked,
    candidateCount: candidates.length, candidateSelected: Boolean(candidateId) || candidates.length === 1,
    sessionPrepared: Boolean(freshSession), readyValid: validReady,
  });
  const credentialSaved = connections.find(c => c.id === draft?.connection_id)?.credential_configured ?? null;
  const wizardInput: WizardInput = {
    gamePrepared: setupState.prepared === true, configurationReady, credentialSaved, mode: setupPrefs.mode,
  };
  const scenarioForRun = run && scenarioRecord.runId === run.run_id ? scenarioRecord.scenario : null;
  const identity = display.identity;
  const bound = locked || freshSession || run
    ? {
      view: boundView(freshSession ? pendingScenario.current : scenarioForRun, identity ?? run?.session),
      label: locked ? '当前对局' : freshSession ? '已选择的对局' : '上一局',
    }
    : null;
  const feedForRun = run && feed.runId === run.run_id ? feed : {runId: null, records: [], state: 'idle' as FeedState};
  const modeInfo = playModes.find(row => row.id === setupPrefs.mode);
  const canAutoStart = configurationReady && !busy && !dirty && !locked && !!profile?.validation.ok && gamePrepared !== false;
  const readyFootnote = validReady && ready
    ? `检查结果 ${Math.max(0, Math.ceil((ready.expires_at - clock) / 1000))} 秒内有效。` : null;

  function openSettings(tab: SetupTab) { setSetupTab(tab); setView('settings'); }
  function onControl(action: ControlAction) {
    switch (action) {
      case 'open_setup': openSettings(firstIncompleteStep(wizardInput) ?? 'game'); break;
      case 'open_model': openSettings('model'); break;
      case 'open_style': openSettings('style'); break;
      case 'discover': void perform(discover); break;
      case 'start': void perform(startMatch); break;
      case 'stop': void perform(stop); break;
      case 'cancel_wait': openingAbort.current?.abort(); break;
      case 'refresh': void perform(query); break;
      case 'none': break;
    }
  }

  const secondary = <>
    {!locked && !openingWaiting && control.phase !== 'setup' && <Button disabled={!canAutoStart} onClick={() => void perform(openingStart)}
      title="在你进入对局后自动找到它并开始，最多等待五分钟">进入对局后自动开始</Button>}
    {(control.phase === 'found' || control.phase === 'ready') && <Button disabled={busy} onClick={() => void perform(discover)}>重新查找</Button>}
    {locked && control.primary.action !== 'refresh' && <Button disabled={busy} onClick={() => void perform(query)}>刷新状态</Button>}
    {(control.phase === 'finished' || control.phase === 'returning') && <Button onClick={() => setView('review')}>查看复盘</Button>}
  </>;

  const setupFlow = <SetupFlow
    variant={wizard ? 'wizard' : 'settings'} tab={setupTab} onTab={setSetupTab} input={wizardInput}
    onFinish={() => { updateSetupPrefs({...setupPrefs, completed: true}); setView('match'); }}
    game={<BetaSetupPanel locked={locked} onStatusChange={setSetupState}
      onPrepared={() => { setReady(null); setSession(null); setCandidates([]); }} />}
    model={<ConnectionConfigPanelV1 locked={locked} onConfigurationState={configurationChanged}
      onSaved={async () => { setReady(null); await load(); }} />}
    mode={<ModeStep mode={setupPrefs.mode} onChange={mode => updateSetupPrefs({...setupPrefs, mode})} />}
    style={<StylePanel profiles={profiles} selected={selected} profile={profile} draft={draft} dirty={dirty}
      commanders={commanders} supported={commanderSupport}
      disabled={busy || locked} onChoose={choose} onEdit={edit} onSave={() => void perform(save)} onReload={() => void perform(load)} />}
  />;

  const details = <DetailsPanel busy={busy}
    onDownload={() => void perform(download)} onResume={() => void perform(resume)} onQuery={() => void perform(query)}
    data={{
      run, current: currentRun ?? undefined, historical: Boolean(display.historical), observedAt,
      application: applicationView(dirty || validReady ? undefined : profile, currentRun?.profile_application, currentRun?.profile_consumption),
      modelCall: modelCallView(currentRun?.events, currentRun?.profile_consumption, currentRun ?? undefined),
      strategy: macroStrategyView(currentRun?.macro_strategy, currentRun?.macro_strategy_unavailable),
      strategic: currentRun
        ? strategicCommandView(currentRun.strategic_client_unavailable ? undefined : currentRun.strategic_client)
        : strategicPreflightView(display.readiness?.capabilities),
      unifiedRows: strategicUnifiedFeedbackV5(currentRun?.macro_unified_feedback_unavailable ? undefined : currentRun?.macro_unified_feedback),
      reevaluation: strategicReevaluationView(currentRun?.macro_strategy_unavailable ? undefined : currentRun?.macro_strategy),
      lifecycle: currentRun ? strategicLifecycleView(currentRun) : null,
      nativeMacro: Boolean((display.readiness?.capabilities ?? currentRun?.capabilities)?.native_macro),
    }} />;

  return <div className={`native-app native-workspace-shell ${wizard ? 'is-wizard' : ''}`}>
    <a className="skip-link" href="#native-main-content">跳至主要内容</a>
    {!wizard && <aside className="nw-sidebar">
      <a className="nw-brand" href="#match" onClick={event => { event.preventDefault(); setView('match'); }}>
        <Circuitry size={31} weight="duotone" /><span><strong>弈核</strong><small>TACTICORE</small></span>
      </a>
      <p className="nw-sidebar-caption">红色警戒 3 AI 指挥官</p>
      <nav aria-label="页面">
        {views.map(item => <button key={item.id} aria-current={view === item.id ? 'page' : undefined} onClick={() => setView(item.id)}>
          <item.icon size={23} weight="light" /><span>{item.label}</span>{view === item.id && <i />}
        </button>)}
      </nav>
      <div className="nw-sidebar-bottom"><span className="nw-dot" /> v{APP_VERSION}</div>
    </aside>}
    <div className="nw-body">
      {!wizard && <header className="nw-topbar">
        <div>
          <span className={`tc-pill ${control.live ? 'is-live' : ''}`}>{control.status}</span>
          <strong>{modeInfo ? `模式：${modeInfo.title}` : '弈核'}</strong>
          {activeCommander
            ? <span className="nw-current-commander tc-topbar-commander">
              <CommanderAvatar commander={activeCommander} size={26} /> 指挥官：{activeCommander.name}
            </span>
            : <span className="nw-topbar-note">{profile?.name ?? ''}</span>}
        </div>
        <div className="nw-global-controls">
          {openingWaiting && <Button onClick={() => openingAbort.current?.abort()}>取消等待</Button>}
          {locked && <Button kind="danger" className="nw-stop" disabled={busy || run?.state === 'stopping'} onClick={() => void perform(stop)}>
            <Stop size={16} weight="bold" /> 停止 AI
          </Button>}
        </div>
      </header>}
      <main id="native-main-content" ref={main} tabIndex={-1} className="nw-content">
        {wizard && <header className="tc-wizard-head">
          <Circuitry size={34} weight="duotone" aria-hidden="true" />
          <div>
            <p className="eyebrow">欢迎使用弈核 · v{APP_VERSION}</p>
            <h1>三步完成设置</h1>
            <p className="native-muted">设置好游戏、模型和玩法后，就可以让弈核 AI 上场了。</p>
          </div>
          <button type="button" className="tc-link" onClick={() => updateSetupPrefs({...setupPrefs, completed: true})}>稍后再说</button>
        </header>}
        {!wizard && view === 'settings' && <header className="nw-page-heading"><h1>设置</h1></header>}
        <div hidden={activeView !== 'wizard' && activeView !== 'settings'}>{setupFlow}</div>

        <div hidden={activeView !== 'match'} className="tc-match">
          <div className="tc-match-grid">
            <div className="tc-match-left">
              <MatchControlPanel control={control} notice={notice} onAction={onControl} secondary={secondary} footnote={readyFootnote} />
              <MatchCard candidates={candidates} selectedId={candidateId} onSelect={setCandidateId}
                bound={bound} mode={setupPrefs.mode} disabled={busy || locked} />
              {setupPrefs.mode && !locked && <details className="native-panel tc-lobby-hint">
                <summary>大厅设置提示 · {modeInfo?.title}</summary>
                <LobbyInstructions mode={setupPrefs.mode as PlayMode} />
                <Button onClick={() => openSettings('mode')}>更换模式</Button>
              </details>}
            </div>
            <DecisionFeed records={feedForRun.records} state={feedForRun.state} live={locked} mock={source === 'mock'} />
          </div>
          {details}
        </div>

        <div hidden={activeView !== 'review'}>
          <header className="nw-page-heading"><h1>复盘</h1></header>
          <ReviewPage hasRun={Boolean(run)} live={locked} records={feedForRun.records} state={feedForRun.state}
            mock={source === 'mock'} scenario={run ? boundView(scenarioForRun, identity ?? run.session) : null}
            busy={busy} onRefresh={() => { if (run) void refreshDecisions(run.run_id, !locked); }} />
        </div>
      </main>
    </div>
  </div>;
}
