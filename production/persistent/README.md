# 长驻生产执行器（本地受控原型）

`client.py`提供`ProductionExecutor.start/submit/status/stop`。导入不注入；start由主控明确执行，使用同PID自然生产样本核验线程，再通过WH_GETMESSAGE在该游戏线程执行有限正常生产调用。不存在remoteThread、spawn、赠钱、价格修改、经济开关或取消原生订单。

当前启用范围由整局宿主限制为已验Flak与Conscript。代码白名单还包含Bear，但没有Bear真机闭环证据，最终宿主不应启用。原型只支持owner3的苏联电脑兵营；工厂被毁时拒绝，不猜测替代地址。

## 接入

```python
executor = ProductionExecutor(
    session_path, snapshot_path, factory_address, commander_uuid,
    natural_observation_path, total_budget=5000,
    reserve_floor=500, min_interval_frames=150)
executor.start()
result = executor.submit({
    "session_id": session_uuid, "player_id": 3,
    "commander_id": commander_uuid,
    "command_id": command_uuid, "task_id": task_uuid,
    "seq": 1, "unit": "conscript", "budget": 300,
    "reserve": 500, "expires_frame": current_frame + 450,
})
feedback = executor.status()["ledger"]
executor.stop()
```

UUID支持标准带连字符或32位hex。内部按完整128bit身份比较；回执保留调用方原始task_id，方便BattleAgent反馈关联。模型命令只含枚举与预算，不接受地址、任意代码、额外字段或布尔值冒充整数。返回回执不含内存地址。

入队回执为`queued`，`started=true, completed=false`。只有同一订单的原生扣款返回累计、node+0x68支付累计、生产tick TLS内原生create返回、正常结单、相同对象ID/归属/模板的活体样本都成立，才为`completed`。节点消失、首次扫描发现、单纯EAX入队ID或余额净差均不能替代。

## 守卫

- EXE SHA256与PID启动时间固定，session文件不得变化；包SHA256、注册表revision/hash与原生人格instanceID→UUID/Side绑定复核。每条派单再次核验原生人格store唯一成员与Side匹配，不靠名字。
- 每PID一个长驻映射，command UUID幂等、相同ID不同payload冲突拒绝、task UUID最多一次、seq严格递增。重复命令回同一receipt，不再排队；重复task新命令为native102。
- 由原生0x7df7e0查询实际报价，费用须在任务预算与全局承诺预算内；当前现金须覆盖现有队列未付负债、新单与预留。
- 最多2个已有订单，核对节点类型/模板/模块归属/ID/双向链接/头尾/费用。一次只追加1个订单；调用后验证旧订单身份、顺序、费用与已付未变，新节点/ID唯一且在尾部。
- 每次正常订单至少间隔设定逻辑帧；有效期不得过期或超过未来900帧。生命周期/时间回退拒绝。
- Python提交前两次读GameLogic+0x15c；游戏线程在调用lookup/price/enqueue前再次读，非0为`game_paused`、无生产调用，关闭snapshot与dispatch之间的暂停竞态。
- Python每0.5秒续本地heartbeat；5秒中断即停止接收新单并恢复5个被动入口字节。stop同样只停止新派单和观测，已排订单与原生AI继续。

每次原生尝试前后都有持久JSONL回执。未知结果禁止自动重试；映射和DLL/跳板PIN到进程退出，避免in-flight释放。stop为本原型的终端状态，同一PID不会重新安装。

## 实证与构建

`capability-evidence.json`关联EXE/包SHA、status/audit SHA、只读原生共享状态复核、旧实测bin与暂停补丁v2 bin。PID46760 Conscript实测：正常报价/原生队列费用/实际支付均85，60笔扣款、queue17、object789，315个活体样本；同命令复用queue，同task新ID拒绝102；stop phase2/restore31/active0。Flak另有严格单次闭环证据。它不是宏观方向或整局胜负证明。

`Build.ps1`当前输出`bin-v2`，保留仍被测试进程PIN住的v1 `bin`。v2仅添加暂停派单守卫，22项本地测试通过；暂停竞态真机验收由最终fresh宿主完成。构建不启动游戏。

```powershell
./Build.ps1
python -m unittest -v test_client
```

`smoke.py`仅由主控执行：无`--unit`只attach观测，指定`--unit conscript`才派一单，`--dedup-check`同时验证两种重复请求。完整比赛宿主应直接使用client类，使执行器覆盖整个对局。

自然线程证据由共享`../natural_evidence.py`验证。已实测UnitBuilder caller0x4f467a使用flag0x200，另一路caller0x4f49e7使用flag0；这两种被动样本都可以证明生产命令线程，仍须精确sentinel/其余5个零、窗口线程及真实匹配node/返回ID/cost，observer必须恢复完成。未知caller/flags拒绝。主动命令始终固定flag0，只排一单位。19:12那次前置拒绝发生在attach前，无映射/派单，不能算恢复失败或未知SDK调用。
