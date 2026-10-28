# 多通道关闭与独立归还审计

`host_runtime.runtime_epoch_release`是可信本机CLI，不在模型或客户端RPC白名单中。它在原Host已结束后读取原游戏映射、所有通道的不可变退役捕获、原始生产账本及原生入口字节；不装钩子、不派游戏命令、不重试接入，不授予战术或自然结算信用。

## 必须同时成立的证据

- Host PID及起始时间匹配原启动回执，操作系统确认该Host已结束；原状态、原会话、原进程起始身份及生产绑定一致，原启动已终态。
- 同一游戏/玩家/指挥官的全部SQLite运行必须组成一个完整、无环的通道链。每次退役、固定后继授权和attach均与原不可变manifest、SHA、绑定、生产付款ID及原Host身份对应；不忽略孤立运行或额外授权。
- 每个通道以原始Bootstrap、演员、成对关闭头、完整事件及钩子流重算`assess_retirement`，要求flags0、state3、restore8191、callback0、NativeHost exit0、无丢失和发布已确认。已被后继替换的旧映射使用原退役时的只读捕获；最后未退役的通道必须重新读取原映射。
- 所有已发送战术包必须逐一对应SQLite命令、原生序号、任务/租约，以及原始事件中的帧/时钟/阶段/归还事实。未知Reserve、Commit或恢复命令需其独立恢复证据，不能由本审计例外消除。
- 最终生产映射需成对稳定，phase2、restore31、callback0、error0；全部实付及SDK前拒绝逐笔对应原始账本。另读19处原入口，检查被动观察器已关闭或映射不存在。
- 在写审计文件前，再次核对全部来源SHA、原Host已结束、SQLite非审计意图集合未变化。新文件fsync后才发布新的审计回执；半发布保持未完成，不自动重试。

## 未决attach的特殊处理

只有原操作为`runtime_channel_attach`且仍为uncertain，并且其原生通道关闭、command generation0、命令0、事件0、receipt idle且未持有控制时，才另记`review_runtime_channel_release`。新记录明确no_control_acquired及无任务效果，绑定同一原接入ID和审计文件SHA。

SQLite只从“当前未决控制投影”中排除此接入；原uncertain状态、原因、历史事件完全保留。该规则不处理未知游戏命令，也不将失败接入改成成功。原Host仍显示fault。

整个Host的`review_runtime_host_release`还需覆盖全部通道。客户端投影验证审计SHA、原Host身份、每个来源SHA、全部运行ID、非审计命令集合，以及全会话未决集合。后续新增命令、增加孤立通道或改动来源会使投影失效。归还证明不声称实际回家、战术效果或自然对局结算；此前局部任务的独立效果证据另存。

## 验证范围

`test_host_runtime_epoch_release.py`重算`131614`真实三通道原始数据，并验证跨进程SQLite重开后旧uncertain仍保留。反例覆盖缺失授权、错误SHA/绑定、漏通道、未确认发布、未知Commit、伪造归还事实、回执不在原事件中，以及审计后新增意图。

这项审计只解决控制归还。G4其余动作/异常、G6高级战术、G7完整自然对局和G8对照实验仍需各自完整证据。
