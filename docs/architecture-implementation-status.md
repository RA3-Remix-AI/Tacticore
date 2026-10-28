# 新架构实施状态

## 最新实机进度（2026-10-28，原生宏观flag消费者）

- 新建隔离的宏观人格/机场建造状态/原生侦察状态；三档编译、ID、标志和BIG校验通过，每档854个旧资产原样保留。原发布包未替换，当前未发布宏观客户端。
- 正常脚本flag helper完成诊断false→true→false与独立树读回；新增7项解码检查通过。真实AI对两个新状态的flag各查询20次；后续6秒启用侦察gate时，指定P3消费者实际返回1，关闭/最终独立回查为false。所有观察入口恢复及helper退出已核验。
- 这是输入、回执和原生消费链的局部实机证据。对应侦察队伍/信息反馈、机场施工与扣费、宏观经济科技预算、区域调度和整局模型效果仍待完成；没有模型请求，不算G7或G8。当前隔离研究局仍由原生AI运行，完整目标active。原件和准确帧关系见[原生宏观标志链](commander-native-macro-flags-20261028.md)。

## 最新源码进度（2026-10-27，宏观模式默认边界与接口审计）

- 新Host默认`macro_native`，不再创建单兵调度器；宏观Host的单兵attach/reserve/commit及换通道入口拒绝。桌面预检/启动/实际派发拒绝旧微操证据，启动参数不再转发旧证据。原始历史源码/制品和只读/停止核对保留。此改动尚未发布到客户端包。
- 新增6项边界、相关56项和完整宿主442项软件检查通过。拒绝规则更新后两次完整回归的旧预期失败原样保留；没有游戏/SDK/真实模型调用。源码检查不替代实际原生AI持续操作的实机验收。
- 固定游戏14处字节/调用、5段反汇编与6份SDK schema只读审计通过；明确战略setter的副作用及MAKE_BASE的原生基地管理路线，未授新能力。见[宏观接口矩阵与证据范围](commander-macro-interface-matrix-20261027.md)。
- 当前仅有限兵种生产具有可复用真实执行证据；建造、侦察、科技及区域调度消费者仍待实施。总目标继续active，下一批沿原生建造/预算状态及战略队伍任务推进，不恢复单位微操验证。

## 当前目标修订（2026-10-27，用户明确调整职责边界）

- 当前执行依据改为[宏观指挥目标与 G0–G8 验收](commander-macro-goal-20261027.md)：核心负责建造/经济科技、侦察、兵种构成和部队区域任务决策；原生 AI 继续负责寻路、局部目标选择、交战、技能和其他操作。
- 逐枪伤害归因、单兵租约、近场攻击与强制物理回家退出当前完成门槛。相关源码和失败证据保留为历史资料；现有近场能力不因此变成已通过或自动进入新模式。
- 已核对：旧自动目标 paused；最近两局诊断均有独立恢复核验及 fixture-ended 记录，当前没有运行中的 RA3/shot_probe/near_runtime 实验进程。本轮未启动游戏、模型宿主或新实验。
- 新验收链是“模型宏观意图→原生高层机制接受→建造/生产/侦察/部署变化→战况反馈”，并保留客户端真实配置、完整对局自然结算及模型贡献证据。新接口尚需核验，不以已有微操/离线成果替代。
- 用户已清除旧自动目标，新版宏观自动目标已创建并active，无预算限制，明确要求持续推进至新版全部验收完成。下方是旧边界下的历史进度和交接；其中active、G4或待测开火等描述不构成恢复旧路线的指令。

## 跨会话并行开发交接（2026-10-27；不代表实机通过）

- 用户明确周六（10月31日）仍以全部G0–G8为目标，并要求单游戏客户端。原实机会话继续独占现场；三个并行Agent只做离线代码：`strategy/tactical_planning/`、`acceptance/reporting/`、`benchmark/contribution.py`及统计回归。详见[并行所有权与单客户端队列](parallel-g0-g8-handoff-20261027.txt)。新模块的调用接线及原生能力仍需实机拥有者按合同接收，不能由离线测试授予。
- 本协调会话已将后续生产/Reserve前的计划有效性门修入`integration/host_runtime/orchestration.py`，保留拒绝/unknown回执、停止和原准备期限；新增`test_host_runtime_plan_freshness.py`，连同原8模块共72项离线测试通过。未改原生活动实现或发布包，未操作游戏。此交接不改变下列历史证据或总目标状态。
- 并行代码已交付：三purpose建议软件100项、只读证据工具34项、统计修复与贡献对照71项通过；根会话用同一candidate13冻结319事件完成双工具绑定/SHA联调，三purpose重放digest一致。统计/编排修复已实际落源，不再只是候选补丁。战术包仍待活动Host接线及实机授权；不计G6实战通过。源码清单及报告在仓库外`parallel-development/20261027-saturday/delivery-manifest.json`，精确API见各新目录说明。

## 最新整体进度（2026-10-27 22:32 原生开火被动采样）

- 新隔离探针被动记录原生攻击、核心开火和伤害入口，逐次原样转发，不调用SDK或取得单位控制。静态审计41处/24段、60组双架构回放和7组隔离边界通过；不授攻击能力。见[三轮实机记录与验证范围](runtime-near-passive-shot-20261027.md)。
- 前两轮825/826行全部为心跳，没有合格开火/伤害样本。第三轮v7等待原生自然生产动员兵后采样90秒，得到843行：9组私有攻击调用和825条心跳；合格开火/伤害仍为0。requested2147483647与调用前后ammo3不作为有限轮数或开火证明。武器配对读取的具体拒绝原因仍需定位。
- 三轮独立核验均证明正常关闭、helper退出、仍活原游戏23处入口恢复。第三轮另检查未准入目标字段清零及完整调用配对。独立恢复核验后结束owned诊断局；零模型请求，无自然结算证明。G4、G6、G7、G8及完整G0–G8目标仍active。

## 历史进度（2026-10-27 20:25 当前编译基础射程实机通过）

- 精确游戏getter/原生消费者字节及真实BIG中Tokenized武器字段交叉核对，确定AK47运行时schema基础射程字段。新读取器实际读取并配对五个字段，源规格仅作期望比较，不能回退替代读取。见[基础射程证据与范围](runtime-near-compiled-range-20261027.md)。
- 全新局实付85创建object798/generation1；115次观察、107个不同帧，两条完整原生射程诊断均为`[150,0,0,0,0]`，一条原生Ready。独立审查直接从仍活同一游戏重新读template/schema/header与24字节原数据匹配，编译基础射程150实机通过。5条武器读取拒绝保留。
- 首次尝试资源不足由原生产器native9在enqueue前拒绝，paid0/created0，新通道未装入；原失败和完整清理保存。驱动只增加提交前的有界资源等待，原reserve1000与原生最终准入不改、不重发。6项Python边界、58组双架构C++回放和v7隔离通信6组通过。
- 新通道零移动/攻击命令与SDK、零模型请求；生产真实调用单独计。新通道/生产器完整释放、三个helper退出，仍活游戏21入口原字节再验证后结束fixture。有效开火条件、shot/damage来源链与G4其余、G6/G7/G8继续实施，总目标active。

## 历史进度（2026-10-27 19:37 新工厂无命令实机资格通过）

- 全新诊断局实付85创建征召兵object789/generation1，新v2工厂真实装入并连续取得115次观察、106个不同帧，6条武器诊断中1条原生Ready。独立解码付款账本、完整共享结构、绑定和执行前92份冻结来源通过；另4条武器身份拒绝原样保留。见[实机范围与失败记录](runtime-near-factory-channel2-20261027.md)。
- 新通道无移动/攻击命令及SDK调用；模型请求0。新通道state3/mask32767/active0、生产phase2/mask31/active0，三个helper退出；仍活同一进程21处入口24字节与固定PE再次比对一致，然后核对精确进程身份结束诊断局。生产本身真实调用SDK，不将整轮称为零游戏SDK。
- 首局实付生产后因客户端在首份观察先于两路回执发布时过早读取而失败，原始证据不覆盖。新采样器等待三份正偶数世代，4项边界测试通过后才换全新局复验；原v1、已冻结v6和出生规则未改。首版审查误将首次稳定注册帧等同完成帧，其失败报告也保留，修正审查语义后重新输出v2。
- 仅新工厂的无命令接入资格通过。当前编译射程、真实发射/命中/伤害归因、受控攻击回撤及组合恢复继续实施；G4、G6、G7模型完整对局自然结算和G8贡献对照仍未完成，完整目标active。

## 历史进度（2026-10-27 近场原生工厂与独立v2通道开发）

- 新原生工厂已接通原生产回执/付费出生、Incarnations、MemoryIO、组合Owner、目标/武器读取和独立准入；全部依赖在安装前构造。原producer核验函数逐字复用，原活动v1不改。目标只由绑定注册表解析opaque key，失效后不能复活。见[工厂与v2合同](runtime-near-factory-channel2-20261027.md)。
- 新DLL/helper/消息/mapping均为独立v2；攻击与原返回命令成对发布，移动/攻击共享Owner序号。双方held及15处32767恢复掩码共同决定终态。未知或回调异常锁定旧图，不自动推进动作；未验证的组合6/7恢复明确拒绝。原180秒helper边界与原租约900帧/120秒保留。
- v5已实际完成DLL/helper构建，6组本机通信检查通过，29项C++/PythonABI一致。新工厂5组未安装边界及原51组回归通过；整套runtime100项通过，随后新增的采样器3项单独通过。构建解析/格式/保留变量错误与v4成功快照均保留，未重写失败。
- 新`near_factory_probe`仅可在明确owned、模型禁用的只读会话装入/观察/停止，拒绝所有命令发布，等待真实付费出生和15入口关闭的实机资格验证。本轮没有游戏/SDK/模型调用或客户端发布，未授新能力；射程/射击伤害/攻击回撤/组合恢复、G6/G7/G8仍未完成，完整目标active。

## 最新整体进度（2026-10-27 独立原生攻击准入与武器读取）

- 新`NativeAdmission`直接引用原Owner/MemoryIO和原生读取器，逐次重读实际租约、已接受命令、Stop94/source1、出生/队伍/epoch、当前目标key/己方视野、AK47就绪及原900帧/120秒期限。停止立即撤销资格，读取后再检查Owner/演员/时钟。不是从调用者的ready/visible字段放行。见[准入合同](runtime-near-native-admission-20261027.md)。
- `WeaponReader`独立配对核对活动槽、条目/asset/状态机反向关系及ReadyState0；保留原请求计数，不当成射击数量。Win32构建策略工厂锁定并校验当前游戏身份及8份固定hash文件，没有公共构造或reviewed开关；源规格射程尚非当前编译数据的实机证明。
- 接线复查修正新观察器提前清除原Stop见证的问题：提交/待发阶段保留原见证，实际攻击交付后失效。新增8组和原47组分别在x86/x64通过，共110次组执行；Win32未安装边界4组、原移动内核51组回归及runtime Python99项通过。
- 本轮没有游戏进程/游戏SDK/模型调用，没有发布新DLL或客户端；正向策略/新读取器、Owner/Execution工厂/新ABI和射击伤害关联仍待实机接入。上轮只读采样继续是原版本限定证据。G4未全通过，G6/G7/G8未完成，完整目标active。

## 最新整体进度（2026-10-27 近场武器与己方可见目标读取实机）

- 新增隔离的只读采样器，真实游戏线程上取得武器身份/反向关系/原生ReadyState及电脑3当前完整视野目标。`165814/readonly03`同段97条自身配对、56条就绪、396条可见目标、1条不再可用；state3/error0/active0，原始二进制独立复核通过。见[实机读取记录](runtime-near-readonly-field-20261027.md)。
- 前两段正常关闭，共951条可见目标记录；当时没有自身征召兵样本，不能替代第三段。第一次`163953`在原生对局结算时因根检查拒绝结束，保留state4/error20及未完成结论，不计模型整局成功。第三段41次自身读取拒绝及第一段48次注册拒绝均保留，未据此放宽准入。
- 模型请求/借兵/游戏SDK均0，未安装游戏入口detour。三个helper退出后，仍活的同一游戏15处入口原字节再次独立读取一致，再结束owned诊断fixture。30份来源冻结，活动v1全部25份输入及3个制品hash未变，candidate13未发布更新。
- 此次只证明读取分项，尚未证明攻击、真实发射/伤害或撤回归还。可信准入/Owner工厂/新ABI及G4其余实机继续推进；G6三战术、G7模型整局自然结算、G8贡献对照未完成，完整目标继续active。

## 最新整体进度（2026-10-27 正常攻击调用链、原生观察器与待发取消）

- 在不改活动v1源码/产物的前提下，新增严格opcode11攻击链及独立原生观察器。正常攻击走facade，copy指针→ID、unpack ID→指针、dispatch及private调用者均需匹配；source0、无限请求、重放或错误目标拒绝归属。新观察器15处钩子，准入默认拒绝，尚未装入游戏或发布。见[原生接入合同](runtime-near-native-lineage-contract-20261027.md)。
- 补齐正常Stop替换尚未解包的攻击：封装当帧完整原记录、实际copy后再核对Stop载荷，保留真实忙槽，不伪造空槽。已解包/已交付攻击不能被标记为取消。旧Move/Stop行为通过原51组测试体对新NearMoveLineage的独立回归；未知仍停止重试并保留held。
- 47组近场C++回放分别在x86/x64通过，另3组真实Win32链接后的未安装边界检查通过；runtime Python99项通过。固定SHA原生审计扩为24点/16段，确认WeaponReadyState0和反向关系，未将弹药/请求计数冒充实际发射。首个缺依赖的冻结构建失败与纠正目录均保留。
- 尚无新游戏进程、SDK调用、模型请求、能力授权或客户端发布。实际准入读取器/工厂/ABI、射击伤害关联及G4实机仍待接入；G6三战术、G7自然整局、G8贡献对照未完成。完整目标继续active，不以开发代码或离线通过替代验收。

## 最新整体进度（2026-10-27 近场合同、组合控制器及原生字节审计）

- 新增开发中的近场控制器、只读目标注册/视野读取器和组合 Owner。Owner 复用原移动控制器的私有原点、Stop3、回家与归还流程；共同管理命令身份及序号，保留原始900帧/120秒租约。攻击/回撤交付未知时停止重试并保持held，命中、实际回家和控制归还分开记录。详见[实现合同](runtime-near-combat-owner-contract-20261027.md)。
- 35组C++实际回放分别在x86、真正x64通过（15近场/11目标/9组合，共70次组执行）；包括30秒显式模拟暂停后的过期撤回、原生让路、归还后立刻重编队、不同路由的命令ID冲突及不明交付。运行时Python98项通过。活动v1声明的输入、DLL和Host哈希未改。
- 对固定SHA游戏二进制完成16处字节/相对调用核验和9段反汇编。正常攻击opcode11会在copy时将目标指针改成ID，unpack时再解析，不能直接套用移动命令存储关系。请求次数1不能单独证明实际有限发射或命中。首个离线快照的x64错误标记及纠正记录原样保留。
- 新组件尚未进入原生DLL、发布ABI、客户端或能力目录；没有新游戏SDK调用、实机攻击、模型请求或新能力授权。当前无游戏或控制Host运行。下一步接入精确攻击调用链、独立武器及射击/伤害证据，再做G4受控实机。G6三战术、G7自然整局、G8贡献对照仍未完成，完整目标active。

## 最新整体进度（2026-10-27 candidate13实机迟后接续、客户端停止和下载）

- `134626`新会话从真实candidate13检查/启动，691份执行前来源冻结，manifest与8,745份伴随文件对应。revision3、614字节有效风格进入真实DeepSeek；24次尝试、23次完整HTTPS200响应，另1次传输超时原样保留且之后恢复，重试计数0。宿主未因超时退出。
- 实付4笔征召兵共340，另6笔生产在SDK前拒绝，原账本完整。801所在首通道无借兵机会后关闭；等屏障解除，用较新生产序号4的807接第二通道，随后无机会正常关闭。两个较早完成的候选序号2/3未被再接为第三通道；原输入重放执行候选过滤同样返回空，不推断这些旧单位具备实际借兵资格。
- 原Host在第一次通道接入后仍真实存活并继续模型调度230.047秒，超过该通道180秒预算约50.047秒；两个原生通道均已关闭，**不是延长NativeHost硬时限**。这轮没有Reserve/Commit、移动或新局部任务成功，不能替代上一轮真实模型动作或G4效果。
- 真实客户端请求停止后Host达到stopped/user_stop，原进程确认退出。包内可信CLI审计两个epoch通过：state3/restore8191/callback0/exit0、生产phase2/restore31、19处新鲜原入口及被动观察器关闭；最后通道另做停止后新映射捕获。全会话未决0，新客户端同时显示宿主已停止/独立控制归还验证。
- 实际下载253,755字节脱敏诊断，319/319事件、未截断，与服务端逐字节一致，补充偏好原文未打包。23项独立复核与698份来源的另进程冻结重放一致。原生之后出现统计页，但Host先由用户停止、本场明确为局部复测，不计G7；独立归还后已结束owned fixture。见[实机检查点](../reports/runtime-candidate13-client-lifecycle-checkpoint-20261027.json)。
- 本轮没有更改活动实现或原生DLL，也没有新增授权。下一步推进[原生自卫/近场战斗缺口](runtime-near-combat-gap-review-20261027.md)的类型合同与重放，再做G4实机；G6三战术、G7完整自然对局、G8贡献对照继续保留，完整目标active。

## 最新整体进度（2026-10-27 三通道独立归还与candidate13）

- 新增可信本机`runtime_epoch_release`审计，覆盖原Host、同会话所有绑定、不可变退役/后继授权、原始战术包/SQLite/事件关联、完整关闭流与最终原生映射。只允许“未决attach且原通道命令0/事件0/未借兵/已关闭”的独立归还例外；未知游戏动作不能套用。新增审计记录可关闭当前控制投影，旧uncertain及原fault不改写。见[审计合同](runtime-epoch-release-contract-20261027.md)。
- 对`131614`真实运行执行审计通过：3通道state3/restore8191/callback0/exit0；最终配对生产原始账本4笔/实付255、19入口原字节和被动观察器关闭通过。追加2条审计记录后跨进程重开：当前fault、独立归还true、全会话未决投影0，原第三attach逐字段仍为原uncertain。重复审计返回幂等，不再读取/派发新原生命令。
- 11项完整审计复核与698份来源独立进程冻结重放一致；原27项局部动作效果证据和原失败继续保留。原生其后显示统计页，但Host先fault且本轮限定为局部验证，不作为G7自然整局验收。独立归还后已结束owned游戏，原session文件不改，活动索引另标fixture_ended。
- 17项新增定向反例、Host全套428及runtime97通过。candidate13完成TypeScript/Vite及Windows release，8,745伴随文件逐项SHA/零额外文件、EXE内嵌manifest pin和包内独立Python导入通过，原生d168未改。包含上一轮晚序生产候选过滤修复；该修复尚未新一轮实机。
- 已打开真实candidate13，确认同一界面保留原“对局需要处理”及局部任务历史，同时显示“已收到独立控制归还验证”；没有强改旧candidate12界面。见[审计/发布检查点](../reports/runtime-three-epoch-release-and-candidate13-checkpoint-20261027.json)。
- 下一步新会话复测迟后接续和候选过滤，再按原G4顺序推进让路/自卫/命中/双兵与异常。G6三战术、G7完整自然对局、G8对照仍未验收，完整目标active。

