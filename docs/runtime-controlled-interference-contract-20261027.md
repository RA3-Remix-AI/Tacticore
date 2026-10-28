# 明确标记的原生干扰诊断合同

状态：2026-10-27已实现独立操作8和bootstrap位2，d168在`095903`实机完成受控外部Move→真实guard未知→独立静止→新操作7第一次回原home/归还。42项原字节检查及178份事后冻结审查来源独立复算一致；177份执行前来源、旧任务失败及全部原始数据保留。[实机检查点](../reports/runtime-controlled-first-home-recovery-checkpoint-20261027.json)。普通操作7/8权限仍关闭；同d168的flags0基本动作与普通Host接线尚待验证。

两个ef38试局`091806`、`092544`都完整完成675帧任务，但没有触发新恢复操作7；没有开第三个相同随机试局。保留这两个真实成功分项。新构建必须使用自己的实际证据，不能继承ef38的实机权限；受控诊断不冒充自然AI干扰或完整任务成功。

## 所需实验

在owned诊断中安排一次明确、可审计的外部移动，让原始Commit真实进入Uncertain，再验证新恢复命令第一次返回原home并归还。故障原因必须标为`controlled_diagnostic_native_move`，不能说成原生AI自然决策。实际移动、原生guard产生的未知、独立静止、新Stop3、实际回家和归还必须来自游戏过程，不能改写状态、坐标或回执来制造它们。

注入操作必须与Query、普通Move和恢复操作分开：

- 新诊断操作号8，独立command/request UUID及全局序号。不能把Query变成有副作用的接口。
- 新bootstrap诊断位2仅启用这一注入入口；保留位0的普通策略和位1的既有让路实验，拒绝混用位3。Native factory/observer和Python transport均核验诊断模式。普通Gateway/模型/transport继续拒绝注入操作。
- 只有当前绑定的付费演员仍由script team持有、处于原Commit的Holding、自己的Stop3归属成立、接地/存活/时钟/线程都有效时，才允许一次注入。每个原生通道至多一次，拒绝新UUID重复注入或在恢复过程中注入。
- 目标必须来自当前Native endpoint registry，距演员30–120且不是原home，不能接受截图坐标或任意数值。游戏线程再次核对当前准入；没有端点就明确拒绝，不移动别的单位。
- 通过既有原生Move facade、source2、在控制器自己的Move scope之外调用。保留所有原生钩子与foreign epoch变化，不暂停、吞掉或伪造任何正常原生调用。不直接写演员坐标、状态机、foreign epoch或Uncertain状态。
- 注入请求在任何SDK副作用之前保存不可覆盖、flush/fsync的明确意图。原始回执、native last sequence与发布序号都保留；注入不得替换原Commit的控制回执。注入确认属于自己的command，原Commit仍应在后续真实guard tick中变为unknown。
- 增加专用原始trace标记，例如kind35，包含诊断来源、原始注入command UUID/sequence、演员和实际目标。注入Move不冒充原Commit的SDK Move计数；复核同时计算控制器Move和外部注入Move，避免“只有一次Move”的歧义。

随后必须重新等待四个独立静止帧、配对空槽和反向链接；由新UUID/序号的操作7发自己的Stop3，再取当前空位证明，第一次返回原home。原Commit依旧失败，恢复的goal effect仍false。若新home Move未知，禁止再派操作7，只能在新的静止证明后另建释放专用命令。

## 验证与授权限制

先验证默认IO拒绝、无诊断位拒绝、非Holding/错演员/越界/原home/过期拒绝、一次性和重复UUID、原Commit身份不被注入确认替换、全局序号不断、以及后续操作7不重试旧home等真实C++路径。Python确认普通Gateway/transport拒绝、CLI必须显式组合、意图在SDK前持久化，且不能绕过原Native endpoint选择。

实机复核需包含：注入前持久化意图、4条各自独立的原始命令（Reserve、Commit、诊断注入、恢复回家）、完整原生trace和Unknown事件、新四帧静止、首次home Move和真实回家/归还、原失败保留、生产器及19入口独立恢复。全部原始资料和执行前来源冻结、另起进程复算。

此实验不是模型对局，也不证明自然AI干扰一定出现。诊断位2不能自动授普通Move/Hold/Return或恢复权限。未来若授普通恢复能力，必须另有同一构建flags0的基本动作证据、明确核对操作7及其静止/返程逻辑不依赖注入位、并单独通过Host/Gateway/账本及实际客户端接线；普通注入入口始终关闭。不得把位1会扩大让路来源策略的历史实验，与仅控制注入入口的位2混为一谈。

完整G4其他分项、当前构建普通Host重复、180秒接续和G5–G8全部保留；这个实验只解决新恢复分支的可复现验证。
