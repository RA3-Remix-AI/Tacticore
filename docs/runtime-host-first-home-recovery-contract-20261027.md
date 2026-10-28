# 宿主第一次回家恢复的独立授权与账本接线

状态：宿主/adapter/Gateway/transport/账本、独立授权器及普通Host可信CLI参数已实现，`111322`实际Host新回家恢复通过56项原字节/SQLite检查及182份冻结复算。[实际Host检查点](../reports/runtime-actual-host-first-home-recovery-checkpoint-20261027.json)。本轮为明确受控位2，操作7仍强制普通verified transport scope；原675帧任务失败保留，不冒充自然AI干扰。客户端登记与handoff双重重核已实现并通过离线回归；新发布包/实际交接及实际失败7后新6仍待验证。默认不生成新grant，仅显式成对pin且复核通过时授独立权限。[授权器检查点](../reports/runtime-first-home-authorizer-checkpoint-20261027.json)。

现有证据分开保留：`095903`为d168位2受控外部Move后原Commit真实unknown、新操作7第一次物理回home/归还的42项原字节证据；`101150`为同d168位0基本动作的21项证据；`101634`为同d168位0、实际Host/Gateway/SQLite连续两任务的47项证据。后两次没有派操作7。本轮Python扩展发生在三次执行结束后，其原执行前快照不改写。

## 已接入的边界

- 新capability为`tactics.reconcile_return_home`，与原移动权限分开。其scope必须绑定当前DLL/Native Host、`tactical/runtime`、`tactical_runtime_v1`、module`runtime_first_home_recovery_v1`、purpose`reconcile_return_home`及单个付费征召兵角色；普通移动grant不能替代。它不会让客户端的risk轴自动显示为广泛撤退能力。
- 仅可信Host恢复代码调用`reconcile_return_home`。原task/lease/actor/generation不变，必须引用本Host实际已有的uncertain Commit；当前原生回执仍精确对应它且held，SDK Move计数为1。四个新独立静止帧及双时钟不倒退后，先持久化新命令意图，再分配全局序号，至多提交一次。原生层仍最终决定私有home、未尝试home、当前空位、自己的Stop3、300范围及30秒/10秒预算，不由Host布尔字段代替。
- 新操作没有target、hold或工作租约续期。同一task使用固定请求ID；响应丢失、未知及重复调用只查原结果，不重派。权限撤销后仍可只读重放已存在的结果；新的物理动作继续需要授权。操作8不进入普通Gateway或普通transport。
- adapter只有实际physical_home、默认队伍、姿态恢复和原生释放回执同时成立才接受新操作7的released；恢复任务的mission_effect_verified始终false。旧Commit/任务的失败不改写。
- 若新操作7本身unknown，不得再发操作7。新的独立静止窗口后，可另建只释放操作6，引用该unknown7；账本沿相同task/lease/generation的恢复引用链关闭控制归属，保留原Commit和新回家操作两条uncertain记录。错误链、跨租约、循环或缺少可信释放不能清除原未知。新操作6不依赖仍有回家能力。
- 四帧审计材料按frame去重，重复读取不替代不同帧；每个实际记录的frame都有对应观察。

## 分项实施与下一步

1. 已实现独立的纯原始字节审查及14输入SHA bundle；当前资料46项通过，180份固定来源另起进程复算一致。原控制UUID、诊断标记/真实foreign epochs、原Unknown前缀、四帧/原生配对槽、首次home Move、当前三帧空位、实际home/Stop3/队伍归还和清理均重算，不执行由report选择的代码或以checkpoint布尔代替。原观察highwater2与独立诊断ack3的不同发布时序分别核验，最终新恢复序号4不变。
2. 已实现独立VerifiedGrant和普通Host CLI成对参数，强制同构建位0基线及恢复bundle。默认目录、模型/RPC仍不能自行带入grant；客户端可信登记及后续native-channel handoff的双重重核已离线接通，见[登记/交接检查点](../reports/runtime-desktop-recovery-registration-checkpoint-20261027.json)；尚未更新实际登记或新发布包，未作实机交接声明。新授权不扩大攻击/侦察/双兵/自然AI干扰的声明。
3. `111322`已实际验证派发前持久意图、四条连续全局序号、旧失败保留、新回家/实际归还、幂等不重派及独立重开只读账本投影。97事件/1330钩子无丢失，生产器及19入口独立恢复后结束fixture。失败7后新的只释放6本轮未实机触达，仍只标离线组合通过；不重试home、不改写旧失败。受控来源与自然干扰继续分开。

其余G4、180秒接续、G5客户端真实配置/模型任务、G6三类战术、G7自然结算和G8贡献/风格对照全部保留为完整目标，不以本合同或恢复分项替代。
