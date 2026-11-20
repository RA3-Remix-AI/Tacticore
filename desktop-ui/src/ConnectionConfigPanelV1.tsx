import {useEffect, useRef, useState} from 'react';
import {Button} from './components/ui';
import './native-setup.css';
import {connectionConfigRpc, connectionConfiguration, connectionConfigError, connectionTestText, testConnection,
  type ConnectionConfigRpc, type ConnectionConfiguration, type ConfigurationReference} from './runtime/connectionConfigRpcV1';
import type {ConnectionConfigurationState} from './runtime/connectionConfigurationStateV1';

type Provider = 'OpenAI' | 'DeepSeek' | '自定义';
type CredentialOperation = 'keep' | 'set' | 'clear';

const endpointExamples: Record<Provider, string> = {
  OpenAI: 'https://api.openai.com/v1',
  DeepSeek: 'https://api.deepseek.com/v1',
  自定义: 'https://你的服务地址/v1',
};
const modelExamples: Record<Provider, string> = {
  OpenAI: '例如：gpt-4o-mini',
  DeepSeek: '例如：deepseek-chat',
  自定义: '填写服务商支持的模型名称',
};

/**
 * Model service, endpoint, model and API key. The key is sent once to the
 * native configuration channel, which stores it; it is never read back,
 * echoed or kept in browser storage.
 */
