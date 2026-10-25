# 默认 PydanticAI 决策层迁移交接

Windows 接手顺序与可复制命令见 [Windows 同步与策略验证](../windows-validation.md)。代码默认已经切换，Windows 安装、新桌面接入、真实模型与游戏实战尚待验收。本轮没有启动游戏，没有调用付费 API，没有读取或修改密钥。

## Windows 同步时的最小改动范围

| 文件 | 改动目的 |
| --- | --- |
| `agent_runtime/` | 新模型层、唯一 factory、固定依赖、离线验证和安装脚本 |
| `strategy/model_backend.py` | 唯一源码路径 bootstrap，避免每个入口自行拼 provider |
| `strategy/service.py` | 使用 factory、增加后端参数与缺依赖错误、health 标明后端 |
| `integration/battle_host.py` | 使用 factory、增加同一后端参数与启动前依赖检查 |
| `integration/probe_strategy.py` | 统一 probe 的模型组装与明确失败 |
| `strategy/test_http_adapter.py` | 合成 HTTP completion 补齐标准协议元数据，其他断言与行为不变 |
| 原 `desktop/` | 15 个 tracked WinForms 源码、脚本与说明文件已删除，不再提供旧客户端 |

没有修改 `strategy/engine.py`、`battle_agent.py`、`missions.py`、`http_adapter.py` 的算法或合同，也没有改 `tactical/`、`native-ai/` 或原生桥接代码。Windows 另一侧可以继续迭代这些模块；合并上述入口时只替换组装行，不能覆盖整份本机文件。原有 prompt/schema 更新会经依赖注入直接生效，不维护第二份策略定义。

## 默认与回退

```powershell
# 在仓库根目录为宿主建立环境；已有明确环境时可直接指定其完整路径。
py -3.12 -m venv .venv
$tacticorePython = (Resolve-Path '.\.venv\Scripts\python.exe').Path
.\agent_runtime\Install-Windows.ps1 -Python $tacticorePython

# 下两行是参数示意，替换 <其余既有参数> 后再运行；所有入口使用同一解释器。
& $tacticorePython .\strategy\service.py --model-backend pydantic <其余既有参数>
& $tacticorePython .\strategy\service.py --model-backend legacy <其余既有参数>
```

示例中的占位参数需要替换，不是可直接运行的实战命令。`battle_host.py` 与 `probe_strategy.py` 使用相同参数。真实入口仍必须先满足原有会话、档案、游戏、能力证据及控制权要求。原 WinForms 客户端已删除；新 `desktop-ui/` 当前是离线演示，真实宿主连接尚未实现。配置默认位于 `%LOCALAPPDATA%/Tacticore/library.v2.json`（非 Windows 为 `~/.local/share/Tacticore/library.v2.json`），`--library` 仍可指定任意明确配置路径，不自动迁移旧文件。

缺依赖固定返回 `pydantic_dependencies_missing_run_agent_runtime_install`，不自动使用旧后端。`--http-retries 1` 与默认后端冲突会返回 `pydantic_retry_must_be_zero`；只有显式 legacy 可保留原 HTTP 重试。

Windows 安装脚本安装锁定版本并运行离线测试，不调用外部模型。安装操作会修改指定 Python 环境；自定义解释器必须与宿主实际运行的解释器一致。源码 bootstrap 优先使用本仓库的 `agent_runtime/src`。未来新桌面必须在宿主侧实现启动前复查，不能沿用已删除 UI 的预检状态或把 UI 就绪标记当授权。

## 合同与安全边界保持

- `context → dict policy` 接口保持；额外提供 `PolicyRequest` v1 和本进程单调时钟 deadline。游戏快照过期仍由宿主判断。
- 旧 `parse_model_json` 保留重复键/NaN/大小错误与 `ContractError` 身份。SDK 前验证原始 HTTP envelope，必须 `finish_reason == "stop"`，拒绝 refusal 与 tool_calls，不能依赖 SDK 对缺失字段的归一化。
- 默认 Agent 无工具、无跨轮消息历史，框架/SDK/HTTP 重试为零；持续游戏记忆、任务、资源预留与执行权仍在旧模块。
- telemetry 保持 `attempts/retries/timeouts/responses/max_request_bytes`、`last_error_code` 与 `last_diagnostics`。最大请求字节数来自真实序列化 wire body，估算仅用于提前压缩。
- SDK client 随每次请求关闭；取消不转成成功结果。所有错误回退仍需经旧 `StrategyEngine` 决策，不自动在模型后端间重试。
- PydanticAI 要求标准 completion envelope。旧测试夹具已补全 `id/object/model/created/index/role`，没有为真实服务商补造字段。非标准自定义服务需修正或显式 legacy。

## 已验证与待验证

本轮 macOS / Python 3.12 离线验证：新运行时 28 项通过；完整 `strategy` 回归 168 项中 166 通过、2 项 Windows DPAPI 测试跳过。默认入口下已有 service 子进程测试覆盖快照更新后拒绝旧响应、停止取消及不派发游戏命令。额外覆盖默认选择、明确回退、缺依赖 JSON 错误、真实框架两轮宿主记忆、原始完成状态和压缩协商。

还需要 Windows 安装和 DPAPI 两项、新桌面与真实宿主连接、启动前复查、真实网络 DNS/取消、所选模型兼容性、受控实战与性能/费用对比。现有历史胜负和原语证据属于旧运行版本，不能标成 PydanticAI 新默认已实战通过。安装新依赖后按原证据门禁重新验收，不修改历史证据文件来放行。
