# 战略产品集成进度 · 2026-10-29

当前依据工程根目录 AGENTS.md 及最终验收 F01–F07。旧精细消费者研究已经停止，历史失败及原件保留。本轮工作不把指定建筑、兵种数量、队列或逐笔付款重新列为完成门槛。正式自然局 **3/3**，F01–F07已按本机固定范围完成总审，详见[最终报告](../reports/strategic-final-acceptance-v9-20261030-v1/README.md)。容量临界输入缺陷仍存在，模拟事件理解不等于实机专用事件生产者已交付。

当前唯一实机与正式验收控制者为 AGENTS.md 指定会话 `01a1856c-3b1e-7413-a45c-f2aa2db875c9`，冻结登记见 `acceptance/strategic-active-owner.json`。本文对应并行支持工作：离线实现、独立复核及隔离业务库的客户端 GUI 验证，不自行启动游戏、模型调用或计入正式局。活动冻结源不热改；新增候选需由控制者选择、冻结及验收。

## 最终验收范围速查

本表记录证据范围，不按研究／测试数量折算完成率。2026-10-30 更新：十四入口已有最终提交索引；v9/c583冻结1118项。85860普通风格自然研究与73204真正Host骤停恢复均已分项独审，明确非正式、不补数。正式首局62660已有前置登记、实际请求／父子命令、完整自然结果及归还、GUI下载与离线播放互补复核，计为1/3。第二次尝试104984虽归还可靠，严格终局尾链未知而未计入；第三次103948已完成6真实响应、严格自然结果和归还及诊断过程归档，主方正式计2/3，自然／归还、账本／前置绑定、请求／GUI导出的三路交叉独审已齐；第四次104244亦因unbound_tail_result_rewrite未计入，归还可靠；第五次14092已通过三路独审，计入1／3／5，正式3/3；后续F01–F07逐项总审已完成；五类真实模型受控检查、无人工事件对照、实际闭环及客户端／异常恢复证据分层汇总，不据三局数自动带过其他项目。旧v6不能代表新恢复源码，CPU通过不替代实机；下文各时点原件保留。

| 项 | 总审通过依据 | 适用范围与限制 |
| --- | --- | --- |
| F01 接管边界 | 十四高层入口，目录、prepared、响应和最终派发多层门，实际方案与物理包均无精细控制 | 旧精细代码保留为历史，不进入模型权限；原负例保各自真实版本 |
| F02 战略判断 | 五类真实模型受控判断、无人工事件的可用信息对照，结合实机公开判断与后轮反馈 | 模拟损伤／受袭事件不冒实机生产者；拒绝与Host回退不算模型成功，不承诺最优战略 |
| F03 原生联通 | 十四入口真实模型、绑定父子ACK与原生状态／任务／策略反馈，窄版本继承已逐项复核 | 偏好、任务和调度门语义分开；已满足不作0→1、移动不作任务成功，研究不补自然数 |
| F04 闭环记忆 | 62660真实侦察效果进入后轮保持／重评；等待、无效果及到期后有公开调整，97968另有到期空偏好实链 | 模型选择与运行时挡重复分开；v6研究保原版本，未知与原失败不补绿 |
| F05 日常客户端 | 配置、发现、预检、启动、观察、GUI停止、下载、下一局和v9 Host失联恢复已有实际流程 | 本机工程／debug EXE范围；未完成跨机器安装包资格；容量临界拒绝缺陷仍在但会安全拒绝及恢复 |
| F06 生命周期 | 身份、合法视野、时效、输入门、未知不盲重发；真实STOP、失联及三局独立归还 | 不用单ACK或Host结束代归还；丢失内存／未观测exit保unknown；同进程重接仍关闭 |
| F07 自然局 | 同v9/profile31第1、3、5次自然结算3/3，三路独审、诊断、过程与原生录像齐 | 第2、4次尾链未知不计入，研究／模拟不补数；不据胜率归因模型或承诺录像完美重演 |