## 最新整体进度（2026-10-27 真实模型首次局部机动与迟后接入拒绝）

- candidate12真实客户端保存并重新载入revision3，614字节偏好未截断；`131614`会话冻结690份执行前来源和8,743份伴随文件。11次真实DeepSeek HTTPS200响应消费同一有效配置，运行明确标记为局部机动生命周期验证，不是整局验收。
- 模型选择宿主提供的opaque机会与端点，原Host/Gateway/SQLite派Reserve/Commit（全局3、4）。实付征召兵798完成保持15帧、返回及原生控制归还；原始120事件、1,617条钩子中可重核完整阶段、四次三帧停止、原生端点及home清空证明和SDK计数[1,1,4,2,1,1]。只授局部动作信用，三战术覆盖不变。
- 第一通道正常退役后，用另一笔较新付款的805完成第二通道接入；该通道未借兵、无机会后正常退役。第三次误选了更早付款的803（生产序号2早于上一演员5），`finish_handoff`拒绝单调生产账本检查，Host在176.4667游戏秒fault。第三attach保留uncertain、不重试，原成功和原失败分别保留。
- 三份关闭报告及原退役只读捕获重核；最新第三通道另作全新只读捕获，state3/restore8191/callback0/exit0、命令0。生产4笔：3完成、1在SDK前拒绝，实付255；全新配对原始生产账本和19入口字节读取通过。旧通道映射已被后继替代，使用其原不可变退役捕获，不伪称事后重新读到了旧映射。最终多epoch独立归还投影仍未完成，第三attach未决仍保留。
- 27项实机复核与697份来源的独立进程冻结重放一致。模型候选现在要求生产序号晚于已退役演员，Host接续边界也在授权/装钩子前拒绝早序候选；新正反例与Host全套411项通过。此修复晚于实际candidate12、尚未构建/实机，原包不覆盖。见[实机检查点](../reports/runtime-actual-model-maneuver-and-handoff-fault-checkpoint-20261027.json)。
- 当前无控制宿主或NativeHost运行；owned游戏保留供独立归还审计，客户端显示原fault及尚未验证归还。下一步审计所有epoch及未决attach，再打新包复测。G4其余动作/异常、G6高级战术、G7自然整局、G8对照仍未验收；完整目标active。

## 最新整体进度（2026-10-27 有界准备、延后接续与candidate12）

- 原生关闭与下一通道授权已拆开：不可变`RuntimeRetirement`只证明旧通道关闭；等新的已付款候选可用后，再一次性生成新绑定/固定演员选择。关闭及迟后attach分别核对独立移动/恢复pin、完整关闭字节和权威屏障，全局序号用迟后时点的高水位，未知不重试。等待期间不poll旧IO。
- 未装通道的付费候选及装通道后的Native就绪等待均有30秒边界；90秒后不接新租约，活动任务120秒前一次停止，Native180秒硬限制不改。退役等待生产屏障时不继续塞新生产。Host生产遵守150帧间隔；模型能看到typed准备状态，不能从付费/准备推导动作权限。
- Reserve前及Ready后均核对最新原生帧/暂停，旧战略快照不能延长计划TTL。Host停止后保留任务历史；客户端单列局部准备、执行及实际home/控制归还事实，局部任务不冒充三战术效果。[生命周期合同](runtime-deferred-lifecycle-contract-20261027.md)。
- Host409、策略200、runtime97、模型后端28、前端51检查通过，TypeScript与Windows release编译通过。跨180秒等待及新付费演员/序号连续仅为注入时钟与显式模拟nativeIO组合证据，尚未实机。[实现与发布检查点](../reports/runtime-deferred-lifecycle-checkpoint-20261027.json)。
- candidate12的8,743份伴随文件逐一SHA和零额外文件核对，exe内嵌manifest pin，22份相关源码另冻。candidate11为复查前未编译/未采用快照，原样保留；候选包未复制凭据，原生d168未改。本轮没有新模型请求或游戏动作。
- 下一步真实客户端核对新界面和模型局部任务，再验证实际通道退役/接续及多epoch最终独立释放。全部G4/G6/G7/G8仍保留，完整目标active，不以本次构建或合成时钟算实机成功。

## 最新整体进度（2026-10-27 真实客户端/模型/生产与规划拒绝修复）

- candidate10已从真实窗口检查并启动`120917`新会话，可信登记同时带d168普通基线及独立恢复pin；689份执行前来源冻结。已保存revision2及同一effective hash实际进入DeepSeek/deepseek-flash，7次HTTPS200完整响应、无注入transport，316字节偏好未截断。实付85完成805；另外两次生产分别因最小间隔和资金/保留底线拒绝，attempted/paid/created/completed均0。
- 本轮没有满足借兵机会：805在原生行为中移动，随后frame2142仍live/identity/birth为真但grounded为假、state77/source0；严格规划观察导致Host在142.4667游戏秒fault。运行时native sequence0、命令0、事件0，完整285钩子；未Borrow、未发移动任务，原fault保持。不能称模型战术、正式整局或风格效果通过。
- 原生state3/restore8191/callback0/Host exit0，生产phase2/restore31/error0；另起只读捕获和19原入口读取一致。新的可信idle审查重新关联3条生产账本及完整原始映射，仅适用于从未借兵；新记录证明no_control_acquired与钩子关闭，当前后端投影fault/独立清理通过/未决0。旧candidate10界面没有新投影代码，仍保留其原先未收到归还的显示，不伪称已升级。见[清理合同](runtime-idle-release-contract-20261027.md)。
- 客户端真实下载99,834字节脱敏诊断，与服务端逐字节一致，补充偏好原文不在包中。游戏其后出现原生统计页，但Host已提前fault、结果内存已清零，不推断胜者或授G7信用。独立清理后已结束owned fixture，当前没有活动游戏/控制宿主。
- 21项复核及697份来源的两版冻结另进程重放完全一致。[实机及修复检查点](../reports/runtime-actual-client-idle-fault-checkpoint-20261027.json)。规划可用性已拆成只读拒绝事实，绑定/演员字节/线程继续严格；动作与恢复仍用严格观察。389项Host、97项runtime通过；随后补强生产进程起始身份等10项定向回归通过。修复尚未打新包/实机。
- 下一步先处理未就绪演员的有界准备与闲置通道生命周期，再跑真实模型移动任务；180秒接续、全部G4异常/效果、完整G6战术、G7整局与G8对照仍保留。总目标active，没有外部阻塞。

## 最新整体进度（2026-10-27 模型局部任务接线与新发布包）

- 模型策略新增独立可选`runtime_task`，仅在可信宿主提供`runtime_opportunity`时选择本轮opaque地点、局部方位/距离及保持帧数；双快照重核同机会/端点。没有坐标、actor、grant或native序号字段，不把它映射为主攻/骚扰/协同。
- 实际Host循环已接`ModelRuntimeTasks`：先关联权威生产账本中的已完成实付征召兵，attach只读观察；沿用独立己方home清空/静止过滤后提供机会。模型接受后持久记录plan关联并经原HostTactical/Gateway/SQLite派Reserve，等待Ready后只提交原选择。端点失效、计划过期或宿主停止走停止归还；未知只保留/报告，不自动重派。
- 回家、控制归还与本地任务效果依赖原生规范回执，结构化反馈进入BattleAgent；局部任务不增加原三类战术效果覆盖。采样等待/暂停/停止状态不能偷偷Commit；同计划不重复派发。10项Host组合、7项策略正反例及native身份拷贝测试新增通过。
- 全套Host378、策略199、运行时96、模型后端28、前端50通过。均为离线/显式模拟IO；没有真实HTTP或游戏动作。[模型局部任务与发布检查点](../reports/runtime-model-local-dispatch-checkpoint-20261027.json)。
- 仓库外candidate10已完成TypeScript/Vite和Windows release编译；8,741份伴随文件逐项SHA核对、零额外文件、exe内嵌manifest pin、7份当前实现与包内源码一致，包内独立Python导入通过。原生DLL仍d168。candidate09为未编译/未采用的复查前快照，原样保留。没有更新实际登记或打开新客户端。
- 下一步从真实客户端新登记验证有效配置/真实模型→任务→回执/停止，再补跨180秒接续和其余G4/G6–G8。局部接线与构建不替代整局/高级战术验收；总目标active。

## 最新整体进度（2026-10-27 客户端恢复登记与交接接线）

- 客户端可信登记已接入独立恢复证据与SHA，只有与普通运行时基线配对且位于可信根内才接受；证据变化使旧就绪令牌失效。Host启动收到原路径/pin，网页和模型没有新增授权入口。实际用户登记与旧发布包尚未更改。
- 普通Host交接在退役旧通道前及绑定新宿主后各重核一次；已有恢复能力不能无pin静默降级，第二次失败不attach、不重试新通道。跨独立Python进程登记重开、路径越界、半配对、旧launch未决禁止替换等反例通过。
- 本次Host完整368项、运行时95项回归通过；6份实现/测试来源另行冻结。[登记与交接离线检查点](../reports/runtime-desktop-recovery-registration-checkpoint-20261027.json)。首轮交接测试夹具缺少构造器状态字段的失败已保留说明，修正夹具后通过，未放宽生产逻辑。
- 这轮没有模型请求、游戏命令或新发布包，不冒充新客户端实机交接。上轮`111322`的实际Host恢复及原任务失败结论继续保留；模型决策目前尚未调用新的单兵任务调度接口，需显式补接并验证，不能用局部移动代替主攻/骚扰/协同验收。
- 下一步：补接实际模型任务调度，合并构建新发布包，再从真实客户端验证配置消费、任务回执和安全停止；180秒接续、其余G4、完整G6/G7/G8继续保留。总目标active，当前无活动游戏、无外部阻塞。

## 最新整体进度（2026-10-27 11:28）

- `111322`首次实际走通新Host/Gateway/SQLite首次回家恢复。新驱动显式owned位2，先重核普通基线和恢复bundle，原生transport即使在诊断模式也对操作7强制独立verified scope，原始报告实际记录恢复证据ID。付费85征召兵781/birth643，741帧Reserve、755帧外出、772帧Hold；独立诊断命令seq3有自己的SQLite意图/序号、fsync封存和SDK前派发claim，795帧真实scope外Move使原Commit2 unknown。
- Host四个新source2停止帧808/810/811/813及原生配对空槽/反链后，新的操作7 seq4于816帧接受；828帧仅第一次home Move，849帧实际home，854帧恢复姿态/归还。原home`(1770,1850,210)`，释放位置约`(1771.959,1851.982,210)`。SDK`[1,1,4,2,1,1]`为两个owned Move，另有一个显式注入Move，不能说成自然AI干扰。
- SQLite四行依次reserve/completed、commit/uncertain、diagnostic_foreign_move/completed、reconcile_return_home/released，连续全局1–4。原Commit失败回执与前缀未改写；新恢复mission_effect=false；四帧观察按frame去重，幂等重放原native sequence4/commands4均未变，独立重开只读控制投影未决0。
- 56项原字节/SQLite复核及182份冻结审查来源另起进程复算一致；181份执行前来源保持原样，77份早期runtime归档匹配，97事件/1330钩子无丢失。Native Host exit0/state3/restore8191/callback0，生产器实付85/phase2/restore31/error0，19入口另读恢复后结束测试局。[Host首次回家恢复检查点](../reports/runtime-actual-host-first-home-recovery-checkpoint-20261027.json)。95项运行时、355项Host离线检查通过，原生DLL未改。
- 这证明新Host恢复分项；原675帧任务仍失败，不授普通位0自然unknown、实际失败7再新6、180秒、模型、自然结算或完整目标信用。失败7→新6和高水位落后仍分配4已用真实SQLite/Host组合的显式合成IO验证，实机本轮未触达该失败分支。
- 下一步接客户端可信恢复pin登记与handoff重核，并推进实际客户端配置/模型任务、180秒及其余G4–G8。总目标active，当前无活动测试游戏。

## 最新整体进度（2026-10-27 11:04）

- 独立首次回家恢复授权器已实现。新的14输入bundle逐项显式SHA pin，读取受限且拒绝重复JSON键、非有限数、路径越界和额外成功标记；不执行report指定的审查代码。核验原执行前来源/SDK前持久意图、当前构建/ABI、普通位0基本动作、位2原生干扰/Unknown前缀、四帧/配对槽、自己的Stop3/当前home空位、唯一首次返程、实际home/归还、原生及生产器清理。[授权器检查点](../reports/runtime-first-home-authorizer-checkpoint-20261027.json)。
- 当前原始资料46项独立检查通过，180份固定授权器来源在另起进程复算完全一致；355项Host、89项运行时测试通过。新的`tactics.reconcile_return_home`仅在可信调用方同时提供基本动作报告pin和恢复bundle pin时生成；默认不授。原生DLL仍d168，操作8未进入普通权限，也不授攻击、广泛撤退、自然干扰或原任务成功。
- 中间快照的共享highwater曾被错误要求为3，审查器因此拒绝真实旧资料。核对原生发布顺序后确认观察highwater2与独立诊断ack3可并存；现严格同时核验旧Commit2 Unknown、独立ack3及其稳定代次、尚未消耗4，增加拒绝缺ack/提前4的反例。原字段及证据未改写，最终新恢复序号仍4。
- 普通Host CLI/production builder/能力目录已接成对`runtime-recovery-report`/`runtime-recovery-sha256`并强制已有普通位0基线。新的实机Host恢复驱动、实际Host/SQLite7验证与客户端可信登记继续实施；本批没有启动游戏或模型，不把历史直接诊断的成功称为新的Host成功。
- 总目标active。下一步由新授权实际验证Host/Gateway/SQLite的恢复、幂等及失败保留，再推进180秒和其余G4–G8；当前无活动测试游戏。

## 最新整体进度（2026-10-27 10:36）

- 同d168已补齐普通位0基线`101150`：实付85征召兵779/birth572，670帧Reserve、683帧Move、Hold15、746帧实际home/归还，SDK`[1,1,4,2,1,1]`。21项完整校准与177份执行前来源独立复算通过。[基线检查点](../reports/runtime-d168-flags0-baseline-checkpoint-20261027.json)。79事件/1260钩子、Native Host exit0、生产器关闭/19入口独立恢复后结束测试局。
- `101634`消费这份基线SHA，实际Host/Gateway/SQLite同一付费征召兵780连续两任务于744/834帧home/归还，全局seq1–4，幂等回放不重派。47项原始/SQLite复核及177份执行前来源复算一致，164事件/2546钩子无丢失，生产器实付85/正常关闭、19入口独立恢复后结束fixture。[两任务检查点](../reports/runtime-d168-two-host-tasks-checkpoint-20261027.json)。原675帧完整任务证据仍属于ef38，未授d168长任务或180秒信用。
- 随后实现单独的`tactics.reconcile_return_home` Host/Gateway/adapter/transport路径：新授权scope与原移动权限分开，限定旧unknown Commit、Move1和新四帧静止；自己的固定请求ID/持久意图/全局序号，只允许新首次回原home，恢复mission effect强制false。新7失败后，新6可关闭同一task/lease/generation的控制引用链，保留旧Commit与7两条unknown；撤权后只读回放不重派。恢复四帧记录去重，并检查帧钟和单调钟不回退。
- 89项运行时Python、330项Host完整检查通过，原生DLL/ABI未改。[接线检查点](../reports/runtime-host-first-home-plumbing-checkpoint-20261027.json)和[授权合同](runtime-host-first-home-recovery-contract-20261027.md)。实际证据目录尚不生成新恢复grant，独立组合证据授权器/可信启动参数及实际Host7仍待完成；不能把本批离线接线称为新的Host实机通过。操作8继续关闭普通入口。
- 下一步实现独立恢复原始证据审查与显式pin接线，再做Host/SQLite新恢复实机验收；180秒、其余G4及G5–G8保留。总目标active，当前无活动测试游戏。

## 最新整体进度（2026-10-27 10:10）

- 新d168在`095903`首次实机触达明确受控干扰及操作7：付费85征召兵779/birth573，761帧Reserve、774帧外出、790帧Hold；812帧独立诊断操作8经scope外source2 Move facade→dispatcher→private Move，真实foreign epoch0→3，原Commit2被guard判unknown。注入有自己的意图/UUID/seq3，不称为自然AI决策，不替换旧任务身份。
- 825/827/828/830四个新source2停止帧、配对空槽/反向链接后，新操作7 seq4于833帧接受；835帧发自己的Stop，842/843/845三帧当前完整空位及同帧SDK前复核后，845帧仅第一次home Move；866帧实际home，871帧恢复姿态/原生池归还。SDK`[1,1,4,2,1,1]`只计两个owned Move，另有一次明确注入Move。原Commit及任务仍failed/unknown，恢复goal effect=false。
- 42项原始字节检查通过；177份执行前来源保持原样，另起178份事后审查来源的独立进程复算一致。95事件/1360钩子无丢失；独立映射另读state3/restore8191/callback0、Host exit0，生产器实付85/phase2/restore31/error0，19入口另读恢复后结束owned fixture。[实机检查点](../reports/runtime-controlled-first-home-recovery-checkpoint-20261027.json)。
- 原只读bootstrap审查器不认识位2，曾明确拒绝capture；现仅增加显式位2读取支持，普通qualifier仍默认位0，位2不能授普通能力；42项审查器/读取测试通过，失败与修正另记。没有重派游戏动作或改写历史证据。旧ef38两次675帧成功仍只属于旧版本。
- 下一步为同d168的flags0基本动作、普通Host同局重复及显式恢复/账本接线，随后180秒接续及其余G4–G8。操作7/8在普通Gateway/transport仍关闭；本次只证明owned诊断恢复分支，不证明完整675帧任务成功、自然干扰、正式模型对局或完整目标。总目标active；当前无活动测试游戏。

## 最新整体进度（2026-10-27 09:59）

- 明确标记的受控干扰操作8已实现：bootstrap位2、每通道至多一次、当前Holding/付费演员/原生端点准入、SDK前exclusive+flush+fsync意图、独立UUID和序号；既有Move facade在自身scope外调用，依赖真实钩子和后续guard识别unknown，不改写坐标或未知状态。普通Gateway/transport继续拒绝7/8。独立操作7仍只能第一次返回原home，原Commit失败保留。
- 新d168原生DLL已编译，ABI和Native Host未变。51组真实C++函数、7组通道、87项运行时Python、318项Host检查通过；重建前完整性检查曾正确拒绝旧manifest，失败另记未覆盖。[实现检查点](../reports/runtime-controlled-interference-implementation-20261027.json)。尚无新d168实机或普通授权，ef38两次675帧成功不转授新版本。
- 下一步在新的owned无模型试局执行一次受控Move，验证真实guard未知、独立停稳、操作7实际回到原位/归还及19入口清理。受控故障不能称为自然AI干扰。当前构建普通Host重复、180秒、其余G4及G5–G8仍未完成，总目标active。

## 最新整体进度（2026-10-27 09:40）

