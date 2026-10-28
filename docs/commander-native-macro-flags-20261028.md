# 原生宏观标志链：实机进展与边界

2026-10-28，属于[新版宏观目标](commander-macro-goal-20261027.md)的G1/G4研发。已取得“原生设置器→独立读回→指定AI查询→原生战略执行→己方队伍移动→关闭后退出”的实机链。新增合法敌情反馈、建造、预算、区域调度及整局模型验收仍未通过。没有接管单兵。

## 接口选择

SDK的`AIStateScriptedFlagHeuristic`可作为建造、预算或战略状态的条件。`AIS_T06_Coop.xml`已有标志启用原生战略队伍的示例。编译器支持`AIBuildStateDefinition`、`AIStrategicStateDefinition`，队伍仍引用原生`ScoutMicroManager`等操作逻辑。

固定游戏的Lua `ExecuteAction`直接进入游戏专用动作dispatcher；`SET_FLAG`的case是返回空操作，随后Lua仍可返回true。因此该返回值不能作执行回执。普通脚本执行器有另一层公共动作分派：action 1经`0x5ae289`调用真实标志设置器`0x58b240`。本次调用后者，使用正常ScriptAction参数构造`0x574c80`、原生字符串构造`0x4cc910`和动作销毁`0x574d70`；不写标志表bool，也不改Lua栈或脚本玩家上下文。

只读lookup是`0x573b10`，表在ScriptEngine+`0x16ce4`。两个unsigned key为FNV-1-32的`(scope,name)`，先乘后xor。首个`/`分离明确scope并去掉名字中的前缀；无斜杠才使用当前脚本context。试验使用`/名字`明确空scope，避免修改context。它仍是本局全局名字，必须按指挥官/槽位命名并拒绝重复人格拥有者，不能假称天然按AI隔离。

`native-ai/audit_macro_interfaces.py`扩展后的静态审计检查30处字节/调用、14段反汇编和6份schema，输出`reports/native-macro-script-flags-static-20261028-v1/audit.json`。它自身不打开游戏进程，也不授予能力。

## 独立读回

`native-ai/read_script_flags.py`仅打开query/read进程权限；验证精确游戏SHA、原始FILETIME和字段签名，按原生双key树查找。区分不存在与false，检查边界、树父链/有序性/循环和前后读稳定性；不创建标志。7项合成内存检查通过，包括FNV-1与FNV-1a区别、显式/当前scope、大小写、深树、缺失与false以及读取中变化。稳定双读仍不是原子快照，也不能独自证明AI消费或效果。

## 隔离宏观包

`native-ai/stage_macro_probe.py`生成特定UUID、Soviet、P3的3个追加资产：独立人格、机场建造状态、原生侦察状态。机场状态受flag、开局完成、机场不存在及没有其他STRUCTURE施工的条件约束，再交原生建造管理器处理前提、落点、队列和资金。侦察状态基于SDK的`SovietScout`，最多一个目标/运行副本、一单位队伍，保留`ScoutMicroManager`，标志关闭时按原生`DISBAND`结束状态。

三档质量编译、原生ID、标志字符串和BIG往返校验通过；每档854个原有资产的payload/import/relo/refs逐一保持，原有本地化保持。输出`native-ai/staging/macro-native-probe-20261028-v2`，BIG SHA `772650fd0a0a3f75a88b72e2017266a374cefac34a69b614933eae3c0b554bed`。v1因执行Python缺少lxml在导入阶段退出，保留该目录；v2用已有bundled Python编译，不改写v1。

`acceptance/Start-MacroProbe.ps1`部署到全新隔离目录并保存启动前源码；原`TFCommanderPlay/TFNames.big`保留，SHA仍为`2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665`。当前局是接口研发局，没有模型请求，不是G7正式对局或干净的原生基线。

## 实机链

本局记录`acceptance/runs/20261028-001626-macro-probe/session.json`：PID39024，原始FILETIME `134375913867066525`，session `071c8b95-2456-4076-a562-20ca2958a0bb`。P3原生人格ID `0x799613e0`、AI `0x42fea60`，原生store/Side/owner链匹配；P4为原生Oleg（ID `0x7b9da0e6`）。菜单和局内身份分别记录，未依赖显示名字猜测。

| 检查 | 结果 | 证据 |
| --- | --- | --- |
| 未被AI引用的诊断flag | false→true→false，3次正常helper调用、3次独立树读回，清理phase2/ack3/error0/active0 | `reports/macro-flag-abi-39024-20261028-v1/` |
| 原生AI关闭状态查询 | 20秒内两个新增flag各查询20次，结果全0，arg1均为绑定AI | `reports/macro-flag-query-39024-20261028-v1/` |
| 短时开启侦察gate | frame9093清false后启true，约6秒后frame9184清false；独立读回和原生停止ack通过 | `reports/macro-scout-state-39024-20261028-v1/` |
| 同时观察原生消费者 | 机场31次均0；侦察29次0、2次1，两个1在frame9108和9123；全部arg1匹配绑定AI | `reports/macro-flag-query-39024-20261028-v2/` |
| 最终独立回查 | scout存在且false，机场flag仍不存在；没有遗留启用标志 | `reports/macro-scout-39024-final-readback-20261028.json` |