最新候选、红色反例、精确哈希和分工集中于 `native5-parallel-handoff-20261029.md`。 下文为历史实施过程，“当前／仍待”只对应各段当时状态；最终结论以本页顶部链接的总报告为准。主源处于现场冻结时，表中的候选只留D盘，不在活动对局中融合。

2026-10-30 后续增量：新停止互斥本体通过独立跨进程检查，但普通启动落账漏协议版本、run_stop可能绕锁的真实CPU反例已报主方；实际backend正在变化，未把修复预算通过。诊断显示层漏expand与四gate的最小5label候选已完成作者与root独审，保历史显示但不授精细动作权限；Native5离线回放候选待真实脱敏链与浏览器播放独审。容量预检由主方融合中，A按源guard分别审核稳定路径。另已导出关闭试运行的公开冻结版本索引示例，仅表示候选声明的hash，最终三局需以最终同冻结候选重新导出；上述均未补算正式自然局。

上述停止选路随后已修复并获B独审，旧红保留；5label诊断源已由主方采用，C的回放ceil上界修订通过真实headless播放／末帧seek，A正独审该最小增量。容量实际部分独审已封：helper/ProfileStore及旧固定MacroDesktop/Bridge拒绝路径通过，最新Host/Backend因WIP漂移仍未补审；实际helper导入初始化与D候选有差异，仅四业务函数AST相同，不写“整模块等同”。玩家指引已更新到10/30并获A静读核对，停止三阶段、调度限制与0/3范围保持公开。

随后v3冻结为d0fe3fe1…／1116源，主方已采用a4e620回放／9262HTML；容量实际未审差额获A新4项通过，33cd未接管清理获C新8项、c321原250ms统一等待增量获C9项。B的完整日志顺序新parser经独审交付，只输出给定日志的ordering／unknown／contradicted，不自证未截尾、Native执行或全F06。root对已关闭65352真实early-stop记录核得stop_committed→constructor admission_denied、0admission，A继续其无接管／旧run账本及具体诊断下载复核。主方转95916做非正式高层入口分项联通，该轮不计三局自然验收。精确版本和证据范围见交接文档，历史失败未覆盖。

后续65352取消／真实诊断下载已获A文件独审，真实下载生成的两条早停记录获C实际浏览器播放／暂停／跳转检查；95916已接管STOP的实际有序日志、parent-child／只读账本及独立Native归还亦获B复核。均保各自范围，不替代全部异常与自然整局。主方再进行v4分项局，新增budgetarmy／advanceconstruction等实际parent后触发战略记忆metadata预算fault；归还通过，失败原件保留。新v5冻结（5e0c005c…、memoryd311）将元数据一并计入原1536策略预算，总16KiB不变；主方重验多轮，A独立边界／实际caller补验中，正式仍0/3。

A的v5独立边界／实际caller／SDK MockTransport连接补验随后通过，未知与必需依据不丢，旧fault保留，现场多轮结果仍以唯一控制者原件为准。C确认现有自然结果Host-mode评估器可读Native5 watch，却只是结果子证明；旧综合评估器不兼容Native5十flags。已交付最小组合接口设计与实际schema／时钟说明，用同候选、真实Host模型连续链、自然胜负及独立返还逐层复核，缺证unknown，不把新工具、视频、完美replay或frame0发令当额外门，也不以watch晚poll误拒正常快速终局返还。

v5已关闭73592的实际七轮记录获A复核：记忆最大1535B、传输回执最大15459B，必需事实及战略身份保持，未再出现预算故障。C另复算73592的自然结果子证明及Native5归还通过，Host至终局连续链有记录；86484虽归还通过，参与者退役后的结果槽改写使严格自然尾部保持unknown，原frame0行存在不可误报缺reset。两局profile均明确研究配置，不补正式，仍0/3。后续暂缓两调度门／STOP及显式推进生产入口由唯一控制者分项补验，支持方只在关闭原件上独立校对。