- `092544`第二次独立ef38试局也完整完成675帧任务：演员779，652帧Reserve、665帧Move、682–1357帧驻留、1387帧实际home、1392帧姿态恢复/归还，SDK`[1,1,4,2,1,1]`。21项独立完整校准及175份冻结复算通过，生产器实付85、19入口另读恢复后结束fixture。[第二次检查点](../reports/runtime-ef38-second675-no-recovery-checkpoint-20261027.json)。两次是独立游戏中的普通动作成功，不是同Host重复任务或180秒运行。
- 两次均无unknown、未触发操作7；保持`operation7_field_verified=false`及普通调用关闭。按原“两轮未触达即回G1/G2”阶段门，停止重复相同随机试局。下一步按[明确标记的原生干扰诊断合同](runtime-controlled-interference-contract-20261027.md)设计可控故障：独立操作/诊断位、SDK前持久化意图、真实外部Move和guard未知、再以新操作7实际回家。不能把受控注入称作自然AI行为，也不能用标记伪造任何状态或动作结果。
- 新注入入口尚未实现。当前ef38自己的675帧基本动作已有两次实机证据，新恢复只有47组C++/79项Python/318项Host等离线证据；普通Host接线、180秒、其余G4及G5–G8仍未完成。目标active，当前无活动测试游戏。

## 最新整体进度（2026-10-27 09:25）

- ef38已实现原生`ReconcileReturnHome=7`及单独的owned诊断入口：须对应实际接受的旧MoveHold、当前SDK Move1、home从未尝试、同一task/lease/actor、四帧独立静止；目标固定原私有home，不能续工作租约或带新Hold。新的Stop3和当前空位检查后，至多第一次home Move；已经在home则不移动。总恢复30秒，观察watchdog10秒和移动无进展90帧不变。原任务保持失败，新恢复的goal effect强制false。另建释放专用命令需要新的静止窗口，序号考虑已发布但被拒绝的尝试，旧未知报告不覆盖。[实现检查点](../reports/runtime-first-home-recovery-implementation-20261027.json)。
- SDK计数不包含NotSent，因此增加原生home尝试标记，IO前设置，连此前被拒绝的home尝试也不能通过操作7再派。47组C++、7组通道、79项运行时Python、318项Host检查通过；新操作在普通Gateway返回operation_unsupported，普通Native transport亦在访问映射前拒绝。共享ABI及Native Host未变。尚未增加普通Host/模型授权。
- `091806`显式诊断没有受到未知干扰，新操作7未触发；但当前新构建真实完成一次675帧任务：征召兵781，741帧Reserve、754帧Move、771–1446帧驻留、1473帧实际home、1478帧恢复姿态并归还，SDK`[1,1,4,2,1,1]`，仅两条原生命令。21项完整校准和175份冻结复算通过，875事件/2255钩子无丢失，生产器实付85、19入口独立核验恢复后结束测试局。[完整675帧检查点](../reports/runtime-ef38-complete675-task-checkpoint-20261027.json)。此报告可供当前构建原有Move/Hold/Return的独立核验，不证明新恢复操作或其300安全返回范围。
- 第二次独立恢复分支诊断已创建`092544`、游戏尚在菜单准备。若再次未触达新操作，将按原阶段门回到G1/G2复现设计，不反复复制相同试局。当前构建普通Host重复、新操作7实机接受、180秒接续及完整G4–G8仍保留；目标active。

## 最新整体进度（2026-10-27 09:03）

- `085009`为当前7fd0的三段实际Host通道、两次明确交接；两笔675帧任务均中断，没有完整长任务通过。第一笔704帧进入Hold，1130帧发生scope外source2的dispatcher opcode50及private Move（kind10→kind2，caller54b045→73b319），1131帧原Commit2保持unknown。四个新停止帧1226/1228/1230/1231的source2/state94、配对空槽和反向链接仅用于新ReconcileRelease3；新的Stop3后1248帧恢复姿态并归还，SDK`[1,1,3,1,1,1]`，physical_home=false。这是新source2释放前置的首次完整实机接受证明。
- 第二通道seed3，Reserve4/Commit5在1298帧开始Hold；1741帧来自己方806/hash`60f0b4e9`的让路请求，reader/普通策略拒绝（typed complete0、enabled0、ordinary eligibility0），1742帧保持unknown。不能把该来源称为Flak；参考目录将该hash映射为镰刀机甲，原生完整事实和权限仍分开。新source1静止帧后ReconcileRelease6于1777帧归还。原失败/uncertain行均保留；回放新释放不重复SDK。
- 第三通道seed6规划窗口无合格借用，明确`not_dispatched`并关闭，第四通道未接入。全局序号1–6连续；三个Native Host均exit0/state3/restore8191/callbacks0。生产器实付85、19入口独立另读恢复后结束fixture。[61项独立原字节/SQLite检查](../acceptance/runs/20261027-085009-runtime-calibration/two-recoveries-independent-review.json)及176份冻结复算一致，[检查点](../reports/runtime-source2-release-unsupported-yield-checkpoint-20261027.json)。总155.187秒，不授180秒、物理回家、完整任务、模型或自然结算信用。
- 当前释放恢复解决的是控制归还，仍缺受干扰后的实际撤回。下一步按[新回家意图合同](runtime-reconcile-return-home-contract-20261027.md)建立独立操作：仅在原home Move从未尝试且重新取得静止证明时，允许新意图第一次返回原home；已经尝试过的home Move不得用此方式重试。合同尚未实现、尚无普通授权，旧失败不改写。其余G4及G5–G8继续保留，目标active；当前无活动测试游戏。

## 最新整体进度（2026-10-27 08:49）

- 当前7fd0在`084604`已完成实际Host/Gateway/SQLite同一付费征召兵779的两笔短任务；730/810帧分别物理回家、恢复姿态并归还，原生序号1–4连续，SDK每笔`[1,1,4,2,1,1]`。47项独立原字节/账本检查与175份冻结复算一致，155事件/2522钩子无丢失；生产器实付85/正常关闭、19入口另读一致后结束测试局。[当前两笔Host任务检查点](../reports/runtime-7fd0-two-host-tasks-checkpoint-20261027.json)。无unknown或补偿恢复、没有模型/自然结算信用。
- 当前版本自己的flags0完整单次校准，以及真实103帧等空位后只发一次home Move、物理回家/归还的新增分支，已有21+9项独立检查及175/176份冻结复算，见下方08:48记录。下一步675帧驻留及显式通道接续；超过180秒完整任务、新source2恢复与完整G4–G8仍未完成，总目标active。当前无活动测试游戏。

## 最新整体进度（2026-10-27 08:48）

- 返程占用已形成一个实际进入的修复分支。旧`082707`的异步己方名单显示803在1479帧仍占位、1501帧已离开；原等空位分支却在1475帧先超时。这只证明等待上限可能过早，不证明延长等待必然使旧局成功，也不改变其原失败。[占用审计](../reports/runtime-long-hold-home-occupancy-audit-20261027.json)。
- 新7fd0只把“尚未发home Move的空位等待”与“已发Move的无进展”分开：发令前最多180帧，超过原90帧的额外部分必须仍在原工作租约内；原90帧有界到期安全返程路径保留。已发Move仍90帧无进展即未知，20空闲、15到达、原home、配对完整名单、三帧Stop3、身份/出借/仲裁和未知不重试均未放宽。39组C++、7组通道、73项运行时Python、317项Host检查通过，ABI和Native Host未变。[构建与回归](../reports/runtime-home-wait-budget-repair-20261027.json)。
- `084128`实机flags0付费征召兵779：666帧Reserve、679帧外出、700帧停稳，要求Hold15且实际16帧。722帧开始返程等待，724–815帧十组配对占用证据保持拒绝；821/823/825三次当前空闲/Stop3后，825帧SDK前同帧复核，只发一次home Move。831帧到达、840帧实际回家、845帧姿态恢复并归还，SDK `[1,1,4,2,1,1]`，只有Reserve/Commit两包，无unknown/recovery/重发。真实发令前等待103帧，跨过了旧90帧边界。
- [21项完整校准](../acceptance/runs/20261027-084128-runtime-calibration/calibration-independent-review.json)及175份冻结复算通过；另[9项新增等待边界复核](../acceptance/runs/20261027-084128-runtime-calibration/extended-wait-independent-review.json)及176份冻结复算一致。原200事件/1419钩子无丢失，生产器和19入口独立另读恢复后结束fixture。[当前7fd0校准检查点](../reports/runtime-7fd0-clean-extended-wait-checkpoint-20261027.json)。新普通Host试验只消费本报告SHA，不沿用dbd3权限。
- `084604`已启动当前7fd0的同Host连续两笔短任务实机复验，175份执行前来源冻结；结果待定。675帧长期任务完整返程、180秒持续任务、新source2恢复、实际客户端模型调度和完整G4–G8继续保留，总目标active。

## 最新整体进度（2026-10-27 08:35）

- G1/G2只读核对定位到`081335`四轮都有反复出现的原生端点，但合格source2/idle16出借候选始终为0；增加目标排序不能制造可借用单位。[旧记录状态对比](../reports/runtime-planning-readiness-audit-20261027.json)。未放宽原生借用条件。Python规划器现保留状态vtable/flags/姿态/path/grounded/team，超时返回专门的`PlanningUnavailable`；真实Host驱动只有在原生序号/命令数量未变、该task没有账本命令时，才能记为`not_dispatched`和持久化规划事件。序号或账本变化继续走原失败/未知路径。原生DLL和ABI未变，73项运行时Python与317项Host检查通过。
- `082707`实机经Host/Gateway/SQLite，Reserve1/Commit2实际完成702–1377帧的675帧驻留；但1385–1465帧九组配对证据显示己方803精确占着原home，系统没有发返程Move，1475帧原Commit保持uncertain。单独己方名单将相同ID/地址与Flak类型2c358c61关联；不把异步名单冒充每个原生拒绝帧的同帧类型读取，也未证明该Flak选择原home的因果。[占用审计](../reports/runtime-long-hold-home-occupancy-audit-20261027.json)。
- 新账本ReconcileRelease3在四个新source1静止帧后发出，1506帧恢复姿态并归还共同池，原失败票据/账本不改写、physical_home=false。一次明确交接后，新通道seed3的30秒规划窗口仍无可借用状态，275次端点可用观察、home_ready0；明确记录`not_dispatched`，序号前后均3、新命令均0。当前通道独立关闭，剩余两轮未接入；SQLite只有Reserve/Commit/新释放及一对退休/接入，未把未派发任务计为成功或制造更多通道。
- [39项原字节/SQLite独立复核](../acceptance/runs/20261027-082707-runtime-calibration/planning-release-independent-review-v2.json)与176份冻结复算一致；两个Native Host均exit0/state3/restore8191/callbacks0，生产器实付85/phase2/restore31/无活动回调或错误，19入口另读一致后结束测试局。[实机检查点](../reports/runtime-planning-refusal-live-checkpoint-20261027.json)。总实验133.593秒，不授完整任务返程、180秒运行、source2恢复或自然结算信用。该未派发分支目前接入可信校准Host驱动，还不能称为实际客户端模型调度已接线。
- 下一步处理长期驻留后原home被原生单位占用的返程合同和仲裁，不通过扩大到达半径、控制未授权邻居或把补偿释放当作回家绕过。新source2恢复、当前版本重复完整任务、完整G4及G5–G8仍待完成；目标active，当前无活动测试游戏。

## 最新整体进度（2026-10-27 08:23）

- 当前dbd3在`080924`完成干净flags0实机校准：实付85征召兵785，40单位移动、15帧驻留、物理回家和847帧姿态恢复/控制归还；21项独立检查及174份冻结复算一致。生产器和19入口另读恢复后结束测试局。[当前校准](../reports/runtime-dbd3-clean-calibration-checkpoint-20261027.json)。`075847`此前返程停在home外20单位，原任务失败保留；新显式释放命令seq3归还控制，15项检查及175份冻结复算一致。该次是source1停止状态，不证明新source2恢复分支。[限定恢复](../reports/runtime-dbd3-source1-recovery-checkpoint-20261027.json)。
- `081335`要求四轮675帧驻留/900帧租约，但实际没有派出任何战术命令。前三通道在30秒规划窗口内未取得合格空闲出借状态/端点组合；第四通道最终grounded=false，按`runtime_actor_observation_not_admissible`退出。四个原任务均保留失败，不能把驱动器的终态标签当作四任务通过。三次显式交接的全局序号仍为0，SQLite只有六条完成的通道生命周期意图，没有借用、移动、驻留或恢复命令。
- 35项独立原字节/SQLite检查及175份冻结复算一致，四个原生通道均state3/restore8191/callbacks0/Host exit0，明确no_control_acquired=true、control_released=false。原生产器总实付85且正常关闭，19处入口另读一致后结束owned测试进程。[零借用检查点](../reports/runtime-dbd3-unborrowed-four-channels-checkpoint-20261027.json)。没有自然结算、新恢复分支、当前版本Host任务重复或180秒长驻留完成信用。
- 已回到G1/G2排查候选状态与借用时机，避免继续盲目重复相同试局；不放宽source0拒绝、借用条件或物理回家半径。当前无活动测试游戏；新source2恢复实际接受、长驻留、桌面/生产/模型owner接续及完整G4–G8仍待完成，总目标active。

## 最新整体进度（2026-10-27 07:54）

- 6102原生版本已在`070313`完成干净flags0校准，21项原始字节检查和174份冻结复算一致；随后`070718`同局同一实付85征召兵780，经实际HostTactical/Gateway/SQLite完成两笔任务、驻留、物理回家和归还，47项检查及174份冻结复算通过，序号1–4连续。生产器和19入口独立确认恢复，测试局正常结束。[6102校准](../reports/runtime-6102-clean-calibration-checkpoint-20261027.json)、[两笔Host任务](../reports/runtime-6102-two-host-tasks-checkpoint-20261027.json)。
- 已实现明确选取新付费单位的封闭交接：下一付款命令UUID写入不可改写manifest；新原生准入后重算原始付款/出生、生产序号、receipt索引、累计支出和预算。真实Host续接入口可指定已完成的生产request；旧单位不能冒充新出生单位，旧任务/租约不继承。该新选择分支仍未完成实机验收。`072126`第一段任务关闭、90秒间隔完成后，第二笔生产因当时现金10、排队负债73及reserve1000而native9拒绝，需求现金1158；原始attempted0/paid0/created0已另读确认，没有接新通道。13项拒绝/清理复核通过，原uncertain意图保留，不算长运行。[资源拒绝](../reports/runtime-paid-successor-resource-refusal-checkpoint-20261027.json)。
- `073613`改为同一已付费单位、四段675帧驻留/900帧租约，以实际任务检验180秒接续。第一段在1130帧受到scope外source2移动干扰，原Commit2保持unknown，未完成675帧，恢复没有发令。649事件/3196钩子独立完整捕获，13项复核和175份冻结复算一致；四个稳定帧1149/1151/1152/1154证实随后进入source2的停止状态94、空命令槽及状态机反向链接，但不是本控制器Stop3。初步把kind2称作Stop的分类错误已单独保存更正：kind2是private_move，caller0x73b319；原始文件不改写。单位控制与13战术入口未归还，结束owned进程仅作明确失败隔离。[外部移动与恢复前置证据](../reports/runtime-foreign-move-stopped-recovery-checkpoint-20261027.json)。
- 当前dbd3构建仅把该source2停止状态加入新释放命令的静止准入，并对96字节命令槽作配对读取；本控制器Stop3/Ready/回家判断仍要求原有归属证明。新恢复不改原失败，不补造任务效果。C++36套、通道7套、Host317项、运行时Python69项通过；dbd3还需自己的flags0实机校准和实际归还复验，6102通过不授予它普通权限。
- 超过180秒持续任务、实际桌面/生产/模型owner接续、其余G4及完整G5–G8仍未完成；新付费单位的资源等待/分配也仍需完善。目标保持active，没有模型战术、自然结算或风格/贡献对照完成信用。

## 最新整体进度（2026-10-27 07:02）

- 新版本387f在`063829`完成一次干净flags0实机校准：实付85征召兵785，659帧稳定准入，40单位Move/Hold15/物理回家及846帧归还；21项独立检查和174份冻结复算一致，生产器、19入口和owned fixture清理均有独立证据。[校准检查点](../reports/runtime-387f-clean-calibration-checkpoint-20261027.json)。此前`063256`的报告替换PermissionError及程序失败完整保留；现在只对已fsync的同一报告字节做有上限的文件替换重试，不重发游戏命令。[报告发布修复](../reports/runtime-report-publication-repair-checkpoint-20261027.json)。
- `064138`第一笔实际任务完成并安全退休，90秒只读区间有真实游戏帧推进，新通道seed2接入成功。第二笔Reserve3在Borrow之后检测到私有scope之外的dispatch/attack，进入state5/held1；仅一次Borrow，未发Commit或恢复包。原始`source0 + idle16 + path0`不是可借用证明，既有恢复未取得合法静止窗口。独立捕获5事件/2767钩子无丢失，17项失败核对及175份冻结复算一致。生产器已清理，但13战术钩子和控制仍未归还；结束owned游戏仅作明确失败隔离，没有用强杀补造释放。总184.719秒不构成长时间运行通过。[原始失败与修复检查点](../reports/runtime-foreign-borrow-lender-checkpoint-20261027.json)。
- 当前6102原生版本在Reserve前及实际Borrow前增加配对source2/idle16、空命令槽、状态机反向链接等出借检查；规划层也等待三帧合格空闲。明确Borrow未发送且单位仍在有效非script队伍时，只关闭没有转移控制的逻辑租约；未知投递仍保留。C++36套、通道7套、运行时Python65项、Host311项通过。6102仍需新flags0校准和真实Host重复；387f/0c4d历史通过不授予新DLL普通权限。
- 真实桌面Host续接API及活跃supervisor核对已有离线实现，仍需客户端实机验证。其余G4自卫/非法改派处置、命中撤回、双兵、视野/停止/死亡，以及G5–G8完整配置/模型任务、三类战术、自然结算、风格和贡献对照仍未完成，完整目标保持active。

## 最新整体进度（2026-10-27 06:00）

- **同局/同一付费单位的三段普通原生通道、两次显式交接、三个真实任务已通过54项独立复核。** `055029`、同一owned游戏11288、同一原生产器及实付85征召兵781，普通flags0/current0c4d不改原生DLL/Host/ABI/容量；三个独立host绑定对应原生seed0/2/4，全局Reserve/Commit序号1–6连续，与同一SQLite通道high-water一致，没有重置命令序号或重编号旧事件。
- 三笔分别817/907/1112帧实际完成Hold15、物理回家、姿态恢复/共同池归还，SDK各`[1,1,4,2,1,1]`。每段当前地形端点、三帧Stop3、全量配对home空闲证据及真正移动/驻留/返程均逐段重算；原事件78/77/90、原钩子1272/1274/1351无丢失，无让路/foreign/attack/unknown分支。首个稳定付费来源观测为644/827/918帧，是新绑定内重新准入的宿主观测incarnation，**不是宣称单位重复出生或跨绑定静默重置同一身份注册表**。
- 新`runtime_rotation`只在旧owner控制已归还、账本无未决、Native Host退出且13战术入口原字节恢复、原始通道完整独立捕获后，持久化一次retire意图/不可改写证据与新的host绑定。新client需原scope及原生再准入，携带全局high-water；attach意图先持久化，未知不重试，旧task/lease不能在新owner重用。本轮两个retire及两个attach均在真实SQLite完成。初次启动仍原scope；新绑定不授战斗。
- [54项独立复核](../acceptance/runs/20261027-055029-runtime-calibration/rotation-independent-review.json)、171份发令前冻结来源、73份早期实际执行归档及172份含reviewer的另起Python复算一致。原生三个Host均exit0/state3/restore8191/callbacks0；生产器最终phase2/restore31/active0/error0/总实付85，19入口独立另读一致，05:59结束owned fixture。301项完整host runtime和59项运行时Python通过。[当前检查点](../reports/runtime-three-native-epoch-handoffs-checkpoint-20261027.json)。
- **总实验76.688秒，仍未证明超过180秒的持续运行或完整客户端生命周期接线。** 下一步长于单段Native Host寿命的真实游戏持续任务，以及与实际客户端/生产/模型owner的交接整合。其余G4、自卫/攻击撤回/双兵/死亡/人类停止和全部G5–G8仍保留，未取得完整模型自然结算与风格/贡献对照信用，goal active。