查询实际对象vtable是`0xc5e8f8`，回调`0x889bf0`经`0x8899a9`调用点返回；它从定义+8取到两个精确新flag名字，并传入本局P3 AI指针。这是动态消费者证据，静态审计里尚未验证的类绑定结论不回写为当时已通过。

第二个查询观察器在frame9126结束，早于侦察gate在frame9184清除，因此它自己的末尾flags快照仍为true。该快照不是清理失败，也不能作为清理证明；后续setter清理回执和更晚的独立回查均为false。时间/帧关系保留，不篡改观察原件。

观察器只转发原float结果，未调用setter或改变AI返回值；两次均已禁用入口观察，并由外部读回确认17字节恢复、active0。DLL/trampoline按设计pin到此测试进程结束。不同观察epoch使用不同DLL/映射名，旧原件和源码副本保留；不覆盖历史二进制或忽略待决状态重用。

## 尚未通过

- 已证明侦察flag被指定AI消费为1，尚未把对应原生队伍创建/招募、战略任务开始、侦察行为和新增合法情报串为一条效果证据。现有原生单位走动不能直接归因于这6秒启用。
- 机场flag尚未启用，尚无建造提交、施工、真实扣费及完成证据。
- 宏观预算、经济/科技、兵种数量/构成、区域目标/改派仍需实际消费者；此试验不是通用模型API。
- 当前桌面Host源码默认宏观边界的442项检查是先前软件检查；本轮没有发布新客户端，也没有真实模型请求或正式整局结算。

上述清单描述第一局短探针时点，后续更新见下节。所有产品能力仍保持未授予，G0–G8整体目标继续active。

## 后续原生任务与己方队伍实证

第二局 `acceptance/runs/20261028-010336-macro-probe/session.json`，PID65460、FILETIME134375942170168194、session0aca00ad-2ec7-48e7-94e7-b47a9894fede，采用v4-feedback-pinned隔离包，SHA99fecb301e0f8e5106599a4978205a5e03029d91778f2d2a6f245771a41e1484。仍逐项保留每档854个原资产。侦察状态加入四个独有反馈键；三档实际序列化及本局定义的4个StringHash值一致。键存在不等于反馈事件已发出，尚未把屏幕文字作回执。

`reports/macro-scout-feedback-65460-20261028-v1`：30秒开关，62个有效样本、1次不稳定读。启用后原生缓存评分正值且创建了active任务；清false在3125帧，3140帧评分归零、执行active=false并cleanup=true，3148帧任务退出有效链表。clear回执早于下一次AI自然评估，不能要求同一帧立即消失。助手停止phase2/ack3/error0/active0，正常退出。

`reports/macro-scout-group-65460-20261028-v2/assessment.json`：同局第二次独立意图，必须先核对上次报告、当前flag=false、旧native映射仍然phase2/ack3/error0/active0/cleanup1及完整身份，再使用新编译epoch5，不盲重发未知结果。63个有效样本，无读错误。11157帧启用，11625帧关闭。原生runtime0x6aa30e8登记AI组1677；经原生AI注册表、Team权威Thing ID向量和GameLogic注册表只读解析为己方Thing1210，type0x33026fa1，即战熊。11295–11625帧38个样本记录到位移1150.21、采样路径1671.71，之后评分归零且任务inactive。路径长度是采样折线，非连续轨迹总长度或覆盖面积；不是模型逐帧指挥。

只读模块 `native-ai/macro_observation.py` 对缓存、runtime owner/definition/self/侵入链、注册表bucket/循环/前后稳定性及己方成员身份核验；使用Team+8/+c的权威Thing ID向量，不调用8350d0刷新缓存。敌方成员在类型/坐标/HP读取前拒绝。11项合成内存检查通过。原生owned ID并非Thing ID，先前361在任务结束后已退出AI注册表，不能据此宣称没有单位或任取同号Thing。

第三次epoch6采集正遇自然结算，native身份检查拒绝，attempted0、无transition；保留失败原件，不算任务启动或停止成功。最终GameLogic frame0、flag表为空、host均已退出；新增源码在attach之前要求有效宏观观察，避免已失败的预检还进入attach。

该局结算截图与57635字节回放存于run目录；先前按图标作出的胜方解读缺少独立玩家索引映射，已另存outcome-review标为未核验，原件保留。model_calls0，不能作G7或干净原生基线。回放SHA5fe867509f0c8170fdf19088fdbbda73b76749efb4d610403602e833b67c81cc。之前39024局也自然结算并保存研究回放，均未验证播放或外部flag事件的回放保真性。正式回放验收仍待完成。

后续独立建造局为 `acceptance/runs/20261028-012228-macro-probe/session.json`，已自然结束。正常开局条件满足后机场状态进入正评分，但gate窗口内未见机场；稍后机场出现没有队列/支付归因，仍不作建造通过。持续执行器、合法视野与预算消费者的进一步实证见[宏观策略原生消费者](commander-macro-policy-runtime-20261028.md)。部队操作始终交给原生AI。