13968关闭局随后获B完整文件／账本附核：双调度门保持暂缓、未到deadline时实际STOP恢复三组件原值，Native二进制、parent-child／有序日志及独立归还一致。只验证调度门暂缓期间STOP；记录的Game.paused全false且精确STOP瞬间无字段，不能授游戏暂停路径。本局空vector回baseline不补显式advanceproduction，该入口继续由主方单独验。README已更新当前Native5试运行范围与旧基线分层；未改任何活动冻结源，正式仍0/3。

97968的v6撤退闭局已获A、B互补文件独审：实际7轮context／SDK回执容量合规，策略身份及必需依据保留；两个合法区域偏好窗口内有己方原生任务活动与成员位移，后续模型消费活动／到期反馈，命令与停止次序、独立归还对应。第一窗前无活动，第二窗前已有活动，不能算第二个新任务；两次到期清除先于最终GUI STOP，不混同为停止清任务。记录中的缺失观测保unknown，不证明方向、到达或任务成功。精确报告与版本见交接文件。唯一控制者继续增援／防守／进攻入口，正式仍0/3。

增援38020、防守50304两个v6闭局随后均获C独立复核：合法模型意图、父子ACK、等待→原生活动任务／己方成员位移、后续模型反馈、到期与最终STOP分别对应；两局各仅1个物理child，缺样本保unknown、被拒方案不算采用。F05版本映射确认已测配置／STOP／诊断相关模块在v3/v5/v6相同，不因prompt变化重做；防守局自动接入已保存启动受理步骤，闭局结果与已有操作历史的完整GUI链另行关联。正式仍0/3。

F06收尾发现需区别同版Native失联恢复与产品Host突失后的恢复流程：旧96308原生构建与当前相同，B已用current纯proof／journal复核真实watchdog恢复，不能因版本表面更新要求原生失联全重测；91584 attached异常finally归还亦可复用其范围。但当前产品宿主骤停后缺少生成独立归还证明的路径，客户端会保留结果未知。唯一控制者已安排非正式异常验证，C仅在D盘准备只读恢复核验方案，不在活动实机热改。缺失原始journal／final或不确定命令不能补写成功，也不能把失去Popen句柄后的helper退出状态猜为0。待该路径修复、独审和实机复验后，再以最终同冻结候选完成三局普通风格自然结算。

50304的F05闭局附核已补齐此前自动启动／下一新局正向指针差额，真实GUI工具历史、1次Host启动、3次模型请求／响应、GUI STOP与实际下载相互绑定；单独每个内部RPC没有另录就不编时间，也不新增逐RPC门。研究style可以证明F05客户端正常操作，F07普通风格自然局仍另验。该结论不自动授整体F05或异常恢复通过，正式仍0/3。

恢复增量的helper身份和orphan读取／账本路径已分别取得固定ce2048、fdc30的必要CPU证据；作者后来64项后端检查通过。中间版本多次变化，独审按guard停止，没有把旧版本检查补称新版本通过。主方新冻结后只补实际变更的必要回归，再做产品Host骤停的非正式实机全链，最终三局仍需同一冻结候选。root曾把临时Memory替换直接外推为产品后续查询失败；核对9ba实际每次新建SDK模块后已更正，仅作为局部依赖清理改进，不作已证产品故障或新增实机门。

## 移除高层决策对精细队列的依赖

原 Host 中区域和侦察控制器继承生产控制器，缺少 builder 样本时提前返回，连预算反馈、战略反馈和下一轮模型判断都会跳过。只读队列竞争因此可能误阻断战略指挥。新的战略模式不再创建 NativeBuildObserver，不安装或采集精细 expansion readiness/dependency/lifecycle，也不向请求审计提供精细生产、建筑、付款和队列供应器。

真实 Host 的 strategic_tick 使用原生战略 observation 与合法己方 census，继续原有侦察和区域任务反馈、期限清理及模型流程；使用原 Regional 能力入口，避免扩展控制器列能力时又扫描精细费用。builder 状态明确为 not_requested，没有伪造空队列或把 queue_changed 当成功。旧精细模式及其资格代码保留原流程。