## 最新整体进度（2026-10-27 05:34）

- **真实Host/Gateway/SQLite的新恢复分支已通过42项独立复核；原第三笔失败保留。** 显式三租约预算实验`052232`中，同一实付85征召兵781前两笔分别827/1206帧完成实际Hold/回家/归还；第三笔1252帧外出、1267–1282帧Hold15完成，1289帧开始返程准备。固定2800行home证明预算在1292帧不足，原生九次明确预算拒绝，只留下2585证明行，没有发出第三笔home Move，也没有丢失原始流。1380帧原Commit seq6保留`return_home_clearance_timeout_no_move`。
- 同一Host从1385/1386/1388/1390四个新静止帧准备恢复；原生kind16/17独立原字节证明空命令槽、状态机反向引用、Stop94/c551a0/path0/stance2和同一己方演员。新的ReconcileRelease由同一Gateway/SQLite分配seq7，1395帧接受、1396帧新Stop3、1406帧实际共同池/原姿态归还。恢复receipt `mission_effect_verified=false`、physical_home=false，未将原native文字`native_control_release_observed`误计成回家或任务成功。
- 原第6笔uncertain行、回执和事件完全不改写；新release明确引用原command，纯只读重开SQLite的未决控制投影为0。重复恢复请求没有新ticket/调用；原411事件、3377钩子无丢失。发令前168份来源/制品、早期71份执行归档逐项吻合；加独立reviewer后169份冻结另起Python复算42项完全一致。[42项复核](../acceptance/runs/20261027-052232-runtime-calibration/journaled-recovery-with-provenance-independent-review.json)。native state3/restore8191/callbacks0/Host0、生产器phase2/restore31/active0/error0、19原入口独立一致后05:30结束owned fixture，无模型或自然结算信用。
- 当前普通两租约`051733`的47项完整成功另行保留；host runtime 293项、运行时Python58项通过，0c4d原生DLL/Host/容量/ABI未改。下一步从“耗尽后安全恢复”推进到**预算/180秒寿命之前的安全通道生命周期**。静态确认原生bootstrap允许旧runtime完全关闭后接新token，也拒绝置换未知未恢复的旧owner；Python当前persisted_sequence固定0及incarnation绑定寿命必须显式审计，不能默默重置计数/演员身份。见[生命周期前置审计](../reports/runtime-channel-lifecycle-audit-20261027.json)。其余G4及全部G5–G8客户端、模型、战术、整局自然结算与贡献对照仍是总目标必做。[恢复检查点](../reports/runtime-journaled-recovery-budget-checkpoint-20261027.json)，goal active。

## 最新整体进度（2026-10-27 05:24）

- **当前0c4d普通flags0真实Host连续两笔任务通过47项独立验收。** `051733`同一实付85征召兵781/generation1，两笔独立task/lease、原始Reserve/Commit序号1–4和SQLite一致，分别815/933帧归还。第一次home `[1770,1850,210]`、目标 `[1770,1890,210]`，第二次重新读取原生home `[1770,1860.000122,210]`、目标 `[1770,1830,210]`；均实际Hold15、物理回家、姿态恢复和共同池归还。原189事件/2590钩子无丢失，无未知/让路/攻击分支；重复请求未增加序号或原生调用。当前045007校准SHA被精确消费，无旧DLL scope。
- [47项独立复核](../acceptance/runs/20261027-051733-runtime-calibration/two-task-independent-review.json)、168份发令前冻结源码/制品及另起Python复算一致。native state3/restore8191/callbacks0/Host0、生产器phase2/restore31/active0/error0/实付85和19处原入口独立读取一致后05:21结束owned fixture。此项不授战斗或自然结算信用。
- **可信Host恢复代码已接入，但本轮没有触发该分支。** 只有匹配同任务/lease/generation、原生当前uncertain及原账本unknown的来源可进入；四个新静止帧后由同一Host/Gateway/SQLite分配新ReconcileRelease序号。归还只关闭未决控制的投影，原命令uncertain状态与旧回执/事件不改写；恢复本身永不计mission effect，未知投递不重试。293项完整host runtime、57项运行时Python通过。随后新增明确CLI三租约预算实验门，运行时Python58项通过；所有原生代码/容量/ABI不变。
- `052232`已启动显式最多三笔真实任务的固定home证明预算边界实验：不伪造占用/结果，不增大缓冲或重发Move；若出现真实unknown，以新可信Host恢复命令核对原生与账本。实验不能替代长局安全通道切换、180秒Host生命周期、其余G4及全部G5–G8自然对局/贡献对照。[当前两租约检查点](../reports/runtime-current-host-repeat-recovery-code-checkpoint-20261027.json)，完整目标active。

## 最新整体进度（2026-10-27 05:10）

- **普通flags0精确Flak来源接线首次实机通过；完整返程和当前Host两租约仍未通过。** `050535`、当前0c4d、实付85征召兵781，在原生Flak789的`694a00→6939aa/opcode48/source2`真实请求828帧后，829帧state26确认，上界125ms；trace21策略字`[0,1,1]`及bootstrap flags0证明未借诊断flags1放行。772帧开始的300帧Hold被合法中止，不计任务效果。没有攻击/foreign epoch或原始流丢失。见[29项限定独立复核](../acceptance/runs/20261027-050535-runtime-calibration/ordinary-yield-source-independent-review.json)。
- 此次home `[1790,1870,210]`返程前持续存在占用；915/917两帧完整配对空闲之后，918又占用，未满足三帧门，因此始终没有home Move。925帧保留90帧返程准入超时；新静止帧后独立ReconcileRelease seq3在947帧恢复姿态/归还控制，physical_home=false，SDK `[1,1,4,1,1,1]`。本轮只证明普通精确来源/中止与失败后的安全归还，不证明完整让路回家。231事件/927钩子原样保留。
- 168份来源/制品（含本轮独立reviewer）冻结、SHA逐项核对、另起Python复算29项与原结果完全一致。native state3/restore8191/callbacks0/Host0、生产器phase2/restore31/active0/error0/实付85、19入口独立读取一致，05:09结束owned fixture，无自然结算信用。
- `045654`真实Host第一笔任务返程曾在发令后出现战熊占用并停滞，21项失败/归还复核与167份冻结复算保留；原SQLite uncertain与持有记录不能用外部清理摘要覆盖。下一步审计持久化可信恢复和动态home占用处理，再验当前Host两笔成功租约；有限通道/180秒Host生命周期、全部剩余G4–G8仍是完整目标必做，不能由单次成功或来源通过替代。[当前检查点](../reports/runtime-ordinary-yield-source-and-return-failures-20261027.json)，goal active。

## 最新整体进度（2026-10-27 05:05）

- **当前普通策略构建的Host连续任务复测失败，安全归还独立核验通过；不能记两租约通过。** `045654` 用045007当前flags0完整校准的精确SHA授单兵移动scope，真实HostTactical/SQLite借入实付85征召兵781。Reserve677、Move690、Hold707–722完成；730/732/733及SDK前733四份当前配对完整home空闲证明均独立通过，只发一次home Move733。原137事件/1397钩子无丢失，无让路或攻击分支。
- 返回时746帧只读同帧己方环境显示原生战熊787占到home附近0.85；演员停在home外19.55481，833帧保留`return_stalled_control_release_unknown`。这是初始空闲之后的动态占用相关证据，尚未证明唯一碰撞因果，不能把准入瞬时空闲当作整条返程保留。新ReconcileRelease seq3在新静止观测后854帧归还控制与姿态，无Move重试；physical_home=false，原账本commit uncertain及reserve held记录不改写，不执行第二笔任务。
- [21项失败/安全归还限定独立复核](../acceptance/runs/20261027-045654-runtime-calibration/failed-return-release-independent-review.json)及167份冻结源码单独复算一致。native state3/restore8191/callbacks0/Host0、生产器phase2/restore31/active0/error0/实付85、19原入口另读一致后05:05结束owned fixture，无自然结算。接下来继续普通flags0真实Flak让路接线及动态home/宿主恢复审计，完整G0–G8保持active。

## 最新整体进度（2026-10-27 04:56）

- **新普通策略构建的flags0完整单兵校准已通过，普通让路的现场分支及当前Host重复任务仍待验收。** 基于043207的34项完整来源/返程证据，代码只把己方Flak hash2c358c61、outer694a00/source2加入普通策略资格；6939aa/opcode48完整参数、typed配对身份、Owned Stop3、state26两帧/250ms确认和原返程门继续独立检查。其他来源类型/外层调用点仍诊断限定，资格不等于接受，原生调用始终只转发一次；诊断flags1仍不能授普通scope。见[普通策略审计](../reports/native-yield-ordinary-admission-contract-20261027.json)。
- 当前DLL `0c4d4a8e78ae6961e045ab560d29ed3dd2d4781ad4cf503519657e92eeeeddd5`，ABI和原生Host不变；trace21的18/19/20字记录诊断标记、精确普通来源资格和schema1。33组实际C++（含来源/调用点/待确认/身份/状态拒绝）、7组通道、57项运行时Python、286项完整host runtime检查通过。尚未自动登记普通scope或扩大到自卫/攻击。
- `045007` 实付85的征召兵779/generation1，762帧Reserve、775帧Move，791帧实际停稳，807帧完成15帧Hold。实际外出约33.33252，833帧距home约6.66650，838帧恢复姿态并归还；SDK `[1,1,4,2,1,1]`。78原事件/1287钩子无丢失，本轮没有让路分支。[21项独立完整校准](../acceptance/runs/20261027-045007-runtime-calibration/calibration-independent-review.json)及167份冻结来源复算均通过，生产器和19处原入口另读一致后结束owned fixture，无自然结算信用。原始native报告SHA `7ab4e6f63ce9a9a60608c7627db73d01bf138a75c46b6ce5c5f7504e008d2b86` 将作为当前Host重复任务唯一消费来源，未沿用d987/424构建记录。
- 下一步真实HostTactical/SQLite连续两次租约和flags0自然Flak让路分支。完整G4其余自卫/非法改派/攻击撤回/双兵/异常、G5–G8继续保留；有限诊断通道的180秒寿命及事件/证明预算仍需在长局接线中核验，不能从两次短租约推断整局宿主持久能力。完整目标active。

## 最新整体进度（2026-10-27 04:43）

- **当前d987已首次实机通过“真实让路确认→中止目标→等待当前home空闲→实际回家→姿态恢复/控制归还”分项；完整G4及总目标仍未完成。** `043207`、flags1、实付85的征召兵781，home `[1770,1850,210]`、当前原生准入且历史出现过的目标 `[1770,1810,210]`。760帧外出，777帧停稳；828帧收到原生Flak790的 `694a00→6939aa/opcode48/source2`，同帧state26确认，确认上界110ms。此时实际距home约33.33374。300帧Hold未完成，目标效果中止且不计成功任务。
- 833帧新Stop3后进入Returning。835–906帧八次实际配对阻挡记录保持拒绝，909/911/913帧三次当前完整空闲/Stop3证明后，913帧SDK前再次配对检查，只发一次home Move。没有放宽原90帧限额、20中心空闲或15到达半径。928帧实际停在 `[1770,1843.333251953125,210]`，距home约6.66675；932帧原生共同池归还并恢复姿态，SDK `[1,1,4,2,1,1]`。只有Reserve1/Commit2，没有reconcile或Move重试。四份完整空闲证明以kind32/33/34独立复算全球791个节点闭合与己方过滤；原212事件/1456钩子无溢出、epoch全0、无攻击。
- [34项独立复核](../acceptance/runs/20261027-043207-runtime-calibration/yield-home-release-independent-review.json)全部通过，涵盖原始来源票据、typed存活己方邻居、state26新鲜确认、真正外出、原生地形端点、占用等待和三帧空闲、四次真实Stop3、物理回家、原生归还和19入口。邻居只作为来源，不授地面/目标权限。额外Flak付款为0，总实付85、生产器phase2/restore31/active0/error0。原生state3/restore8191/callbacks0/Host exit0、19处原入口一致；167份源码/制品冻结，另起Python使用冻结模块和原保存入口字节重算34项一致，未伪造新现场读取。04:42按PID/start/path结束owned fixture，无自然结算信用。
- 此证据是**显式flags1诊断分项**，没有登记普通scope，也不能替代当前flags0完整校准、真实Host连续任务、自卫、命中/撤回、双兵和异常场景。下一步审计如何仅将这个已证明的Flak原生来源链接入普通仲裁；任何新DLL均重新校准并复测Host账本，不沿用d987或424构建权限。G5客户端运行中停止/导出、G6完整战术与宏观缺口、G7真实模型完整对局及G8风格/贡献对照继续全范围待办。当前无游戏/native Host活动；[成功分项检查点](../reports/runtime-native-yield-home-success-checkpoint-20261027.json)，总目标active。

## 最新整体进度（2026-10-27 04:35）

- **d987的占用拒绝/安全归还已实机进入，完整物理返程和当前Host连续任务仍未通过。** `040234` 的完整原183事件/283钩子无丢失；711–793帧九次配对读取同一个己方阻挡781。没有home Move，800帧保留占用等待超时；新显式恢复820帧恢复姿态并归还，physical_home=false、SDK `[1,1,4,1,1,1]`。生产器、19处入口独立核验通过后结束fixture。[16项限定复核](../acceptance/runs/20261027-040234-runtime-calibration/occupied-home-denial-release-independent-review.json)仅证明占用拒绝及归还，不授完整校准。到期恢复修复的离线回归已过，但此现场恢复未晚于旧期限，不能称为该晚期分支已实机通过。
- `040921` 尝试从大厅分配电脑起点，没有取得可核验的位置分配设置。未开始比赛、未发控制命令，读取19处原入口后结束菜单fixture；positions_controlled保持false。没有把后续随机位置试局说成固定起点实验，也未继续按相同拥堵home重复派单。
- 已回到G1核对原队伍：固定游戏 `838820→7ae280→79dfd0→78dbb0→839f10→829230` 删除Team ID列表中的演员，82925f..829278将后续ID前移并置dirty；8311b0按顺序追加ID。Team+10指向列表，+8/+c为begin/end，成员是Thing+dc的ID。见[静态合同](../reports/native-home-team-repacking-20261027/static-contract.json)与[追加接口](../reports/native-home-team-repacking-20261027/static-append-contract.json)。**列表序号等于实际站位、原占用由这次前移导致，均未证明。**
- 新只读 `team_roster.py` 配对完整全球Thing相关字段及原Team ID向量，校验完整成员/归属/帧/演员绑定；记录失败不影响原生安全停止。`042319` 只Reserve征召兵779、Ready观察30帧、无Commit/无SDK Move；587帧原队伍 `[775,777,779]`（演员在末尾），589帧实际Reserve同队，591/601/621帧源队伍为 `[775,777]`，没有其他成员前移。六份实际名单已独立复算，三次身份或跨读变化拒绝保留。这不能将“末尾成员”变成未来home空闲授权。
- 本轮在641帧发生原生Bear781的 `694a00→6939aa/opcode48/source2` 请求，普通flags0按合同拒绝，642帧epoch1/unknown；cleanup期间只发一次新reconcile seq2，834帧归还，SDK `[1,1,3,0,1,1]`、physical_home=false。原79事件/604钩子完整，生产器及19入口独立核验后结束fixture。[15项限定复核](../acceptance/runs/20261027-042319-runtime-calibration/team-order-denial-release-independent-review.json)保存普通模式拒绝事实，**不授让路确认或物理回家**。167份源码/制品冻结。运行时Python现57项通过。
- 原生d987未改。`043207` 正在进行显式flags1的原生历史单元拦截/让路专项，并记录源Team上下文；根据042319实际来源改用自然邻居，不再额外付款买并非请求来源的Flak。端点仍只能来自当前原生准入且该演员历史实际出现过的单元，原地形/home/到达/租约/未知不重试门不变。此专项结果尚未验收。完整G0–G8 active，G4其他分项及G5–G8全部保留。见[队伍和来源检查点](../reports/runtime-team-order-yield-source-checkpoint-20261027.json)。

## 最新整体进度（2026-10-27 04:03）

- **034841为明确失败，未归还控制；新修复构建正在重新校准，总目标未完成。** 窗口工具重启并激活后恢复，bd3a版实机进入付费征召兵779的外出/Hold，但return扫描只看512项，全局名单前缀没有受控演员，800帧保留 `return_home_clearance_timeout_no_move`。重复保存不完整前缀导致轨迹溢出；58275条中54179条已覆盖。原事件283条完整，不能用保留尾部冒充完整轨迹或无非法命令证明。
- 新显式ReconcileRelease seq3在3104帧获原生接受，但原租约1401已到期，同一帧旧期限分支把恢复Stance覆盖为ReturnBraking，3200帧再次超时。SDK `[1,1,4,1,0,0]`，held1/control0/physical_home0，Host输出safe_terminal=false；19原入口只有6处恢复，13处战术入口未恢复。保存配对原始header、保留原票据及独立入口字节后03:56按PID/start/path结束owned fixture，**这是失败隔离，不能称为安全归还**。[11项冻结原事件复核](../acceptance/runs/20261027-034841-runtime-calibration/frozen-event-failure-review.json)只证明这些失败事实。稍后的独立完整名单为790项、演员第751项，与原票据的512项/actor matches0截断一致；不把晚读当成原帧的精确名单。
- 现已将完整扫描上限恢复为原20000，证明v2以kind33每行存三个全局pointer/next/owner配对，kind34保存所有己方身份/位置配对，保留全局链闭合和己方过滤的独立复算。清空证明每组最多640行、每binding最多2800行；预算不足时拒绝Move。占用拒绝只保留头和实际阻挡对象，无完整空闲信用；重复拒绝每10帧留证，检查仍每帧执行。原4096容量、15到达半径、20空闲距离、90帧限额和未知不重试均未改变。
- 到期逻辑现排除显式紧急/恢复释放，避免再发返程。33组实际C++、7组通道、47项运行时Python和286项完整host runtime测试通过。新增751个对象的真实C++ MemoryIO样本以253行闭合，独立Python复核通过；日志预算耗尽会拒绝SDK，迟于旧租约的恢复回归无Move并归还。**这些仍是离线证据**，当前DLL `d987e2d91f6de9455a17d0d995f10fb581d77c158a204da1511f35d9db1eb372` 必须重新做实机单次、Host连续任务和让路专项；旧版scope不授权它。见[修复检查点](../reports/runtime-home-clearance-v2-checkpoint-20261027.json)。`040234` 新fixture正在准备。

