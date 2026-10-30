import {useEffect, useRef, useState} from 'react';
import {Button} from './components/ui';
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
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), [notice, setNotice] = useState('等待查询本机连接。');
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
      ? successNotice ?? '已读取当前本机配置。本次仅检查凭据是否已保存，未验证密钥或远端可用性。'
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
    await load('连接已保存。请重新载入指挥官配置并检查对局；远端可用性仍以实际调用为准。'); await onSaved();
  }
  async function recover(reference: ConfigurationReference) {
    const result = await rpc<{saved: boolean}>('connections.recover', reference);
    await load(result.saved ? '未完成的保存已核对恢复，请重新检查配置。' : '未应用的更新已取消，原配置已保留。'); await onSaved();
  }
  return <section className="native-panel"><h2>本机连接配置</h2>
    <p role="status" className="native-muted">{notice}</p>
    <p className="native-muted">密钥只提交给本机可信配置服务，不会回显或写入浏览器存储。更改接口时需重新输入密钥。</p>
    {configuration?.ready && <>
      <label>连接<select value={selected} disabled={busy || locked || uncertain} onChange={e => choose(e.target.value)}>
        {configuration.connections.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label>名称<input maxLength={60} value={name} disabled={busy || locked || uncertain} onChange={e => setName(e.target.value)} /></label>
      <label>提供方<select value={provider} disabled={busy || locked || uncertain} onChange={e => setProvider(e.target.value as typeof provider)}>
        <option>OpenAI</option><option>DeepSeek</option><option>自定义</option></select></label>
      <label>接口根地址<input maxLength={2048} value={endpoint} disabled={busy || locked || uncertain} onChange={e => setEndpoint(e.target.value)} /></label>
      <label>默认模型<input maxLength={200} value={model} disabled={busy || locked || uncertain} onChange={e => setModel(e.target.value)} /></label>
      <label>密钥处理<select value={credential} disabled={busy || locked || uncertain} onChange={e => {setCredential(e.target.value as typeof credential); setKey('');}}>
        <option value="keep">保留当前密钥设置</option><option value="set">保存或替换密钥</option><option value="clear">停用保存的密钥</option></select></label>
      {credential === 'set' && <label>新密钥<input type="password" autoComplete="new-password" maxLength={4096} value={key}
        disabled={busy || locked || uncertain} onChange={e => setKey(e.target.value)} /></label>}
      <Button disabled={busy || locked || uncertain || !selected || credential === 'set' && !key} onClick={() => void perform(save)}>保存连接</Button>
      {configuration.retired_credentials.length > 0 && <p className="native-muted">有不再使用的旧密钥仍保存在本机。
        {configuration.retired_credentials.map((reference, index) => <Button key={reference.configuration_request_id} disabled={busy || locked || uncertain}
          onClick={() => void perform(async () => {await rpc('connections.cleanup_retired', reference); await load(); setNotice('所选旧密钥已清理。');})}>清理旧密钥 {index + 1}</Button>)}</p>}
    </>}
    {configuration?.recovery.map(reference => <Button key={reference.configuration_request_id} disabled={busy || locked}
      onClick={() => void perform(() => recover(reference))}>核对未完成的保存</Button>)}
    <div className="native-actions"><Button disabled={busy} onClick={() => void perform(load)}>重新查询连接</Button>
      {!configuration && <Button disabled={busy || locked} onClick={() => void perform(async () => {await rpc('connections.bootstrap', {}); await load(); await onSaved();})}>初始化本机配置</Button>}</div>
    {locked && <p className="native-warning">请先停止当前运行并确认归还，再修改连接。</p>}
    {uncertain && <p className="native-warning">配置尚未核验；请重新查询或核对未完成的保存，再启动指挥官。</p>}
  </section>;
}