该路径在已验证的 transport 构造返回后，只绑定一次实际 session、进程创建时间、己方 AI/人格/模板及 engine。每轮重新核对 Native1/2 身份、ACK、独立 flags、合法视野、己方归属与原始时钟；存在精细活动目标、资源未决或未知送达则拒绝。原生回调或顺序读取跨帧时延后下一次正常观察，不重发命令、不修改原始采样时间。

后续补上暂停边界：暂停时不调用会发送 kind1 空动作的两次 controller tick，仍检查 Native/flags 并刷新反馈，可用动作为空；恢复后沿用原期限，STOP 保留 kind2 路径。原生 kind1 在暂停时会拒绝，原代码在到期或侦察失活时可能产生未知送达。改前真实 Host/人工 Native 反例保留，独立增加了仍持有非空 Native 偏好的暂停案例；原件 `reports/strategic-paused-parent-independent-20261029-v1/review.json`。这仍是 CPU 证据，未冒称现场暂停验收。

`macro_strategic_observation_v1.py` 已进入软件依赖冻结清单。实际 Host/controller/model/journal/派发的人工原生端回归覆盖两种协议及预算、侦察、区域进攻；启动历史、合法视野、迟到回复、停止归还、结果候选和历史扩展路径相关检查通过。初次回归暴露旧未初始化 Host 测试缺少战略标记的兼容问题，已修复；失败没有作为通过证据。当前代码仍需要独立复核及新冻结后的实机联通，旧短窗不自动资格化本次变更。

## 普通客户端配置

新增配置服务使用现有 library.v2 schema 和当前用户 DPAPI，保存时轮换连接 UUID，先写未引用密文，再原子更新连接与指挥官引用。连接地址或 provider 改变时必须重新输入密钥；不把旧密钥自动带到新目标。风格草稿保留并只增加一次修订，旧准入需要重新检查。

签封的事务记录、跨实例共享准入锁以及显式恢复用于处理 library、注册和两个 SQLite 提交边界。恢复期间状态、停止和诊断可用，新检查或启动不能绕过一致性门。独立审查复现并修复了首次初始化标记和凭据封装密钥直接写入可能留下半文件的问题：采用临时文件完整写入后排他发布；不会覆盖已有损坏的封装密钥。

独立审查只使用 D 盘临时人工库和假密钥，验证真实 Windows DPAPI 与既有 load_profile 互通、真实重启恢复、原风格单次迁移及跨服务实例互斥。原始用户库、密钥和活动设置没有用于这些测试。报告为 `reports/connection-config-independent-20261029-v2/review.json`；本轮尚不能由这些服务检查宣布完整客户端或 F05 通过，实际原生 channel、页面入口、重载及 GUI 正常流程继续融合和验收。

实际配置 channel、Tauri 注册及权限、页面面板和正常 RPC 重载现已融合并编译。独立子进程审查通过首用、保存、跨库中断恢复与普通入口重新载入；报告 `reports/connection-config-fused-independent-20261029-v1/review.json`。主线程随后实际启动新 EXE，确认自动读取真实配置及旧宿主最后记录；手动连接查询可用；没有游戏时发现及预检明确拒绝，启动保持禁用。本次未保存连接、未输入密钥、未调用模型、未启动游戏。界面提示仍显示“等待查询”的问题已交回修复，不能把这段有限只读验证当作完整 F05。原件 `reports/strategic-client-gui-readonly-20261029-v1/observation.json`。

查询提示修复后，已用真实 EXE/WebView 完成另一段更完整的隔离验证：首次初始化 → 自动载入 → 保存人工假密钥及 loopback 测试端点 → 普通指挥官源自动重载 → 正常关闭/重开后持久化 → 真实 configure 在 library 已替换、注册尚未写入处中断 → GUI 发现 prepared 事务 → 手动核对恢复 → 再次自动重载。业务库、注册、凭据与状态均在指定 D 盘夹具；实际 WebView 子进程数据目录也已核为夹具目录。只读核对使用原 load_profile 与 Windows DPAPI 验证假凭据互通，未使用或更改用户已有连接/密钥，没有模型或游戏指令。不能宣称全应用所有写入都被隔离，Tauri 仍只读检查已有 KnownFolder 目录。