## 最新整体进度（2026-10-27 03:47）

- 新home实时占用门的源码/构建/离线检查已完成，**实机复测未完成**。`034300` 游戏PID30460启动且Responding=true，但Computer Use在重新选择唯一游戏窗口后仍返回 `foreground window did not report a process id`，既不能读取画面也不能激活窗口。按工具恢复规范停止UI输入，没有操作旧坐标，也没有派发任何原生控制命令。没有把这个工具故障算成战术失败复现或成功校准。
- 在大厅尚未确认、native Host未启动、0条控制命令的状态下，另读19处原入口一致，按PID/start/path核对后于03:45结束owned菜单fixture。[原始清理记录](../acceptance/runs/20261027-034300-runtime-calibration/fixture-end.json)保留 `actor_control_acquired=false`，不声称控制归还或物理回家。当前无活动游戏/Host，新版本没有获得普通执行scope。
- 原032313失败/安全归还证据在另起Python进程中使用162份冻结源码/制品重算23项全部一致。[冻结复算](../acceptance/runs/20261027-032313-runtime-calibration/frozen-review-recalculation.json)只使用先前保存的独立入口读取字节，未重读已结束的游戏、未伪造新现场样本。让路后完整回家仍未通过，下一次实机需先恢复可读取的窗口，再重新做新构建校准与Host连续任务。

## 最新整体进度（2026-10-27 03:43）

- **真实原生让路再次进入分支，显式恢复已安全交还控制；物理回家仍失败，完整G4及G0–G8未完成。** `032313` 使用原424构建，实付85的征召兵781在828帧收到Flak789的原生请求，830帧确认（上界234ms），中止目标并返程。836帧只发一次home Move，931帧因返程停滞保留unknown，最近距home为20，未达到原15到达半径。新的显式ReconcileRelease seq3在四个新静止帧之后执行，952帧恢复姿态并交还控制，SDK `[1,1,4,2,1,1]`。原失败不覆盖，[23项独立限定复核](../acceptance/runs/20261027-032313-runtime-calibration/yield-source-failed-home-safe-release-independent-review.json)只授来源/中止/安全归还，不授物理回家或完整让路成功。
- 原始同帧己方名单显示：发出home Move前一帧835，战熊787恰在home `[2890,2910,210]`；之后840–900帧仍占据原点。实际路径阻挡回调的唯一因果尚未追踪，故只记录占用事实及停滞，不把相关性说成唯一根因。额外实付220的Flak792到928帧才出生，晚于828帧让路；真正请求来源是原生Flak789，不能把新付费单位记成触发者。原生state3/restore8191/callbacks0/Host exit0、生产器phase2/restore31/active0/error0和19处入口独立核验通过后，03:30按PID/start/path结束owned fixture，无自然结算信用。
- `030921` 旧轨迹距离规划器拒绝，只有Reserve、无Commit、14项取消限定复核通过；旧helper源码缺原始归档，保留这个缺口。现规划器只选择当前原生准入且在该演员历史中**实际出现过的原生单元**中的点，离线重建不是旧源码精确重放或实机成功。`031648` 没有满足home窗口，0条控制命令、11项清理复核通过；不能记借兵或物理返程成功。后续诊断归档已补齐helper及路径/生产依赖的来源和SHA。
- 搜索节点静态链补全为query+70上下文经69c4e0/69bbf0/69bfcc设置+2c，与query+9c别名，由6aab12写入搜索节点+14 bit0，再由69a358传播到path+1f。见[固定字节调查](../reports/native-yield-path-context-20261027/search_node_object_context_chain-v2.json)。这不是路径点Z字段，没有增加查询调用/路径修改权限。
- 修改前冻结162份源码/制品及原始失败证据，见[检查点](../reports/runtime-yield-home-safe-release-checkpoint-20261027.json)。现在补上**返程前当前home占用门**：新配对完整名单、连续三帧Stop3与空闲、SDK前再查，限额后保留unknown且不重试Move。新增kind32/33原字节可独立重算名单闭合、成对相等、占用与三帧门；重复同一阻挡只每10帧保存完整名单，实际检查仍每帧执行。32组实际C++、7组通道、47项运行时Python及285项host runtime测试通过。新DLL `bd3a63f37d8380ef6b2d0cd30c18a2ccf7d936561dd2a2d5c55410ae40ece076` **尚未实机通过**，旧424校准/连续租约scope不能授给它；`034300` 新校准fixture正在准备。
- 总目标保持active。当前重点是新版本单兵校准、连续Host任务及让路后实际回家/归还；自卫、攻击撤回、双兵、异常场景、G5客户端运行中停止/导出、G6完整战术与宏观缺口、G7真实模型整局和G8贡献对照仍全部保留。

## 最新整体进度（2026-10-27 02:55）

- **新增原生路径节点读取并取得实机原始样本；完整让路返程仍未通过。** 原生424构建和既有控制门未改；023122两租约44项成功继续保留，不外推完整G4或总目标。G1路径调查已确认静态调用链 `70cdba→6a05f0→696570→694930→693960`：沿原生路径节点扫描单元及可让路对象，并非按最近邻居距离触发。已有[固定游戏字节与反汇编合同](../reports/native-yield-path-context-20261027/static-contract-review.json)，当前没有查询/路径修改权限。
- 新只读 `tactical/terrain/native_path.py` 在完整己方名单和同帧配对原字节下读取演员、PathfinderPath/vtablec18cd4/secondaryc18cc4、typed params及实际LocomotorSet mask1、完整有界节点链。构造函数明确初始化到+48，路径对象只读76字节，未沿用历史a0越界研究跨度。节点next+8、xyz+c、layer+18，最多64个；未绑定的初始化params/objectID0、变化读、链环、错误身份等均拒绝。只读研究不授Borrow、路线、目标或让路来源信用。运行时Python41项、terrain/path21项通过。
- `024440` 只Reserve征召兵779/generation1，原地Ready后通过同一原生产器提交一次额外Flak请求seq2/budget220；总预算305、reserve1000、间隔150保持不变。Flak790实付220，856帧出厂，未借它或给它下控制命令；真实原生队列及付款两条回执保留，总实付305。征召兵未Commit、全程位移0；限额后1003帧取消归还。原始400条事件/485条hook，kind18..25全部缺席，原 `failed_or_unknown/reserved_yield_not_observed_no_commit` 保留。[19项限定复核](../acceptance/runs/20261027-024440-runtime-calibration/paid-neighbor-no-yield-independent-review.json)通过，只证明付款、原地取消与清理，不构成让路成功。生产器phase2/restore31/active0/error0、19入口另读一致后结束owned fixture，无自然结算信用。
- 取得一条960帧Flak790的真实typed路径：两节点 `[1790,1830,210]→[1810,1830,210]`，与演员所在中心单元 `[89,92]` 相邻（路径节点为 `[89,91]、[90,91]`）。[4项独立原字节复核](../acceptance/runs/20261027-024440-runtime-calibration/path-snapshot-independent-review.json)通过；该**单个样本**的模板/Thing/path+1f外层扫描前置开关为false，不能外推单位整个生命周期都未进入扫描。另有5次未绑定params、17次无可用路径指针的拒绝，原样保留。执行器终态后追加8秒纯只读战熊比较为0条有效路径，保留8次无路径和1次mask未验证拒绝，不能声称战熊路径合同已通过。
- 范围 `690000..6a2000` 的[静态标记写入调查](../reports/native-yield-path-context-20261027/path_flag_writer_review.json)找到69a358在搜索节点EBP+14 bit0非零时设置path+1f；此处是搜索节点字段，不是路径点Z字段。该bit语义及全映像其他写入者仍未验证。下一步继续核对搜索节点/阻挡关系和真实路径单元，形成合法空地上的拦截准备条件后再安排下一次来源专项，不重复相同“出厂即会让路”假设。
- 当前无活动游戏/native Host，完整G0–G8保持active；让路/自卫/攻击撤回/双兵/异常与G5–G8全部原范围待办保持不变。见[原生路径触发调查检查点](../reports/runtime-native-yield-path-checkpoint-20261027.json)。

## 最新整体进度（2026-10-27 02:35）

- **当前424构建的真实HostTactical/SQLite连续两次租约已实机通过，完整G4及G0–G8仍未完成。** `023122` 显式核验并消费 `020337/calibration-native.json` 的SHA `b5f3d2b90dd53136598a19a136f55bfdae3189e3008b47b89b0949f1edfc2363`，没有沿用801旧构建scope。仅限付费征召兵Move/Hold/物理回家/原生归还；没有扩大到攻击或客户端正式整局。当前DLL仍为424，原生源码/门限未修改。
- 同一个实付85的object780/generation1，通过真实HostTactical和权威账本依次派出Reserve1/Commit2、Reserve3/Commit4，两个不同task/lease。第一项738帧归还，第二项818帧归还；实际外出约33.33374、26.66699，Hold各15帧，最后距各自home约6.66675、3.33337。每项SDK `[1,1,4,2,1,1]`，重复提交后的原生命令数分别保持2和4。150条原始事件、303条hook，模型0/攻击0/未决账本0。[44项独立复核](../acceptance/runs/20261027-023122-runtime-calibration/two-task-independent-review.json)全部通过，另读生产器phase2/restore31/active0/error0、19处原入口一致。153份审查源码/制品已冻结，另起Python进程使用冻结模块/制品复算44项仍通过；安全清理后结束owned fixture。
- 前一次 `022450` 第一项实机完成，但第二次在借兵前由 `preborrow_actor_identity_or_owner_changed` 拒绝；原失败保留。15项限定复核只确认第一项效果/回家/归还，实际SQLite仅Reserve completed/Commit released和序号1/2；未发第二次Reserve。DLL确实在controller.tick之前发布ambient observation，归还事件可能先于下一帧普通样本。已增加“归还后必须等到更新帧，再重新满足原严格home窗口”的规划等待，同时保存具体拒绝字段；38项运行时Python检查通过。**023122没有进入新增等待分支，不能声称实机复现并解决了022450的唯一根因。** 022450后期读取时单位地址已失效/复用，该晚读不能替代742帧失败当时的证明。
- 原生让路专项仍未覆盖：`022043` 只Reserve、原地Ready等待，753帧起点，首次观察到限额为1054帧（301帧跨度，阈值300），未Commit、全程位移0，1077帧取消归还。405条原始事件/490条hook；14项[限定取消复核](../acceptance/runs/20261027-022043-runtime-calibration/stationary-cancel-no-yield-independent-review.json)通过，19处入口与生产器清理通过。原 `failed_or_unknown/reserved_yield_not_observed_no_commit` 保留；不授让路或外出信用。与020901连续两次未进入分支后，停止同条件重复试局。
- [轨迹复算](../reports/runtime-yield-neighbor-context-20261027.json)发现020901等待时战熊曾近至12.28，022043曾近至15.42，故“没有邻居靠近”不能解释未触发；先前“离开出兵通道”的猜测不足以定因。更关键的[历史真实来源票据](../reports/runtime-yield-positive-trigger-context-20261027.json)表明235143的真正请求方是有原生移动路径的Bear781，641帧距演员约85.84，而非当时最近的Bear777。下一步查原生路径/单元碰撞请求上下文，不以邻居距离或普通300帧等待冒充让路触发。
- 当前无活动游戏/native Host。完整待办仍为让路中止后实际回家/归还、自卫来源/非法命令、近场命中与撤回、双兵/可见性/死亡/人工停止；G5运行中客户端停止和结构化导出、G6主攻/经济骚扰/兵种协同及宏观缺口、G7完整客户端真实模型整局自然结算、G8风格与模型贡献对照继续保持未完成。见[当前连续租约检查点](../reports/runtime-current-host-repeat-checkpoint-20261027.json)。

## 最新整体进度（2026-10-27 02:17）

- **新版原生空地端点已经接入，限定单征召兵 Move/Hold/物理回家/控制归还实机通过；完整G4和G0–G8总目标仍未完成。** 当前DLL SHA `42437307c0c490d7241438016d614a12d05eb9c2871fad9b14db104b11e362dc`，Host SHA `f51274654b9812a91d73e1b327d08bc5e834a319601537fd34a1a5d0d27f68c7`。`land_geometry.h` 在游戏线程配对读取真实LocomotorSet mask、width1脚印、原生heightmap顶点和pathgrid空单元；准入票据29/30/31可独立重算。身份/实付/脚下cache/静止home/Stop3/占用/租约门保持原限制。旧版本scope不能授给当前构建。
- `020337` 实付85创建object780/generation1，目标与home间距40，实际外出约33.33；15帧Hold后返回，最终距home约6.67，742帧原生归还。75条事件、152条hook、3组原始空地证明，SDK `[1,1,4,2,1,1]`，模型0。当前源码[20项独立验收](../acceptance/runs/20261027-020337-runtime-calibration/calibration-independent-review.json)全部通过；另读生产器phase2/restore31/active0/error0及19处入口原始字节一致。153份审查源码/制品已冻结，另起Python进程使用冻结模块/制品复算20项仍通过。没有登记新普通scope，历史记录不改写。
- `020901` 为同构建flags1的原生让路专项：680帧Ready、698帧开始Hold、998帧正常持有300帧结束、1026帧归还，SDK同上。**本轮没有原生让路来源或state26分支，不能算让路成功。** 原始通道420条事件/544条hook、0丢失，kind18..25全部缺席。13项[限定正常返程复核](../acceptance/runs/20261027-020901-runtime-calibration/normal-return-no-yield-independent-review.json)通过；完整FILE_MAP_READ通道、生产器原始header及19处原入口另读已保存。安全清理后按PID/start/path核验结束owned fixture；无自然结算信用。旧235143让路后未回家/未恢复控制的失败仍保留。
- 当前无活动游戏/native Host；持续目标保持active。下一步核对让路触发所需的原生邻居/路径情境，完成让路中止后物理回家及归还；避免将未触发的长Hold重复当作专项进展。随后继续当前构建Host连续租约/账本、近场命中与撤回、双兵/可见性/死亡/人工停止，及G5–G8客户端完整链和风格贡献。
- 当前构建已运行30组实际C++、7组原生通道、274项host_runtime全套检查；之后新增缺失空地票据反例，相关34项专项通过。测试数量仅为对应时点验证，不代表实机总目标完成。

## 最新整体进度（2026-10-27 01:49）

- **已形成有正反例的原生空地读取前置条件，尚未接入原生执行器/派移动，完整G4仍未通过。** `013405` 禁模型、禁注入/生产/租约。最终窗口101条同帧单元记录，9个己方单位、3个不同帧；32条满足限定空地前置条件，69条由原始地形mask/对象记录等拒绝。原始分类代码0/2/4/7/9，不冒认其他代码的地形名字。8项[独立原始字段复核](../acceptance/runs/20261027-013405-runtime-calibration/land-cell-independent-review.json)通过，当前terrain Python15项检查通过。
- 原生调用关系已拆清：68a870先检查单元层关系；69fa40调用696fc0拒绝谓词，再进入69c2e0/69bbf0角色脚印/对象检查。常量表0xcb122c前11字为 `[9,10,12,24,40,72,72,136,8,520,1032]`，不与mask相交返回拒绝5。新读取器只研究mask1、code0、primary layer1、flag18 clear和无对象记录指针的分支，不授路线保证。
- 首轮读取因geometry override=-1被错误数值范围拒绝，0样本；独立原字节显示半径5、override=-1，原生 `>0` 分支才覆盖尺寸。其后发现6f0360/UnitAI+180/+184是忽略对象值而非通行mask，已保留原失败源码/输出并补字段来源反例。真实PathfinderPath+3c→PathfindParameters表明：初始化中objectID0的4520帧不能绑定角色；4549帧匹配Flak975的typed params，其settings指针恰为UnitAI+1fc/vtablec37620，settings+14即UnitAI+210的真实surface mask1。native setup68a740在无settings时才用default1；读取器现在每次配对实际LocomotorSet的mask字段。
- 中间窗口因脚下cache/status条件未满足而0样本，失败原样保留。最终研究将**单元条件读取**与**演员借兵资格**分开：每条保留缺失原因，101条native surface reference全部仍未通过，不凭单元前置条件给这些单位grounded/Borrow信用。原控制器的actor cache、身份/实付/三帧静止home、Stop3、占用与租约门均未改。CLI后续已明确以数据门返回insufficient/observed；旧0样本输出不补写为通过。
- 全程SDK/模型/注入/命令/租约0；19处原入口另读一致、无观察/生产mapping和native Host后结束owned PID59372。当前无活动游戏/Host；DLL967保持不变，未授任何新目标或普通scope。下一步依据[明确的端点合同](../tactical/terrain/ENDPOINT_CONTRACT.md)接入game-thread独立地形/单元检查、保存原始准入票据，重建并在新局完成当前构建完整Move/Hold/物理Return/Release，再回到native yield分支。G5运行停止、G4攻击/双兵/异常、G6三战术、完整G7与G8继续保持原范围未完成。

## 最新整体进度（2026-10-27 01:27）

- **活动地图高度读取正向对照通过，完整G4及总目标仍未完成。** `011212` 为全程禁模型、禁注入/生产/租约的只读地图研究。第一窗口17条平地匹配，3个原生己方单位、17个不同帧；坡面窗口27条匹配，11个单位、6个不同帧，其中3条非平坦样本跨3帧、覆盖两种三角分支。原始四uint16顶点、索引、坐标、native pose/height-cache/status/身份全部保留；独立使用重心公式重算，9项[坡面复核](../acceptance/runs/20261027-011212-runtime-calibration/terrain-slope-independent-review.json)通过、0高度差异。实际坡面范围仅210..210.023727，不外推水面/桥梁/落点/路径。首个坡面窗口被64条平地填满而提前结束，保留insufficient结果；随后限制平地记录24条，才进入真实坡面，不改写旧输出。
- 定位并静态追溯具名 `ThePathfindSystem` 注册（628d6a→global0xce3e30）和构造函数6b0930/vtable0xc18e20；活动4652帧独立采集PathfindSystem、TerrainLogic与三个子对象原字节。新增只读 `pathgrid.py`，复现68d010/544720的layer1坐标及单元寻址：0.05坐标缩放、列指针表、48字节stride，不解释原始分类位。21条同帧己方足兵/栅格样本覆盖6个单位、9个不同帧，raw低四位均0；4项[原始一致性复核](../acceptance/runs/20261027-011212-runtime-calibration/pathgrid-independent-review.json)通过。**通行谓词、类型枚举、层、碰撞/footprint、动态障碍与目标权限仍未验证**。
- 当前地形Python合计11项检查通过；native967构建及既有控制门未修改，没有授当前构建普通移动scope。011212最终另读19处原始入口均一致，没有生产/观察mapping或活动native Host；按PID/start/path核验后结束owned fixture。全程未建立注入执行器，不能称作“执行器归还成功”；没有自然结算信用。当前无活动游戏/Host。
- 下一步从已经定位的原生cell lookup继续查明actor/layer/terrain/障碍通行谓词，形成有正反例的隔离目标合同，再回到当前版本完整移动与让路后物理回家/归还。G5运行中人工停止、G4近场命中/双兵/异常、G6三战术、完整正式局G7与风格贡献G8均保持未完成。见[本轮地形检查点](../reports/runtime-terrain-height-checkpoint-20261027.json)。