export function ConnectionConfigPanelV1({locked, onSaved, onConfigurationState, rpc = connectionConfigRpc}: {
  locked: boolean; onSaved: () => void | Promise<void>;
  onConfigurationState?: (state: ConnectionConfigurationState) => void; rpc?: ConnectionConfigRpc;
}) {
  const [configuration, setConfiguration] = useState<ConnectionConfiguration | null>(null);
  const [selected, setSelected] = useState('');
  const [name, setName] = useState('');
  const [provider, setProvider] = useState<Provider>('OpenAI');
  const [endpoint, setEndpoint] = useState('');
  const [model, setModel] = useState('');
  const [key, setKey] = useState('');
  const [credential, setCredential] = useState<CredentialOperation>('keep');
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [notice, setNotice] = useState('正在读取模型设置…');
  const [testNotice, setTestNotice] = useState<{text: string; ok: boolean} | null>(null);
  const pending = useRef(false);
  const observedState = useRef<ConnectionConfigurationState>('unverified');

  function choose(id: string, value = configuration) {
    const row = value?.connections.find(candidate => candidate.id === id);
    if (!row) return;
    setSelected(id); setName(row.name); setProvider(row.provider); setEndpoint(row.endpoint); setModel(row.model);
    setKey(''); setCredential(row.credential_configured ? 'keep' : 'set'); setTestNotice(null);
  }
  async function load(successNotice?: string) {
    const result = connectionConfiguration(await rpc('connections.configuration', {}));
    observedState.current = result.ready ? 'ready' : 'pending';
    setConfiguration(result); setUncertain(!result.ready);
    setNotice(result.ready
      ? successNotice ?? '已读取模型设置。'
      : '上次保存还没有完成。请点击「处理未完成的保存」，完成前不能开始新的对局。');
    if (result.ready) choose(result.connections.some(row => row.id === selected) ? selected : result.connections[0].id, result);
  }
  async function perform(operation: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    observedState.current = 'unknown';
    onConfigurationState?.('checking');
    setBusy(true);
    try { await operation(); onConfigurationState?.(observedState.current); }
    catch (error) { setNotice(connectionConfigError(error)); setUncertain(true); onConfigurationState?.('unknown'); }
    finally { pending.current = false; setBusy(false); setKey(''); }
  }
  useEffect(() => { void perform(load); }, []);

  async function save() {
    if (!configuration?.ready || !configuration.config_fingerprint || locked || uncertain) return;
    await rpc('connections.configure', {schema_version: 1, connection_id: selected,
      expected_config_fingerprint: configuration.config_fingerprint, name, provider, endpoint, model,
      credential_operation: credential, ...(credential === 'set' ? {api_key: key} : {})});
    await load('已保存。'); await onSaved();
  }
  async function recover(reference: ConfigurationReference) {
    const result = await rpc<{saved: boolean}>('connections.recover', reference);
    await load(result.saved ? '未完成的保存已处理完毕。' : '未完成的修改已取消，原来的设置已保留。'); await onSaved();
  }
  async function runTest() {
    if (pending.current || !selected) return;
    pending.current = true; setBusy(true); setTestNotice({text: '正在测试…', ok: true});
    try { setTestNotice(connectionTestText(await testConnection(rpc, selected))); }
    finally { pending.current = false; setBusy(false); }
  }

  const disabled = busy || locked || uncertain;
  const current = configuration?.connections.find(row => row.id === selected);
  const changedDestination = Boolean(current && (current.provider !== provider || current.endpoint !== endpoint));
  const unsaved = Boolean(current && (current.name !== name || current.provider !== provider || current.endpoint !== endpoint
    || current.model !== model || credential !== 'keep'));

  function validationMessage() {
    if (!name.trim()) return '请填写一个名称，方便你区分不同设置。';
    try {
      const url = new URL(endpoint);
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
        return '接口地址只填根地址，不要包含用户名、密码或参数。';
      }
    } catch { return `请填写完整的接口地址，例如 ${endpointExamples[provider]}。`; }
    if (credential === 'keep' && current?.remember_key && changedDestination) return '更换了服务商或接口地址，请重新填写 API Key，或选择清除。';
    if (credential === 'set' && (!key || /\s/.test(key))) return 'API Key 不能为空，也不能包含空格或换行。';
    return '';
  }
  function requestSave() {
    const message = validationMessage();
    if (message) { setNotice(message); return; }
    void perform(save);
  }

  const badge = busy ? '处理中' : uncertain ? '需要处理' : configuration?.ready ? '已保存' : '未设置';
  return <section className="native-panel connection-panel setup-panel">
    <div className="setup-panel-heading">
      <div>
        <h2>模型与 API Key</h2>
        <p className="setup-description">弈核 AI 通过你自己的模型服务思考。填写服务商、接口地址、模型名称和 API Key。</p>
      </div>
      <span className={`setup-badge ${configuration?.ready && !uncertain ? 'is-ready' : ''}`}>{badge}</span>
    </div>
    <p role="status" className={`setup-notice ${uncertain ? 'is-warning' : ''}`}>{notice}</p>

    {configuration?.ready && <>
      <div className="connection-form-grid">
        {configuration.connections.length > 1 && <label className="connection-full">使用哪组设置
          <select value={selected} disabled={disabled} onChange={e => choose(e.target.value)}>
            {configuration.connections.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>}
        <label>服务商
          <select value={provider} disabled={disabled} onChange={e => setProvider(e.target.value as Provider)}>
            <option>OpenAI</option><option>DeepSeek</option><option value="自定义">其他（兼容 OpenAI 接口）</option>
          </select>
        </label>
        <label>名称
          <input placeholder="例如：我的 DeepSeek" maxLength={60} value={name} disabled={disabled} onChange={e => setName(e.target.value)} />
        </label>
        <label className="connection-full">接口地址
          <input type="url" spellCheck={false} placeholder={endpointExamples[provider]} maxLength={2048} value={endpoint}
            disabled={disabled} onChange={e => setEndpoint(e.target.value)} />
          <small>只填根地址，不需要加 /chat/completions。</small>
        </label>
        <label className="connection-full">模型名称
          <input spellCheck={false} placeholder={modelExamples[provider]} maxLength={200} value={model}
            disabled={disabled} onChange={e => setModel(e.target.value)} />
        </label>
      </div>

      <div className="connection-credentials">
        <div className="connection-section-heading">
          <h3>API Key</h3>
          <span className="setup-step-state">{current?.credential_configured ? '已保存在本机' : '尚未保存'}</span>
        </div>
        <p>API Key 只保存在这台电脑上，保存后不会再显示。</p>
        <label>API Key 处理方式
          <select value={credential} disabled={disabled} onChange={e => { setCredential(e.target.value as CredentialOperation); setKey(''); }}>
            {current?.credential_configured ? <>
              <option value="keep">保留已保存的 Key</option>
              <option value="set">换一个新的 Key</option>
              <option value="clear">清除已保存的 Key</option>
            </> : <>
              <option value="set">填写 API Key</option>
              <option value="keep">不使用 API Key（例如本机模型服务）</option>
            </>}
          </select>
        </label>
        {credential === 'clear' && <p className="setup-notice is-warning">保存后将清除这台电脑上的 Key。需要 Key 的服务将无法使用。</p>}
        {credential === 'set' && <label>{current?.credential_configured ? '新的 API Key' : 'API Key'}
          <input type="password" autoComplete="new-password" placeholder="粘贴 API Key" maxLength={4096} value={key}
            disabled={disabled} onChange={e => setKey(e.target.value)} />
          <small>保存后输入框会清空，Key 不会写入浏览器存储。</small>
        </label>}
      </div>

      <div className="setup-footer">
        <Button disabled={disabled || unsaved || !selected} onClick={() => void runTest()}>测试连接</Button>
        <Button kind="primary" loading={busy} disabled={disabled || !selected || (credential === 'set' && !key)} onClick={requestSave}>保存</Button>
      </div>
      {unsaved && <p className="setup-description">有未保存的修改。测试连接使用的是已保存的设置。</p>}
      {testNotice && <p role="status" className={`setup-notice ${testNotice.ok ? '' : 'is-warning'}`}>{testNotice.text}</p>}

      {configuration.retired_credentials.length > 0 && <details className="setup-details">
        <summary>清理不再使用的旧 Key（{configuration.retired_credentials.length}）</summary>
        <p>这些旧 Key 仍保存在本机，可以逐个清理。</p>
        <div className="native-actions">
          {configuration.retired_credentials.map((reference, index) => <Button key={reference.configuration_request_id} disabled={disabled}
            onClick={() => void perform(async () => {
              await rpc('connections.cleanup_retired', reference); await load(); setNotice('已清理所选的旧 Key。');
            })}>清理旧 Key {index + 1}</Button>)}
        </div>
      </details>}
    </>}

    {!configuration && !busy && <div className="connection-first-use">
      <span className="setup-step-number">1</span>
      <div><h3>第一次使用</h3><p>先创建本机设置，然后填写模型服务和 API Key。</p></div>
      <Button kind="primary" disabled={busy || locked} onClick={() => void perform(async () => {
        await rpc('connections.bootstrap', {}); await load(); await onSaved();
      })}>开始设置</Button>
    </div>}
    {configuration?.recovery.map(reference => <Button key={reference.configuration_request_id} disabled={busy || locked}
      onClick={() => void perform(() => recover(reference))}>处理未完成的保存</Button>)}

    <div className="setup-footer connection-query">
      <span className="setup-description">设置在别处改过，或结果不确定时，可以重新读取。</span>
      <Button disabled={busy} onClick={() => void perform(load)}>重新读取</Button>
    </div>
    {locked && <p className="setup-notice is-warning">弈核 AI 正在使用游戏。请先停止它，再修改模型设置。</p>}
  </section>;
}
