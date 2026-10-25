# HTTP 模型适配器与文件快照服务

`service.py` 默认通过 `agent_runtime/` 的 PydanticAI 后端读取连接库和文件快照，执行非流式 Chat Completions 请求，经原引擎校验后输出策略。旧 `http_adapter.py` 传输仅通过 `--model-backend legacy` 显式选择，其档案解析与严格 JSON 合同仍被默认后端复用。**服务不包含游戏执行器，不会因模型请求成功而解锁游戏控制。** 本轮测试只调用localhost，DPAPI测试使用临时目录中的fake key，没有调用真实付费服务或读取用户真实密钥。

持续服务现默认使用有界记忆的BattleAgent，每次只传summary+delta+pending decisions。宿主任务、能力证据与执行反馈API见[BATTLE_AGENT.md](BATTLE_AGENT.md)。

## 脱敏就绪检查

先按 [Windows 同步与验证](../docs/windows-validation.md) 安装模型依赖。以下命令均从仓库根目录运行；`$tacticorePython` 是安装脚本实际使用的完整解释器路径，UUID / 路径占位符需先替换。安装说明见 [运行时文档](../agent_runtime/README.md)。

```powershell
& $tacticorePython .\strategy\service.py --commander <连接库中的指挥官UUID> --check-profile
```

默认只读 `%LOCALAPPDATA%/Tacticore/library.v2.json`，非 Windows 为 `~/.local/share/Tacticore/library.v2.json`，可用 `--library` 指定路径。不自动迁移历史配置或凭据。原 WinForms 客户端已删除；新 `desktop-ui/` 当前只提供离线演示，不创建真实连接库或保存密钥。不做HTTP请求，只输出ready/credential_available/model_configured及稳定绑定ID；不输出端点、密钥或回答正文。模型覆盖留空时继承连接default_model。远程服务仍要求在连接库同级 `secrets/<connection_id>.dpapi` 中存在由当前 Windows 用户加密的凭据，且 `remember_key=true`；当前没有新的凭据写入界面，完整配置流程尚待接入。不要将明文密钥写进 JSON。仅 localhost 允许不带密钥。

缺框架依赖会返回 `pydantic_dependencies_missing_run_agent_runtime_install`，不会静默改用旧后端。`--check-profile` 只检查依赖与档案，不发模型请求。

连接库使用 `schema_version: 2`，包含 `connections` 与 `commanders`；可参考 [离线测试中的合成格式](test_http_adapter.py)，那里的地址和密钥仅是测试夹具。模型与凭据格式校验由 `load_profile` 保留执行。

缺密钥原因：`credential_not_saved`表示remember_key未启用，`credential_file_missing`表示加密文件缺失，`credential_unavailable`表示无法解密或密钥格式无效。不会修改坏文件或自动迁移旧配置。

## 单次与持续运行

```powershell
& $tacticorePython .\strategy\service.py --commander <UUID> --player 3 --snapshot-file <snapshot.json> --once --runtime <本轮目录>
& $tacticorePython .\strategy\service.py --commander <UUID> --player 3 --snapshot-file <snapshot.json> --stop-file <stop.json> --runtime <本轮目录>
```

运行服务会真实请求所选模型，可能产生费用。`--once`请求一次决策；持续模式只在快照内容变化时处理新快照，等待模型时继续观察文件更新，并校验晚回答是否过时。快照文件应由采集器在同目录原子替换，契约见README及fixtures/snapshot.json。电力无法读取时用`resources.power_balance=null`，不伪填0；敌方视野未经验证时用空enemy_observations。生产原语未经验证时，capabilities.production_focus只提供native_baseline。

首个快照锁定session_id，`--session`可额外显式固定。换对局、换玩家或时间倒退不能自动重新绑定，应停止并重新启动实例。

输出位于 `<runtime>/<session>/player-<编号>/<commander>/`：