## 最新整体进度（2026-10-27 01:06）

- **静止home准备后取消/归还已实机进入，当前版本完整Move/Hold/Return及让路后物理回家仍未通过。** `002123`、DLL832版本在753帧Ready，等待目标至限额后未发Commit，894帧恢复姿态/归还；home与最终位置均 `[1770,1850,210]`，最大位移0，SDK `[1,1,3,1,1,1]`。[13项限定复核](../acceptance/runs/20261027-002123-runtime-calibration/stationary-preparation-cancel-independent-review.json)只证明准备取消及原位置归还，不证明外出或回程路径。
- `001225` 首次静止home实机暴露新Python检查的tuple/list比较错误：真实 `own_candidates` 用struct.unpack产生tuple，历史坐标却存为list，导致原地也交替判为移动。此局0条控制命令，6项[拒绝/清理复核](../acceptance/runs/20261027-001225-runtime-calibration/planning-type-mismatch-independent-review.json)保留原失败。现已统一tuple，补真实采样器返回形态回归；后续002123确实达到Ready。原生home路径/状态门未放宽。
- 已把原始通道只读取证整理为 `integration/host_runtime/runtime_channel_capture.py`：FILE_MAP_READ、当前构建/付款/出生/bootstrap/会话/实际进程pin、完整原票据、双读相同、上下文文件不变；不导入原子发布器、不加载游戏DLL、不派发命令。五项损坏/错绑/丢票/撕裂检查通过，并已实际捕获001225、002123及003832通道。
- `003832` 使用新增目录日志的967版本，663帧Ready、804帧归还，仍无Commit、最大位移0。183条事件、225条钩子，其中10条目录概要、7条过滤记录；12项[目录/准备取消限定复核](../acceptance/runs/20261027-003832-runtime-calibration/catalogue-independent-review.json)通过。147条Ready相关事件（不是147个不同帧）对应的已登记点全部被占用，最后5点中4点还低于30距离；没有日志截断。不能从此推断其他空地不可走。该结果明确暴露“仅用己方曾停过的点”无法覆盖空地，后续回到G1/G2补地形接口，而不是继续重复同一目录派单。
- 目录取证新增被动kind26/27概要/过滤原因及kind28限额标记；不改距离/占用/高度/到达/租约门，不计SDK。最多512条，截断不能授完整移动scope。最新DLL SHA `967f18b661603059e68c03cfdb2264bd5b07ee0d6bbcbcecc6a325ed65342ca9`、Host仍 `f51274654b9812a91d73e1b327d08bc5e834a319601537fd34a1a5d0d27f68c7`，ABI不变。28组实际C++、7组通道、33项运行时Python、266项host runtime检查通过；新的目录字段已由实机原票据逐项校验。
- 底层地形研究见[接口记录](../acceptance/runs/20261027-003832-runtime-calibration/terrain-interface-contract-research.json)：`0x85a780` 的bool是self+0x3c与基础高度的比较，不能当通行性/位置有效性返回；实际基础高度路径为global `0xce9c40`、vtable `0xc0a6f0`、slot+0x54实现 `0x8ed070`。已按其uint16栅格、0.1坐标缩放、0.0390625高度缩放及两三角插值写出 `tactical/terrain/heightmap.py`，只读四顶点及配对元数据，无原生调用/游戏写入。5项离线检查通过；实际场景已重置为frame0/map_data null时正确拒绝 `heightmap_scene_inactive`。**活动地图正向对照、水面/桥梁/落点/碰撞/通行/路线仍未验证，未授新目标权限**。
- 三局都已另读生产器phase2/mask31/active0、战术state3/mask8191/active0/Host exit0及19处原字节后结束owned fixture。003832后看到结算统计界面，但没有独立本局结果参与者证明，仍不授正式自然结算信用。当前没有活动游戏/Host。下一步在新活动地图上跨不同帧对照己方原生足兵脚下高度，完成地形读取的正向证据后再设计隔离目标实验；当前完整直接校准、让路后回家/归还、运行中人工停止、近场命中/双兵、三战术、完整正式局和贡献对照均保持未完成，总目标active。

## 00:10阶段记录

- **真实让路来源和任务中止已进入分支，物理回家/归还仍未通过。** `235143`、DLL `cc3a15a6275a8eedbd564e3122c4be502d7f18238977793b82dad964673cedfc`、实验flags1、实付85的征召兵779/generation1，在641帧捕获外层 `0x694a00` → facade `0x693960` → dispatcher返回 `0x6939aa` / opcode48 / source2 / 邻居战熊781。原生update的邻居ID、实际state26/vtable0xc553d0、完整身份和94ms确认上界逐项匹配；epoch保持0。原目标从未Commit，新Stop后只发一次原home移动，SDK `[1,1,2,1,0,0]`。[22项独立局部复核](../acceptance/runs/20261026-235143-runtime-calibration/yield-abort-partial-independent-review.json)只证明来源/中止/返程启动及失败留存，**不授回家、归还或普通执行权限**。
- 此局返程距原home最近28.5229，763帧进入 `return_stalled_control_release_unknown`。初次停止期间才发生该失败，旧清理流程没有再次进入显式恢复；Native Host随后自行退出，明确 `safe_terminal=false`。退出后完整只读捕获167条原始事件、3475条原始钩子票据，未溢出、未改号。通道state5/held1/control_released0/hooks_restored0；19入口中只有6处生产/观察入口原样，13处战术入口未恢复。已保存原始字节与截图后结束owned fixture作为**失败隔离**，不记成功清理或自然结算。当前无活动游戏/Host。
- 在后续修改前将此局原始数据、旧实现、审查器和制品冻结于 `235143/reviewer-before-home-fix`（68文件），独立进程仍重算22项局部检查通过，失败事实不变。此前 `222727` 19项和 `223257` 41项的801版本完整移动证据及candidate08基础模型局仍原样保留，不授权当前新DLL。
- `233421` 普通模式先进入Ready再遇原生让路，保留unknown后显式归还，无物理回家信用；13项[拒绝/归还限定复核](../acceptance/runs/20261026-233421-runtime-calibration/native-yield-denial-independent-review.json)。`234251` 补齐原生触发前后原始物理字段，定位拒绝条件为邻居 `Thing+0x48` 缺bit4；该局flags1仍正确拒绝，随后显式归还，13项[物理拒绝复核](../acceptance/runs/20261026-234251-runtime-calibration/native-yield-physical-denial-independent-review.json)。两局均未重试Move，完整19入口独立恢复后结束。
- 固定游戏 `0x7e2a90` 的反汇编证明 `Thing+0x48` bit4是 `+0x5c` 高度差缓存有效位，不是直接的地面位。见[静态语义记录](../reports/runtime-native-height-cache-analysis-20261026.json)。现在受控演员和落点仍需原有效缓存/高度/存活/状态门；让路邻居仅作为请求来源，要求完整己方身份、列表映射、正HP、状态和非容器门，不用其未验证高度授落点或借兵权限。原生getter未被调用，观察仍无游戏写入；opcode50仍unknown。
- 当前已修复两处新缺口：所有准备规划等待同一空闲位置连续三帧、path0/低状态位0，原生home门再次拒绝仍有路径/动作标志的演员，避免在出厂移动中捕获未证明可停的home（尚未证明这是旧返程阻挡的碰撞因果）；安全停止不再覆盖紧急显式归还而转成新Move；诊断停止期间才进入unknown时，可在新的四帧静止证明后最多发一次release-only reconciliation，原失败和首次停止超时仍保存。
- 最新DLL SHA `83201eee75df8ae1b679cfabfc46ec45a88b61d37a6548f0c5065617ad951b79`；Host仍 `f51274654b9812a91d73e1b327d08bc5e834a319601537fd34a1a5d0d27f68c7`，ABI仍Bootstrap232/shared1624056、恢复8191。27组实际C++、7组通道、32项运行时Python、257项完整host runtime检查通过，**最新home/停止恢复修复尚待实机**。下一步先做当前构建静止home/让路后物理回家与归还或有证据的紧急归还，补当前版本完整直接校准，再接连续宿主任务和后续G4/G6/G7/G8；总目标active。

## 2026-10-26 23:30阶段记录

- 已实现隔离实验模式的原生让路中止/回家逻辑，但**尚无实机让路成功信用，当前新构建也尚未通过完整直接校准**。新增第13个被动入口 `0x693960`，捕获外层返回地址、邻居完整己方身份/存活/列表证明、原始命令、派发后邻居ID及实际state26；原始调用始终转发一次。仅完整来源候选可等待至多2模拟帧/250ms确认，等待期间不发动作，确认后取消任务效果并执行新的Stop/物理回家/归还；未知来源、opcode50或其他干扰仍进入unknown。普通模式 `experimental_flags=0` 保持原拒绝规则，实验模式不能获得普通移动能力。
- 当前DLL SHA `f481db286989bade7023a139bdc047971296fdf3a5235cb322c9e56c77657b58`，Host SHA `f51274654b9812a91d73e1b327d08bc5e834a319601537fd34a1a5d0d27f68c7`。Bootstrap232、command offset280、receipt648、events2032、shared1624056，13入口恢复mask8191。25组实际C++函数、7组原生通道、28项运行时Python和完整host runtime257项检查通过；离线结果不授实机权限。
- 新普通模式实机 `232247` 实付85产出object779，但30秒内未获得home空闲和目标同时可用的窗口：274次规划观察中目标可用37次、home可用132次、共同窗口0。目标可用806–867帧对应63次home检查均为 `home_occupied_wait`，806帧Flak787距离拟home18.6073，低于20门限。六类战术SDK计数全0、0条战术命令；不是移动失败后重试，也不放宽占用门。89组当时己方环境采样保留。[限定独立复核](../acceptance/runs/20261026-232247-runtime-calibration/no-window-independent-review.json)的10项检查通过；完整直接校准仍not_passed。
- `232247` 战术终态state3/mask8191/active0/Host exit0，生产器phase2/error0/mask31/active0，19处原入口均另行读回通过。只在此后结束owned fixture，当前没有活动游戏或Host。下一步解决实机共同准入窗口并完成当前构建直接校准，然后采集真实让路完整来源及回撤证据；不能借旧801版本scope授权新DLL。
- `223257` 两任务41/41、`222727` 单任务19/19及candidate08基础模型实战证据均保留。后续开发前在 `223257/reviewer-before-yield` 冻结旧实现/审查器/二进制，并在独立进程重新算出19/19和41/41，保证ABI变化后仍可复核历史。完整G4/G5停止分支/G6三战术/G7完整正式局/G8贡献对照仍未完成，总目标保持active。

## 22:48阶段记录

- **当前版本连续两任务已实机通过。** `223257` 使用实际HostTactical、CommandJournal和原NativeRuntimeClient；同一实付85征召兵object781/generation1完成独立租约A、B，四个原始包Reserve1/Commit2/Reserve3/Commit4。41项独立检查全部通过，原始报告SHA `2029683a5c7845a54a9e773745ca88fc76928045e3995c4e75399cbb7d993b9d`。见[两租约原始记录/账本验收](../acceptance/runs/20261026-223257-runtime-calibration/two-task-independent-review.json)及[可读连续任务摘要](../acceptance/runs/20261026-223257-runtime-calibration/continuous-task-summary.json)。
- A的home到目标39.7896、实际保持15帧、1074帧归还；B为33.1211、实际保持16帧、1150帧归还。目标停止距目标约6.46，归还距各自原home约6.7，均满足原15半径；两租约SDK各为 `[1,1,4,2,1,1]`。重复Reserve/Commit命令ID一致，A前后native sequence/count仍2/2，B仍4/4，权威账本未决0；没有foreign、攻击或unknown信用。
- 本局只消费 `222727` 当前构建原始报告SHA `9afcfb5b3924683af6272366e4db86e49e97c01f3a1268a9c6c940cb1065fcf1` 授予的限定移动能力，DLL仍为 `801b9e3caf77eae84774128992b5efda19e2af1aaa031e3696368f397004ca7e`，未复用旧执行器scope。该结果证明真实宿主账本下的两个局部移动/保持/回家/归还任务；本局模型禁用，不能当作模型三战术或完整G7/G8完成。
- 独立另读生产器phase2/error0/restore31/active0、18处原入口全部恢复；战术终态state3/mask4095/active0/host_exit0。之后实际看到游戏结束界面并保存，但没有独立胜负参与者证明，不授正式自然结算信用。owned fixture在以上清理确认后结束，当前没有活动游戏或Host。旧失败记录原样保留。[连续任务阶段证据包](../reports/20261026-223257-continuous-control-evidence.zip)含摘要、审查、截图、构建hash及完整原始记录的路径/SHA索引，不替代原始数据重算。
- 同步补齐诊断导出的结构化plan/proposal：匹配plan/task/generation/会话身份后保留策略、预算和任务关联；模型自由文本、未知嵌套字段及地址不直接导出，错绑或缺ID的嵌套数据不归到当前事件。9项诊断检查、完整host runtime256项检查通过，尚待下一版真实客户端局验证；候选08历史导出不改写。
- 下一步仍按原G4顺序处理原生让路/自卫来源、近场可归因命中及撤回、双兵及视野/死亡/人工停止异常，再接G6主攻/骚扰/协同、G7完整正式局和G8风格贡献。原opcode48/50未因这次无干扰成功获得白名单；任何新原生实现需重新构建、直接校准并验收，当前完整总目标保持active。

## 22:33阶段记录

- 当前 `801b9e3caf77eae84774128992b5efda19e2af1aaa031e3696368f397004ca7e` 构建已重新完成实机单兵完整Move/Hold/物理回家/原生归还：`222727` object781/generation1，实付85，home到目标76.4685，保持15帧，1020帧归还，SDK计数 `[1,1,4,2,1,1]`。19项原始记录检查全部通过，见[本构建独立验收](../acceptance/runs/20261026-222727-runtime-calibration/calibration-independent-review.json)。原始报告SHA为 `9afcfb5b3924683af6272366e4db86e49e97c01f3a1268a9c6c940cb1065fcf1`；不是旧构建报告复用。
- 另行独立读取生产器终态phase2/error0/restore31/active0及18处观察/生产/战术原入口，全部恢复；游戏截图已归档。该owned fixture只在以上确认后结束，[限定基线](../acceptance/runs/20261026-222727-runtime-calibration/current-single-actor-baseline.json)不授战斗、三战术、双兵或自然结算信用。
- `221938` 已证明采样时差修复后能等待到联合窗口、实际Reserve及Ready，但没有合格提交点，0条Commit；最终物理回家距离10.4001、控制归还/姿态/双执行器清理独立通过。保留[本轮局部复核](../acceptance/runs/20261026-221938-runtime-calibration/home-window-timing-partial-independent-review.json)，完整校准仍not_passed。
- 新增Ready后有界只读等待：不改租约期限，最多8秒/120模拟帧，并保留至少120帧回撤空间；每次记录原生候选和过滤后候选，任何unknown或离开Ready立即中止，未观察到目标不派Commit。运行时Python27项检查通过；`222727` 的候选在第一次Ready观察即可选定，尚未以该局证明实际等待后恢复候选的分支。
- 现在以本版原始报告的明确SHA，在全新 `223257`、session `ce10060f-6055-4e2c-ad70-1f1fef31518f` 做实际HostTactical/CommandJournal任务A→归还→任务B验收。新局尚在大厅准备，不能将其记为连续任务通过。模型仍禁用，原生让路/近场命中、双兵/异常处理、G5运行中手动停止、G6三战术、完整能力G7及G8风格贡献对照均保持未完成。总目标active。

## 20:50阶段记录

- 基础客户端/真实模型/实付生产/自然结算里程碑仍成立，candidate-08的39次模型响应、85实付征召兵及铁锤胜原生奥列格证据保持原样。完整G4、三类战术G6、完整能力正式局G7及风格贡献G8仍未通过，总目标active。
- 新增 `preborrow.py`：借兵前最多30秒只读等待，要求三个不同帧的独立己方空闲窗口；未获得窗口不创建租约、不派Reserve，原生现场占用门仍作最终判定。`190103` 确实等到窗口并借兵，但Ready后原候选不再被原生目录接受；Commit未派发，随后实际回家及归还、18入口恢复独立通过。[限定复核](../acceptance/runs/20261026-190103-runtime-calibration/home-window-partial-independent-review.json)。候选失效的具体原因未证实，不将其推断为已证明的碰撞或距离问题。
- 已改为Ready后重选当前原生候选，目标同时受实际Reserve事件home与当前演员位置的局部范围约束；`NativeRuntimeClient.reserved_home`读取匹配task/lease的原始事件，不以当前坐标替代home。原生拒绝之后仍不重试。`190928` 的30秒等待没有共同窗口，0条控制器命令，独立清理通过；[等待失败复核](../acceptance/runs/20261026-190928-runtime-calibration/no-window-independent-review.json)保留。
- 该局额外五组只读己方采样确认Conscript/Flak/Bear共用 `0xc48670/0xc48528` 更新布局与状态回链，仍逐对象检查地面位、实际高度、存活及状态；高于地面的对象不据兵种名认定为落点。新增纯只读 `GroundGeometry`，它不实现IO或NativeCalls，不生成演员出生/租约/控制权限。原生目录保留三个不同帧静止点规则，刷新全己方中心占用，租约期间只刷新占用、不扩张点目录；读取不全则目录不可用。此为几何与保守中心距离检查，不能证明全路径或后续动态可达。
- 最新DLL为 `801b9e3caf77eae84774128992b5efda19e2af1aaa031e3696368f397004ca7e`。23组实际C++函数、ABI6组、完整host runtime254项及运行时Python26项检查通过。`203509` 新局出现21个候选帧、65个home准备帧，但共同窗口0；未借兵、六类控制器SDK计数全0，完整校准仍not_passed，[独立记录](../acceptance/runs/20261026-203509-runtime-calibration/no-window-independent-review.json)。观察器state3/mask4095/active0/host_exit0、生产器phase2/mask31/active0、18处原字节均独立核验后结束owned fixture，当前没有活动游戏或Host。
- 进一步修正规划采样的双时钟问题：同帧完整独立己方清单用于规划占用检查；原生样本可有至多两帧的新鲜度差，不再要求移动演员在不同帧坐标相同，新增实际位置差日志及回归。原生现场home占用/身份/动作准入未放宽。这一最新Python修复尚待新局，当前构建仍没有完整Move/Hold/Return通过记录，不使用旧构建scope授权它。下一步新局完成当前构建直接校准，再验收真实HostTactical两租约；原生让路/近场、G6三战术及G7/G8保持原完整范围。

## 18:56阶段记录

