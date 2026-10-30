# 统一战略通道5：私有候选实施

当前将原生十项高层 flags 与两类管理器意图合入同一 Native、同一 journal 和同一公共租约。没有精确建筑、兵种、数量、坐标、队列或单位任务字段；开局调度、原生已提交任务及复合生产族的语义限制继续保留。具体选择与操作全部归原生 AI。

Private build unified-20261029-v5e：1440字节Shared、72字节Gate、1360字节混合Journal。Journal.kind区分管理器/flags，保存 callback 序号和原始意图绝对游戏帧期限；当前 i386 编译与 ctypes 全偏移相同。before-call Unknown 必须 WriteFile+FlushFileBuffers 后才进入原正常 API。flags未知apply先两次不同帧只读确认，再作为不同目的清理到原false；未知restore不重复调用。管理器沿用已实机复核的 v2候选，不能改变其首次基线。

Aggregate return 要求 flags实际全清、两类管理器实际回到各自原值、后续callback复核、原生自有Hook解除及真实公共租约归还。客户端等待辅助进程真正结束后，再独立读组件/flags/信号量并检查Native journal；不能只用flag mask=0替代整体归还。暂停时新的推进/暂缓/flag动作拒绝；已知恢复可按独立callback序号复核，Unknown仍须不同后续游戏帧确认。

新增 not_after_frame 绑定原始游戏期限。publisher 在完整输入核验和 durable prepare 后重新读实际帧，过期则撤销准备且不增加Native request；Native也按此绝对期限裁剪本次TTL，并在最终guard拒绝过期调用。管理器还按原绝对期限提前服务归还，避免较晚快照重新延长期限。

当前离线证据：实际编译mask predicate对0..1025共1026种组合与合同一致；实际32位host确认无修饰导出名可找到，但不装Hook；4组Python检查覆盖布局、旧compile-only拒绝、prepare期间过期不派发、未知/冲突ID不重发。flags生命周期头文件在人工flag操作环境执行6组，包含durable-before-call失败、部分apply未知后的单独恢复、未知restore不重试及未恢复时不可整体归还。这些CPU组不打开游戏、不调用硬编码Native API，不冒充现场证据。

a为首次编译警告失败，b/c为compile-only旧稿，d/e为进一步修订；早期输入变化后不能继续当前准入。保留原件，当前现场只使用完整109项闭包的e。v5在新目录实现，没有热改Native3/v4已附着源。当前刚启动PID101428用于组合实机验证，尚无本协议现场通过，不给模型/产品权限。建设/生产组件采用及独立生命周期的旧4h记录不能自动授新5产品资格。正式自然验收0/3，完整F01–F07仍待完成。

后续：e 在 PID101428 完成 flags+两类管理器共存、换向、过期、held STOP；26条Native journal、真实组件原值、十flags全清、Host实际退出0、公共信号量1/1以及新读回归还通过。PID95056 同一e完成持有三类控制时的publisher/helper失联，Native自有watchdog整体归还，通过后均再次新读回并结束精确进程。原件保留，不补计正式局。

实现态下并行复核又修正两处：client归还增加实际句柄PID/原始创建时间、当前Game/Player/AI/人格根链和有界顺序复读；flags收紧当前帧重读后计算及后续callback的原绝对期限。当前主执行者另审阅并独占写入了admission失败清理的窄修复：Unhook或Release失败不伪造清理、保持实际资源并用私有闩锁禁止重试；普通STOP路径未改。源/原件/哈希为strategic-unified-admission-root-merge-20261029-v1。

f已重冻109输入重新编译，1440/1360布局及1026组合检查通过；4组publisher/布局加10组绝对期限检查通过。旧e不能继续准入。f正准备自然结束边界研究，仍无模型，不计正式；对局结束后AI对象退役的处理需实际观察。产品只读观测另在新strategic_unified_observation_v5.py实现真实管理器root/vector成员采样，避免重用堆候选作为任务成员证明；尚未测试或接入产品。
