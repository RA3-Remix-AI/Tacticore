import {useEffect, useRef, useState} from 'react';
import {Button} from './components/ui';
import './native-setup.css';
import {connectionConfigRpc, connectionConfiguration, connectionConfigError,
  type ConnectionConfigRpc, type ConnectionConfiguration, type ConfigurationReference} from './runtime/connectionConfigRpcV1';
import type {ConnectionConfigurationState} from './runtime/connectionConfigurationStateV1';

/** New component only; mount outside the existing profile conditional after native fusion. */
export function ConnectionConfigPanelV1({locked, onSaved, onConfigurationState, rpc = connectionConfigRpc}: {
  locked: boolean; onSaved: () => void | Promise<void>;
  onConfigurationState?: (state: ConnectionConfigurationState) => void; rpc?: ConnectionConfigRpc;
}) {
  const [configuration, setConfiguration] = useState<ConnectionConfiguration | null>(null);
  const [selected, setSelected] = useState(''), [name, setName] = useState(''), [provider, setProvider] = useState<'OpenAI' | 'DeepSeek' | '自定义'>('OpenAI');
  const [endpoint, setEndpoint] = useState(''), [model, setModel] = useState(''), [key, setKey] = useState('');
  const [credential, setCredential] = useState<'keep' | 'set' | 'clear'>('keep');
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [notice, setNotice] = useState('正在读取本机连接配置…');
  const pending = useRef(false);
  const observedState = useRef<ConnectionConfigurationState>('unverified');
  function choose(id: string, value = configuration) {
    const row = value?.connections.find(candidate => candidate.id === id);
    if (!row) return;
    setSelected(id); setName(row.name); setProvider(row.provider); setEndpoint(row.endpoint); setModel(row.model);
    setKey(''); setCredential('keep');
  }
  async function load(successNotice?: string) {
    const result = connectionConfiguration(await rpc('connections.configuration', {}));
    observedState.current = result.ready ? 'ready' : 'pending';
    setConfiguration(result); setUncertain(!result.ready);
    setNotice(result.ready
      ? successNotice ?? '已读取本机配置。远端连接尚未测试。'
      : '上次配置更新尚未核验，请核对未完成的保存；当前不能开始新的指挥。');
    if (result.ready) {choose(result.connections.some(row => row.id === selected) ? selected : result.connections[0].id, result);}
  }
  async function perform(operation: () => Promise<void>) {
    if (pending.current) return;
    pending.current = true;
    observedState.current = 'unknown';
    onConfigurationState?.('checking');
    setBusy(true);
    try {await operation(); onConfigurationState?.(observedState.current);}
    catch (error) {setNotice(connectionConfigError(error)); setUncertain(true); onConfigurationState?.('unknown');}
    finally {pending.current = false; setBusy(false); setKey('');}
  }
  useEffect(() => {void perform(load);}, []);
  async function save() {
    if (!configuration?.ready || !configuration.config_fingerprint || locked || uncertain) return;
    await rpc('connections.configure', {schema_version: 1, connection_id: selected,
      expected_config_fingerprint: configuration.config_fingerprint, name, provider, endpoint, model,
      credential_operation: credential, ...(credential === 'set' ? {api_key: key} : {})});
    await load('连接已保存。请重新检查对局；远端可用性仍以实际调用为准。'); await onSaved();
  }
  async function recover(reference: ConfigurationReference) {
    const result = await rpc<{saved: boolean}>('connections.recover', reference);
    await load(result.saved ? '未完成的保存已核对恢复，请重新检查配置。' : '未应用的更新已取消，原配置已保留。'); await onSaved();
  }
  const disabled = busy || locked || uncertain;
  const current = configuration?.connections.find(row => row.id === selected);
  const changedDestination = Boolean(current && (current.provider !== provider || current.endpoint !== endpoint));
  function validationMessage() {
    if (!name.trim()) return '请填写连接名称。';
    try {
      const url = new URL(endpoint);
      if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) return '请填写不含账户、参数或片段的接口根地址。';
    } catch {return '请填写完整接口地址，例如 https://api.openai.com/v1。';}
    if (credential === 'keep' && current?.remember_key && changedDestination) return '接口已更改，请选择设置新密钥或清除已存密钥。';
    if (credential === 'set' && (!key || /\s/.test(key))) return '新密钥不能为空，也不能包含空格或换行。';
    return '';
  }
  function requestSave() {
    const message=validationMessage();
    if(message){setNotice(message);return;}
    void perform(save);
  }
  return <section className="native-panel connection-panel setup-panel">
    <div className="setup-panel-heading"><div><p className="eyebrow">MODEL CONNECTION / 02</p><h2>连接你的模型</h2><p className="setup-description">选择提供方，配置指挥官使用的模型。</p></div><span className={`setup-badge ${configuration?.ready&&!uncertain?'is-ready':''}`}>{busy?'正在处理':uncertain?'待核验':configuration?.ready?'本机已配置':'首次设置'}</span></div>
    <p role="status" className={`setup-notice ${uncertain?'is-warning':''}`}>{notice}</p>
    {configuration?.ready && <>
      <div className="connection-form-grid">
        <label className="connection-full">当前连接<select value={selected} disabled={disabled} onChange={e => choose(e.target.value)}>
          {configuration.connections.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
        <label>连接名称<input placeholder="例如：我的指挥官连接" maxLength={60} value={name} disabled={disabled} onChange={e => setName(e.target.value)} /></label>
        <label>提供方<select value={provider} disabled={disabled} onChange={e => setProvider(e.target.value as typeof provider)}>
          <option>OpenAI</option><option>DeepSeek</option><option>自定义</option></select></label>
        <label className="connection-full">接口根地址<input type="url" spellCheck={false} placeholder={provider==='DeepSeek'?'https://api.deepseek.com/v1':'https://api.openai.com/v1'} maxLength={2048} value={endpoint} disabled={disabled} onChange={e => setEndpoint(e.target.value)} /><small>填写 API 根地址，无需添加 /chat/completions。</small></label>
        <label className="connection-full">默认模型<input spellCheck={false} placeholder={provider==='DeepSeek'?'例如：deepseek-chat':'填写提供方支持的模型 ID'} maxLength={200} value={model} disabled={disabled} onChange={e => setModel(e.target.value)} /><small>可留空；指挥官指定的模型优先使用。</small></label>
      </div>
      <div className="connection-credentials"><div className="connection-section-heading"><h3>API 密钥</h3><span className="setup-step-state">{current?.credential_configured?'本机已保存':'尚未保存'}</span></div>
        <p>密钥仅保存在本机，不会回显。保存配置不会测试远端连接。</p>
        <label>密钥处理<select value={credential} disabled={disabled} onChange={e => {setCredential(e.target.value as typeof credential); setKey('');}}>
          <option value="keep">保留当前密钥设置</option><option value="set">设置或替换密钥</option><option value="clear">清除当前密钥设置</option></select></label>
        {credential==='keep'&&<small>保持当前设置；修改提供方或接口时，需重新设置或清除密钥。</small>}
        {credential==='clear'&&<p className="setup-notice is-warning">保存后将停用当前密钥。旧凭据可在下方清理；需认证的模型要重新设置密钥。</p>}
        {credential === 'set' && <label>新密钥<input type="password" autoComplete="new-password" placeholder="粘贴该接口的 API Key" maxLength={4096} value={key}
          disabled={disabled} onChange={e => setKey(e.target.value)} /><small>提交后清空输入框，不写入浏览器存储。</small></label>}
      </div>
      <div className="setup-footer"><p className="setup-description">保存后需重新检查对局配置。</p><Button kind="primary" loading={busy} disabled={disabled || !selected || credential === 'set' && !key} onClick={requestSave}>保存连接</Button></div>
      {configuration.retired_credentials.length > 0 && <details className="setup-details"><summary>清理不再使用的旧密钥（{configuration.retired_credentials.length}）</summary><p>旧密钥仍保存在本机，可逐一清理。</p>
        <div className="native-actions">{configuration.retired_credentials.map((reference, index) => <Button key={reference.configuration_request_id} disabled={disabled}
          onClick={() => void perform(async () => {await rpc('connections.cleanup_retired', reference); await load(); setNotice('所选旧密钥已清理。');})}>清理旧密钥 {index + 1}</Button>)}</div></details>}
    </>}
    {!configuration&&!busy&&<div className="connection-first-use"><span className="setup-step-number">01</span><div><h3>建立你的第一个连接</h3><p>初始化后，填写提供方、模型与 API 密钥。</p></div><Button kind="primary" disabled={busy || locked} onClick={() => void perform(async () => {await rpc('connections.bootstrap', {}); await load(); await onSaved();})}>初始化本机配置</Button></div>}
    {configuration?.recovery.map(reference => <Button key={reference.configuration_request_id} disabled={busy || locked}
      onClick={() => void perform(() => recover(reference))}>核对未完成的保存</Button>)}
    <div className="setup-footer connection-query"><span className="setup-description">配置有变更或结果不确定时，可重新查询。</span><Button disabled={busy} onClick={() => void perform(load)}>重新查询连接</Button></div>
    {locked && <p className="setup-notice is-warning">请先停止当前运行并确认归还，再修改连接。</p>}
    {uncertain && <p className="setup-notice is-warning">配置尚未核验；请重新查询或核对未完成的保存，再启动指挥官。</p>}
  </section>;
}