- 真实桌面客户端→保存配置→局内模型→账本→实付生产→自然结算的基础链已通过：candidate-08共39次真实模型响应、实付85产出一个征召兵，铁锤胜原生奥列格；清理和脱敏诊断已归档。[阶段证据包](../reports/20261026-c08-base-match-evidence.zip)仅证明该基础里程碑。
- 单兵完整移动/保持/回家/归还曾通过；连续任务仍未通过。最新 `184106` 任务A完成且重复请求未重派，任务B到达并保持15帧，但返程离原home最近20.2552，随后显式恢复归还控制，**没有物理回家证明**。原账本uncertain保持原样。[独立局部复核](../acceptance/runs/20261026-184106-runtime-calibration/independent-partial-recovery-review.json)。
- 新增110组当时的己方周边采样。任务B借兵前1061帧，另一己方Flak object798就在home同一坐标；现有home准入缺少占用检查。此事实不等于已独立证明碰撞因果。另一路原生opcode48让路及后续opcode50仍未获白名单，[回溯分析](../reports/runtime-yield-route-analysis-20261026-1842.json)保留原始解码和固定游戏反汇编。
- 已补原生home占用准入：在Borrow前独立扫描完整当前己方live list，任何己方类型在home中心20以内、同高度范围即拒绝；读取不全也拒绝，不沿用旧home授权。这是保守中心距离检查，不是原生碰撞半径或路径保证，不能防止后续动态占用。实际C++22组、ABI6组、evidence32项、repeat verifier7项、transport10项及诊断/清理8项检查通过。
- 当前新DLL为 `00aff0e622b69e67f3305b066a1d805c3949a13f8ad357713c8ad774e7dee03a`。旧 `171654` scope不能授权修改后的当前executor。全新 `185147` 的0模型实机在Borrow前被新home门拒绝，原始ack明确 `private_home_ground_or_vacancy_unverified`、六类控制器SDK计数全0；819帧独立己方采样有两个Bear分别距演员拟home13.0171和16.1723。见[占用拒绝限定实机复核](../acceptance/runs/20261026-185147-runtime-calibration/occupied-home-admission-independent-review.json)。这仅通过“拥挤home不借兵”分支，完整校准仍not_passed，未授当前版本普通移动能力。观察器state3/mask4095/active0/host_exit0，生产器phase2/mask31/active0，18处原字节独立读回；两次owned fixture都已在清理确认后结束，当前没有活动游戏或Host。
- 后续先补借兵前有界等待：独立观察可用home窗口，仍由原生门作最终判定，不重试已拒绝/未知的派发；再完成当前构建的直接校准与两租约验收。动态占用、全路径可达和原生让路不因静态home门而解决。
- 完整G4、G6主攻/骚扰/协同及回撤、G7完整能力正式局、G8风格与模型贡献对照仍未完成。G5运行中手动停止仍缺实机验收，新的plan/task持久关联尚未进入下一版正式局。总目标保持active。

2026-10-26 用户明确授权按 [建设计划](architecture-iteration-plan-20261026.md) 组织多 Agent 开发、设立 goals 并持续推进至完整验收。旧 MF 试错线保持停止；原主目标 blocked、原接续目标 paused 不是新架构的前置条件。

## 持续目标与分工

### 17:42 真实客户端首次启动Host与发布依赖修复

`173150-desktop-match` 是独立新局，非校准局换标签；模型启用，大厅重新核验。candidate-05发布包在真实窗口完成预检和启动，run `145be12a-1050-41d5-b2e4-7050506db7fc`、实际Host PID17476。宿主接收profile revision2/hash55a906…，局内请求返回一次响应；窗口显示当前修订应用回执及模型响应。transport证据为provider_transport，`real_network_verified` 仍false，不能据此宣称已完成独立网络证明或风格实战效果。见[真实Host局部复核](../acceptance/runs/20261026-173150-desktop-match/client-host-independent-review.json)。

Host在生产派发前失败 `native_observer_failed`，dispatches0。根因是发布快照漏带 `production/bin/NativeProductionObserver.dll`（原生helper从自身目录LoadLibrary），与游戏策略无关。已补齐此DLL及one-shot helper相应DLL，并将observer stderr和退出码纳入后续诊断；candidate-05保持原封不动，candidate-06在新目录重新打包编译。

可信session登记现在允许显式 `--replace-stopped` 刷新从未启动的大厅元数据pin；任何旧launch仍必须满足独立清理和无未决命令，新增两项边界检查通过。首次预检曾因登记后补写大厅信息导致hash失效，保留其拒绝行为，不跳过hash检查。

实际失败Host已退出。新可信工具 `host_runtime.unattached_release` 只对没有生产意图/派发、gateway未附着、同一Host已结束的情况逐项独立读取六处观察/生产原入口及确认通道不存在，再添加新的 `review_host_release` 权威记录；不修改原fault或模型记录、不调用SDK、不赋予回家/自然结算。实机复核已通过并归档[原始清理复核](../acceptance/runs/20261026-173150-desktop-match/unattached-release-review.json)，该owned fixture随后结束。

Desktop状态现在能从账本中已验证的生产stop回执或上述独立清理复核显示release；不从Host退出、UI布尔值或停止请求推定归还，含战术scope时不以生产归还替代战术归还。G5生产完整链、G6三战术、G7自然结算、G8对照仍未通过。路径/让路问题保持待办，没有以本次客户端局部结果缩小目标。

candidate-06真实窗口已读取旧fault任务的独立归还证明，并在保留fault状态的同时解除终态锁定；旧run仍保留原ID及原结果，不清除localStorage冒充新开始。新局 `174342-desktop-match`、PID66920、session `51f65ebb-d1cc-4a91-bbd2-ef62eebdd750` 大厅完成核验后冻结登记，通过真实窗口预检和启动新run `8cc22972-dcf7-4b97-8891-5e5d1a6f1522`、Host PID65740。真实profile revision2应用及局内模型响应已显示；当前等待30秒原生生产观察，生产完整链与自然结算尚未宣布通过。

candidate-06 companion manifest SHA为 `76e051dd3e4e34d7bdf545499f4eb468f320f9782a507cbd5e39a02317ac7179`，四个改动Python入口及两项补齐DLL与当前源码/制品hash逐项一致，独立RPC smoke通过。最新完整host runtime 252项、battle_host16项、前端50项检查通过。曾有一次全套中的Windows surrogate停止状态间歇失败，原输出保留在执行历史；同一项独立复跑和完整重跑通过，尚未将其推断为产品失败根因。

### 17:51 candidate-06实际后续与安全元数据依赖

上述Host PID65740随后在30.922秒以fault退出；局内模型响应共2次，原生观察器确实完成30秒、12次原生build观察，state2/error0/原字节恢复/active0。之后 `ProductionExecutor.start` 在任何生产派发前读取companion中不存在的 `unknown_sessions.json`，出现FileNotFoundError。没有把其当成生产已接通。详见[本轮客户端Host复核](../acceptance/runs/20261026-174342-desktop-match/client-host-independent-review.json)。

已增加 `production/session_history.py`：使用manifest固定的companion-layout source_root只读当前未知会话安全元数据，代码和执行器仍取包内制品；拒绝缺失/相对路径/重复键/无效schema，不打包陈旧拒绝清单，不把缺文件当空清单。5项安全元数据测试和原22项persistent client测试通过。

独立清理工具增加被动观察器已恢复通道的原生68字节header核验（同PID、state2、error0、active0、restore_verified1及同线程），生产通道仍必须不存在，同时读回六处原入口。真实复核通过且作为新记录保存，不更改原fault；owned fixture已在复核后结束。candidate-07新目录正在打包编译，当前无活动游戏或Host。完整目标继续active；下一步新客户端局验证生产接线，再持续处理连续战术/三战术/自然结算及对照。

### 18:05 candidate-07真实网关握手与首个模型增产任务

`175230-desktop-match`、PID57752、session `a7bb0f49-c08c-4147-9b1a-054cc46a7e25` 已重新实际核验大厅。candidate-07真实窗口启动run `5110a07e-e31a-40d6-ad41-a47593b50abf`、Host PID12872；观察器通过后，真实ProductionExecutor phase1、HostProduction gateway attached及执行启用均已实机确认，模型共返回20次响应。前期资金较低，模型多次保留native_baseline；后期真实提出infantry增产任务，却在派发前因TaskCoordinator的32位hex任务ID不满足HostProduction canonical UUID合同而fault，不能把本局记为已出兵或模型战术生效。

已在任务ID源头改为标准UUID，不放宽权威账本校验；新增真实BattleAgent→真实Host方法→生产网关→回执归原任务的组合回归通过。strategy192项、完整host runtime254项检查通过。原生执行器已真实停止，phase2/error0/restore31/active0、spent0/count0，六处观察/生产原入口独立读回通过；[本轮局部复核](../acceptance/runs/20261026-175230-desktop-match/client-host-independent-review.json)保存原始native header与字节，fixture在复核后结束，不作为自然结算。

下一版本同时增加实际受控HTTPS传输凭证：记录完整响应后、固定目标源、默认非注入传输的字节数与请求/响应SHA；不保存正文、header或密钥。自定义backend及MockTransport不能自行赋予real_network_verified。使用revision2/hash55a906…的独立真实提供方请求已通过，见[HTTPS传输实证](../reports/desktop-style-provider-transport-proof-20261026.json)；这是合成战况探测，不替代正式局内证明。agent_runtime28项检查通过；deadline取消测试改为在真实框架进入调用后推进测试时钟，生产期限未修改。

candidate-08新目录正在打包编译。当前无活动游戏或Host。完整G0–G8仍active，G5实付生产/停止/查询、G6三战术、G7自然结算和G8对照仍未完成。

### 18:30 candidate-08基础模型辅助对局自然结算

新局 `180735-desktop-match`，session `158e3f2c-91ff-4347-8a27-dbed34eaff3e`、PID49488；candidate-08真实窗口启动run `5d8fcf1c-cad4-4dba-97be-b3f636c0858d`、Host PID39024。本局使用已保存profile revision2/hash55a906…，39次模型请求和响应，受控非注入HTTPS传输凭证为真。真实模型增产任务 `805ac151-77d4-4e94-8fa2-91cd0852f950` 经账本命令 `4590bec0-fada-4db5-86bd-10ec5c7367d3` 以seq1实付85、创建object803，原始native receipt已独立读取并与SQLite完成回执匹配。另两条原生拒绝为error4最小生产间隔、error9资金/预算门，attempted0/paid0/created0，没有重试伪造成功。

本局自然结算已实际确认：铁锤玩家3/蓝色胜，原生奥列格玩家4/橙色负，双方中等、10000、Industrial Strength。原生胜负帧9226，候选观察帧9271；当时victory manager映射player3未败、player4已败，两AI互敌且observer独立。实际统计画面已核对并保存部队/信息/资源/建筑四页。结算后原生场景已正常重置，额外独立读取得到frame0/空participants，保留此事实，不覆盖Host候选时记录。游戏实际保存回放并复制归档，但注入生产能否被回放忠实重现仍未验证，不用回放替代原始动作证据。

生产器终态phase2/error0/restore31/active0、spent85/count3，原生header与三条receipt留存；六处观察/生产原入口独立读回通过。真实客户端显示结算候选及独立控制归还验证，权威账本未决为0。窗口下载脱敏诊断成功，298/298条已记录事件全部导出，无截断。详见[本局自然结算确认](../acceptance/runs/20261026-180735-desktop-match/result-confirmation.json)与[阶段证据包](../reports/20261026-c08-base-match-evidence.zip)。owned进程仅在自然结果、截图/回放与清理复核后结束，不以结束进程替代自然结算。

本局仅为“原生AI辅助模型追加生产”的基础里程碑，不能宣称模型独立作战、三战术通过或完整G7/G8完成。第一生产任务到plan ID的关联已在有界agent历史中淘汰，未补造；后续代码现已在派发前持久记录 `plan_applied`/`task_proposed`，计划/请求ID源头也统一为标准UUID，等待新局验证。运行中手动停止分支、完整连续战术、主攻/骚扰/协同实效回撤与风格对照仍缺。

完整目标保持active。当前没有活动游戏或Host；下一步回到G4/G6近场路径和原生让路仲裁，补齐连续任务、三类战术，再用完整可追溯版本验收正式局及对照。

### 17:20 连续任务失败复核与新版本再校准

`164643` 已真实通过 HostTactical/CommandJournal 完成任务A，物理回家/归还/效果为真；重复 commit 和 reserve 沿用原命令ID，native sequence2、命令总数2均未增加。任务B在1030帧被原生opcode48/source2/返回地址0x6939aa打断，1031帧保持 uncertain；该局没有通过。固定游戏二进制反汇编将该路径对应至 state26、vtable0xc553d0，名称 `UnitAIMoveOutOfTheWayState`。未将该路径或后续opcode50加入宽泛白名单。原始账本及故障隔离记录保持不变，见[连续任务失败复核](../acceptance/runs/20261026-164643-runtime-calibration/independent-repetition-failure-review.json)。

恢复修复已落盘：foreign清除旧 delivered 事实；显式恢复允许独立证明的state94静止或state16空闲窗口，不再借用旧Stop完成标志。诊断清理等待4个不同静止帧、稳定epoch和位置后仅发一次新reconcile；没有窗口则不发恢复命令，仍尝试独立停止。实际C++函数22组、清理4项、transport10项、独立证据32项检查通过，均为离线验证。

新版本实机 `171654` 支付85创建object780，完整Move/Hold15帧/物理回家/归还再次通过19项独立原始字节检查。DLL为 `7ae3588227971da25d0e534fc10feeba25ab1d792cab1827f8b27c3236c27ff5`，原始报告SHA为 `fed3d036f5655d1a1f516b6d20e5c90a9adc7ef2184a8c6efe901b8cf65eebe3`；见[本版本限定校准复核](../acceptance/runs/20261026-171654-runtime-calibration/calibration-independent-review.json)。双执行器清理通过后结束owned fixture，不作为自然结算。旧d93版本报告不能授权修改后的当前executor。

后续 `172046`、PID65440已实际核验大厅并使用本版本pin开始HostTactical任务。第一任务目标 `[2910,2890,210]` 最近仍有20.1545，未满足15到达半径；937帧触发90帧无进展回撤，962帧真正回家/归还，终态明确为 `native_control_release_without_goal_effect`，没有目标效果信用。独立复核确认物理回家、原生归还、姿态恢复、12入口恢复及生产清理通过，见[无效果回撤复核](../acceptance/runs/20261026-172046-runtime-calibration/independent-no-effect-return-review.json)。该fixture在确认清理后结束；事后只读己方census不能冒充当时阻挡物证明。下一步必须处理落点证明不等于路径可达的问题，不增大到达半径，不用重复随机开局替代修复。

新增 `runtime_repeat_evidence.py` 对两租约分别核验原始包、原始事件、停止采样、Move目标、物理效果与回家，并与只读SQLite账本关联；不合成单任务header、重编号原票据或授新能力。原单任务审查中的出生/付款验证提取为共用函数，原32项回归通过；新增7项合成审查器检查与完整248项host runtime检查通过，不是连续任务实机成功证据。实际172046输入被独立拒绝，见[two-task review](../acceptance/runs/20261026-172046-runtime-calibration/two-task-independent-review.json)。当前无活动游戏fixture，完整目标仍active；客户端Host实战、三类战术、自然结算与模型贡献仍未完成。

### 15:43 持续跟进接续

用户在新会话 `01a17718-2237-7d62-99a9-62a199ed223f` 明确要求持续跟进直到完整目标达成；该会话已建立 active 跟进目标。旧主线和桌面会话的最近实际命令分别停在 15:23:45、15:23:51，当前协作树无法找到旧实例，不能仅凭旧 `inProgress`/`active` 字段声称仍持续执行。没有直接改写 Codex 数据库或将旧任务冒记完成。

本次修复 `test_native_move_goal_must_match_requested_target` 的失效定位：新增 private Stop trace 后固定下标指向了 Stop，原用例修改的是无关数据。现在按实际 Move trace 类型选择，并确认待修改的目标字非零，再验证目标篡改被拒。验收器和真实能力边界未放宽。检查结果：runtime evidence 32 项、全部 host runtime 240 项、strategy 192 项、原生实际 C++ 函数 15 组和 Python transport 7 项均通过；这些都是离线验证。

最新旧实机为 `20261026-151325-runtime-calibration`：`fixture-end.json` 记录停止复制/延迟派发调用链未知、显式恢复被拒、held=true、hooks_restored=0；该 owned fixture 已故障隔离终止，physical_home/native_release/natural_result 全部未验证。失败原件保持不变。

当前无活动游戏后，新建 `20261026-154312-runtime-calibration`、PID16656；沿用独立核验过的游戏和 mod hash，模型禁用。当前为菜单配置阶段，lobby_verified=false；必须重新实际核对大厅和新会话身份后才能执行局部校准。本次不把新开局作为旧局控制归还证明。

### 15:55 新校准失败与清理修复

`154312` 已实际核对大厅并保存 `lobby.png`，模型请求为 0，真实支付 85 并创建 object787。该演员从 `[2929.2183,2920.2520,210]` 实际移动最大 41.9306；请求目标为 `[2952.4541,2956.8279,210]`，留存样本离目标最近 32.0561，未满足半径 15 的到达要求，不能算 Move/Hold/Return 通过。

两条逐帧恢复事实使旧 512 条 trace 缓冲溢出；旧 `finally` 初始 poll 抛错后跳过了安全停止。已保留原始失败 JSON、当时源码/制品、现场截图和[独立失败复核](../acceptance/runs/20261026-154312-runtime-calibration/independent-failure-review.json)。随后独立核对同一进程和通道身份，发送有界安全停止，`safety-stop.json` 仍记 state5/held=true/hooks_restored=0；该明确 owned fixture 已故障隔离终止，`fixture-end.json` 全部归还/回家/自然结算标志为 false。未覆盖或改写原失败。

当前修复：`diagnose.cleanup_runtime` 将恢复读取与安全停止分开，读取失败也尝试 stop，stop 失败单独保留 unknown；两项故障回归检查通过。C++/Python trace ABI 同步扩为 4096 条，覆盖 900 帧租约的两条逐帧事实和调用链余量；仍拒绝任何溢出。完整 native 重建通过、实际 channel 6 组检查通过；transport 7 项及 evidence 32 项再次通过。新 DLL 为 `4c14fa2b95a9b443d95c5a01438a8f7f40bdf3cdeaf0bb66bcf55ffc609fc5be`，host 为 `88eb37c5bba3f060f84fba10845d861c23f46cace576ce84d815e4a8340d4607`，当前依旧 execution_ready=false。

下一阶段门：先用保留的实际位置/目标/原生状态重放分析到达未满足的原因，补充无进展时的有界停止/回撤路径与证据，再做单因素实机复核；不扩大到达半径，不把调用被接受当作物理到达，不进入三战术或正式整局。当前没有活动游戏 fixture。

### 16:02 后续阶段门与接续位置

已使用 `154312` 的实际起点/目标/停点构造真实 C++ Controller 回放：出站 90 模拟帧没有至少 1 单位更近进展时，进入一次 Stop/Return；返程无进展则保持 unknown，不重复 Move。回家/归还完成但没有完成目标 Hold 的终态为 `native_control_release_without_goal_effect`，Host adapter 不再仅凭 physical_home/stance_restored 赋予任务效果。该分支、返程阻断不重试和 Host 无效果归还反例均通过；这些仍为离线证据。

