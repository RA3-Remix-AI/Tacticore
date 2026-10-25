# Tacticore Decision Runtime

这是默认的 **PydanticAI 决策模型层**。`strategy/service.py`、`integration/battle_host.py`、`integration/probe_strategy.py` 三个真实模型入口已统一接入；默认 `pydantic`，原 `ChatAdapter` 仅通过显式 `--model-backend legacy` 回退，不会静默替代。

模型层的代码默认已切换；本轮只完成离线验证，没有真实模型或 Windows 游戏实战验证。`StrategyEngine` 的合同、过期检查与执行门禁，以及 `BattleAgent` 的游戏记忆和任务生命周期保持原样。

PydanticAI 2.61.0 负责一次受限 `context → JSON policy` 模型调用，统一管理 provider、请求预算、JSON 输出与取消。输出仍交给现有严格 parser 和宿主 validator 审定。选型见 [ADR](../docs/agent-runtime/0001-pydantic-decision-runtime.md)，Windows 合并边界见 [迁移交接](../docs/agent-runtime/migration-handoff.md)。

## 安装和离线验证

需要 Python 3.12+。Mac 离线验证在仓库根目录执行，虚拟环境放在仓库外。没有模型密钥，也不需要游戏。Windows 先运行 `./agent_runtime/Install-Windows.ps1`；脚本依次尝试 `py -3.12`、满足 3.12+ 的 `python`，也可用 `-Python <完整路径>` 明确指定；显式指定失败时不会换解释器。**必须使用脚本输出的同一解释器运行 `strategy/service.py` 或 `integration/battle_host.py`**。不依赖 Codex 或旧桌面私有目录。

```bash
python3.12 -m venv /tmp/tacticore-agent-runtime
/tmp/tacticore-agent-runtime/bin/python -m pip install -r agent_runtime/requirements-pydantic.lock
/tmp/tacticore-agent-runtime/bin/python -m pip install --no-deps ./agent_runtime

PYTHONDONTWRITEBYTECODE=1 PYDANTIC_AI_NO_BANNER=1 TACTICORE_REQUIRE_FRAMEWORK=1 \
PYTHONPATH=agent_runtime/src:strategy /tmp/tacticore-agent-runtime/bin/python \
  -m unittest discover -s agent_runtime/tests -v

PYTHONDONTWRITEBYTECODE=1 PYDANTIC_AI_NO_BANNER=1 PYTHONPATH=agent_runtime/src:strategy \
  /tmp/tacticore-agent-runtime/bin/python -m tacticore_agent_runtime.demo
```

Windows 的完整同解释器安装与验证步骤见 [Windows 指南](../docs/windows-validation.md)。已安装环境后，在仓库根目录执行；`$tacticorePython` 是安装脚本使用的完整 `python.exe` 路径：

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'agent_runtime\src') + ';' + (Join-Path $PWD 'strategy')
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYDANTIC_AI_NO_BANNER = '1'
$env:TACTICORE_REQUIRE_FRAMEWORK = '1'
& $tacticorePython -m unittest discover -s agent_runtime/tests -v
```

本轮实测：macOS arm64、Python 3.12.14，28 项全部通过。Windows 命令为运行说明，尚未在 Windows 验证。测试真正运行 PydanticAI 的 `Agent.run` / `FunctionModel`；DeepSeek 请求由内存 `MockTransport` 接收，旧 `ChatAdapter` 的测试只访问进程内 localhost 假服务。没有真实模型请求、游戏读取或写入。

演示结果应为 `status: accepted`、`execution_enabled: false`。这是旧策略引擎接受合成策略，**不表示游戏执行成功**。

未安装模型依赖时，`import tacticore_agent_runtime`、`LegacyBackend` 和 `ReplayBackend` 仍只需要标准库。省略 `TACTICORE_REQUIRE_FRAMEWORK=1` 可运行核心测试，框架测试会明确跳过；验收必须设置该变量，不能把跳过当框架通过。

`requirements-pydantic.lock` 锁定本轮实际安装的完整依赖版本；`pyproject.toml` 锁定默认框架直接版本。它是版本锁，不是带 wheel 哈希的跨平台制品锁；Windows 安装和制品许可需另外验证。

## 默认入口与显式回退

三个模型 CLI 都接受 `--model-backend pydantic|legacy`，省略即 PydanticAI。缺依赖返回 `pydantic_dependencies_missing_run_agent_runtime_install` 并退出；安装脚本只安装和做离线测试，不启动模型。原 WinForms 桌面已删除，新的 `desktop-ui/` 尚未连接真实宿主。宿主 CLI 默认读取 `Tacticore/library.v2.json`，可用 `--library` 显式指定；不自动搬移历史配置或凭据。

`--http-retries 1` 仅可与 `--model-backend legacy` 配合；PydanticAI 路径返回明确配置错误，避免多层重试。`service.py --check-profile` 检查依赖与本地档案；`battle_host.py --check` 还采样并核验当前游戏、会话、证据与构建，但都不调用模型或派单。后者可以产生本地采样记录，不是无 I/O 检查。

## 调用边界

| 入口 | 作用 |
| --- | --- |
| `create_backend(profile)` | 默认 PydanticAI；依赖缺失会明确失败，不联网探测、不回退 |
| `create_backend(profile, backend="legacy")` | 显式原适配器回退，仅此路径允许旧 HTTP 重试配置 |
| `LegacyBackend(existing_adapter)` | 只包裹已创建的旧 `ChatAdapter`，保留原返回值、异常和输入预算接口 |
| `ReplayBackend(entries, parse_json=...)` | 内存回放，匹配完整上下文 SHA256；不读取目录、不保存新记录 |
| `PydanticBackend(FunctionModel(...), ...)` | 离线框架验证，使用原 prompt 和原严格 JSON 解析器 |
| `openai_compatible_backend(profile, ...)` | 低层资源工厂，默认拒绝联网；生产 `create_backend` 仅在显式启动的服务发起决策时使用它 |

所有后端保留旧 `await backend(context) -> dict` 接口，并提供版本化入口：

```python
from tacticore_agent_runtime import PolicyRequest, LegacyBackend

