# 原生区域防守候选（2026-10-28）

沿用 SDK BalancedDefense 的 StaticDefense 任务与 DefenseMicroManager，保留原生招募、寻路、交战和技能。宏观接口只选择公开区域与任务有效期；没有逐单位命令。

隔离包 `native-ai/staging/macro-area-defense-20261028-v1` 的东侧任务替换为原生区域防守，西侧仍为原生 SimpleAttack。13 个标志、16 个资产和预算/建造/生产/侦察资产不变；三套编译流各有 866 个原有资产保持一致，保存审计见 `reports/macro-area-defense-package-preservation-20261028-v1/audit.json`。

原有观测器及桌面传输不改动。新增版本只增加 StaticDefense 原生类型读取；AST 比较保证旧解析、所有权和链表检查保留。候选原生传输 epoch33 已通过 28 个掩码检查，观测器、传输隔离与效果评估器测试通过。

尚未实机验证候选任务布局、原生部队接受、区域效果和释放，故未接入产品或授予模型执行权限。后续只读追踪原生任务及己方部队，观察任务进入区域或在区域内驻守；不以单兵移动、命中、无伤或强制回家作为验收要求。


## 第一版实机结果与下一候选

PID70732 的两区域固定试验未观察到有效原生任务部队，两项效果为 false；不是成功。状态进入评分和静态类型匹配不等于执行。全部标志、原生hook和租约清除，未知指令为空，已在保存报告后结束该研究进程；无模型、无单位命令、非自然结算。评估 `reports/macro-area-defense-assessment-70732-20261028-v1/assessment.json`。

第二候选沿用 SDK `CoopStates.xml / CommandHold_Land` 中原有 StaticDefense、BeaconHoldMicroManager 和 250 距离范围；保留原生COOP队伍优先级，添加状态关闭即结束，以便有界释放。关闭 aesthetics 管理也是原生指定位置任务的原有配置。没有创建新单位操作逻辑。包 `native-ai/staging/macro-area-hold-20261028-v1` SHA c76b3c9492848cdc91b7221cf5247d4ff0d6cf99bebb7f432f5624372d939622，epoch34，静态保存审计和编译通过；实机尚待核对。当前PID78532。


## 指定位置候选首轮

PID78532 采用同一 epoch34 包，先远端进攻后近端驻守。原生 SimpleAttack 的 15 条己方单位轨迹向西侧推进，效果通过；StaticDefense 出现原生执行且有可解析己方成员，但没有观察到充分的驻守范围效果。另有严格组解析拒绝，保留未知，不放宽 kind/所有权/链表检查。该结果记录为任务存在true、区域实效false，无产品授权。全部标志/hook/租约清理后结束，非自然对局、0模型/0单位命令。

当前PID1604 准备使用同一包先近端驻守再远端调度，以核对任务顺序；依旧沿用原生单位操作。已自然结算的模型局与阶段交付文件不改动。