`Endpoints` 现在要求三个不同帧的稳定原生停驻、无活动 path、并在候选提供时已腾空；不再把行走途中的瞬时坐标作为已证明停点。完整 native 重建与 241 项 host runtime 检查通过。

实机 `20261026-160239-runtime-calibration`（PID65516）实付85创建 object779，但未找到合格落点，因此在 Borrow 前拒绝，commands=[]、SDK计数均0、held=false。后续观察发现原生 AI 将这个从未借用的单位编入其他队伍；旧 observer 清理条件却无条件要求 default_team，导致 hooks restore pending。没有通过借兵/强制转队来清理。已保存原始校准、源码制品、大厅截图及 fixture-end 故障隔离终态；该 fixture 已结束，未宣称归还或自然结算。

新清理修复跟踪 borrow_attempted：从未 Borrow 时允许在无活动回调、无 scope、无 pending、未 held 的前提下恢复纯观察钩子；一旦尝试过 Borrow，仍必须验证默认队伍，不放宽控制归还。19 组实际 C++ 函数、6 组 channel、7 项 transport 和2项诊断清理检查通过；最新真实 manifest 的源码/制品/PE/ABI 独立核对通过，完整记录见[持续跟进检查点](../reports/runtime-continuous-followup-20261026.json)。本修复尚待实际未借用会话复核。

当前由跟进会话的 active goal 持续接手，不将旧 active/inProgress 条目当作活跃执行证明。接续先验证未借用 observer 清理，再研究稳定落点的实际可用性和路径到达；没有合格点就保持拒绝，不能放宽15到达半径。G4/G5实机、G6三战术、G7自然结算、G8风格/模型贡献仍未通过。游戏现场当前无活动 fixture，不恢复旧 MF 试错线。

| 目标 | 会话 ID | 责任与当前状态 |
| --- | --- | --- |
| G0—G8 持续跟进与当前执行 | `01a17718-2237-7d62-99a9-62a199ed223f` | 当前 active goal，接续完整集成、实机及验收；当前仅本会话操作校准现场 |
| 旧恢复总目标记录 | `01a17702-3c82-7201-8087-a71df7292e82` | 最近实际命令15:23:45；持久字段 active/inProgress 不证明当前有 live 执行 |
| 旧 Windows 桌面工作包记录 | `01a17703-8127-79b0-b83d-63dc02fbe451` | 最近实际命令15:23:51；已有 candidate04 的真实解释器PID/窗口证据，实际 Host 对局闭环未完成 |
| 旧 G4 恢复工作包记录 | `01a17703-5076-7fa0-80cb-f2c6ef95450e` | 因模型容量错误 failed，不能当作仍在操作游戏 |
| 命令账本 | 原交接会话内开发，交总 Agent 集成 | journal.py 已有首批实现；独立审阅与跨模块接线进行中 |

总目标包含真实客户端配置、重复任务、三战术真实效果、AI 对原生电脑自然结算与完整过程证据。子目标通过不能将总目标标记完成。

### 16:19 真实被动清理已验证，修正原生编队与落点合同

`161304` 未找到合格落点，借兵前拒绝。此次 observer 清理实机通过：state3、hooks_restored=4095、active_callbacks=0、host_exit=0，两个终态头一致，12处入口原字节在当前进程再次独立读取一致；归档源码/制品hash和PE核对通过。见[限定被动清理复核](../acceptance/runs/20261026-161304-runtime-calibration/passive-cleanup-independent-review.json)。仅证明未借兵时卸除观察钩子，不证明借兵归还、Move/Hold/Return或普通能力。该诊断 fixture 随后在清理确认后正常结束，模型请求0。

同局20秒、95组只读己方样本证明：原生单位会加入另一个真实己方队伍，owner回链全部一致；多数停驻样本处于10/13状态，而不是本控制器 Stop3 的94状态。已修正两个错误混用：Borrow 不再限定原生 common pool，但每次实际读当前team→owner回链，其他玩家队伍即使actor owner字没变也拒绝；归还仍到原生common pool。地面候选按grounded、不同帧稳定位置、path为空和腾空判断，不把候选点当作94/16控制状态授权；控制器的Stop3/原生动作/返回检查不变。20组真实C++函数检查、native重建及transport/evidence检查通过，等待本次实机验证。

新增可重复的 `acceptance/Start-RuntimeCalibration.ps1`：禁止已有游戏时启动，核对固定game/mod hash与当前runtime source/artifact/ABI，不复制原大厅成功标志。`162620` 为当前新的有界实机诊断，模型禁用；Borrow前候选等待最多30秒，记录每个不同帧的候选/过滤数量与实际坐标，不延长任何已持有租约。

### 16:38 单兵基础 Move/Hold/Return 实机通过

`162620` 已实际到达目标，停稳位置到目标距离4.6758，实际保持15帧；返程因私有home不在通用候选目录而进入unknown。显式紧急恢复执行TransferBack后，下一次异步采样已被原生AI重新编队，未证实归还终态。失败与限定的[部分观察复核](../acceptance/runs/20261026-162620-runtime-calibration/independent-partial-failure-review.json)保留，fixture故障隔离不算归还。

当前修复让原生 IO 在 Reserve 前独立重采同一actor/frame/position后私有登记home，不接受UI坐标；home的路程和物理到达仍须实际验证。TransferBack 同步执行后立即独立采样原生 common pool、owner及原姿态，不等到下一轮原生重新编队；清理允许在已有同步归还见证、当前队伍确属原生己方且非script时恢复观察钩子。客户端终态引用匹配原始receipt的事件观察，未收到该事件时保持pending，不借当前环境样本冒认归还。21组原生函数、9项transport、32项evidence及241项host runtime检查通过。

`20261026-163452-runtime-calibration`（PID42292）独立原始字节复核19项全部通过：实付85、object780/generation1，目标距离39.9848，保持15帧，实际回家和姿态0/原生common pool归还；SDK计数为 Borrow1/Hold1/Stop4/Move2/Restore1/Transfer1。events80、traces125，无溢出；state3、4095恢复位、callbacks0、host_exit0，生产器也为phase2/mask31/callbacks0。见[完整限定复核](../acceptance/runs/20261026-163452-runtime-calibration/calibration-independent-review.json)及[源码/制品和清理基线](../reports/runtime-move-hold-return-baseline-20261026.json)。此fixture在归还及双方执行器清理确认后结束，不作为自然结算。

当前 runtime DLL SHA 为 `d93f5bf00122b1c884151bfa0a05cab1daebedfa984db1b629096b4d035273aa`，通过原始报告SHA `2f26c0a79b49a79cdcb1b84c67053bf1322e043ffe4ba713dc98cdd155f59b6b` 可独立注册 `tactics.move_hold_return` 限定scope；它只授一个付费征召兵局部移动/保持/物理回家/归还，不授攻击、侦察或宏观动作，不说明普通Host已实际执行成功。

持续目标仍 active。下一步：在新受控会话通过真实 HostTactical/权威账本执行同局任务A→释放→任务B，并核验重复request不重派；接着从真实客户端配置/原生登记启动实际Host，验证配置及模型消费、生产/查询/停止。之后仍须G4其他控制分支、G6三类战术实效及回撤、G7正式自然结算、G8风格与模型贡献，不能把本次基础校准替代总目标。当前没有活动校准游戏或未清理执行器。

### 13:34 执行恢复记录

13:33 核验发现旧三个 goal 的数据库记录仍为 active，但对应 live Agent 已不在协作树，源码/会话更新停在 12:26，且没有活动的 Rust/MSVC 安装或编译进程。因此旧会话 `01a17637-7de8-7813-b68a-bfeaccb3faab`、`01a17638-44ec-7ad2-addf-edcd21ccffcd`、`01a17638-7f0d-7a40-a378-16fb8ce5535c` 保留为历史执行记录，不能据其 active 字段声称开发持续进行，也未将其标成完成或直接改写 Codex 数据库。

恢复主 Agent 及两个工作包已建立上述新目标并实际开工，复用全部已有源码。13:35 重新执行当前 `test_host_runtime_*`，179 项通过；这仍是离线验证。原生目录已有半成品制品，但其后对象文件又被修改，必须完整重建并核验清单，不能直接用于实机。

## 阶段事实

### 15:00 后续恢复核验

14:57 再次核对旧恢复批次：目标数据库记录不等于 live Agent；新恢复总目标与上述工作包已实际启动。第一次分派遇到模型容量错误，保持既定模型重试后桌面工作包已恢复，未把容量错误当作代码成功或完整目标受阻。

新主 Agent 只读检查确认：`140150/fixture-end.json` 明确记载旧 PID36652 以故障隔离方式结束，`native_runtime_release_verified=false`、`physical_home_verified=false`，不能记为归还。当前游戏是 `141832` 新局 PID65000，其校准文件停在 `waiting_paid_birth`；没有可用的新桌面 Host 成功证据。需核对当前钩子和生产器真实终态后才能继续，不能把第三轮旧 held 状态直接当成当前新局仍持有。

15:00 后重新运行 `test_host_runtime_*`：229 项通过，6.694 秒；该次是离线验证，没有网络模型请求或游戏动作。

| 阶段 | 当前结论 | 证据或剩余工作 |
| --- | --- | --- |
| G0 旧线停止与基线 | 旧线已停，当前冻结资产须继续保留 | 原控制器/生产器终态已保存，轨迹记录器正常退出；新发布包的基线清单仍需集成记录 |
| G1 能力与配置合同 | 合同与模型工厂已接；保存风格的真实 HTTP 消费已验证，局内效果未验收 | 实际窗口保存 revision 2，独立有界 DeepSeek HTTP 返回有效策略，使用同一 effective hash；观测仍为合成，不构成风格实战效果。见[真实提供方报告](../reports/desktop-style-provider-probe-20261026.json) |
| G2 观测与编排重放 | 新编排的离线完整链与反例已通过 | 每候选拒绝原因、双时钟、付费出厂→就绪→同租约提交→效果/回家/释放的合成链；MF18 缺失的历史 selector 输入未补造 |
| G3 可重复宿主与账本 | d168两租约及新Host首次回家恢复分项通过；客户端恢复pin登记已实机；handoff扩展仅离线 | `101634`47项/177份；`111322`56项/182份，原Commit保持uncertain，新7实际home/归还且控制投影0未决。受控位2、幂等不重派；失败7后新6仅离线验证，完整G3/G4其余要求保留 |
| G4 原生控制与近场闭环 | d168位0基本动作与位2受控首次回家/归还分别通过；完整G4未通过 | `101150`21项/177份，`095903`42项/178份。原任务失败保留；自然让路完整返程、自卫/攻击命中撤回、双兵/异常分支仍待验收 |
| G5 客户端配置接线 | Windows debug 与仓库外 release 配置窗口已通过；当前配置/真实模型/单兵生产分项通过；完整端到端未通过 | 真实窗口保存 steady 为 revision 2，重开恢复；独立 HTTP 消费同一 hash。release 的 8,636 文件 manifest 摘要编译进 Rust，真实开窗验证额外代码阻断和干净包恢复；见[debug 验收](../reports/desktop-native-acceptance-20261026.json)、[release 验收](../reports/desktop-release-acceptance-20261026.json)。外置可信新会话登记/Host 实际回执继续实施 |
| G6 战术和宏观动作 | 未通过 | 原三类战术与缺失风格执行能力保持原验收范围 |
| G7 客户端正式整局 | 未通过 | 没有以新架构完成的自然结算记录 |
| G8 风格与模型贡献 | 未通过 | 待链路稳定后开展分层对照 |

## 已执行的账本检查

入口：`.venv/Scripts/python.exe -m unittest discover -s integration -p test_host_runtime_journal.py -v`。

首批 10 项通过，包括真实 SQLite 两连接争抢同一请求、派发前意图持久化、子进程 `os._exit` 后重新打开账本、未知结果禁止自动重派、事务失败时命令与事件一起回滚、跨 run 错挂拒绝及凭据字段拒绝。

这些结果只证明账本边界，不构成原生权限、任务效果、风格实际消费或完整对局验收。`reconcile_interrupted` 的调用方必须先独立确认宿主死亡；账本中的 evidence ID 本身不是执行授权。

## 本批集成下一步

1. Windows debug 与 release companion 配置窗口已通过真实编译/开窗；继续外置可信 session 根与原生登记、实际 Host 端到端。release 最终集成时重采当前源码并重编译 manifest pin，不能把初版配置快照当作最终实战包。
2. G4 新活动单演员状态机与原生 IO 的独立离线门已通过；旧 MF18 暂停局已正常退出，新局先做0模型、单个85实付征召兵的有界 Move/Hold/物理回家/原生归还校准。独立原始字节验收通过前不授普通战术能力。
3. 从可信登记的全新会话验证 DesktopBackend → 实际 Host → 模型消费与生产回执，然后逐项补控制仲裁、近场命中、双兵回撤和原三战术。

## 当前新增模块

`integration/host_runtime/` 中的 contracts/profiles/capabilities/evidence_adapter 定义配置和可信能力；selector/orchestration/replay 负责纯编排；lifecycle/arbitration 区分效果、实际回家和控制释放；journal 是权威 SQLite 账本；gateway/coordinator 将编排、持久意图和受控 adapter 连接起来。`native_adapters` 对接原生产执行器，当前范围为原已支持的生产/查询/停止，不虚构新的战术 dispatcher。

`ExecutionLimits` 与风格偏好分开；真实 adapter 要核对其总生产额度和保留底线与已启动原生执行器一致。账本 `reserve_native_sequence` 在同一权威数据库中分配原生序号，按游戏进程身份、会话、玩家和指挥官维持高水位，不因新的 host/run 归零。

默认旧证据 verifier 已离线重算：征召兵持续生产和 MCT7 限定攻击保留各自已验证 scope；Flak one-shot 证据缺历史 executor pin，不授 persistent 生产；移动/归还的证据子集不等于已有独立 Move 接口。该核验没有读当前游戏内存、调用 SDK 或发送模型请求。

统一检查入口：`.venv/Scripts/python.exe -m unittest discover -s integration -p "test_host_runtime_*.py" -q`。每次阶段报告以该次运行和对应源码快照为准，动态测试数量不代表实机能力或总目标完成。

由 architecture_delivery 持续维护本文件；所有“完成”状态必须附实际证据和对应代码版本。

## 本批已落盘接线与检查

- `application.py` 将配置接到原模型工厂，`battle_agent.py` 的生产投影只消费 `army` 额度；经济和科技明确标注未分配执行器。strategy 全套 192 项通过。
- `HostProduction` 已用实际 Host 方法通过原生产 wire 的组合测试；宿主派发前保存权威命令 ID 和原生序号。停止/query 仅可访问原绑定 executor，不因结算 owner 销毁而阻断安全清理；生产准入不放宽。
- `ProfileStore` 是风格修订和保存回执的 SQLite 权威源，不修改受保护库/DPAPI 文件；双连接 CAS、重开幂等和超长输入拒绝均已覆盖。保存回执始终 `host_applied:false`。
- `bridge_service` 使用有界具名 JSON-line RPC，真实 Python 子进程循环已验证；默认 CLI 已接 DesktopBackend，没有注册会话则返回 `session_unavailable`。前端不传路径、命令或地址。
- DesktopBackend 的启动 ID 等于 request ID，响应丢失后只查该 ID；启动前复查修订/hash、会话、能力、TTL 和父进程身份。配置服务退出不等于 Host 停止，停止请求不等于原生归还。
- Rust 仅授权主窗口调用 `host_request`，超时不重试；React 对不匹配 profile/revision/hash 的历史应用/消费回执不显示成功。Windows debug 已真实编译并开窗保存 revision 2 后重开恢复；[最终窗口截图](../reports/desktop-native-final-reopen-20261026.jpg)及[验收清单](../reports/desktop-native-acceptance-20261026.json)已记录制品与源码 hash。固定 registry 来源变化将中断配置服务，不静默切换已接受配置。仓库外 release 已使用包内固定 Python 通过配置 RPC，实际窗口验证额外 `.py` 的完整性拦截；[release 验收清单](../reports/desktop-release-acceptance-20261026.json)明确限定配置范围，未冒充实战或最终发布验收。

以上属于代码与离线证据；G4/G6/G7/G8 的真实效果、自然结算及模型贡献仍未通过。

## 恢复后的独立检查

恢复批次完整 integration 480 项、strategy 192 项通过；该次测试没有实际模型网络或游戏动作。其后新增的桌面登记和原始字节验收测试数量单独记录，不与上述批次混算。

`runtime_evidence.py` 独立检查原生诊断的二进制包、当前构建源码/制品hash、原生host实际 `--layout`、实付创建回执、bootstrap与native admitted actor世代、完整事件序列、SDK计数、三帧物理停止、实际持有、目标与物理回家、原生队伍归还、稳定终态及12处原入口字节。22项离线正/反例已通过，反例包括缺样、时钟倒退、世代错绑、付款不足、旧构建、外来控制、未恢复入口、缺少显式SHA pin和跨模组错用。合成输入通过只证明审查器工作，不授原生能力，不证明真实效果。`build_catalog` 已可接收由宿主明确登记的 `runtime_report` 与SHA pin，但尚未登记任何新原生能力。

本轮实际独立重算 `tactical/runtime/bin/build-manifest.json` 全部输入与制品，并执行已编译host的ABI输出通过。DLL SHA-256 为 `9db0f0de712887860411337a5b9927c941d95447bdfffb3ab3caddbacdc4f6cd`，host 为 `29ff47acdf503299ba98d59e9286eb0caf9eba3cbd0d38b56ccf18609dd377c5`；这属于构建/ABI证明，不能替代实机能力验收。

第二轮局部校准已真实支付85并创建征召兵object786；新runtime构造在创建mapping前因x64 `kernel32` 不导出 `InterlockedExchange` 而失败，未借兵。生产器正常停止，mask31/callbacks0。已添加固定hash的本机x64 intrinsic桥 `atomic_publish.dll`，SHA `42d51e8cc480d8413f6873f436c9c087d9456de86c4ada971fcce426def7426f`，独立 `dumpbin` 确认唯一 `runtime_exchange` 导出、零import、零入口点；实际8线程8000次交换检查通过。完整重建与三制品manifest核对后再重试，失败记录不改写。

本批新增后完整 integration 508 项通过（23.163秒）；没有由该测试套件发真实模型请求或游戏动作。

第三轮原始源为 `acceptance/runs/20261026-140150-runtime-calibration/calibration-native.json`。独立重算证明构建/绑定/实付actor检查通过，但因缺少已释放终态，`calibration-independent-review.json` 结论为 `not_passed/terminal_headers_missing`；无普通能力授权。Borrow后未知命令的精确opcode/caller未被旧版hook事件记录，暂不推断具体原因。现有恢复门需要Stop3，而本轮Borrow后尚未Stop，恢复前置关系需要修订；禁止靠忽略foreign或新造重复指令让结果变绿。后续若隔离结束owned fixture，必须明确标作未恢复控制的故障清理，不能替换归还或自然结算证据。

[恢复源码清单](../reports/architecture-recovery-baseline-20261026.json)记录当前111份实现/测试源码hash，并独立核对原审查中列出的MF18冻结源码、审查报告和原始失败记录全部未变；这份清单是恢复时点快照，不冒称实现文件等于原始审查版本。
