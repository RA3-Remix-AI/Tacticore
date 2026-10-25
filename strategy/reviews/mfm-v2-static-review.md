# MFM v2 最小修正静态独审

只读审阅 `tactical/mission-formation-v2` 与 V1 的差异，没有修改执行器、SDK、GUI、模型或旧原件。结论限于首次现场诊断建议；不构成新能力授证或真实效果证据。

核对的 v2 DLL：`a75cd370cab920f09542e1d1658064a6e326f31b87d887f3174d46f22d881e1e`；host：`a47d80ed19f19f6aac3ebf1702bb7c829d640575ad09c8ea6e103513126dc6e5`；`mission_state.cpp.inc`：`3459b7cd66a42eb62eb3ed26674af9b123e5fdca285efc093588433dae628230`。后续修订须另外核对哈希，不能把本结论自动沿用到新构建。

## 已确认

- Stop 等待预算由 30 帧变为 60 帧，实际稳定门槛仍是三个不同帧、相邻位置≤1、path0、低16位状态0、命令来源1。没有放宽移动到达半径或双角色几何。
- Stop 超时、覆盖、期限及部分失败改为 `request_cleanup`，进入 phase7，逐个仍存活且已借出的单位重新下正常 Stop，再等待稳定后正常归还。
- cleanup 达到 60 帧仍未稳定时发出独立事件69；稳定才发事件68。校验器只把真实稳定的66/67/68作为正常归还边界，不把69当作稳定成功。任一角色未知，整体恢复不会通过。
- tuple/list 处理在纯 assessment 输入做 JSON canonical roundtrip，不改变原生命令、坐标或阈值。
- 原本对身份失效或死亡的保守拒绝没有被改成 completed；实际伤害、完整推进/撤退、固定入口字节及两角色恢复仍需真实 raw 独立验证。

## 可运行验证

在 `bridge-probe/tactical/mission-formation-v2` 执行项目 Python 的：

```text
python -m unittest test_mission -v
```

初审独立运行34项全过；作者在尚未安装窗口补齐error35异常分支并增加回归后，最终独立运行 **36 项全部通过**。

另外使用该文件的 `ReleaseTests.rec()` 离线夹具，分别将 role0 或 role1 的正常 final gate66 改为强制事件69，另一角色保持正常返回；两种情况下 `control_release` 均返回 `restoration_verified=False`、`completion_claim=False`。该验证只测试纯校验边界，不代表实际内存现场证据。

## 初审发现及最终修正

初审发现接管两角色后检查team的error35分支仍直接调用 `normal_return()`，未经过cleanup。现有纯校验器会因缺正常Stop gate保持恢复未证实，不会误授证，但不符合统一清理的目标。该问题已直接反馈作者及Root；作者在零安装窗口改为 `request_cleanup(35,now)`。最终独立重读 `mission_state.cpp.inc:75` 和生成的 `lease.cpp:179`，均为该新调用。上列a75cd3/3459b7哈希对应最终构建，旧未装载构建不沿用。

策略层 `missions.py` 与 `BattleAgent` 接口在本轮保持冻结。真实案例后仍需逐角色核对原始稳定帧、来源伤害、撤退与返回，强制返回或部分阵亡只能按已证实的失败收尾。