- status.json：经校验当前计划、最近结果和指标，始终execution.enabled=false/dry_run=true。
- plans.jsonl：引擎允许字段审计，不含原回答、端点、密钥和异常正文。
- service-health.json：输入状态与HTTP计数、固定错误码，无敏感请求内容。
- agent-state.json / jobs.json：持续记忆、确定性摘要与带task_id/plan_id/generation的有限任务建议，始终execution_authorized=false。

同一runtime目录下，OS文件锁确保同一session/player只有一个服务实例，指挥官换名或换档案不能绕开。退出或进程终止后OS释放锁，遗留.lock文件本身不代表被占用。不同runtime目录不共享锁；真实宿主必须统一租约目录，不能把此协作租约当作对恶意进程的安全边界。

停止可按Ctrl+C，或者原子写入：

```json
{"stop":true,"session_id":"<当前UUID>","player_id":3,"commander_id":"<当前UUID>"}
```

停止只取消本服务的在途请求和计划，不关闭游戏、不操作其他玩家。状态中的computer_verified仍为false，文件中的玩家身份不是可信游戏识别证据。

## 传输与费用边界

默认 PydanticAI 后端单次请求预算 12 秒，覆盖排队和 SDK 请求；无工具、无自动重试，关闭 tracing。HTTP body 受输入预算限制、响应正文最多 128 KiB，策略 JSON 最多 16 KiB；严格拒绝重复键、工具调用、拒绝或截断回答，原始 completion 必须明确 `finish_reason="stop"`。SDK 的 DNS 与取消行为不同于旧可终止解析子进程，仍需 Windows 真实网络验收，不能继承旧传输测试结论。

下面的解析子进程与 TransportPool 行为**仅适用于显式 legacy 后端**：总传输期限默认 12 秒，包含排队、可终止 DNS 子进程、TCP/TLS、响应读取与重试。HTTPS使用默认证书校验，HTTP仅限回环地址；不跟随重定向，不跨地址转发认证。响应头16 KiB，正文128 KiB，模型策略JSON16 KiB，拒绝重复JSON键、工具调用、拒绝或截断回答。DNS子进程不接收密钥，hostname经stdin传入，不打印诊断输出；取消会终止解析子进程。

两种后端默认都不重试。默认 PydanticAI 配合 `--http-retries 1` 会明确报错；只有 `--model-backend legacy --http-retries 1` 最多重试一次429/502/503/504，所有尝试仍受同一总期限约束；超时和连接失败不自动重试，避免不确定重复收费。legacy 的共享 TransportPool 默认最多两个在途请求；PydanticAI factory 使用对应的有界信号量。服务当前一个档案一个实例，不能把一个实例的上限误认为跨进程全局上限。

两种后端的 OpenAI 预设均经模拟线格式测试使用 max_completion_tokens，DeepSeek 和自定义兼容路径使用 max_tokens。DeepSeek关闭thinking以缩短简单战略JSON响应时间。供应商或特殊模型不支持参数时会返回固定错误码并走本地接续，不自动换模型或降低契约。档案personality与traits放入system消息，战场数据放入user消息；密钥只在Authorization中使用。

依据：[OpenAI Chat Completions官方接口](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[DeepSeek Chat Completions官方接口](https://api-docs.deepseek.com/api/create-chat-completion/)。模型未变更为任何其他默认模型。

## 本地验收

```powershell
& $tacticorePython -m unittest discover -s strategy -p 'test*.py' -v
```

历史旧适配器记录为42项通过，原始结果在http-test-results.txt；本轮完整 strategy 回归168项中166通过、2项Windows DPAPI跳过，另有新运行时28项离线通过。旧适配器测试覆盖Windows DPAPI互通（仅假密钥）、默认模型继承/覆盖、请求认证/性格上下文、不同供应商参数、重定向阻断、总超时/终止DNS、响应大小与分块读取、显式有限重试、并发上限、租约、文件更新后过时响应拒绝、绑定停止及敏感内容不落日志。真实供应商连通性与游戏效果不在这些测试结论中。