# existing_chat_adapter 由现有代码创建；这里不加载密钥或自行导入原引擎。
backend = LegacyBackend(existing_chat_adapter)
result = await backend.run(PolicyRequest(
    context=sanitized_context,
    protocol_version=1,
    deadline=asyncio.get_running_loop().time() + 3.0,
))
```

`deadline` 是本进程 asyncio 单调时钟，不能作为 IPC 时间戳发送，也不是游戏时间。它只缩短本次调用预算；当前快照是否过期、任务是否还可派发，仍由宿主在返回后重新判断。取消向上传播；协作式取消无法强制终止一个故意吞掉取消的第三方模型实现，所以不得移除 `StrategyEngine` 原有超时/在途请求保护。

代码通过依赖注入复用 `parse_model_json` 和 `system_prompt(profile, context)`，没有复制旧 policy schema。SDK 返回原始文本后交给原解析器，因此重复 JSON 键、NaN 等仍产生原 `ContractError`；字段、绑定与战术有效性仍由旧引擎校验。没有 Pydantic 自动类型纠正，也没有“修复输出”重试。

## 当前约束

- 每次新建无历史 Agent；不启用工具、handoff、框架记忆或持久化。至多一次模型请求，框架/SDK/HTTP 重试均为 0。
- `agent.instrument=False`，不配置任何 tracing exporter；拒绝预包装的 `InstrumentedModel`。若外部进程全局注入 HTTP 监控，需由该进程单独审查，模块不能撤销外部监控。
- 网络工厂仅接受由现有宿主核验过的 `Profile`。客户端显式传密钥，拒绝无密钥的远端连接；不读取环境密钥、不跟随重定向、不使用环境代理。
- 默认输入预算 16 KiB（服务可显式配置 4–32 KiB）。框架估算预留 1 KiB 消息封装空间，帮助 `BattleAgent` 提前压缩；最终 HTTP body 再检查，`max_request_bytes` 记录实际发送体大小，不把估算当实测。响应上限 128 KiB，策略原文上限沿用旧解析器的 16 KiB；拒绝压缩响应。
- DeepSeek 的 Chat Completions JSON 模式、`max_tokens`、关闭思考参数已通过模拟线格式测试。尚未证明真实服务商兼容性、质量、费用、延迟或 Windows 运行可靠性。
- 不提供游戏工具、不接触原始地址、会话授权、档案存储、DPAPI 或生产/战术执行器。不得将本模块的成功返回直接视为派单授权。
- 底层 SDK 的 DNS/取消行为不等同于原 `ChatAdapter` 的可终止解析子进程；虽然代码默认已切换，真实网络故障、关闭退出和 Windows 实战仍须验证，不能以离线通过宣称生产可靠性。必要时显式选择 legacy。
- 默认 SDK 要求标准 Chat Completions envelope（例如 id/object/model、choice index、assistant role），比旧最小解析更严格；不补造服务端缺失元数据。非标准自定义服务须修正或显式回退。