对应 `reports/strategic-client-first-use-gui-20261029-v1/`、`reports/strategic-client-reopen-recovery-gui-20261029-v1/`。旧 EXE 在 prepared 期间仍显示自动等待入口可用的 UI 问题已如实保留；后端准入实际拒绝。父组件配置门和独立限权控制通路现已修复、编译并完成实际 WebView 验证。后者只从原生固定状态目录加载既有运行账本，不提供连接库、凭据、新准入或 Host 创建接口，并使用独立 mutex 与子进程；普通检查/启动的严格来源约束保持原样。隔离 Python pipe、实际 Rust dispatch 及独审通过，所测 EXE SHA256 为 `168ebbad430c76cdd60c2b66bf3312737abd4e24bbceb0cc9657c6bf13cc57aa`。细节见 `commander-control-only-channel-v1-20261029.md`。

新版 GUI 的两次隔离复测确认：真实签封 prepared 期间检查、直接启动和自动进入均禁用；核对恢复后普通模型配置自动重载，启动仍需新检查。另用真实 DesktopBackend 在派发前因原期限过期而取消的人工记录，实际完成坏配置下的手动恢复观察、同一运行状态查询、脱敏导出与下载。实际下载 9261 字节，与新生成的导出逐字节及 SHA256 一致。此记录明确标为人工非对局，只有原 host_start cancelled、没有 Host 派发或 Native 序列，不冒充活动游戏停止或原生归还；最后正常 Alt+F4 退出。报告为 `reports/strategic-client-cancelled-control-gui-20261029-v1/observation.json`，最终只读独审为 `reports/gui-cancelled-control-fixture-A-final-readonly-20261029-v2/review.json`。

另一份空账本复测中，配置恢复成功，但正常关闭输入被工具拒绝，最后按 PID/EXE/哈希核验后受控终止自有客户端；该次不记正常退出。原件为 `reports/strategic-client-gate-recovery-gui-20261029-v1/observation.json`，最终只读独审确认 completed、库/注册/meta/receipt 一致、六账本仍为0。两次业务与 WebView 数据均在指定 D 夹具，但诊断下载落在实际 Windows Downloads，故没有宣称全应用所有写入均隔离在 D。实际活动 Host 的停止/失联、受信游戏的全流程、安装版运行组件及旧 token/已 armed 等待的 GUI 场景仍需验收，完整 F05/F06 不因此勾选。

人工取消场景还暴露一处文案误称：页面通用提示把派发前取消也称为独立归还。源代码现已最小修正为“未取得原生控制”，真实归还提示保留；TypeScript 检查通过。该文案变更未重建到上述已测 EXE，保留源/二进制版本差异，等待下一次候选统一构建。

## 高层原生入口

stock 扩张候选复用原 SimpleExpansion，保留原生选点、创建、护卫、冷却与条件；具体建筑和兵种不是指挥官参数。独立静态复核确认原策略与新增偏好克隆可能同时存在，单个 state 的 MaxRunningCopies 不等于整个 AI 只会进行一个扩张。撤销偏好或清空指挥 flags 也不等于取消已经交给原生的任务。

建设门存在开局调度绕过，不能称全局硬禁建设；原生生产门同时影响 UnitBuilder 和 PrerequisiteBuilder，混合初始值不能用单一开关保证恢复。当前建设/生产整体门与新扩张保持未接通；候选观察和原值恢复合同没有实机派发权限。编译字段独立解码、真实采用/等待/效果以及归还证据仍待完成。

扩张编译字段现已从实际 BIG、三质量流 payload、imports、relocations 和注册数组独立解码，与安装链 stock 原件比较；原件 `reports/compiled-stock-expansion-definition-20261029-v3/`。真实编译字段通过仍不证明现场采用。另一个经用户继续的主执行会话已在 PID91144 上运行自己的 `strategic_transport_profile_v1.py` / `strategic_transport_client_v1.py` 十动作试验；本线程不控制该游戏，转为其原件独审。旧文件评分为零且未报告 runtime，没有采用或效果的正证据。后续独审发现旧 runtime+0x60 实为组件内部自环，不能证明本方管理器成员；runtime+0x28 是原生任务对象，也不能与 compiled tactic 指针比较。因此旧局的“未观测到”不能改写为“实际没有任务”。修正将用于新候选，旧报告不补算通过。根线程另写的 `strategic_transport_contract_v1.py` / `build_strategic_transport_v1.py` 属于未编译、未接入的离线草稿，不能与该实机 build 混用或继承资格。

