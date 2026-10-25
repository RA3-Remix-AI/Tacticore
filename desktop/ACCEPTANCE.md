# 桌面端验收项4：多指挥官控制台

当前开发入口：`CommanderDesktop.exe`，已由主Agent按v3源码重建；保留独立输出 `CommanderDesktop.acceptance.v3.exe` 供对照。更新时未关闭用户原有桌面实例。`Build.ps1` 已切换至新主表单 `CommanderHub.cs`；旧 `CommanderDesktop.cs` 与 `DesktopTests.cs` 保留作历史参考，不参与新构建。

## 已实现

- 三分区：模型连接库、指挥官档案、战局与日志。
- 完全自绘深色tab容器，移除原生白色header余白与3D边框；下拉项、收起态箭头、禁用态边框使用深色绘制。真实开始按钮为暗色浅字“真实指挥尚未就绪”。
- 连接：稳定UUID、名字、供应商、端点、默认模型、独立API Key；同一连接可被多个档案引用。
- 档案：稳定UUID、独立显示名、connection_id、可选模型覆盖、性格预设与偏好。模型覆盖留空继承连接默认模型。
- 默认本地档案为铁锤、堡垒、幽灵，共享OpenAI连接；默认模型和密钥未填写时明确显示未配置。改连接或档案名字不改变UUID。
- 不提供删除连接操作，因此不会静默把引用档案切到其他服务。
- 新持久化文件：当前用户LocalAppData/TriadFrontCommander/library.v2.json。密钥按连接UUID分别保存到secrets/*.dpapi，使用DPAPI CurrentUser，不写入JSON、导出或日志。
- 旧config.json/key.dpapi只读迁移到内存，用户显式保存后写新库；旧文件原样保留。旧文件是迁移备份，取消新版密钥保存不会自动删除它们。
- 某连接解密失败只让该连接显示需重填，保留原密钥字节与其他档案。未重填且继续保存时不会覆盖坏密钥文件。整个库损坏时打开只读恢复视图，不覆盖原文件。
- 显式保存导出commander-bindings.json，含稳定档案ID、显示名、connection_id、模型覆盖/实际模型与性格，不含端点或密钥，标记game_sync_verified=false。策略实例键定义为(session_id,player_id,commander_id)，不按显示名或全局档案名共享记忆。
- 读取strategy/status.json协议或fixture的模拟状态，展示绑定匹配、计划、执行反馈与计数；当前只接受明确mode=simulation、provenance.kind=simulated、computer_verified=false、execution.enabled=false的数据。
- 本窗口离线演练可以开始/停止；不会请求模型、读取游戏或发游戏命令。读取外部状态的“停止本地观察”只停止本窗口timer，不宣称停止外部服务或游戏。
- “真实指挥尚未就绪”始终禁用。模型连接测试通过、载入模拟计划或按下游戏ping都不能解除锁定。

## 未通过/未实现的游戏能力

没有真实电脑玩家身份采集，因此目标列表只有明确标识的离线样例，无法选择或自动认定真实电脑。没有验证游戏中多个指挥官名字注册、原生AI持续接管、生产控制或正常模拟线程入口。UI不会将本地档案保存等同于游戏同步、真实绑定或接管成功。

当前状态查看器一次观察一个状态文件；它没有启动策略服务CLI或管理多个真实游戏实例。未来多个电脑复用同一档案时，每个session/player需由策略服务创建独立实例。

## 构建与测试

```powershell
.\Build.ps1 -OutputName CommanderDesktop.acceptance.v3.exe
.\Test.ps1
```

41项本地检查通过，详见acceptance-tests.log，包括：

- 多档案共享连接、默认模型继承与覆盖、改名保留UUID。
- 两个连接独立DPAPI往返、单连接坏密钥隔离/保留/重填、遗忘一把密钥不影响另一把。
- 旧配置只读迁移、保存后原文件不变、损坏整库不覆盖。
- 导出与JSON没有测试密钥；无效连接引用在写盘前拒绝。
- 供应商切换清空当前密钥、端点预设、本地模拟HTTP请求路径/认证与无效响应清除成功状态。
- 三个strategy fixture兼容；声称真实游戏或执行启用的状态被拒绝。
- 离线演练/状态导入/模型验证均不能解锁真实开始；停止仅结束本地timer。

测试只使用localhost模拟服务与fake-key，测试配置写在desktop/test-runs/，没有使用真实服务商密钥，也没有改用户LocalAppData配置。图形布局最终视觉QA由主Agent完成；本Agent未控制用户GUI或启动游戏。
