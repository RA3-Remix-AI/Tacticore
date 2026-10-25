import {
  CheckCircle,
  FloppyDisk,
  Key,
  Plug,
  Plus,
} from "@phosphor-icons/react";
import { Button, PageHeading, PanelHeading } from "../components/ui";
import type { Connection } from "../state/settings";
export function ConnectionsPage({
  connections,
  selectedId,
  onSelect,
  onChange,
  onSave,
  onAdd,
  onValidate,
  dirty,
  locked,
  keyValue,
  onKeyChange,
  validating,
  validation,
}: {
  connections: Connection[];
  selectedId: string;
  onSelect: (id: string) => void;
  onChange: (patch: Partial<Connection>) => void;
  onSave: () => void;
  onAdd: () => void;
  onValidate: () => void;
  dirty: boolean;
  locked: boolean;
  keyValue: string;
  onKeyChange: (value: string) => void;
  validating: boolean;
  validation: string | null;
}) {
  const selected =
    connections.find((c) => c.id === selectedId) ?? connections[0];
  return (
    <>
      <PageHeading
        eyebrow="MODEL CONNECTIONS / 模型连接"
        title="连接判断力。"
        description="预先整理模型与连接档案。此演示不发起任何模型请求，也不会保存 API Key。"
      >
        <Button onClick={onAdd} disabled={locked || connections.length >= 12}>
          <Plus size={16} />
          新增连接
        </Button>
      </PageHeading>
      <div className="editor-grid">
        <aside className="profile-list" aria-label="连接列表">
          {connections.map((c) => (
            <button
              className={`profile-card ${c.id === selected.id ? "selected" : ""}`}
              key={c.id}
              aria-pressed={c.id === selected.id}
              onClick={() => onSelect(c.id)}
              disabled={locked}
            >
              <span className="profile-card-icon">
                <Plug size={25} />
              </span>
              <span>
                <strong>{c.name}</strong>
                <small>{c.provider} / 未连接</small>
              </span>
            </button>
          ))}
          <div className="aside-note">
            <Key size={22} />
            <p>
              连接配置与指挥官分开。
              <br />
              同一连接可供多个档案引用。
            </p>
          </div>
        </aside>
        <section className="panel editor-panel">
          <PanelHeading eyebrow="CONNECTION PROFILE" title="连接配置">
            <span className="tiny-pill">演示配置</span>
          </PanelHeading>
          <fieldset disabled={locked}>
            <div className="form-grid">
              <label>
                连接名称
                <input
                  value={selected.name}
                  maxLength={60}
                  onChange={(e) => onChange({ name: e.target.value })}
                />
              </label>
              <label>
                服务类型
                <select
                  value={selected.provider}
                  onChange={(e) => {
                    const provider = e.target.value as Connection["provider"];
                    onKeyChange("");
                    onChange({
                      provider,
                      endpoint:
                        provider === "OpenAI"
                          ? "https://api.openai.com/v1"
                          : provider === "DeepSeek"
                            ? "https://api.deepseek.com"
                            : "",
                    });
                  }}
                >
                  <option>OpenAI</option>
                  <option>DeepSeek</option>
                  <option>自定义</option>
                </select>
              </label>
            </div>
            <label>
              基础地址
              <input
                type="url"
                value={selected.endpoint}
                placeholder="https://api.example.com/v1"
                onChange={(e) => onChange({ endpoint: e.target.value })}
              />
              <small>仅在本机检查格式；不会请求此地址。</small>
            </label>
            <label>
              演示模型名称
              <input
                value={selected.model}
                maxLength={200}
                placeholder="填写准备使用的模型名称"
                onChange={(e) => onChange({ model: e.target.value })}
              />
            </label>
            <label>
              API Key <span className="optional">无需填写真实密钥</span>
              <input
                type="password"
                value={keyValue}
                autoComplete="off"
                placeholder="仅演示输入交互，不连接模型"
                onChange={(e) => onKeyChange(e.target.value)}
              />
              <small>
                仅保留在当前窗口内存中，刷新或关闭后清空；不保存、不发送。
              </small>
            </label>
          </fieldset>
          <div className="validation-note" role="status">
            <CheckCircle size={17} />
            <span>
              {validation ?? "尚未检查配置格式。格式通过也不代表真实连接成功。"}
            </span>
          </div>
          <div className="form-footer">
            <p>
              {dirty ? "有未保存的演示配置。" : "非敏感演示配置已保存在本机。"}
            </p>
            <div className="button-group">
              <Button
                onClick={onValidate}
                loading={validating}
                disabled={locked}
              >
                检查配置格式
              </Button>
              <Button
                kind="primary"
                onClick={onSave}
                disabled={!dirty || locked}
              >
                <FloppyDisk size={16} />
                保存配置
              </Button>
            </div>
          </div>
        </section>
      </div>
      <div className="info-banner">
        <Plug size={22} />
        <p>
          <strong>真实模型接入尚未启用。</strong>{" "}
          当前客户端不会读取本机凭据、游戏会话文件或调用原生执行器。
        </p>
      </div>
    </>
  );
}