PID91144 的本轮试验已结束：最终请求/回执4、phase2、error0、mask0、cleanup1、hook0、lease0、宿主返回0、未知列表为空，独立公共信号量为1。仅证明额外偏好及运输归还，不表示原生已接手任务被取消。文件独审为 `reports/strategic-field-C-offline-review-91144-20261029-v1/review.json`；完整 F03 及正式自然局仍未通过。

后续唯一控制者的 PID85252 有界研究出现实际进展：修正后的己方管理器根观测记录到 SimpleExpansion 活动任务，同一原生任务／编组中的己方成员持续移动。并行文件交叉核对确认 15 条完整活动样本（frame4622–5048）以及同一成员约 704 单位的位移，并核对最终 STOP、零控制标志、Hook／租约归还、宿主返回0和无未知指令。原始 `native_adoption_verified` 仍为 false，本次交叉核对未篡改或升级该字段；活动任务及移动与基地建成、独占因果归因分开记录。该局由研究脚本选择高层意图，没有模型决策，不计正式局或新产品授权。只读原件交叉核对为 `reports/strategic-expansion-file-corroboration-root-20261029-v1/review.json`，它不替代原采集器、编译输入或现场资格审查。

## 当前统一通道的离线修正

唯一实机控制者已建立独立 Native5 草稿，将高层 flags 偏好与建设／生产管理器放在同一共同租约下。它仍是研究通道，不能据协议枚举、编译布局或有界研究自动授予产品模型权限。并行支持没有运行该通道或认领其现场效果。

独审复现旧归还检查只核对旧组件地址，缺少当前 Game／己方 AI 身份链。经当前 Native5 单方法移植与13项全人工 AST 检查，保留其 flags 清空门和 journal-before-publish 顺序，加入不可变绑定、实际句柄 PID／原始 FILETIME、当前己方根链、原值／flags／semaphore 顺序复读与完整采样窗口。实机归还后，在实现态且冻结表为空时，经独占写锁内二次核对，单次融合到当前 `client.py`，SHA256 `b29e8a70962259de5097bf4445634018ce3dd8387c4119f7651c2bcd198c270c`。原4版本及历史报告不改；证据为 `reports/strategic-manager-return-v5-A-integration-20261029-v1/review.json`。

另一项解析反例发现，回调初始帧用于压缩 duration，后续读帧却重新起算相对期限，后续 service 又没有独立检查绝对期限，可能使偏好跨过原绝对边界。最小修正重读当前帧、约束实际截止帧并在后续 callback 独立检查原绝对期限，保留 wall／STOP／未知与管理器路径。10项表达式检查通过，并由主线程独立复跑。在同样的归还与独占锁条件下，仅单次融合 `flags.h`，SHA256 `449290e6eeb65fdb5310fd28fa679560ca719eb257b53328243ad6710d06113e`；证据为 `reports/strategic-unified-absolute-flag-deadline-C-integration-20261029-v1/review.json`。

admission 异常分支还存在未核验 Unhook 失败的窄缺口。最小候选在失败时保留实际 hook／租约／句柄，使用私有 latch 阻止后续回调重入，保持 cleanup 未确认；普通 prepare／return 路径原字节保留。8组纯 fake CPU 场景与6项独立源码检查通过。并行任务随后按条件准备融合时，发现唯一控制者已采用相同候选并进入现场准备，因此未打开写锁、未落地或重试；只读确认实际 `native.cpp` SHA256 为 `8f82c5bec0c48a35d22a636b886888d3a3237be7c0ca55893e746adad61105af`。独审为 `reports/strategic-unified-admission-cleanup-C-independent-20261029-v1/review.json`，本任务的如实跳过记录为 `reports/strategic-unified-admission-cleanup-A-integration-attempt-20261029-v1/review.json`。该异常保留未决资源，不能冒称自动清理成功；须独立失败核验或进程结束解除。

