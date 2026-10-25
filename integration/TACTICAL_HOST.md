# 整局战术宿主接入

本文件说明已实现的宿主协议，不替代真实能力验收。未通过原始游戏证据的purpose始终锁定。

## 启动及证据

`battle_host.py`新增`--with-visibility`：校验精确EXE、Mod包、视野实现和来源证据，再在当前session按真实电脑人格/玩家及视野链握手。观察者视野不得进入电脑快照。

`--tactical-evidence <manifest.json>`同时要求真实执行宿主和视野握手。清单是schema1精确结构：

```json
{"schema_version":1,"sources":[{"module":"combined_arms","purpose":"coordinate_force","report":"<已完成的原始实测报告绝对路径>"}]}
```

宿主通过`tactical/evidence.py`重新计算原始判据并核包、玩家、指挥官、当前DLL/host修订，之后才构造`TacticalEvidence`。不能给清单写一个passed字段解锁；recon、harass_economy、main_attack、coordinate_force分别验收。真实执行器启动时再次验证授权来源。

## 数据及任务

己方对象采集使用原生GameLogic活体列表，仅导出指定玩家的对象。联网局势包含己方聚合资源/生产、受指定电脑视野过滤的联系人、有限地区和不含ObjectID的编队。具体对象、坐标、HP、模板及视野格集合留在宿主私有查找表。

`FormationRegistry`按session生成不透明编队ID、成员互斥并标记版本。初版可用角色限已验证的Conscript/Flak；编队预留后不补入新成员，执行中的原版本保留用于回执关联。原生执行器仍会逐个重验真实单位、归属、有效期、可见目标及原生上下文。

派单顺序：先持久化command/task/seq、允许成员、版本和期限，预留编队，再`agent.host_commit_task()`，最后调用异步执行器。`dispatch_pending`保留任务及预算锁，不冒充已经发出SDK命令；真实issued证据到来才发送started。执行器accepted时分配的实际成员必须非空、无重复、全属于可信编队，随后冻结，不要求把预算上限全部用完。

同一时刻宿主只派一个原生战术任务，避免不同DLL同时挂接相同入口。所有新请求仍经过完整目的能力守卫，不能用校准API的成功回执冒充高级任务。

完成回执须满足：

- 精确session/player/commander、command和公开seq；执行窗口与编队版本不变。
- 逐份原始报告来自本局运行目录，child command/task UUID及native seq匹配。
- 原始issued/returned在冻结的派单至过期窗口内，聚合issued与反馈一致。
- 原始报告完整且不重复覆盖accepted分配成员；双角色批次必须完整对应前排/支援。
- 当前purpose的原始游戏判据重新通过，真实目标达成且原生恢复已验证。

任何未知结果继续占用，不按未派发取消。已started但恢复未证时停止新的战术派发，并进入宿主安全停止流程。目的失败、到达失败或没有伤害都保留失败记录。

## 时钟及退出

own与visibility组合样本的模拟帧差最多3帧、暂停状态必须一致；时钟回退、身份或包漂移硬拒绝。明确非原子读取失败最多连续重试5次，重试时清空可执行目标，不发新命令；恢复成功后计数归零。完整对局持续使用同一个BattleAgent，保留短时记忆、摘要及结构化结果。

停止时先取消在途模型请求，收取最终合法生产及战术回执、恢复原生执行器，再停止Agent。独立只读`watch_match.py`以0.1秒周期保留清理前的原生结算，不把返回统计菜单后的frame0当作胜负证明。胜负仍需实际参与者身份和结算画面交叉确认。

Windows日志写入对临时共享读锁作有界重试。永久I/O错误保持失败/未知，不能把不完整的文件当成功。