上述三个精确哈希进入唯一控制者的 PID52600 冻结研究，目录 `reports/strategic-unified-natural-terminal-52600-20261029-v1`。之后只读交叉核对确认9次唯一指令及回执、24条解码日志、当前 OS／己方身份、flags清空、hook／租约归还和宿主返回0。原始 `match_ended_verified=False`，没有模型决策，不能算完整自然结算或正式局。原件为 `reports/strategic-unified-terminal-file-corroboration-root-20261029-v1/`。其中0ns记录来自本机粗粒度 `GetTickCount64()` 单调时钟（分辨率15.625ms），没有解释为瞬时或原子读取。

## 新观测绑定与当前产品候选

当前 Native5 rooted 观测模块修复尾部读取漏计时窗，并在采样前后核对当前 Game／engine／唯一 slot3 己方根链。构造要求显式 caller_binding；模块只核传入上下文，真实 OS 句柄认证仍属调用方责任。保留主执行方 `object_ids_resolved` 后，经归还、空冻结表及独占锁核对，单次融合 SHA `269291a25374585537291ba8c693f016544e2a07557556dba35fdecc25d8b7be`。证据为 `reports/strategic-unified-observer-binding-A-integration-20261029-v2/review.json`。主执行方随后补入实际产品 caller 的显式上下文，旧三参构造错误已不再是当前问题。

新增只读 factory `integration/host_runtime/native5_strategic_observer_v1.py` 借同一 admitted Probe 句柄，对原始 FILETIME、不可变 session／binding、当前己方根链及完整时窗进行核对。首版漏掉最后 OS 查询期间的 Game 替换，独审红色原件保留；修订后28项纯 fake 检查通过，允许正常 callback_serial 单调推进，其余状态仍严格守卫。当前已融合 SHA `86edf825d0cd8e55f3a5ea27872f8f8d120a32112e928405245d03b227713bb5`，证据 `reports/native5-observer-serial-A-integration-20261029-v1/review.json`。主运输尚未接用该 factory，离线通过不表示现场可用或新增模型权限。

主执行方已新增 Native5 controller、合法视野绑定、独立 controls 读回、域释放反馈、严格归还回放、软件闭包及客户端展示。完整 parent ACK 会释放省略的 manager 并应用完整 flags，不能与 SDK 单独 manager ACK 混同。仍在独立修订的 F04 候选处理真实 child 期限与模型窗的交集，防止900帧原生上限却把父回执记为更长模型期限；只写 D 盘新副本，不改冻结源码。当前 validator 已拒绝 phase5，旧 synthetic RestoreUnknown 不能作为正常产品路径漏洞结论。

该F04候选现已封为 `d3fdefb1…`，A独审23项中20通过、3明确跳过，确认不同域各自期限、父包络、缺期限unknown、独立组件读回及新seq隔离；计数不与作者16通过／3跳过相加。实际效果、预算采用和active三个出口共用真实域窗；只证明frame窗口，没有独立wall截止证明。主方已改用本地纯合同加载适配，旧补丁不能盲套。报告 `D:/CodexScratch/ra3-independent-next/f04-window-A-20261029-v1/review.json`，未融合。

上述“未融合”为候选阶段记录；最新已在独立归还后、implementing且空冻结表时单次受限融合为controller426fc789与产品测试eeb5accf。持两个源的独占读写handle前中后核owner、源和实际归还proof，逐文件一次写入及回读，安装后8产品＋3当前Runtime衔接全过。报告 `reports/f04-window-C-integration-20261029-v1/review.json` SHA `839e368311672fcf0a2a86d0e3207586a87f293ea6ea4c74121594f04629b0ab`。保留主方新合同导入及反馈／memory压缩变更；未改Native或observer，不授实机资格，下一闭包须重新冻结。

跨域冷却也已完成两轮反例修订与独审：同一失败work不能通过增加预算／其他gate绕过冷却，单纯情报过期或known→unknown不作新事实；可信新值、明确观测0或45s边界仍可重评。保留主方native事实优先规则后，单次受限融合为memorydec1bc2a及原测试文件76e351b3；安装后40全策略＋8产品＋3Runtime共51项通过。报告 `reports/A03-memory-C-integration-20261029-v1/review.json` SHA `087af96f11a923a921273351780ed97a99bc275a4a01cac098f4b76a6a359cef`。原TTL／schema／unknown／容量保留，不自动剥动作或部分派发，不从混合已有effect猜某域失败，不把no_effect当物理任务失败；仅支持新冻结生命周期，不迁移老私有行。真实重评链仍待实机。

另一项当前完整链CPU反例确认：独立controls最后旧Game.frame读取期间切换当前根，早先rooted样本和SDK wire不变时，现有validate_sample及Host反馈链仍接受旧样本。只证明人工环境的Host反馈可达，后续新采样和Native live_identity对物理派发仍有约束，未冒称实机已错误派发。C在D准备最小尾链候选，B独审；实际源不改，顺序读取不称原子。具体原件与分工见交接文档。

第一份尾链候选被B新增末frame变更PlayerManager／ownAI／profile的反例否决；第二份研究候选虽补末身份seal，却不能证明最后identitytail也在原整窗2frame内。两份均未融合；后者明确不支持无条件融合，不以新范围标签缩小原合同。当前仅在D研究完整tail之后更晚已完成Native callback作为有界只读见证，不保证可行或现场可用。

截至 owner `2026-10-29T14:30:03.637379Z`，唯一控制者已进入新实际客户端试运行准备，PID104548，session `49604a99-feeb-4c63-b547-5306c7441a0b`，正式仍0/3。其最新说明为新客户端已编译，正走发现、预检、启动、观察、停止与诊断，尚未公布整条流程通过。本任务仅离线复核与新候选，不修改这些冻结源、不操作游戏。用户已明确授权跨会话协调，但发送仍遇活动写入者，尚未送达；事实和分工保存在 `native5-parallel-handoff-20261029.md`，不冒称主执行方已确认。

最新 owner `2026-10-29T14:58:14.426789Z` 已进入 `field_running`，新PID102464／session `a0ac9e7d-c230-5056-9fc2-abc2ca98bbf0`，用途 `normal_GUI_real_model_trial`，正式仍0/3。这是进行中登记，不单凭名称证明实际模型调用、原生接管或流程通过；旧未接管局由主执行方正常关闭后才开启新进程。当前发布包另经A只读复核：debug仍依赖固化的工程和Python，已有文档声明；packager未完整收Native5非Python制品／资格闭包，旧release不继承新资格。保留发布限制，不把debug.GUI冒称安装版通过，也不将独立portable分发额外设为当前仓库试运行前置。

后续已在103756／e5c75新会话取得一条真实模型方案、Native接收及独立归还，第二轮因context_budget_exceeded停止。主方转implementing／空冻结修压缩后，并行支持按上述归还前提融合controller426及memorydec1，51项安装后检查通过。最新跨会话同步已成功送达主方，含精确源码／报告／缺口；未将送达冒称已读或采用。主方将以新冻结重跑连续决策，旧单条方案不补计正式局；细节及合法style转义预算边界见交接文件。

## 剩余退出条件

1. 独立复核并重新冻结战略观测和客户端配置融合；实际完成配置、发现、预检、启动、观察、停止、诊断与下一局。
2. 接通符合已公布语义的建设/生产/扩张高层入口，验证采用、等待、期限和原值恢复，不用预算偏好冒充这些功能。
3. 验证有效效果及无效、条件改变后的战略保持或调整，再以同一冻结候选完成三局普通自然结算和独立生命周期复核。

这些事项未全部完成前，不结束目标，不给出完成百分比或用离线测试数量替代产品进度。
