# Native5 并行支持交接 · 2026-10-29

用户已明确授权两个会话直接同步协调。此前跨会话发送连续返回 `already has an active writer`；最新一次同步已成功返回目标threadId，实际送达主会话，包含F04／A03已融合的精确版本、报告与剩余缺口。工具成功不代表主方已读或确认采用。本文件保留历史尝试和当前事实，没有通过中断、迁移或暂停主会话来绕过活动写入者。

唯一实机、真实模型与正式计数控制者仍是 AGENTS.md 指定会话。并行支持不启动第二个游戏或模型，不改活动冻结源，不把 CPU／研究／文件核对计入正式三局。

## 2026-10-30 最新正式状态

正式 **3/3**：首局62660、第三次103948和第五次14092通过且三路独审已齐；第二次104984保留为 `not_counted_unconfirmed_tail`，不因归还或导出通过补算。v9/c583、profile31保持冻结。主执行会话曾因 remote compact 网络错误失败，已在同一会话恢复；恢复后确认第三次103948尚在开局大厅、无活动Host或未决指令，继续原次尝试；后续已自然结算并完成主方单局核验，正式升2/3，第四次104244随后因终局尾部unbound_tail_result_rewrite未计入，归还通过，当时正式2/3；随后第五次14092已按同一候选通过，正式3/3，随后F01–F07按本机固定范围完成总审，最终报告及保留限制见下。并行任务没有控制游戏或重发指令。当前状态需结合主执行会话和 owner 核对，后续带旧PID、implementing或0/3的段落为历史记录。

第二次104984的A文件附核已封：`D:/CodexScratch/ra3-independent-next/104984-attempt2-payload-GUI-A-file-review-20261030-v1/review.json`，SHA `276f631963eb694bda9f917257fe5f6b9cefa9e26be8c19bef6ca4e04530fea0`。10次真实请求、8接受／2区域绑定拒绝均保留，memory1536／context8588／记录wire15473B；实际下载470174B，SHA `9e9c2ce7ccf0706634984fb9e6bfaec5c55346d80b33459054d292651af82db0`，与归档一致。218事件／316秒过程数据与HTML一致、播放JS与首局相同，未新增headless执行。仅证明这些分项，不覆盖C所证终局尾链未知；与B只读SQL、C自然结果及归还报告互补，正式加数0。已直接同步主执行方。

### 最终交接：F01–F07本机范围通过

主执行已封 `reports/strategic-final-acceptance-v9-20261030-v1/README.md`、`acceptance-summary.json`、组件manifest与全部引用证据；owner状态 `formal_acceptance_complete`、game_pid为空、正式3/3，游戏／Host／helper收尾清单为空。当前v9/c583及1118冻结项不变；同进程重接保持关闭，正常新局路径已验。容量缺陷未融修正，实机专用损伤／受袭事件未资格化，本机debug非跨机安装版，原生Replay不保证外部指挥完美重演，均为明确保留限制。

A最终工件独核 `D:/CodexScratch/ra3-independent-next/final-delivery-artifacts-A-readonly-20261030-v2/review.json` SHA `83fc500bbc8b1a86e590eb66e2b7c5cfba86619ab442385cf98fa17572e4d868`：28相对链接0缺、26最终及13历史组件副本与原件hash一致、summary引用hash匹配；三局实际诊断／JSONHTML／同JS／原生录像hash及header齐，未重复调用SDK或游戏回放。后续只统一本支持任务五份当前说明的完成措辞，不改冻结源码或原证据；旧草稿和历史失败保留。

来源受限对照B独核 `D:/CodexScratch/native5-F02-producer-limited-B-readonly-20261030-v1/review.json` SHA `d8c31b0910a338fe426bfb5c10eed7cde07d2a344eaccd8be6d1f8d7890f431d`，C v3 delta `D:/CodexScratch/ra3-native-strategic/F02-producer-limited-v3-C-delta-20261030-v1/review.json` SHA `1f5617a3ce0b72cf015a93465767b9eaec2f81d04d1d8d02eb5459e34f229861`：v2／v3 force fixture及实际context仅随机session不同，无人工事件或答案改写；v2条件拒绝保留，v3真实model hold／prepare／空意图支持低当前兵力下合法保持，不冒确认伤亡／全可靠。v1真实2responses／1savedresult，旧note1／0及C沿用旧计数均保原件并由新附注纠正；全组三批5responses／3savedvalidresults／2distinct scenarios，未以Host fallback计模型成功。原五受控案与三自然局不受此统计纠正影响。

### 第五次14092三路闭局独审已齐

run `5aee4dd7-ed65-4f95-83d1-bf39d60bbfc5`／session `63078bf8-f4ea-5e26-8206-c3e2aaf4784e`，Host `acceptance/runs/desktop-ea5e6305-a61a-4a24-83d5-8b81017e411f/battle-host`，归档 `reports/strategic-formal-v9-attempt5-14092-20261030-v1`。主方登记自然通过，计入同一v9／profile31的第1、3、5次，正式3/3；第2、4次原尾链未确认保持排除，整体F01–F07未因计数自动完成。

C `D:/CodexScratch/ra3-native-strategic/formal-attempt5-14092-C-closed-review-20261030-v1/review.json` SHA `f4a61046cd6c65fa64064ae69513d8b28b79c61b6d77e6476f41a23eab7a4457`：b724实际file-only重算与main完全一致，historical／whole／global true、P3胜P4负、errors空；4539终局→watch272@4541→Host结果4549 event709／STOP710→NativeSTOP4549／proof4550，9一致终局行→retire281→真实frame0／resettrue。4df正常final／proof／journal全true，helperseal／v9／438copies及428outerpins同，477输入稳定。9started／8真实完成，seq6事件456／snap226本地门拒、seq7事件506真实200恢复，6父子ACK，unknown空，32audit全早NativeSTOP，HostSTOP后无新增provider／dispatch；Game结束证书PID／rawFT／run同，不冒实际OS查询。

B `D:/CodexScratch/native5-formal-attempt5-14092-B-file-review-20261030-v1/review.json` SHA `137d12206f4bc2eb12ede9355913df068f8eddf305fcf021ddfe18310a26840a`：最小前置投影 `D:/CodexScratch/native5-attempt5-root-tool-projection-20261030-v1/tool-projection.json` 含14条已完成元数据，原source_index201 prospective append／ordinary→211arm→218GameStart→224session→231Hostrun→240running，不由afterpassed标签自证，也不新增beforePopen门。限定run只读DB两快照同，1launch／14commands／755events、未决0；32audit／16paired scopes在自然Hoststop前，之后策略DB0／Native新request0。9context／8HTTP／6父子ACK、原seq6无receipt／parent／Native，7–9真实恢复。strict工具缺GUI marker的unknown保其scope，不造自然GUI STOP新要求。A／C精确引用，原2／4失败不改。

A `D:/CodexScratch/ra3-independent-next/14092-attempt5-payload-GUI-A-file-review-20261030-v1/review.json` SHA `41d342b2873758623a6bb083400cdd19f27c3154ddd8a29bd36f1b25c68d4cd4`：9实际context／8接受和真实response，seq6local inputbudget保原，memory1536／context8602／记录wire15457B，后续真实恢复，无拒绝／超时；v9／ordinary840B／profile31-f94／EXE0b34／438sourcecopies均核。实际下载精确文件 `C:/Users/Administrator/Downloads/tacticore-diagnostics-17faa981-830c-5cb7-a0f5-0a62b5e2fa76.json`，440795B，SHA `819bcd9f0b23620cf58f83bddbbac14fe4012620f0b974ef3d1339a1089ac73f`，与归档相同；231events／303秒／last302.6，HTML数据相同且播放JS同首局，无新headless。已保存图与14completed工具顺序核，未返回MCP payload／未单存running UI文字均不虚构。各报告只授其范围，不单独签整个目标。

### 五类受控F02判断与确定性示例引用候选

B运输来源补件已封：`D:/CodexScratch/native5-F02-controlled-model-B-readonly-20261030-v2/review.json` SHA `9625aaf52f1cf49e3adb1c64fb88addf53d0e3eca39c4abfd5f1ced4d7411490`。五case各四事件，context实际字节／SHA重算、result与assessment逐项同，5次非注入expectedorigin／HTTPS／nonloopback200元数据三处一致；wire bytes／SHA仅真实BoundedTransport记录，原包未持久，不拿context／Plan冒raw重构。正常provider调用、无expectedaction代模型／transport注入／派发，8产品guard同v9及harness自身hash；额外factory／http／pydantic当前pin同，不冒现场全递归closure。29输入稳定，v1把diagnostic sortedset误当raw顺序的文档断言保留，v2只纠正报告集合范围，产品未改。

C来源澄清同语义报告目录 `loss-signal-producer-scope-addendum.json` SHA `11f84afbccc3fd3a20a2616dfb4f0c303da9d35a84d5be2feab5780f2cce0122`：knownloss人工fixture.after.events=[major_loss]走正常Snapshot enum校验及BattleAgent delta.game_event，非临时context加fact；publicrefs是敌可见步兵／己armor／credits。当前macro_live实际events固定为空，限查未证实机major_loss／base_under_attack事件生产者，不得把理解人工前提写成已自动识别实机确定损伤或受袭。resource／机会使用正常字段模拟值，noeffect为模拟supplier。root已同步该信息边界，并请主方优先选现成等价证据，或补两条events空、仅实际producer标准角色／敌情／资源字段的受控对照；不要求确定伤亡结论或逐类新实机局，不重算自然数。原五案及原语义结论保留。

主方封档 `reports/strategic-F02-controlled-model-v9-20261030-v1`：evaluate.py／simulated-cases.json／preflight.json／assessment.json，五次真实模型响应、0Native派发、明确模拟观测，不计正式自然局。C语义独审 `D:/CodexScratch/ra3-native-strategic/F02-controlled-model-semantic-C-review-20261030-v1/review.json` SHA `e64c45e311e478e59beed38b3bfdacb4178be6297fefd4a1c776e7f7a4bb72bc`：固定普通profile31及相同风格，无按case指定动作或定时指令。威胁4→20且基地受袭→防御紧急／防守任务+军备偏好；人工明确major_loss且己方4／1／0→recover_force／reinforce；己方35／12／6及5000资源、合法当前可见敌步兵1与经济建筑2→economy_window／pressure／进攻+军备，公开refs与事实相符。资源0选scout／stabilize／holdtier是合法谨慎选择，不要求固定经济动作／资源恢复或证明最优；无效果案读模拟waiting后不重复scout，选择经济意图，支持有限应对，fresh memory单response不能代替F04实机跨轮闭环。actualcontext不含literal simulation_contract字段，外层preflight／fixture/source明示模拟；不能虚构API字段或假实机。B运输／来源独审另行封件。

A容量修复仅D候选 `D:/CodexScratch/ra3-independent-next/prompt-example-ref-order-candidate-A-20261030-v1/review.json` SHA `59a05d087ed567329d76c5cd17e8b89a62a38cd609d6581d6de4886fc971c508`；同目录 `native_delegation_prompt_v1.py` SHA `afd9e13355b41a147e407a5f7e77b3cb2980365d26074f9688ef9a9f209a98e9`，`prompt.patch` SHA `3dbc434f6e56910a606ac892088c93a1e2e6fddaeaf0d865f228930d896f9d8d`。guard原prompt `91c1ff11224aed6885368f8cd014c53065e608bec5015532af4a06d51a9e222c`；唯一ref assignment改为已有非None own.credits优先、无则按现有key确定排序，空目录None沿旧形状不称可准入。实际seq5／6／7原dict与sort后prompt保持原准备文本、估算均16273／16379／16369；三必要fallback分支无输入mutation。16KiB／1536及事实、帧、ID、动作合同不变，0SDK／backend构造／网络／原源写，初CRLF候选另存保留，最终LF仅一hunk。root静读补丁后已同步主方，由唯一控制者按活动会话收尾、融合冻结及版本资格决定后续；当前产品尚未因候选自动改变，旧失败不覆盖。

### 第四次104244未计入与容量错误定位

run `7eb5e4a3-1c0f-40f7-a650-b36baac23d16`／session `ba02dc4e-ed9e-5a90-9e36-976a8ddcfa6a`，Host `acceptance/runs/desktop-e78d9808-a712-47f9-a90b-bb453eb0ac46/battle-host`，归档 `reports/strategic-formal-v9-attempt4-104244-20261030-v1`。主方登记尾链未确认、不计入，正常归还后关闭原游戏；正式仍2/3，后续登记游戏14092。主方另开展明确标为模拟的五类F02真实模型判断检查，不能算自然局或原生效果。

C `D:/CodexScratch/ra3-native-strategic/formal-attempt4-104244-C-closed-host-review-20261030-v1/review.json` SHA `6af2ae333ed22d3b98665f3fdeb32b8ef09fbfc1725415c133de64de6cacf3d1`：当前b724真实重算与main一致，historical true，whole／global false；215@3741首次bound，224@3857仍bound胜3741，225@3863 participants空且胜改3862，严格报unbound_tail_result_rewrite。226真实frame0保留，resetfalse系selector已停225。当前4df正常三项true，Host结果3747→STOP→NativeSTOP3747／proof3748、unknown空。C原JSON正确保seq6失败，FINAL一度误写第7；新附注 `failed-sequence-wording-clarification.json` SHA `fb602b75a9ed8f336273da0248f023f41a1dbbd45b64afb64ea06c7dac3584bc` 纠正为seq6失败／seq7 HTTP200，未改原评估。

B `D:/CodexScratch/native5-formal-attempt4-104244-B-file-review-20261030-v1/review.json` SHA `96bf35c4647801c0289e86dae09dc0fe06a2efef6d439e16ff7881b6c28b1373`：前一B冻结roster已登记4 launched／passedFalse／sessionNone，普通v9／profile31与首局相同；7starts只6真实响应(seq1–5／7)，3父子ACK，限定run只读DB两投影同，1launch／8commands／555events、未决0；22audit全在自然Hoststop前，之后策略DB0／Native请求0。失败事件的历史real_network_verifiedTrue不冒本次实发成功，不与尾部结果失败混同。B首次读取时Game结束／导出文件未封，按当时pending保留，不额外造门或改研究身份。

A纯字节根因报告 `D:/CodexScratch/ra3-independent-next/104244-input-budget-A-closed-analysis-20261030-v1/review.json` SHA `4e2c3cc86fabc863b2d46716dde71a3010b7acaad77506ab2d4e19487ceb0f9f`：冻结v9源码下实际seq6原dict估算16379B，通过外层；Pydantic run经encode_context(sort_keys=True)后估算16388B，超16KiB 4B。唯一prompt差异是按fact_catalog首项取Example ref，own.credits变capabilities.actions，prompt5527→5536增加9B。memory1485／context8601，不是1536策略子门；attempts5／responses5／max15466及代码更新顺序定位Agent／HTTP前local input_size拒绝，seq6无wire／未知送达。seq7真实200／wire15476恢复，不能将失败时max15466写成全局最终。仅真实七row的纯字节／AST检查，无backend实例／SDK／网络／Game／原源写；D harness初漏stdlib guard拒绝保留，修的仅D guard。问题与三路报告已同步主方；是否修新候选由唯一控制者按冻结和收尾流程决定，不热改或覆盖失败。

### 第三次103948闭局交叉复核

run `32938db1-63a4-483e-ba16-b2e6d4e0f3e9`／session `3549ea8d-b3af-5359-96b1-be23ac580b90`，Host `acceptance/runs/desktop-ea0e6e9f-018b-43cc-b3c9-f4ce5284f19f/battle-host`，归档 `reports/strategic-formal-v9-attempt3-103948-20261030-v1`。主方单局核验通过并登记2/3、关闭原游戏后启动104244；C/B/A文件交叉复核均已封审，不自行控制新局。

C报告 `D:/CodexScratch/ra3-native-strategic/formal-attempt3-103948-C-closed-host-review-20261030-v1/review.json`，SHA `ee0f80e8b369945b3b0324acc8df485e2981388d2fb26091fcfdca7b8b2229e7`：当前b724纯自然评估实际复算与主方JSON一致，historical／whole／global全true，P3胜P4负；4404原终局→watch210@4405／Host结果4405 event490→STOP491→NativeSTOP／proof4406，9条一致终局行后retire219及真实frame0。当前4df正常final／proof／journal三项true，v9／helperseal／源码一致；6请求6接受、4父子ACK、unknown空，22准入且STOP后无新增。只文件闭局审查，不冒称支持方查OS或控制游戏。初次独立runner局部变量NameError保留，v2仅修runner后封审，不是产品修复。

主方实际诊断下载精确文件 `C:/Users/Administrator/Downloads/tacticore-diagnostics-1867a0de-d2dd-5161-80f7-cf6ab54576e3.json`，329824B，SHA `85eab61ca6b03ee2c0a2c5560f15cc9e224c5bef54d8b4ab7ce22d80c052f7a6`；203事件／294秒。七条已完成GUI保存／下载click／精确归档／export工具元数据的最小投影为 `D:/CodexScratch/native5-attempt3-root-tool-projection-20261030-v1/gui-tool-projection.json`，供A复核，不将未返回的MCP图文结果虚构进投影。自然归还由原proof独证，不覆盖exporter局部字段或虚构GUI STOP。

A/B后续均已封审并同步主方。B `D:/CodexScratch/native5-formal-attempt3-103948-B-file-review-20261030-v1/review.json` SHA `2df59742993da76a4049e34577e51f3b8e1adfae76404ece29c50ce69295fdd2`：前置身份／普通配置成立，attempt2 B冻结roster已在本局通过前记其launched／sessionNone／passedFalse；限定run只读DB两投影一致，1launch／10commands／524events、未决0，22audit／11成对scope全在自然Hoststop前，之后策略DB0／NativeSTOP4406后请求0。缺GUI stop marker的strict工具unknown保其scope，不加自然finally必GUI STOP新门。A `D:/CodexScratch/ra3-independent-next/103948-attempt3-payload-GUI-A-file-review-20261030-v1/review.json` SHA `35b5bd1bd3372d220f2860ec6acb09169c68e5303e1996f21b20383e06219a25`：6实际请求／回执6接受，memory最大1536／context8572／记录wire15471B，无容量fault；v9／普通profile31／840B／EXE0b34／438源码副本匹配；精确下载与归档相同，203事件／294秒／last293.0667、HTML数据一致且播放JS同首局，无新headless。各自不越权授自然物理／总正式，三路共同补足该局不同证据范围。

### 最终提交的有界证据索引

B的F01索引 `D:/CodexScratch/native5-F01-final-boundary-evidence-index-B-20261030-v2/review.json`，SHA `c74c25a6a8d35a03d6bdc2ea14a4769abbf20421cd73289fb922313b9186b72b`，同目录中文 `index.md`。18产品源码匹配v9，目录／prepared／响应schema／Host最后门／controller／SDK／Native／stockconsumer分层索引；62660及104984共27实际context与15发布高层plan无精细参数。历史A24 CPU精细字段拒绝保真实版本及字节等同范围，104984两个区域拒绝不冒充实机精细恶意输入；未发现新精细派发绕过，不自授全部F01–F07。v1索引构建误将integration test当runtimepin的错误原件保留，v2纠正报告范围，产品未改／无新测试。

C的F02/F04索引 `D:/CodexScratch/ra3-native-strategic/F02-F04-public-judgment-index-C-20261030-v1/index.json`，SHA `7fbbdfba329e1d705566941b45a25159301101c0b843fe9d9972142dad8ef889`，同目录 `index.md` 一页表。62660的有效scout反馈→后续模型继续scout并引用native.scout，可与97968已封的expire→execute改assess／empty→mask0条件失效链互补；后者保v6研究身份，不拼成v9正式局。F02仅这些选定档案不能全勾：威胁变化与低资源对应合法请求有部分支持，角色presence18→14不能当确定伤亡，机会窗口尚无足够选定链。按canonical继续结合后两局及已有真实记录核对，不以赢局、低层守卫或私有推理替代公开证据，也不新增每标签必开一局／固定措辞要求。范围澄清附注同目录 `F02-scope-clarification-addendum.json` SHA `f0a79a22e5ef7faf440c3a0189272cbdc8a0fe1cede01f1e003ed1c939604e65`：F02核合法判断，采用／效果归F03/F04；资源未恢复或Host挡派发本身不构成F02缺口，选定材料不足也不等于证明功能失败。

A的F05索引 `D:/CodexScratch/ra3-independent-next/F05-final-minimal-evidence-index-A-20261030-v1/review.json`，SHA `78d15f8921e17ed9007d7b1c320901019c9c1c10f0f17a8d9da3617b14b69006`，同目录中文 `index.md`。逐步关联旧配置GUI及模块有限等同、50304自动接入／预检／启动／GUI STOP／实际下载／下一局、73204 v9真正Host失联后GUI STOP及独立归还解锁、62660实际后续入场及17真实回执。各版本及继承范围明确；自然finally不虚构GUI STOP，未单存RPC不虚构时间，debug不称安装包，丢失内存／exit仍unknown。未发现新阻碍，不重跑GUI／测试，也不自行授整体F05或增加正式计数。两个索引均已直接同步唯一实机主执行方。

## 2026-10-30 较早集成汇总（历史阶段）

正式仍 **0/3**。用户对直接同步协调的明确授权持续有效。主执行方已确认采用 F04／A03；已将 factory 与更晚完成 callback 见证接入产品。下文“尚待接线”“仅研究 callback”的段落是历史过程，不能据此否认当前实现。固定版本独审 `D:/CodexScratch/ra3-native-strategic/actual-callback-binding-C-readonly-20261030-v1/review.json`（SHA `f23d964f1eb62aa025d38562261b8aa225d641abfdc88bc7669e18d5d954f3bd`）覆盖实际 AST／1440 字节 Shared 的10项人工检查；不将有界顺序读取称为原子样本，也不替代现场复验。

最新已读 owner 为 UTC `2026-10-29T16:54:12.274027Z`、implementing、空冻结表、`last_native_release_verified=true`，last trial `desktop-d3aea588-682e-4d58-a8d5-1b2cd9ec473e`。主方登记正常 active GUI STOP 及完整独立归还通过，正在实现共享 durable-stop／publish admission barrier；支持方尚未逐件复核该最新 trial。状态会继续变化，任何源变更前重读 owner；本汇总不授权并行任务修改主方正在写的源。

随后 root 已固定该关闭会话的 session／Host status、events、release／Native final、proof、journal／build manifest／纯验证器九项原件，前后逐字节不变，重放完整 verified_final 通过；错session、截断journal、semaphore0三个负对照均拒。两次模型请求获接纳，Host 为 user_stop，macro_host_stop_started 之后无新 model_call_started／dispatch_prepared／plan_applied。报告 `D:/CodexScratch/native5-gui-stop-root-20261030-v1/review.json`，SHA `ff5c59b4a33e6f3d919f60881920e449acb9b8d67b4e6b88f8af29accd6d3451`。仅文件核对，不声称独立看到了GUI点击、held-manager停止或新 durable-stop 互斥通过，不补算自然局。

### 完成 ACK、停止边界与历史未知

91584 试运行共6次模型请求，Native seq／ACK 只有1–4；第6次模型请求对应 ACK4，不能称 Native ACK6。ACK 已发布而 callback active 仍为1时，严格消费者正确拒绝完整回执。主方修正为发布一次后，只读等待同 seq／result 的完成快照，不重发；B独审9项，报告 `D:/CodexScratch/native5-ack-completion-B-independent-20261030-v1/review.json`，SHA `edea06f7a0acbbedf4625d6e280d6e17842149151d79dad7eefab847f7211855`。轮询250ms是软等待预算，不冒称控制采样的硬250ms证明。独立归还可以解除资源占用，但旧 parent unknown 仍保留，不能倒填命令成功。

旧停止边界窄审 `D:/CodexScratch/native5-stop-batch-boundary-B-20261030-v1/review.json`，SHA `986101dc175ad1347bb6f445f6661536ba5d9f0e7f32662b354207f70018e6b2`，证明旧实现 stop.json 持久化后已入父批次仍可能发后续 child；旧独审器锚点却是 macro_host_stop_started。报告未擅自判定当前F06通过或失败。stop.json 以 session 绑定，不含 HMAC，不能套用配置事务的签封说法。主方最新已实现共享互斥并接入模型准入，正核启动接管；B仅只读当前固定源独审。不能把旧反例套成新实现仍有漏洞，也不能把简单 child 前检查称为无 TOCTOU 的硬零新增。

当前 B06／归还独审5项：`D:/CodexScratch/ra3-native-strategic/B06-discovery-return-C-independent-20261030-v1/review.json`，SHA `6bb4ebe0968efec7b12b13da87ae383d4b1a073591eca718bc981cc63bf8b4ec`。完整103756归还原件可解除占用，人工两条历史 unknown 保留不改；同 PID＋原始 FILETIME 的新局和原局都仍拒重接。新进程路径通过的只是准入假环境，发现列表可见不代表获准 attach；B06继续关闭。

### 接管前容量候选（D候选已审，主方开始融合）

合法1200B转义风格可在 prepared 的保守估算门被拒，不能据此称实际 SDK 已发超16KiB包。新容量预检 v3 仅D盘：`D:/CodexScratch/ra3-independent-next/native5-capacity-preflight-candidate-A-20261030-v3/review.json`，SHA `1b79a974141f92b984ec58b35013e77d0e5daff9615530b61c35ee6e1952cb5c`；补丁 SHA `0bf5b30c7965fa5ee956c9d0b1ca0f31e21ef988f152780c16ff9f58b6c07941`。它在 run.check 与 Native 构造前做纯容量检查，并核已应用 provider；模板不入模型、审计或 Native 观测，保真实后续 prepared 与16384上限。有限预留不保证任意后续情报／历史都能装下。

C固定候选重跑作者6项＋独立3项共9项通过：`D:/CodexScratch/ra3-native-strategic/capacity-C-independent-20261030-v1/review.json`，SHA `b47abb93a63de5e49ecddf63b1c29912a7f4d2204597bf623e793a7eedce68db`。无真实网络、密钥加载、Native 构造或伪造归还。保当前 macro_desktop58db 的 released()；主方后续正在改停止协议，若选择融合须重新核实际 hunk 和最新源，不用旧整文件覆盖，并重新冻结／编译／GUI验证。旧两次 guard 拒绝原件不改。

最新主方工具已显示正在采用容量v3：复制新helper为 `integration/host_runtime/native5_capacity_preflight_v1.py`，手工增量到客户端／Bridge／Backend／Host／Profile；这是主方进行中的融合，不是支持方写源。上文“尚未融合”描述的是已封D候选及其独审范围；最终实际组合、停止协议保留、软件闭包和GUI资格仍待固定后独审。

### 自然结算、时限与交付工件

结算解析6项CPU检查报告 `D:/CodexScratch/ra3-native-strategic/F07-settlement-parser-C-readonly-20261030-v1/review.json`，SHA `d92dc15ae742ac3993a6d3c15f7f8510dbbcff0468829ae28306c2291f8e007a`。watcher 的 natural_settlement_verified／winner_verified 与 read_match_state.match_ended_verified 是固定保守 false；不能把该字段单独当作结算失败，也不能直接改 true。分层 evaluator 为 assess_macro_natural_outcome_v3：PE pins、参与者映射、Host／可信视觉、完整归还及独立F01–F07逐层核验。

旧52600／103756支持历史 Native 映射 P3胜／P4负、生命周期归还；胜利管理器 +0xc0 的4是最后被击败者，不能读成胜者。两档缺相应 host_result／research-settlement 证据，不能补算正式。103756归还帧1634早于watcher首帧1850／终局5865，后续自然结束不证明模型全局在线。保留历史 false 与旧失败原件。

固定 Native 生命周期上限与容量另审 `D:/CodexScratch/ra3-native-strategic/F07-lifetime-C-static-20261030-v1/review.json`，SHA `3bbb003e9b5fb62f433b39b5bbab0efa9a647d8eb395e83d54341e94834b4c56`：Host最长3540秒、Native硬墙3600000ms、总请求2048／journal4096；两个 manager 共用128条 receipt、不回收，已满足的启停也消耗。单意图TTL不续全局epoch；这是产品限制及收证风险，不伪造成已经发生的长局失败，也不自行新增无限时长门槛。

A交付工件清点原件 `D:/CodexScratch/ra3-independent-next/F07-delivery-artifacts-A-20261030-v1/review.json`，SHA `5c9ef59a8026a8696a73a4e38eda12cb87ecd50ddc6d7d1764852c438da32713`。已封历史指针和缺口；随后纠正视频仅可选，不新增验收门。原计划要求离线过程回放，Native5全14动作／unified feedback 的可播放HTML增量正在D盘制作；原生 replay 后缀／hash 不能证明可播放。旧软件 export_time_files 及旧生产组件清单不能代替最终冻结 Native5 manifest；两个不同 schema13候选不能合称同冻结三局。独立 portable 安装仍属另项计划，不加入当前目标。

本段新结论和候选分工已直接发送主执行会话；发送成功只表示送达。后续是否采用及实际现场结论，以主方明确回复和冻结原件为准。

### 后续独审增量：普通启动到停止、诊断投影与版本索引

B在新屏障实际接线中发现确定缺口：`DesktopBackend._dispatch_launch` 的 capabilities 白名单漏 `native_transport_protocol`，真实 Journal 因而只留 native_macro；run_stop 却依该字段严格int5选择新锁，普通启动可能走旧原子写路径。固定 backend `5fa739baacc8b5e0b7f67c1dfe73a69c25e3b3fc029429dec55777035c6d4773` 等7源的真实早段launch／Journal／run_stop CPU反例，另一个子进程持同run/binding Gate.admit时，stop仍落账且guard内可见。原件 `D:/CodexScratch/native5-stop-barrier-B-independent-20261030-v1/routing-evidence.json`；明确准入资格及“已派发”的人工seam，0game／Native／model／spawner。这是新接线反例，不是旧停止窗口反例重跑；已立即同步主方。屏障本体原4＋独立7共11项另通过，不能覆盖或抵消该路由缺口。随后backend发生变化，A按guard停止受影响容量端点检查，B另封旧红并固定新源补审；不把WIP修复预先算通过。

该路由缺口随后已由主方修复并获B新v2独审通过：backend4f413d8e…d2d7正常launch保存protocol5，真实Journal／跨进程run_stop使用同name同stop_path的Windows mutex，批次持锁时不落stop，退出后提交完整run/binding stop，后续准入拒；协议4保原session-only路径。报告 `D:/CodexScratch/native5-stop-barrier-B-independent-20261030-v2/review.json` SHA `9a4512343201964ef4c273f15cad68472941a5f57743d2441353495736f06a2a`。旧v1红报告SHA `2cced983fd2d19981d3caa23cf9e48cc2f3590f59818758d0cfa1aeb155e7e11` 保留，不为旧缺字段行补认证。该独审不授完整F06／现场资格；停止生效锚点与已准入批次／provider请求的完成语义仍需普通用户流程公开说明，不能把GUI点击、stop文件提交、Host停止和独立归还混作同一时刻。

C确认 `diagnostics.project_plan` 旧显示白名单遗漏合法14动作中的expand及4个建设／生产gate，包含任一个时会丢整个macro_actions字段。最小D补丁只加5个显示label，保历史精细标签的旧诊断显示兼容；历史显示不授当前Native5模型动作权限。候选目录 `D:/CodexScratch/ra3-native-strategic/native5-diagnostic-plan-C-candidate-20261030-v1/`，报告SHA `0f4d911f25e3f385a9b639846a6da79046d6171398b7a84ba2bc0a830728b2ba`，源4d7f→候选 `8481e5fd71b1cc65cb897e466dcf28e891e9f05a72572d5f195dfc799609de31`，patch SHA `af91ee2dc109ab9bfe45fae0805681d0fb383d60d0df9d0b0385421e64375dd9`。作者4项过；root独审另外验证整模块AST只加这5成员、5动作混合、6非法列表拒、4历史显示不变、私字段和输入不改。root报告 `D:/CodexScratch/native5-redactor-root-independent-20261030-v2/review.json` SHA `8568b4d4744bdd2902b47e0b293ca55c60c4cc874caf75e0b12c5dd5787c4e11`。root v1误删所有expand字面量、连原stance枚举也删，harness失败原件保留；v2只在唯一含5新成员set做比较后过，不声称候选曾因此失败。均只验证macro_strategy=None的投影窄面，尚不等于整个导出／现场资格。

A时间线D候选 `D:/CodexScratch/ra3-independent-next/native5-timeline-candidate-A-20261030-v1/`，报告SHA `9113442ae14f69b8e88236baeb323a60b1973b9d3257e21aeda6f4fbf61e89ab`，patch SHA `d08fc6e8ffe380cff01fd47f30c028392bc7880ad59a8dd41416f4f08190109c`。6项作者CPU和JS语法过，保原observed_frame/t，decision不当ACK，waiting／adoption／already-satisfied／movement分开，未知不猜补，mission/exclusive不伪造；Native5 raw入口明确拒绝并指向脱敏诊断，历史路径保留。作者未实际浏览器播放；C正做真实redactor→timeline与独立headless播放验证，结果未回前不称可播放验收通过。该增量和5label投影候选均未由支持方写入主源。

root另完成只读冻结版本索引导出器 `D:/CodexScratch/native5-version-manifest-root-20261030-v1/export_version_manifest.py` SHA `af34260791dff937a619490fa54c8a87d6571cac2c7b8f2964b20c6a6d713d85`，5项CPU验证文档绑定、碰撞／重复JSON拒、脱敏、确定性、缺组件声明。只读显式schema13 candidate及受其pin绑定的Native build manifest，不打开pin目标、不授软件资格。关闭482ad914候选的1113pin示例 `closed-trial-version-manifest.json` SHA `9dd70e55ce1fe1d33258f63a9fd3114a45e0256c797eab148bfa3ea549516777`，明确新stop_gate与capacity helper不在旧冻结表；不把旧局清单称最终版本。准备报告SHA `16f313e2c350750f2460477ba465028112ec521e88362c5baa2fc98ce3e03a9e`。最终同冻结候选须重新导出并结合实际归档／绑定／验收；当前diagnostics.export_time_files仍只是导出时观察，不能替代该冻结清单。

版本索引随后获B独审8组与真实CLI通过：`D:/CodexScratch/native5-version-manifest-B-independent-20261030-v1/review.json` SHA `c7ca14cdd2c087fea9626d287db87cb8ab420d2de4e4ef7283ff2e9e81b541bb`。CLI明确两输入各读两次、输出xb一次，未读其他pin目标；Native manifest本身也是被显式读取的pin，因此旧文句“不打开pin目标”过宽。新 `D:/CodexScratch/native5-version-manifest-root-20261030-v2/` 仅改docstring及公开semantics两字符串，计算AST相同，作者5项回归过；导出器SHA `b3663cab920932b6bb7bee7441e8ed9daa8f337f347eba82f5bbeb9bf22f2a85`，旧候选新示例SHA `2861a8ffc50c0cfd3d1ee2a9ab5f41bb9b881e86e64c313328e6932c1ac2e3e6`，v2准备报告SHA `ac8224afdc49ee4fa3e84d16d25c84b9bcf24ffe99edd9e871b95a60998c5869`。v1原件不改，8组不追认为v2新执行；均不授正式／归档／现场资格。

容量实际融合部分独审 `D:/CodexScratch/ra3-independent-next/capacity-actual-integration-A-20261030-v1/review.json` SHA `b198b5200bddf4e385c8726a7a0e19d5b5cdd646d86749b3b6c5891684c1cdf0`。实际f9f720 helper／ProfileStore与固定93ad MacroDesktop／6523 Bridge拒绝路径通过，Backend从首guard漂移、Host／MacroDesktop后续变化，最新实际入口未补审。首轮Host被过宽harness socket audit挡住asyncio内部socketpair，尚未执行产品run，不能算产品失败或远端阻断证据。报告的helper_AST_exact_to_reviewed_v3=false正确；其note／早先消息误称整模块AST同，A已保原件并补 `helper-AST-clarification.json` SHA `f013fae07b5a1ca464254b35a2273ef007c119eec7c7797cf67333dfc048adae`：仅4业务函数AST同，实际Path/sys固定repo路径及相对contract wrapper初始化导入有变化，作为新实际闭包记录，不继承旧模块资格。

F06现场收证窄审 `D:/CodexScratch/native5-stop-field-evidence-B-20261030-v1/review.json` SHA `632e3be82eb848291098c8fe43c8936421c360d7e6ebfcf6fda6f7b82e35998e`，范围限定acceptance顶层strategic/natural与显式release模块。所见旧review_live硬编码旧run／9动作／HostStop锚点，Native5归还验证不查新durable提交后的准入顺序；当前stop UTC在atomic前取，Host相对wall／SQLite不同记录无可比commit点。缺新现场链不判违规，也不以旧d3证明新barrier。最小审查器设计在同目录reviewer-design.md，建议同锁受信审计序列／提交marker绑定／admission标识及parent-child关联；这是设计建议，不擅自增加Native ABI或新模型字段。明确允许先前已准入provider完成及真实STOP／baseline归还，不把任何mask0策略叫cleanup而放行。主方已获该缺口和设计。

C回放旧7174在实际headless浏览器复现末row不可达，纯精确float修订也因range序列化向下舍入而seek末端失败，两红原件保留。新v3仅duration取ceil(max真实t)，HTML不变，原事件／t／frame逐值同，末尾不足一秒是播放padding，非新增观测。`D:/CodexScratch/ra3-native-strategic/native5-timeline-endpoint-C-candidate-20261030-v3/review.json` SHA `ccd7cd2b62e73bd783b28aae0c29262264f9d7fa59d630d1374599ad29b8ee07`，exporter SHA `a4e620edf3bed7e9e2745656468ef575537af1ecc81a6b6d11770840abdbdfe3`。当前主方diagnostics已与8481五label候选逐字同；C新固定入口真实project_event→14decision／旧关闭103756公开schema，CPU12过，真实Chrome155播放推进／暂停保持／恢复结束／末row1508／seek末端／倒回隐藏通过，A正独审该最小增量，不冒称A独立审核其自写旧整体。

root另清点四个明确关闭的bcd／244／dc8／d3ae试运行，`D:/CodexScratch/native5-action-coverage-root-20261030-v2/review.json` SHA `d918c446b513f4f32f9607861d6889826f8aa8e6e4ad9e5643f8aecbab375c05`。仅这四档的plan／parent ACK只出现budgeteconomy、scout；其余12项无此类记录，不能据此推断全历史无证，也不能自动将response／ACK／feedback计数合并成模型效果链或正式覆盖。各档不同版本不可拼同冻结三局。原v1 inventory误把终态fault当faulted的harness失败保留，v2按真实fault/stopped读取；输入九件前后稳定，0实机／模型。该表供F03逐入口补证规划，不以动作次数折算进度或强迫模型定时出动作。

用户指引 `docs/desktop-next/player-guide.md` 已由root更新原生段，SHA `3a29c84202cc34a3c91f83db1e25a799bcb79749a99bf6d8c658cbd4a4607936`；A固定字节静读未见本轮容量／停止／能力措辞越界。旧168ebbad只标历史构建，新候选语义／三阶段STOP／同进程重接关闭／回放待审／debug非安装版／正式0/3均公开，历史浏览器演示段不变。原生普通GUI最终资格仍须主方实测。

A对C回放precision v3的增量窄审已封：`D:/CodexScratch/ra3-independent-next/timeline-endpoint-C-delta-A-review-20261030-v1/review.json` SHA `c2404573e37417a8dc2d647cde3b7754492d12cb6d48df738f9ff03a9c76e983`。5项覆盖8个人工时间边界，原1508帧／t不变、duration101可达、空／0／分数／整数／uint32保持合法，C实际headless报告及旧red证据hash／断言另已核，A未另开浏览器。只审C一表达式增量，不将A自写旧候选称完全独立；尚未由支持方融合。采用应取C目录 `patched/acceptance/export_macro_timeline.py` 与对应A原HTML9262，不能只把endpoint补丁套到未加Native5功能的旧1d429源。

主方之后生成 `acceptance/runs/desktop-fe19ebfa-4918-4063-af5c-9683e5c43e80/unified-schema13-v2.json`。这是新的准备候选，owner仍implementing／空冻结，非已计正式局。A依此明确pin准备补实际容量未审差额，C转审新 `strategic_no_attachment_v5.py` 的启动前未接管证明与finally；所有检查均只读固定源／人工CPU。新cleanup可能为独立未接管证明打开只读Memory，不能误将“未构造publisher”说成“不读取进程”，也不能将测试fake collector当真实归还。源再漂则停受影响项，不改旧报告。sole控制者仍负责实际Memory／游戏／模型及正式排程。

A随后对该v2候选（SHA `a418fed8997f903538762cb776406bbb310aa61264e7566d1d1b01166b504974`）严格pin guard在产品导入／CPU执行前拒：Host expected7609959684ef73f2a039446da31949cef9971857bff6f4eb130e71d4cec84691，actual2067c4764c2e4661c7e76d3e69af515204f6db7710fa592d5f06be813d04d206，其余7目标匹配；0测试、未调用fake collector，不重定guard。A封存拒绝后待下一稳定冻结。主方同时实际新增 `strategic-admission.jsonl` 有序日志，已读gate SHA `f3d53243c0d2261665578418e36481dd27b528c32e677ea0407ca78bdc945f56`，B转审实际新实现／调用点，尚不授资格；旧“缺现场可比链”报告仍保其时点。主方明确正在补新锚点收证，故不把实现中的准备候选当最终冻结。

## v3冻结后的实测与补验 · 2026-10-30

唯一控制者已采用回放exporter `a4e620edf3bed7e9e2745656468ef575537af1ecc81a6b6d11770840abdbdfe3` 与HTML `9262d090c6fe6cc45b5880fe8142676d1ce2323615af1173d0dee7a1db69f7b9`。冻结候选为 `acceptance/runs/desktop-fe19ebfa-4918-4063-af5c-9683e5c43e80/unified-schema13-v3.json`，SHA `d0fe3fe13957e2ab4d225257403f20160e67505c7b77a061dda93d848da3434d`，1116源。所有支持方只读或写D，不改冻结源。root当前候选的公开预期版本索引为 `D:/CodexScratch/native5-frozen-trial-v3-version-root-20261030-v1/version-manifest.json`，SHA `29d569d4f73ab0f360634281fd788649bf38e4082e34ef8be887c3b22ab886a8`，含新stop／capacity／callback，EXE预期hash `48de48f40ffdd5f07f7203aa8476ecb4bb072cda7cb7e0625be2f1c9338e26b4`。它仍仅是声明索引，不授正式、当前文件全验或归档资格。

A实际容量v3补审已封：`D:/CodexScratch/ra3-independent-next/capacity-actual-integration-A-20261030-v3/review.json` SHA `2478fae011d47e7212ba153d0f6d295f8a3ab157b02f007d698708482ca49e87`。4项CPU，9目标前后match、79实际production模块导入对candidate pins，另1纯测试夹具单列hash；真实Backend check/start与Bridge两safe码、whole Host在Native module spec／publisher之前拒容量均已补。fake只读collector明确抛未决，实际finally保持macro_stop_unverified、没有伪造release或Native-stop journal；collector真实条件另由C核验，不把fake当归还证据。0目标OS／游戏／SDK模型／provider／网络，原b198／f013／bde2历史不改。

C发现旧capture(None)在try前Memory构造异常可能漏只读handle（Open1/Close0），原18项窄审 `D:/CodexScratch/ra3-native-strategic/F05-no-attachment-C-independent-20261030-v1/review.json` SHA `6a6998c6f8ed9ec4307ad7eb99f8171c902fbb96dfd1f85cbb28eb55de48d2dc` 保留。主方局部先保留__new__对象再__init__、finally清理，当前no_attachment源 `33cd1b3f260700822fd34958a88c5d3c4b57ec76cc04c33905d90f3aabfef301` 的8组delta复核通过，报告 `D:/CodexScratch/ra3-native-strategic/F05-no-attachment-C-delta-20261030-v2/review.json` SHA `e56e3b4f4f11740c2f2b6d98686cb1c1b7eaa1bc16aaf7129e80ead178f0f1c4`。成功FakeClose条件下构造后失败Close1／handleNone，owned与borrowed、原异常、未知对象拒绝均保持；不冒称全SDK CloseHandle异常安全。无接管证明只覆盖同OS/EXE、双模块／命名对象缺席和冻结无constructor历史，不声称核了当前Game／P3根，不声明manager已恢复。

C当前observer c321的9项等待delta复核亦通过，`D:/CodexScratch/ra3-native-strategic/native5-observer-c321-C-delta-20261030-v1/review.json` SHA `59f2f49a49a3be748282f11d6e3d039df3950f202192bcb4b8713f4c4ee6245e`。静态比较自有旧21e48原件，仅3hunk使busy等待及末尾采样共同受原250ms deadline；200ms等待＋51ms尾读取、3frame、当前Game／OS身份漂移仍拒。strict-later仍在controls，非factory新证明；只借AST确同的transport方法，其他apply／receipt变化不重标。相关8pins与d0fe相符，0实机／源写。

B新f3d有序记录器13项必要CPU期望达成，报告 `D:/CodexScratch/native5-ordered-admission-audit-B-20261030-v1/review.json` SHA `1d0e4b0a9da17bba7ba218c3a8c41961d8685d4dbb493e04ab8cde41126be30b`。运行时只验尾行，不能自证旧prefix完整。独立whole-log新D候选v3检查全行严格JSON／连续seq／binding／marker与状态机；缺坏链unknown优先，完整后停新准入contradicted，正链仅ordering_verified。候选 `D:/CodexScratch/native5-whole-log-order-B-candidate-20261030-v3/review_ordered_admission_v1.py` SHA `1edae21a8a25741cc9f7a10f7039fcb4fc26460272ad74bc9e7402e7a7bb99e9`，freeze SHA `fac3171754c32ab1e7400104ac8bd5b895872a96247db398abf553c8d6f241d8`，B16项及真实跨进程人工日志CLI通过。root独审 `D:/CodexScratch/native5-whole-log-root-independent-20261030-v2/review.json` SHA `3558056393ed309e74d3dc9d6e19ce1ebb6ec348e492326ad8985e296ae27b8d` 通过；早v2允许可选application终止行先于started却linked的观察原件c79ec保留，新v3仅收紧2行，正序linked／逆序unknown，core audit结论不混。无prevhash为实际schema事实，不增硬门；来源真实性／未截尾／Native执行／归还／F06都不能仅靠该日志或parser证明，admitted fsync失败可能body0，不授权重试。

主方已完成65352的普通GUI早期停止，关闭会话 `desktop-0f6f848d-1db6-4e67-96ce-1651cd479e7d`，run `e27a60d8-eb0a-47b8-a902-ee03e52aff68`，真实模型0、未构造Native。root仅对该关闭会话的实际audit／marker／Host events纯CLI校对：stop_committed seq1→native_constructor admission_denied seq2，admissions0、ordering_verified；5输入前后hash相同。报告 `D:/CodexScratch/native5-early-stop-order-root-20261030-v1/review.json` SHA `7a38d4df818f17ac69eabafabbec4f203751654cf0cf881932ef518f309174d1`，只证明给定记录顺序，不作held-batch STOP、日志完整真实性或全F06通过。A正复核无接管证明、限定旧run账本及具体下载958efb75…26691字节，支持方没有独立看GUI点击。

另有旧91584闭环记录关联复核 `D:/CodexScratch/native5-feedback-loop-root-20261030-v1/review.json` SHA `818b3a23bb247a69c34294eaeb68c2d39ec52f03e1b5057da7a8ece3650139e4`：request4等待→同snapshot execute/scout/ACK2→原移动3001帧在域窗[2896,3301)→request5带moving3229及memory effect_observed→同snapshot assess/空vector/ACK3，context bytes/hash与真实响应回执匹配。未重新解码全部合法原生根、未重建raw wire；额外意图撤销不等于撤原生已提交任务。后续第6次模型请求／NativeACK4的parent unknown／Host fault保留，不补算正式。

主方当前转入95916的非正式高层入口分项联通，由真实模型从合法观测选择尚未覆盖的兼容意图，无分时脚本。该研究局仍不计同冻结三局自然验收，正式0/3；新游戏状态与现场效果只由唯一控制者登记。

A已封65352早期取消文件独审，`D:/CodexScratch/ra3-independent-next/F05-early-GUI-stop-A-file-review-20261030-v1/review.json` SHA `6407ccbab08200c2e2ba3cf67dc124828e94f40c7ec638e3a0bc1174b4df71e2`：两个实际DB以mode=ro仅查指定run，host_start／host_stop completed、macro_policy_stop released、0未决；436冻结copy／明确构建4pins、当前纯verified_capture重放Host15ms／独立32ms证明、真实26691B下载与归档及server export逐字hash一致。17账本event及脱敏投影链吻合，不读配置凭据、不执行归档／SDK／目标OS／GUI。只支持该轮启动前取消及诊断下载，不授全F05、attached Native STOP、manager恢复或正式局。

root使用当前实际exporter CLI从该下载生成 `reports/native5-early-cancel-timeline-root-20261030-v2/`，唯一来源SHA `b83d1cfacfc505b922654ebcbac3dedc1a574a0ac9e4bef410e5f151e55084ae`／26691B。两row为strategy_state与stop，t104.8、duration105，未虚构模型方案或单位动画。HTML SHA `8b1b98c107c9b3fb770ab7b327bd6f2b858b4b6182cf6ecd9d98cf26834c13b4`、JSON SHA `ed8bbcc1c3e42940ca169140d509863a5ff617d20740a24abdfac12ff61a81df`。首个D output被actualCLI的reports根guard正常拒，失败 `D:/CodexScratch/native5-early-cancel-timeline-root-20261030-v1/failure.json` 保留；随后用合法新reports目录，不改guard／任何冻结源。此为新增独立产物目录，前文“只D”指实施候选和测试，未把产物写入冻结源码。

C对这份实际下载产物完成真实headless检查，`D:/CodexScratch/ra3-native-strategic/native5-real-download-headless-C-20261030-v1/review.json` SHA `4d3e42edc43486a114aed058613ac42375cd682b0c49b72a65c1f63e0f1a6669`：嵌入payload与JSON同、文件前后不变，实际rAF／暂停保持／恢复到105／seek两端／两row显示，0JS异常。模型计划0、release／fidelity／formal／effect均false；末0.2s只是播放器留白，不计额外观测、自然局或完整游戏回放。只用自有headless／loopbackCDP，0用户GUI／目标游戏查询。玩家指引新增该本机早停示例，当前SHA `6ed7a9e0d53e0e1119de12cba79477483dc0aa5c3e165593779f7127c8c580f2`。

95916分项局后亦由主方停止并核验归还，closed trial `desktop-38d78193-db90-41c2-ae85-4295dd7359b5`／session `81859db7-2c2e-5d64-9ff3-4f217d387444`／run `6a9e9232-90d5-4839-998c-271027df9789`；B仅该关闭原件审查，不读后续活动局。主方保留战略ID拒绝失败，说明新战略用null、保持用现有ID后重新冻结，校验规则不削弱。B初步看到10请求／10响应／2accepted、其中仅1scout真正派发，另有strategy_objective_requires_new_id拒dispatch；这不是14入口或正式局通过，完整关闭局独审尚待封存。

B关闭95916文件独审及真实账本附核随后均完成，原v1不覆盖：`D:/CodexScratch/native5-closed-95916-B-file-review-20261030-v1/review.json` SHA `94c454e048f9c81c22eca04f6e03860b47349dc94a0e9500bcd79139c97fef51`；`D:/CodexScratch/native5-closed-95916-B-db-addendum-20261030-v1/review.json` SHA `3521428d5ea69f816ce5b5c64005ec6a939f4b5488befd6252f20f72d512c3d7`。actual25行ordering_verified／10个provider ID关联，Native final／proof／journal纯校验及Host release hash一致；436副本只426匹配outer1116pins，另10本局元数据／额外legacy源，不冒全1116归档。1scout parent→uuid5 flags child seq1／ACK active0，batch admitted→SDKprepare→receipt→finished→stop commit绝对mono顺序成立。仅mode=ro查指定run的5commands／两个run-launch绑定／selectedevents，前后投影同，10 model_call_started皆在其admission scope内且早于stop seq25。host_stop是请求回执false，macro-stop是released／proof true，两阶段不混。uncertain[]，未提升为全F06、14入口、效果或自然局。

主方随后v4候选 `d989e9e98c85022e9facd11731e8436c1afb988c779038dc2143beef627589d6` 在28728／session `7b1fafbf-c943-58a9-81ba-256e40978b27`、closed trial `desktop-56f7f940-9c2f-4aa4-9fab-362040cf0385`、run `20638dd2-0c8a-417d-a171-6a579ca1b2c8` 发现真实strategy_context_budget失败。主方报告8请求／5accepted／3实际parent（scout、budgetarmy、advanceconstruction）、独立Native归还通过，原fault保留，不计自然局。问题定位为完整strategy.context预算：压缩之后追加missing_basis_refs等metadata，不能称实际SDK包已超过16KiB。修订只将元数据提前纳入同一压缩预算及移除后置补救loop，保1536策略门与16KiB总门，不削弱身份或执行规则。

已读新v5冻结为 `acceptance/runs/desktop-fe19ebfa-4918-4063-af5c-9683e5c43e80/unified-schema13-v5.json`，SHA `5e0c005cfa70e0d0e1a36a6b9dea65ea94cdfc8e6e1e94c1407cb22a9993ea50`，memory `d311ec5eed8b9abdd6377120b7a7f602887e9626c89de1161bba2a7bc3f20d4f` 与ownerpin一致，主方73592重新多轮验证。A先前只读WIP／保存closed数据，没有执行旧归档代码；现按明确新freeze补最终payload端点、当前strategy／必需basis／unknown guard／Native事实优先、实际1536 caller和SDK估算连接的独审，尚未返回结论。任何源漂即停受影响项，旧fault／guard拒不重标。正式仍0/3。

A该v5压缩独审随后通过：`D:/CodexScratch/ra3-independent-next/strategy-context-budget-A-review-20261030-v2/review.json` SHA `5efd3c0697c147702e9e57649122953d4ac00eb89da145b7004a4ab33e8d80b2`。五项必要case包括完整core1105B接受／1104拒、缺basis及unknown／guard保留、实际Audit1536接受／1537拒且backend0、context之外Memory函数AST同closeddec1。实际prepare→SDK MockTransport软件组合保持snapshot275／time266.2／feedback3992，memory1479B、prepared8567B、body14509B、估算15412B，0外网／真实模型／目标OS／Native。它明确使用closed postStop公开memory＋原request/snapshot软件组合，不冒原faultstate exact重放；主方另已重放原正文1520B＋元数据后1544B、修复后1352B，二者范围分开。40实际repo执行源逐个和末尾按v5pin核，第三方另hash；旧夹具失败保留，1536／16384不扩大。

C F07实际Host-mode兼容窄审：`D:/CodexScratch/ra3-native-strategic/F07-Native5-host-review-C-20261030-v1/review.json` SHA `251695f3ed9d04c3f2d4c9e5e66c5e82482f8e2475f99ecc67d46586f1905aa3`；组合接口设计同目录 `combined-review-interface-design.json` SHA `fbcd9dc733223f5b3c8504d658c1c624ef30d795e7e0276a014e00037099e6d3`。7定向文件／当前AST case确认：outcome_v3 Host-mode结果子证明无旧flags限制、可消费Native5 watch schema，Native5独立归还函数可消费closed实际结构；旧综合natural_release／desktop经旧trial先缺preflight、补旧prefix仍因13flag拒Native5十flag。outcome_v3不查Native final／proof／journal、真实provider和完整Host在线，固定fullG7／formalfalse是范围声明。最终需明确合并自然结果、同冻结参与者、真实合法模型持续／保持重评／STOP链和Native5完整归还，三局另聚合；缺证unknown，不用旧研究补数、不把子green或scopefalse当全F07结论。

当前PE原件精确总数为14项＝13条指令site＋1个vtable，均与原EXE匹配；前文“13PE pins”是较早简写，不能拿13当总项资格门。C的首fixture误数13导致的失败原件保留，新入口按14总／13指令检查。当前MacroSampler仍在snapshot→inspect／registry／verify_two_ai后检查presence，ownAI先退役的假序列会先fault，正常根可到result candidate；仅边界，不宣现场必败。最小组合设计允许正常入局预检／预热，不要求frame0发令，也不增固定时长、视频或完美原生录像保真门；新审查工具本身不阻唯一控制者并行采自然局，原始视觉／replay／下载应分局保留。

C另封 `schema-clock-addendum-v1.json` SHA `75b6e2ac6ca60b9094fa2ef09842de72a189d5f1922d479513ade57ca7527f0c`（同F07目录），原2516／fbcd未改。实际Host.freeze有独立profile.json、不在sources rows；draft按sources定位commander-draft副本／hash，不以固定索引或当前用户库替代。Native5 attach_prepared／attach_acknowledged确在Native commands.jsonl，ACK可能active1，不是已完成callback／效果证明。时钟必须区别内生raw[2]/[3]胜负firstframe、watch首次采到的simulation_frame、Host result-native-state／journal最新frame以及独立cleanup帧。Host可能较快检测并返还，不能仅因return早于watch下一poll就拒自然连续性；以真实内生结果和来源绑定证据交叉，缺项unknown、不猜固定最大gap。旧103756的cleanup1634仍远早于内生5864／watch5865，不能用poll延迟消除旧早退缺口。无新增形式门／测试次数／正式计数。

## v5多轮与自然结果研究的实际原件复核

关闭73592：Host为 `acceptance/runs/desktop-1054b323-94a5-4bb2-9759-67337e6785df/battle-host`，run `88b570f9-7003-4e42-86df-77cb72638c81`，归档 `reports/strategic-unified-natural-product-73592-20261030-v1/`；同冻结5e0c。A现场记忆／传输文件独审 `D:/CodexScratch/ra3-independent-next/73592-memory-wire-A-file-review-20261030-v1/review.json` SHA `353d161a03cebd0924aaf4fa683e4e58743fbbbd1c7a4ab9a434a73d364a73f1`：7真实context最终bytes／hash逐一相等，strategy memory为648／647／1523／1507／1507／1507／1535B，均≤1536；context最大8680B。7份记录的真实SDK传输回执逐sequence／snapshot／time一致，wire最大15459B≤16384，expected origin／HTTPS／完整200／非注入；只核原件metadata，不重构原发包体或执行SDK。req3–7同strategy ID及必需facts逐值保留、missing0、history0→2与lastoutcome保留，无预算或context故障。unknown／missing分支未在此局出现，不补覆盖；可选Native facts在部分轮被裁但原feedback保留，不把“可选”改成必留门。

该局真实下载为指定e78f0967…文件，324979B，SHA `37228…`（完整hash见A报告），与归档逐字相等，518条脱敏timeline hash及Host原件索引同；现有过程回放187 events、duration251，此处仅metadata核对，未重跑播放。436 sourcecopies／5e0c／d311和相关6当前pin相符。0产品code／SDK／目标OS／GUI／model／DB执行或原件写；本A结论不授Native归还、自然或正式资格。

C对两局实际自然子证明复算已封：`D:/CodexScratch/ra3-native-strategic/F07-two-closed-natural-C-20261030-v1/review.json` SHA `440c6743dc981cd1b72a9497e9bebe51915e0b9f1b7fad8da86e70dba4bed20a`，详情实际路径／archive／visual／replay／download pins见同目录summaries.json。current outcome_v3.file-only重算结果与主方原assessment逐值相等，而非读取passed布尔。73592 historical／whole／global natural均true、errors[]，Native5独立返还重放true；内生胜负帧3751／watch首见3752／Host结果snapshot3760／cleanup3761／proof3762，最后合法feedback3752及7请求／响应相连，非旧提前归还后等原生打完的情况。

另一关闭86484 run `88824622-9ef8-495e-8df6-d61f6181a9af`，归档 `reports/strategic-unified-gates-expand-86484-20261030-v1/`，同5e0c，Native独立返还true；历史P3胜／P4负映射true，但严格whole／global natural保持false／unknown。精确原因 `unbound_tail_result_rewrite`：原第287行frame4637仍有P3／P4，第288行frame4652参与者已空，胜利槽内生帧从4530改为4651；第289行frame0实际存在，不能写成“没有reset行”。该局内生4530／watch4533／Host4538／cleanup4539／proof4540，visual／participant／source子项真也不能抹未知tail。10模型调用仅8个response回执，另1失败、末1pending不补成功；minimum_hold保持原件不改。

两局实际profile revisions23／24的custom_traits均明确分项研究且不计正式，formal_candidate_match=false／formal0，即使73592自然结果子证明通过也不回填正式。C只执行当前file-only函数，未执行归档review／end脚本、未读当时活动13968、未采目标OS／SDK／Native／model／GUI，全部源码／原件hash尾核同。主方继续同v5在13968验证两个调度门的暂缓／归还，另将显式advanceproduction单独补验；撤销额外意图回基线不替代显式推进生产入口。

## 调度门持有期间的实际STOP与用户文档

13968 closed trial `desktop-7c0b5cdd-4042-4423-8ecc-dc46e7082f6d`／session `a7e30f52-52ac-552a-9363-b537f0b95711`／Native run `eb2161c3-ac65-4472-9925-f433524e136f` 已获B独审，`D:/CodexScratch/native5-held-gate-stop-13968-B-file-review-20261030-v1/review.json` SHA `75ff65de26a102197e6b608cfe64d2f30ad5ab4477cb7919b28dcd75cd079fe7`。先固定status stopped／user_stop与release true，才读关闭原件。wholelog19行ordering_verified／provider ID关联、当前纯verified_final／proof／journal皆true；22条1360B Native二进制审计按固定i386 offsets独立解码，与SDK sidecar语义一致，未import／执行SDK。

本局3个完整parent是双pause→空vector释放两gate→双pause，9child。最后controls3034–3035帧三组件皆0，gate held＋baseline captured；STOP trigger2于3043帧开始restore，own component index均回baseline1；两gate deadline3090且wall未到，支持实际STOP恢复而非TTL过期。最终三组件1、flags清、Hook／lease归还、Host ended0；真实DB3parent／9child completed、admission UUID与Native seq1..9和stop顺序一致，限定run的两次readonly投影同。SDK seq8／9原缓存active1保留，完整parent ACK按已冻运输的只读completed等待语义核，不改原件或倒填旧缓存。

该结论不等于“游戏暂停时STOP”：186份实际snapshot Game.paused均false，physical STOP瞬间没有直接字段，单列unknown；调度门pause与Game.paused分开。中间空vector的release4／5只是回原baseline，本局没有enable／advanceproduction，不能合并入口覆盖。5model started只有4response，第5terminal未证，不补完成／取消。0新场／目标OS／Memory／SDK／Native／model／GUI或原件写，不升全F06、14入口或正式自然局。

root已确认README不在活动冻结表后更新其当前状态，`README.md` SHA `e30ae5b37eb66fa9ea4e5d92387b66e812bf28aa4d784a14edb3eca2ddad792b`（此前9bff…）。改为10/30 Native5十四高层试运行目录、已接调度门／扩张偏好、真实普通客户端分项、研究自然结果与严格unknown范围，正式0/3及旧G0–G8／schema9历史不变；旧168ebbad只历史预览，当前使用按冻结版本清单。新安装版／跨机未冒称通过，无stage／commit／push或冻结源码变更，已同步唯一控制者。

## 显式推进生产与v6区域说明

97144已关闭trial `desktop-a6ee3aab-8338-4752-bb06-0a20e5b662e2`／session `665064ca-0982-5f72-8091-d19a5ffdcadb`／Native run `3afb8e24-0e5d-4338-a053-34fb5093dc3c` 的显式advanceproduction独审完成：`D:/CodexScratch/native5-advanceproduction-97144-B-file-review-20261030-v2/review.json` SHA `64afdc2ee4b4f64851d62a47b8d39e6691dc470bbc1902addde764a2834f7254`。16context hash／bytes核对，四个origin=model plan由snapshot113／179／357／457对应request6／8／14／16，联到declared strategy、真实DB parent／admission与四次gate1 enable(enabledTrue,releaseFalse)，另四个flags child，共8child／Native seq1..8，均非13968的release路径。

四个enable均为already_satisfied1／attempted0／observed1，证明显式入口和已满足状态反馈，不证明0→1改变、队列或产出。441完整controls在各有效窗读回生产两组件1，另4份controlsNone保unknown，不声称连续全覆盖；90条adopted＋alreadySatisfied、150 released不当mission。wholelog43行ordering_verified／16个application关联（14response＋2failed），18条Native binary独立struct重放、sidecar、current pure final／proof／journal、Host release一致；限定run readonly账本两次投影同、unknown[]。436capture仅426匹配v5／5e0c的1116pins，另10独立解释，不冒全归档。原16req／5accepted／2adapter_errors／9rejected、区域ID／policy／pairdefer拒保留；v1 harness误把controlsNone当dict的失败原件保留，新v2显式记unknown，非产品缺陷。0原件／当前场／OS／Memory／SDK／Native／model／GUI写查，不补余四入口、全F03／F06或自然局。

主方为余withdraw／reinforce／deploydefense／deployattack四入口重冻v6：`unified-schema13-v6.json` SHA `cb911b655b64da4992352c04f70f3604ae5fca4ec2e9d39b728fe7762820fbdd`（同fe19目录），1116pins。root比较v5→v6仅legacy-schema9声明路径替换，唯一执行源变化为 `strategy/native_delegation_prompt_v1.py` 6b9160e0…→`91c1ff11224aed6885368f8cd014c53065e608bec5015532af4a06d51a9e222c`；物理合同／Native输入未据此改动。A只D独审trusted RegionMap与既有offered target／allowed regions一致，无新增坐标或单位权限，并重测额外文本的SDK容量。

A初测将closed73592旧prepared contexts直接套新v6 prompt时，保存883B风格的SDK估算seq3／4／6／7为16529／16387／16430／16454B，部分过门；legacy重新编码body最大15627B仍未超16384，0发送。这只证明prepared不能跨新prompt复用，不是fresh prepare失败或实际已发超包。数据在 `D:/CodexScratch/ra3-independent-next/v6-prompt-region-budget-A-review-20261030-v1/direct-saved-context-measurements.json`；A继续当前fresh prepare／原有压缩链，核保原帧、当前ID、必需facts及unknown后能否合法装入，尚无最终结论。绝不放宽1536／16384，也不追活动源漂移补绿。C同时整理14入口分层证据矩阵，当前新场只由唯一控制者处理，正式仍0/3。

该v6 fresh链随后通过，报告同目录 `review.json` SHA `2fe5da97a8fc852c4bdd0c0dcfd47f06bc8bf0b74030107c60e0ad2f505940a8`。当前prepare真实触发现有压缩，两个明确软件组合snapshot72／time151.5333与snapshot211／time226.4，初始SDK估算17980／18603→最终16259／16371B，实际MockTransport body15357／15469B，memory1474／1535B；原observed frame／status／currentstrategy对象及必需fact值未改，unknown变体仍unknown／guard且0send。3测试方法含实际SDK两组合与边界／authority；41实际执行repo源按v6pin前后相等。RegionMap5项（含reinforce）确取offered restoredcatalog与已有allowed regions，未改physical validator／scope／grammar，未给expand或gate坐标。旧prepared估算超限不等于fresh失败，初测原件不改；最紧SDK余13B，仅说明此组合可装，不能保证未来任意style／反馈，现有逐请求硬门仍须保留。0外网／真实model／用户库／目标Game或OS／Native／源码写，不授剩四入口或正式资格。

## 观测模块与 caller

`native-ai/strategic_unified_observation_v5.py` 当前已融合到 SHA `269291a25374585537291ba8c693f016544e2a07557556dba35fdecc25d8b7be`，保留主执行方新增的 `object_ids_resolved` 行。修正了尾部慢读取漏计时窗，并封存 Game／engine／己方身份，在采样时核对当前 PlayerManager 的唯一 slot3 挂接。

构造必须传 `caller_binding={pid, process_creation_filetime, session_id}`，direct sampler 必须传 `expected_binding`。调用方应先真实认证借用 handle 的原始 FILETIME／会话；字典与 `Memory.pid` 不是 OS 证明。模块明确输出 `actual_OS_identity_verified_by_module=False`。当前 Native5 Probe 构造已做精确 raw FILETIME 核验，不能只依赖旧 Memory 的 start_time 容差。

融合时尚无实际产品 caller；主执行方之后新增了 `integration/host_runtime/strategic_unified_transport_v5.py`。最初三参构造会 TypeError，随后已自行补入显式 caller_binding；不要继续把旧签名错误当作当前状态。仍需核对 observer 的 seal 与 Native5 不可变 binding 相同，而非仅各自看似有效。

融合记录：`reports/strategic-unified-observer-binding-A-integration-20261029-v2/review.json`，SHA `7343eca6e4372099aef37105c4dc5adcdf73547480f8e7e865b9d8e50b063af5`。

## 只读 factory 已完成离线修订，尚待实际接线

新增 `integration/host_runtime/native5_strategic_observer_v1.py`，入口 `create_native5_strategic_observer(probe)`，保持 `.identity`／`.sample()` 接口，借用同一 admitted Probe 的 handle／kernel／不可变 binding，不新建 Probe、opener 或 WinDLL，不派发或调用模型。

首版 SHA `4ccd1d3e…` 的11项作者 fake 检查通过，但独审增加了一个确定反例：内层采样完成后，最后 OS 查询期间 current Game 被替换，末帧仍来自旧 Game，错误返回完整。该版未接线；红色原件保留在 `reports/native5-strategic-observer-adapter-A-independent-20261029-v1/`，报告 SHA `8be5533188e74bc3c0a97a7cd94333fd3bdd09a68eb8da341c034bb214a4d9d0`。

修订在尾部 OS 查询后重核当前本方根链，将全部尾读取纳入时窗；19项独立 fake 检查通过。随后仅对 phase1 观察允许正常 callback_serial 前进，拒回退／回绕／耗尽，其余控制状态仍严格相等，保留实际 Native 后续回调归还规则。28项纯 fake 检查通过，当前源已受限融合为 SHA `86edf825d0cd8e55f3a5ea27872f8f8d120a32112e928405245d03b227713bb5`。记录 `reports/native5-observer-serial-A-integration-20261029-v1/review.json`，SHA `a0c3d799ee80627291cc6c59ab72b2b401e86ef0d69185681a75bde43f0a7912`。

API仍为 `create_native5_strategic_observer(self._probe)`。可选两行替换补丁位于 `reports/native5-strategic-observer-adapter-A-independent-20261029-v2/optional-factory-wiring.patch`，应先核当前主运输版本再采用。本任务未改主运输，未实测此 factory；必须将新源纳入软件 closure 后，由唯一控制者验证合法模型输入和生命周期。不得把 fake 通过当场景可用性或派发权限。

## F04 窗口与域语义

主执行方新增的 controller 明确释放 omitted manager，再应用完整 flags，因此完整 parent ACK 与 SDK 单独 manager ACK 的语义不同，不能混用反例。

并行支持已对草稿 `controller71869f98…` 完成真实 class／假 transport 的6项检查：duration 上限900帧，实际flags deadline2400，但 parent receipt 写模型3000，会扩大真实 Native 窗。fresh mask0 后任务继续的例子已被该版现有 mask 检查挡住，不能再称该点无保护；更窄的 RestoreUnknown 缓存非零mask／实际期限已过场景仍需被当前最终绑定入口与效果判定联合拒绝，不声称现场已发生。旧 MacroStrategyRuntime 仅按 mask0 判断释放，不能直接复用于 manager 域；flags-only 意图结束也不应被无关 manager 一概阻断。主执行方已新增 `UnifiedStrategyRuntimeV5` 的域检查，应按实际新消费者继续核对，不能把旧类反例误指为新路径已发生故障。

完整 CPU 证据与按域状态／效果窗候选位于 `D:/CodexScratch/native5-f04-domain-migration-20261029-v1/review.md`，JSON报告 SHA `d26f11be12a32e244d79d958ea94334b4682a14ff3fbd96f7571234260361fec`。不创造新模型字段，不输出全局归还或已验证效果，不修改主执行方正在写的 controller。

下一份 F04 补丁固定当前 `controller896cffc49d1c7189fe779df64fd84a50d439aa9bf3f330c4e534c983139bc9ea`，仅写 D 盘新副本。使用已验证 child 的 `native.flag_deadline`／`native.gates[gate].deadline_frame`，逐域与模型期限取交；内部 parent 扁平窗只表示 domain envelope。当前独立 controls、新域释放 runtime、完整 desired-vector parent ACK 与空恢复语义均须保留。当前 binding validator 已拒绝 phase5，不能把旧 synthetic RestoreUnknown 例子作为产品正常可达漏洞。缺真实期限不能由请求 duration 推算补证；frame 窗不冒称独立 wall 截止证明。作者结果待独审，未融合。

主执行方负责 Host／模型 schema／默认入口／实机；并行支持负责新 factory 与独审、F04 反例／候选，不覆盖正在编写或冻结的 controller。接口的实际模型权限与正式资格，以主执行方新候选验收为准。

F04候选已封在 `D:/CodexScratch/native5-f04-window-patch-candidate-20261029-v1/`，`review.json` SHA `322752f7e574606cafc15436c82cc9e75d35fcf685b4e1cc8d007e1971a80c1d`，候选 SHA `d3fdefb1989d68310e8488440daeb38472224f7cec1914fd708d9dd3d73dae12`，`controller.patch` SHA `b1be397abf08560318b53b9d85732436aae88cf2293edfb05af281a6d4c31ef2`。最终candidate-only为16通过、3明确跳过，旧15例仅开发历史不相加。健康phase1／last_frame2399、obs和controls2402、实际flags截止2400的人工时序经现有validator允许lag，但候选在效果、预算采用和active导出三处均拒正归因；partial unknown也停止旧vector正归因。A正在独审，尚未融合。主方改过合同导入，不能盲套旧基线补丁。

A独审已完成：23项中20通过、3明确跳过，含5个新增必要反例，确认较早结束的flags不会裁掉较晚manager域、半开边界、缺实际deadline进入unknown、独立组件不符不计采用、新seq不能沿旧窗归因或假释放。与作者计数不相加。精确报告 `D:/CodexScratch/ra3-independent-next/f04-window-A-20261029-v1/review.json`，SHA `50fbab096f85a626d155a4b7201921e9c2c6ec5ae36ea24e677381b54e23366a`。仍仅支持固定候选的离线frame窗，未融合、无wall资格，不能替代独立controls身份尾链修复。

A静态逐字核对确认main963de相对896c仅合同导入行变化；原grammar哈希仍相同。其新D可选候选 `controller-main-import-preserved-candidate.py` SHA `426fc789bb3ef7c192b852fda20946f8a5101a59afda6363b6e2a75022abed08` 保留新导入，非import AST与已审d3f一致。不要用旧整文件覆盖新导入。root随后以新入口执行当前963de class、当前d1a4 UnifiedStrategyRuntime与该426候选，3个针对性CPU连接场景通过，确认真实期限消费、预算不是work、未知owned gate不release、较晚manager尾窗及采用非完工。报告 `D:/CodexScratch/native5-f04-current-runtime-root-20261029-v1/review.json` SHA `e700c8ecff8a6a98bbea664f8352dd76c506bfb236f649d683329b63904f8f0a`。不解除旧guard／skip，也不补算旧测试或授予现场资格；运输、journal、observation、memory存储均人工。

**已实际融合：** UTC `2026-10-29T15:37:35Z`，controller963de→上述426；产品测试22313445→`eeb5accfd79e31717c471eefbcfdb852c45a7577aba1404d4045404286db56c0`。唯一主方已按本lasttrial `desktop-bcd88e90-e31e-4f87-94c1-9f2ec32da025` 完成独立归还并登记implementing／空冻结表。C在两源同时FileAccess.ReadWrite／FileShare.None持锁后，校验源、候选、实际proof／journal／final与owner原始字节，再各写一次、Flush(true)、同handle回读；owner五阶段字节相同。安装后8产品＋3当前Runtime衔接共11项通过、无skip。报告 `reports/f04-window-C-integration-20261029-v1/review.json` SHA `839e368311672fcf0a2a86d0e3207586a87f293ea6ea4c74121594f04629b0ab`。不声称双文件原子提交；未改反馈fafb、memory134、Native、observer或owner。反馈仅执行当前Runtime和projection AST，未执行或资格化主方正在压缩的audit/catalog。下一软件闭包须收当前426；不继承旧现场资格。

窗口反例的范围补充：100s→200s、模型截止3000／Native900帧上限的case是直接controller的人工防御性输入；正常engine的valid_for为5..60s，memory也检查expires≤based+60，不能据此称普通模型曾发出100秒计划。融合改进的是按真实child证据及各域窗口记录／判定的适配层合同，不以该人工case证明正常客户端已发生长期越界；正常计划下的现场归因仍待新冻结复验。

## 独立 controls 尾链复核

C在当前实际函数组合的纯人工字节环境中，复现 controls 最后旧Game.frame读取期间切换current Game／engine／PlayerManager／己方链时，早先rooted样本完整且SDK wire未变，现有validate_sample、Host.unified_tick和controller.observe仍接受旧样本。精确报告 `D:/CodexScratch/ra3-native-strategic/main-observation-composition-C-20261029-v1/review.json`，SHA `97c2b7e1e4e4c87b422a977ad8843c685dfbcf9a2b5520edac19137fb3736a74`；5组CPU验证包括确定反例与原有拒绝路径。当前只证明可达Host反馈，不声称进入实际模型或错误物理派发：后者还有新的采样与Native live_identity。C仅在D准备最小尾链候选，由B独审；不修改活动源。任何修复仍是有界顺序读取，不能称原子样本或保证采样结束后身份永久不变。

审核已拆开并行：A只审F04，B独审C尾链。C首个尾链候选f6de的7项作者CPU检查通过，但B新增在第4次旧Game.frame读取期间变更PlayerManager／ownAI／profile的确定反例，仍到达完整反馈链，因此**不支持融合**。其3个候选方法中2过1红，不把失败算通过；报告 `D:/CodexScratch/native5-controls-tail-B-independent-20261029-v1/review.json` SHA `9355061e2bf537c061a4321124b9f43026b5b6ab8c1d5d87a2b56d1407540c48`，原件保留。C继续在D出新delta，不追求最后一次identity读取以后永不变化的原子承诺。

C第二份研究候选eb0d删去额外末frame，完整identity seal放在最后遥测帧戳之后；8组作者CPU检查通过，同时明确复现尾identity期间frame100→103仍可能complete。它只保全controls250ms，不能证明最后identity也在整窗2frame内，`unconditional_merge_supported=False`。B确认此否定结论；当前validator忽略新增范围标签，不能据此偷偷缩小原合同或授权融合。记录 `D:/CodexScratch/ra3-native-strategic/main-controls-tail-C-candidate-20261029-v2/review.json` SHA `56d5861a6b6887566f486d6ead9ab32b7ac82069313ab45e97b5863ff65e8fb9`。下一方案仅研究完整tail之后严格更晚、已完成Native callback的只读身份／last_frame见证；无法在原250ms／2frame内取得就应延后样本，不改Native、不新派指令，未有可用性或融合结论。

强只读见证原型66686a保留原整窗2frame／250ms：rawtail后先取得稳定anchor，再等严格更晚completed callback作为帧后界，无及时callback即延后。12项作者fake及9项B定向fake支持有前提的静态可行性，不能相加或称Native已执行。B报告 `D:/CodexScratch/native5-controls-callback-B-independent-20261029-v1/review.json` SHA `9340c391a36a8deda284aac2ee42f2e524b1bfc65054adc83c15cbecf4d1ed0c`。真实producer／fresh SDK拷贝／x86发布及单局帧单调是前提，Native后callback不复查Side／store；这些仅由tail证明在窗内。两方均明确merge／field／model资格为false，主源仍cad727，未融合强原型。

## 分发状态窄审

A确认debug不依赖开发shell的PYTHONPATH／cwd，但依赖编译固化的仓库和基础CPython；已有README／player-guide明确它不是安装包，未列为新回归。当前packager仅复制native-ai的Python，微型人工fixture证明Native5非Python制品／manifest会被遗漏，verify纯文件入口因缺manifest拒绝；schema13还依赖资格proof、profile及绝对inputpins，复制DLL不足以赋予新路径资格。旧release仅覆盖历史配置／RPC，不继承新Native5或新客户端验收。报告 `D:/CodexScratch/ra3-independent-next/desktop-distribution-A-20261029-v1/review.json` SHA `495caf0b7e4b730634be53a1df9ca94482ffd662833383a4e6c6d23d264ac17d`，无主源修改。此项如实保留发布限制，不将独立portable安装新增为当前仓库F05试运行前置，也不把debug流程冒称安装版通过。

## F02／F04 记忆到prepared请求

A以13项当前源码前后固定哈希，执行真实纯类与人工可信反馈／fake backend的7项必要检查：新expand／建设门／生产门进入catalog、下一轮memory及prepared冻结；换plan ID不延在途期限，预算采用不抹掉work no_effect，manager采用只记录bounded state而非完工。人工完整wire6903bytes，超过17k的输入在fake provider前拒，不能据人工wire声称真实provider token／网络请求已验证。报告 `D:/CodexScratch/ra3-independent-next/unified-memory-request-A-20261029-v1/review.json` SHA `ff82f83bbea114126ab50c202b5e717e7c0b3431190339692e1b686afd18d724`。这些前提依赖上游真实身份／时间读回；无现场、模型或Native调用。

已确认当前重复抑制按完整intent fingerprint而非每域。新增窄审将核对：相同受阻work、事实未变且仍冷却时，仅加入／切换预算或另一gate是否可重派；尚未有本边界的确定缺陷结论，不因潜在组合问题一概禁止合法新战略。

后续A已用当前audit→memory review→当前完整controller fake派发确认该边界：旧expand在102s记录no_effect并released、had_effectFalse，103s同strategyID新planID、四项basis全同，增加预算／切换预算／增加建设门三种新vector均获strategy_allowed并再次apply含expand。不是只有fingerprint的静态猜测。对照真换work、仅新gate、资源真变可重评，unknown全局门仍拒且无新派发。报告 `D:/CodexScratch/ra3-independent-next/A03-cross-domain-repeat-A-20261029-v1/review.json` SHA `c565be19e333c834d71615a99439d01e4f2e4bf4f0258d8e82732af1eca75b8a`，纯fake无现场调用。A正在D准备最小按已知无效work独立冷却的候选；保留完整vector及unknown门，不自动剥动作，不将mixed had_effectTrue推成某域失败，不一概禁止合理组合。未修改主源，尚未有补丁独审或融合结论。

首个A03候选992被B确定反例否决：lastseen仅随时间超过120s过滤而丢失count键，会被误当事实变化，仍在45s冷却内再次放行expand。红报告 `D:/CodexScratch/A03-work-cooldown-B-independent-20261029-v1/review.json` SHA `f30681c048a42097dd132e798c2fe9f1d2e03fd8b179eb6781a8deeef983e00b`。新D77ed候选只以当前可信新值／不同值作为变化，丢键、过期或known→unknown不解除冷却，公开reason复用现有no_effect_cooldown。作者16组、B定向8组CPU分别通过（B最终封存待确认），未融合。主方memory134相对bccc仅context()中native.* facts优先一行，后续融合须保留，不能用旧完整文件覆盖。

当前A03融合准备为新D dec1bc2a，逐hunk应用到主方134并保留context()优先行；C以最新426控制器及完整fake wire、canonical新memory、当前Runtime5a36新跑27项通过，无skip。准备报告 `D:/CodexScratch/ra3-native-strategic/A03-main-rebase-C-prepared-20261029-v1/review.json` SHA `723d44273197d684462d072fc861f04fdd481961cb28aeac9b8c9ff84fc0d8cb`。尚未写主memory；等待B原77ed独审最终可核报告，不把旧963时期测试改称新426全链。

B最终独审已封：`D:/CodexScratch/A03-work-cooldown-B-independent-20261029-v2/review.json` SHA `ec4f884e069c5186be1a583d967ef3a8201082af6243a932ca527c027dfd4ee4`，明确8组逻辑执行于963时期、后磁盘426漂移单列、旧guard未放宽，不称最新组合重验。C再在现有 `strategy/test_macro_strategy.py` 中追加4项长期行为回归，保原全部test AST；新current组合及全策略测试通过后，由root审定。

**A03已实际融合：** UTC `2026-10-29T15:55:16Z`，memory134→`dec1bc2ae4d1b36a9ceb5c839dc810b3141c100b85b123bbd7444f25543d6a15`，测试51e4→`76e351b3449a340d075d052886fa73538c18693b6767c660cc59d75d8ac9b59e`。按同一implementing／空冻结／实际归还前提，两existing源先同时独占handle、锁中校验来源／实际归还／owner，逐文件各一次写入、Flush(true)、回读；owner五阶段原始字节全同。安装后40全策略＋8产品＋3当前Runtime衔接，共51项通过、无skip；此前27／16／8不相加。报告 `reports/A03-memory-C-integration-20261029-v1/review.json` SHA `087af96f11a923a921273351780ed97a99bc275a4a01cac098f4b76a6a359cef`。保主方native.* facts优先及原schema／TTL／容量／unknown门；复用原冷却公开reason。controller426、产品testeeb5、feedbackfafb、Native／observer／owner均未改动。0游戏／模型／Probe／Native执行，不授field或正式资格；下一软件闭包纳新memory与test。

## 十四入口分层证据矩阵（五个已关闭研究局）

C的最终矩阵为 `D:/CodexScratch/ra3-native-strategic/F03-fourteen-entry-matrix-C-20261030-v1/matrix-v2.json`，SHA `4cb820d2b1ce3a499643a191be2588b26970a5cd30cee90e4ee897dc546212e7`；同目录CSV SHA `b3651e39d17c11b2758c51e421379ceb847e4e10b95dc9613b2a897f79ef804a`。审查报告 `review-v2.json` SHA `f55104a796d91df200ab1d13be7779c805e21e90255bb9356557c872f3b9a8ab`。每入口分别列模型合法方案、parent/child UUID及seq ACK、实际域窗内等待／已满足／组件采用／活动任务／移动，预算share采用使用另一路反馈；每局独立归还不等于被拒动作已经执行。

范围仅73592、86484、13968、97144、28728五个关闭原件。此集合尚无withdraw／deployattack派发，reinforce／deploydefense仅区域绑定拒绝；v6/97968新撤退局不在此集合内。显式advanceproduction97144和advanceconstruction的已满足读回不能算0→1、具体产兵或任务成功，空vector归还不算推进入口。budgetarmy实际ACK／share采用仅见旧28728，不继承为其他v5局成功。

实际Host.sources与归档副本逐一绑定：28728为v4/d989，其余四局为v5/5e0c。C原手写说明曾误称28728为v3/d0fe，矩阵原数据和计数正确；保留原84d稿，新增 `version-correction-addendum-v1.json` SHA `5bb918ac91103527ca0b86e76109f88b43494a4627b034905047887a8bd632fb`纠正文案，不重算／挪用证据。该矩阵不授F03总资格，不汇总产品百分比，正式仍0/3；主方已收到上述分工与缺口。

v6候选公开预期版本索引为 `D:/CodexScratch/native5-frozen-trial-v6-version-root-20261030-v1/version-manifest.json`，SHA `b3f5841b2759e1dec3dce3e927bbb68bc749eb5df0ede6125e6b852e395c7c27`，绑定cb911候选1116pins。它只列候选声明的版本，不替代实际归档源、实机或正式资格。

## v6实际撤退局的多轮记忆与请求容量

97968关闭研究run `5982e5ad-9d95-4406-b5c4-cefe9b545d5f`，session `75ac2fee-99ba-5d2d-8fa8-94c8b9a9a4c2`，Host `acceptance/runs/desktop-61958d56-f5ff-4276-a981-bbe817416081/battle-host`。主方STOP后独立归还并关闭精确旧进程，原件 `reports/strategic-unified-withdraw-97968-20261030-v1/`。A实际文件复核 `D:/CodexScratch/ra3-independent-next/97968-v6-memory-wire-A-file-review-20261030-v1/review.json` SHA `eb10ffb0f7fb1a3dc7ca7272b5539a3fa9292743247be12636f9c47b0b603c57`：7request／started／response及SDK回执齐，context bytes/hash逐条相等；memory最大1523B，context8645B，记录wire15461B，snapshot/time绑定一致，完整200、expectedHTTPS、non-injected，无context预算故障。436实际sourcecopies核齐v6cb911／prompt91c1／memoryd311。

round2–7同strategy ID保持，必需refs逐值核；seq7当前full反馈空时native.withdraw保留missing，seq6的intent_in_flight guard也未丢。原反馈帧／status与保存的Host完整反馈相符，history0→2。wire仅原回执metadata，没有保存raw providerbody，不称独立重建发包体；实际unknown分支未发生，不补授该分支。A只锚定归还／关闭工件身份与hash，不重复B的Native、命令次序和归还语义独审。本局为撤退分项研究，不计自然局，正式仍0/3；支持方不读新进程活局。

### 97968命令、任务窗口与归还独立复核

B报告 `D:/CodexScratch/native5-withdraw-97968-B-file-review-20261030-v3/review.json` SHA `adbcde984a4ad93bb7b25f30ff6b620a24febd6c01cc4d87d111c2bf045c55a0`，从raw audit／marker／Host events重算23行ordering_verified及7个provider ID，限定run的只读DB核3parent／3child completed、UUID5／ACK／合法home region8_3；436源副本中426匹配v6外pins、10额外meta，Native70e绑定及纯return三函数通过。10条Native binary flag journal独立struct解码与sidecar相等，未执行SDK或旧review脚本。

两个实际withdraw窗口1785..2414和3010..3634分别有43／46个有界活动样本，12个己方member keys各有>10单位位移，最大457.39／2253.40。第一窗前active0，第二窗前已有44个活动样本，所以不能把第二次偏好当第二个新任务。req2／5消费活动与移动反馈并保effect记忆，req3／6后续消费expired／released，req7只留旧expired记忆、当前无active反馈。原生trigger1在2414／3634到期清除，随后空mask parent seq3、再GUI STOP；到期释放和最终停止归还分开记录。

89条不完整observation保unknown，defer／newID／inflight拒绝与交付未知0均保留。该链不证明方向、到达、全军撤回、战略成功或独占因果，也不因活动任务可能跨期继续而把窗外移动归给已过期偏好。B开发v1／v2对缺失native与hex owner格式的错误假设中止原件保留，v3按实际schema严格核对，不冒称原生缺陷。上述结果已交唯一控制者，不授全F03／F06或正式局。

### 已有撤退记录中的条件失效重评链

B短附核 `D:/CodexScratch/native5-F04-expiry-reassessment-B-addendum-20261030-v1/review.json` SHA `c0eeaa03e38015c2c0d9fb9a1420438decc79ec4ccc99b51092867d2d096a54d`。第二withdraw plan `161815cc-7255-4d35-a3c2-83457cd7db09`在3634帧到期，Host记expired@243.2；真实request6 snapshot264／game248.7333携带该plan expired及native.withdraw preference_released／activeFalse。真实response6的diagnostics明确macro_actions present、list_length0；下一model-origin plan `e29b3cf3-fc53-401f-8cf3-23ecee4b9f95`保持recover_force与strategy144de179，由execute改assess、expected no_change、actions[]，显式引用native.withdraw，之后落空parent／flags seq3，早于GUI STOP。

这为F04“等待／无效／条件失效”中的条件失效分支提供现成真实链，不是Native拒绝或刻意失败场景，也不是Host剥动作得到空vector。request所带intent_in_flight只是前轮Host guard；资源／兵力也变化，不称expiry是独占原因或推理质量已获全面证明。与已有有效效果链互补，由主方按原canonical标准汇总，不自行授全F02／F04／F06或正式局。

## 最终证据清点的可运行辅助

C的D-only CLI `D:/CodexScratch/ra3-native-strategic/F07-explicit-inventory-C-candidate-20261030-v1/native5_final_evidence_inventory_v1.py` SHA `270911156133977ed9aa598d5b71411bb8b0de1de96810cb60983dc5124ca376`，用法与两闭局显式输入同目录。参数为 `--workspace` 绝对工程、`--input` 新JSON清单、`--output` 新D文件。复用锁定当前outcome_v3及Native5 file-only归还，按显式源关联候选／身份／参与者／profile／真实回执和context hash／诊断／过程／原生录像／外部结论；不执行归档源码、SDK、游戏或模型。

root独审 `D:/CodexScratch/native5-final-inventory-root-independent-20261030-v1/review.json` SHA `aa08fe90f9dd158dd781f440d4830f40415efc31e506344f3e5a3bd7e7ebb1ac`：实际73592／86484输出与作者逐字节同SHA `fd00945f84e2f751a97f71fc9760bc3e2e49e59de597d2621cd713e19eb1bb92`，前者自然子证明true、后者whole生命周期false／尾部unknown、两者归还true且excluded_research。三份同局只有1distinct；caller formal=true被schema拒且不创建输出。0被禁网络／进程／Native操作尝试，主源及原输入未变。

该工具仅清点，机械三局／同候选不授正式，外部true只记录来源，全程合法视野／Host模型连续性／普通风格及人工视觉语义仍按原验收独审。所有F01–F07／formal自动授权固定false/0表示工具范围，不表示产品永远不能通过；不将此新工具列为自然局前置。正式三局收齐后可用实际新清单汇总，不能回填旧研究局。

## v6增援闭局与客户端证据版本映射

38020闭局run `2e3e838c-63fa-4d49-8629-19e570cc33eb`／session `b73cdb8f-e199-5d2b-a7d3-5e609264864d` 的C报告 `D:/CodexScratch/ra3-native-strategic/reinforce-38020-C-closed-review-20261030-v1/review.json` SHA `e07e91323dc2e7bd824f4fd06a5f6e43c4cae469dffcf5d84b6f75062016d9e2`，补充 `association-stop-scope-addendum-v1.json` SHA `da5000563aa8f6d941b69a9daf2e59f55fc3c9dedb6716888515795dda073676`。实际v6/cb911、profile28研究；唯一合法model reinforce region8_3，1parent／1flag child mask8、completed与ACK绑定，窗口1648–2047。15waiting→21active，首任务1815／首moving1824，P3 group275／Thing762同对象19个valid样本至2019位移554.94；不证明任务成功或独占归因。

request2消费1963的活动／移动反馈并有真实response，3–5消费released并有response，虽继续建议reinforce，物理始终仅1child。2047 Native到期由phase3→4、独立flagfalse；2048／2058仍见已提交原生任务，不能把clear说成取消任务。STOP3029及独立完整归还另核，Native未知／DB unresolved0；15admission行的seq15commit后无新admitted。27条raw不完整保持unknown，不以preACK过滤未见匹配证明全局无原生任务。下载236870B与playable141events／202s、嵌入JSON及source绑定相符，仅文件核验未重播，不授全F03/F06或正式局。

F05版本映射 `D:/CodexScratch/ra3-independent-next/F05-evidence-version-map-A-20261030-v1/review.json` SHA `7697c4b71e68fe0089455b72ba65bb8778bc18714fcff9df8f3ea891c1effa63`：v3／v5／v6相关NativeApp／views／Rust／Bridge／Backend／diagnostics及EXE48de pins相同，配置core／Panel／RPC不变；已覆盖配置、STOP、下载不因prompt改动重做。未发现新功能缺陷，最小待补是现有正向GUI操作来源索引、自动启动结果与前局归还后下一新局链。不能从缺指针断言操作未发生。

已完成的50304 UI步骤工件只读附核为同目录 `autoentry-starting-step-addendum.json` SHA `61e386b0507cadba6ab0ff311c712fe74927d18e51f5f6b8bbaf27f09af77cc9`：PNG65c4def1…／UI1e6a6c33…显示启动已受理、启动中、等待Host／模型回执，尚不授自动启动完成。`scope-clarification.json` SHA `2b233d9e99802d6ab1a0051d113a6d791f5a7e8b67eba1045b55ec98fd6a34ac`明确F05普通指客户端正常操作无需手改session，不要求该局无研究style或自然结算，F07三局另外验证。陈旧文案发现对应desktop-ui/README旧b0c副本；root随后只修非冻结文档，未误指根README或补绿GUI。最终流程结果待闭局后关联，不读活局Host／Native。

### v6防守闭局

C报告 `D:/CodexScratch/ra3-native-strategic/defense-50304-C-closed-review-20261030-v1/review.json` SHA `46a7a527a35aacfc492fb5200ea8574588dd333742995f633e4e71cf96127a61`，补充 `association-stop-scope-addendum-v1.json` SHA `c0cbac4dc0adc8d9945899942c062ceb1dbd5ff6071b81c80d80bca7fef2dfe1`。闭局run `fa44a47c-0f0b-4a45-89f8-d4842250fc2e`／session `7071f636-f418-57c6-9025-f6c4b6294bac`、v6cb911／profile29研究。3真实request/response、2accepted／1unsupported_action localfallback，唯一合法region8_3 parent→flag child mask256，SQL双读completed／unknown0。窗口1695–2319：11waiting→38taskactive，1812 raw static_defense有12own成员但inactive，1821active／1836moving；group275／Thing771同对象至1959位移456.22，不推新任务创建、任务成功或独占因果。

seq2 context2021消费活动／移动并有真response；seq3 context2396消费released并有真response，但该方案被拒，不算再次采用。durable expiry2319 phase3→4、flag2311真／2320假；STOP与独立proof2512另核。2320仍见原生任务，不称clear取消已提交任务。34unknown raw保留，11admission seq11commit后0新admitted，current pure fullreturn真、Native未知／SQL unresolved0。下载159213B、playable76events／167s绑定与嵌入JSON一致，仅文件核验未重播。主方关闭精确旧进程后继续进攻研究；A单独关联此闭局F05自动入场／下一局，不由C重复授GUI资格。

### F05自动启动与下一新局实际闭链

A闭局附核 `D:/CodexScratch/ra3-independent-next/F05-50304-autoentry-closed-A-addendum-20261030-v1/review.json` SHA `1cb57d02fbf099ea908a2449e2418c6bc27034620f0d6b4585649e75d6cb0842`，已完成主方UI工具历史投影SHA `7be514a173d27e8c245cc92c40d1e4bb510a40762109d6753104dc0d8a996179`。38020旧run/session已归还→exec5fd8自动等待与取消控件→exec1fc新fa44/7071启动中→exec888运行中及应用／模型回执→execb845 GUI STOP→execad8实际下载。仅本run只读SQL核1次host_start completed、5commands无未决、3真实模型started/returned，profile29／effective2edd与Host同，stopped/user_stop；相关EXE48de和App／openingStart／Backend／diagnostics同v6pins、436sourcecopies相符。

指定下载159213B，SHA `d264bf543cbf5afb4abc7f4562c6a88b43ac3721ef1ff5300c09b085016598cc`，与归档逐字节一致，229Journal snapshots hash吻合。单独每个discover/prepare/check RPC没有额外录制，不编造时间；冻结代码强制顺序、UI、新绑定和实际账本支持此case，不新增逐RPC观测门。start.finally清ready解释启动受理同时显示尚未检查，无新绕门缺陷。可关闭原F05映射的auto/next-positive指针差额，不再为该case另开研究或重做配置；旧7697及starting阶段unknown报告保留。整体F05与正式资格仍按原矩阵汇总。

## 同版原生失联、产品宿主骤停与恢复缺口

B报告 `D:/CodexScratch/native5-loss-cleanup-scope-B-review-20261030-v1/review.json` SHA `79fecc7b60b4eb4a1ff1bd9e22657eef38426e5389d4926e2fd4b08f6fc43a4a`，Rust附核 `control-rust-pin-addendum.json` SHA `6cdbfb31ec50331a8fd4879f3012713e1e5830a01b416969ab66b0407f29c129`。96308 v2的115copies/pins同当前Native70e／SDKb29／DLL7a4ad／helper56e；current纯verified_proof明确用真实abnormal helper rc1、journal重放通过。停止heartbeat并结束helper后，phase2/stop0已清flags、双gate、hook、lease，watchdog trigger3@779远早于TTL；之后SDK.close才stop1，不能把STOP或到期冒作失联恢复。Python研究controller仍活并持Popen句柄，因此不证明产品MacroHost硬死后的恢复。

91584 attached adapter／parent异常finally STOP的current纯proof／journal也通过，adapter._close／controller.stop与v6 AST相同，Host.finish_transport attached-tail相同（新增分支仅None未接管证明）。这些子项可复用。当前resume/status保unknown、STOP只提交marker；_release_receipt→macro_desktop.released要求macro-stop及完整proof，unknown_ownership只解除所有权阻塞，不改原命令成功。无通用force-reconcile或自动补proof入口。唯一控制者已确认缺口，完成进攻后处理非正式产品Host骤停／独立归还／客户端恢复链，正式三局尚未开始。

C静核还发现SDK未持久化Nativehelper PID/rawFT，MacroHost死亡后Popen句柄丢失；Game内hook_held不等于host.cpp的launcher hook也结束。旧epoch没有helper结束证据时不能把host_process_ended或returncode0补真。映射、Native durable journal及原始binding可提供只读基础，但完整恢复需真实helper生命周期封条／新经审contract。C只在D准备最小生命周期记录候选，主方保有UI/Backend集成和实机，旧proof与历史记录不改；未观测字段保unknown。

## 进攻闭局与正常归还合同分层附核

B进攻部分独审 `D:/CodexScratch/native5-deployattack-106208-B-partial-review-20261030-v2/review.json` SHA `2cfd766aacc863b713fb474276bed808492ec49bbf139980ae41651b55d3cd9c`。闭局run `f23a735f-c61a-4ced-956e-b7d7289c753c`／session `6309e6c5-15f1-5c99-b339-8fcb4554ee28`、v6cb911。4真实context／2 model parent-child mask128 seq1/2，合法region1_3，15audit ordering/appID相连、闭DB双读同且未知0、436copies／426外pins匹配。8条Native journal固定header／binding／sidecar独立解码。

第一窗口1618..2016有13active／11own keys位移>10、最大663.34，窗前active0；第二2168..2799有21active／12keys>10、最大896.48，窗前已有13active，不算第二新任务。request2消费active/movement，request3消费expired/released并给新attack，request4消费第二active；90缺identity样本保持unknown。第一2016 trigger1 expiry，第二2704 trigger2 STOP早于2799。缺项原为current纯return由7f4→4df源码WIP而guard截停，不执行旧archive／不追新pin。

明确授权固定4df后的小附核 `D:/CodexScratch/native5-attack-normal-return-4df-B-addendum-20261030-v1/review.json` SHA `71f4158ac3011cc9a853b4c5583a6320b86a28cb490f451a774f56a806815fdf`：current实际模块前后同，closed106208 actual final／proof／journal三函数全true，None／bool／1／字符串0或endedFalse均拒正常合同。旧7f4只读AST不执行：verified_final／journal AST同，原proof主体提取为_current_restoration，新wrapper保真实int退出码与endedTrue约束。原partial不改；这是后来正常语义复核，闭局仍实际7f4，不授新orphan路径或正式资格。

## 恢复增量独审：红色原件、固定CPU与范围纠正

C早期静读报告 `D:/CodexScratch/ra3-native-strategic/native5-orphan-return-C-independent-20261030-v1/review-early-static-v1.json` SHA `6f2c30f50d2d3131d6e9bfc6059cc526ce859bbf21aac979c300833f884b748f`，normal交叉 `normal-contract-crosscheck.json` SHA `10e87ad6de8dd9aeed33a7aebff50b72b5628a67797ca42b748dae3a0ddb5ec8`。旧212/e8d指出未落账证明文件可能跳fresh采集后先改账、Memory构造丢句柄、缺journal误补空等版本化问题；后续主方已修为source检查前置、未提交文件fresh复核、安全Memory构造及journal直接读取。早期212仅tool静读，后有完整e8d副本，不把它改称全CPU或当前缺陷。

A旧3417身份API无效PID／FT误判ended反例与源码漂移报告 `D:/CodexScratch/ra3-independent-next/native5-helper-identity-A-review-20261030-v1/review.json` SHA `d184cf4e4243107bb721b6da3a1dac6eb25e519b47187b922068cb7089eced04`，74ea复制前漂移的v2报告SHA `28cffcde43d58d0b5b974154c2de329e9d8e0048b2cd8dab8700eb52cfdb904a`。两次后续测试在import前拒绝，不能计执行通过；caller已有部分类型门，不把API反例直接外推全恢复穿透。

明确固定ce2048／transport9ba后，A v3报告 `D:/CodexScratch/ra3-independent-next/native5-helper-identity-A-review-20261030-v3/review.json` SHA `43408c1837f3ff9fd61a07f30c39f4a7ba8b79c8dd56b2dda1186f43f8d6b0aa`：七类必要fakeKernel／Popen／fsync／构造条件及原八invalid子例回归满足、源码前后同；首轮漏projection夹具红保留，仅修夹具重跑该项，不叠加覆盖计数。仅固定WIP CPU，FT人工超uint64仍无显式上限的静态局限保留，caller由恢复合同另审。

C固定fdc30的12组必要CPU报告 `D:/CodexScratch/ra3-native-strategic/native5-orphan-return-C-independent-20261030-v2/review.json` SHA `0c35abb989f8ddb2622d427cfd3fe6b79c98db0d024ca3578f327739f0e96de3`。使用fake SDK collector及本地ctypes布局，不采游戏根或授实机。后续92a→114168变化时停止delta执行，等真正新候选从actualpins只补实际AST变化；旧12项不补称新版本通过。

root曾将fdc临时client.Memory替换未恢复外推成“下一产品查询必失败”，C提醒并核对9ba.native_module每次新建SDK模块后已撤回该可达性推断。root尝试fdc时guard发现3a4，保 `D:/CodexScratch/native5-memory-wrapper-root-counterexample-20261030-v1/guard.json`、产品函数执行0；再试92a也在执行前发现新源而拒。不得把这些称为已执行产品反例。主方后来隔离collect_current并恢复依赖，作为合理局部清理与必要回归，不新增field门。上述恢复源码由唯一控制者实现，支持方只D复核，正式仍0/3。

## v9最终冻结、十四入口提交与恢复差额独审

实际新冻结为 `acceptance/runs/desktop-fe19ebfa-4918-4063-af5c-9683e5c43e80/unified-schema13-v9.json`，SHA `c58306af92654d8087e36ce42983b4c5e1d0dac41af9b5457f39393f0faf687c`，1118pins；orphan `593865b89f60e10ad72eee9a26c4b8fa67f0c498de4e1106615c53752cad051d`，helperce2048、normal release4df、transport9ba。owner最初只更新candidate字段、旧candidate_bundle仍v6，C因此合理停在旧基线；root指出后主方已对齐两组字段，旧snapshot保留，不由支持方改owner。新公开预期版本索引 `D:/CodexScratch/native5-frozen-trial-v9-version-root-20261030-v1/version-manifest.json` SHA `6b483e363b7d8b8433b3d26a13ac1be13d9ba3678d2ecb60d03e6fc82e79a744`，只列预期版本，不替代actual archive或实机资格。

B十四入口最终提交索引 `D:/CodexScratch/native5-F03-final-submission-index-B-20261030-v1/index.md` SHA `a9e57edc0c33abdfcf0bc9e3a5850d672ae7a173b8fa53249d3415360e4d08ff`；完整index.json SHA `8ff1e71f6a016226d9f2c18017324f5a91b6b0fe40e9598c9848a06cc9e5b41d`，manifest SHA `a10c032ba017699d45042fe46e5ed635a6487bb73507374e133ce54de5102535`。逐入口列真实模型、父子UUID/seq、原窗口反馈、后续模型和独立归还报告／未证项，四个新v6区域闭局补原矩阵缺口；budgetarmy仍只旧v4/d989，不改成v6，advance已满足不造0→1。0新run/test/tool，不授F03整体或正式。

B最小继承审查 `D:/CodexScratch/native5-v6-v9-inheritance-B-readonly-20261030-v1/review.json` SHA `2098967d5f69b823a63c8c02661803a160ccb7136be512aab755af164bbe8946`，可读review.md SHA `807e4d0880f587dd93af8e7b261ea68ec0118fb1547d82101e9bb6088430451f`。精确差集1109同pin、6同path变化、3add/1remove（含legacy路径替换），不是早期口头的7个同path变化。38关键源actualbytes相符、87inputs前后同。Native70e DLL/helper/SDKb29／grammar／boundary／Host／controller／feedback／observer／prompt／memory／stopgate／Rust／config／control相同，transport唯ctor加身份记录，其他方法AST同。Backend唯_status恢复与diagnostics工件变，普通run_check/start/stop/status/resume AST同；macro_desktop新增orphan优先分支，normal4df引用已封真实纯附核。旧各run保实际版本，不以同Native自动授全产品，也不新增14项全重跑门。新ctor、恢复、EXE和lifecycleView由新field/GUI补证；无oldTS字节就不假造等价。

C最终v9差额 `D:/CodexScratch/ra3-native-strategic/native5-orphan-return-C-independent-20261030-v3-v9/review.json` SHA `9e16a2fc74fe784c868755a5cab6fe32965e0e1d126567d761825d62f7edf226`。实际c583与7核心源前后同；fdc→v9变化inputs/capture/verified_return、新增collect_current，其余7函数含verified_capture/recover_after_stop AST同，Backend仅补OverflowError。新增7组必要CPU均过：身份上下界、Memory成功／失败／重复调用清理，mapping及缺journal重试与真空文件、None保unknown不造exit0、Overflow不改账、未提交旧文件fresh复核／可信receipt幂等与原父子unknown保留。旧fdc12不重标v9；fake SDK collector、本地ctypes布局，0目标OS/SDK/Game/Native/model/GUI，不授field或全F06。作者64后端检查是另一层范围，计数不叠加为产品进度。

唯一控制者已沿普通界面在85860开始非正式Hostloss验证，故障脚本只在真实封条匹配、原生仍持未到期意图时结束对应Host，不替模型下战略命令。早期两次剩余期不足的预检未改变进程，记录保留；等待新真实意图不补正式自然局。正式仍0/3。

## v9正常研究与真正骤停场景的闭局独审

85860自然研究run `3c59566f-3409-4d0e-b576-150a04a49257`、Host `desktop-ca702153-e925-4a8f-b3ae-2cf7ca8aa7d4`。C报告 `D:/CodexScratch/ra3-native-strategic/natural-85860-C-closed-review-20261030-v1/review.json` SHA `2313de7bae70b30466ec2e1189c862c3b5e3bb6e501e1b765bbd4658913e545d`：自然实际重算与main同、P3胜、intrinsic4333→Host4342→STOP/proof4343，normal4df三项true、helper封条／438copies／v9一致，8请求7接受1拒、5父子ACK。A实际payload/GUI/export报告 `D:/CodexScratch/ra3-independent-next/85860-v9-memory-GUI-A-file-review-20261030-v1/review.json` SHA `c21cb65112a2e3c8828a4b82e50e25f79cb5a6083e1a674eabd8ca2ddfa6e8ad`：memory1534B/context8592B/记录wire15480B、8真回执，新EXE0b34与下载430248B/hash8f90…相符，过程331events/289s仅数据。该局fault未触发，formalfalse0不回填；旧replay mtime模板草稿和实际纠正稿均保留，原replay bytes不变。

73204真正Host硬死run `1c55a795-b288-4bcd-b0b0-438b827e1de4`、Host `desktop-aabd019d-dd9c-4ca9-9bee-71b0c2f35931`：C `D:/CodexScratch/ra3-native-strategic/orphan-73204-C-closed-review-20261030-v1/review.json` SHA `5f2d5700937d38fac8c8b6484088a99e095ff021433ed31743489301de72e715`；B `D:/CodexScratch/native5-product-Host-loss-73204-B-file-review-20261030-v1/review.json` SHA `8a46f0fbe6a6b32ba87c5c205d35a2bf00610aead85bf44bddf62621b3d3f791`；A `D:/CodexScratch/ra3-independent-next/73204-v9-recovery-GUI-A-file-review-20261030-v1/review.json` SHA `d369f5a15316581719cc0773742dea98b07f24f93470087f052a8bd0283d7e25`。各审原生／账本／GUI，不互相冒全链。

Host97360/rawFT精确结束，Game与helper未被kill；原model economy+scout mask18、seq1原ACK已完成。watchdog trigger3在1669帧清18→0、早于原1997期限；phase4期限清0，旧错误的逐行deadline比较脚本保留后改用phase3原期限关联。新proof读回2717帧、lease1、flags/hook归还、exitNone/unknownNone，不伪旧normalexit0；本局gates未持有，不叫三域恢复。B两次限定DB一致、5commands45events无未决；Hoststart仅生命周期started→uncertain→completed，未倒填父子成功；host_stop请求false与macro-stop独立released分开，7行admission/commit7无新准入，Native仍request=ack1/stop0，恢复发命令0。C438copy/463输入和A v9/EXE0b34绑定相符。A实际“未知→GUI STOP→独立归还→next解锁→诊断下载46049B/hashcbf155…”完整，旧Host running保stale，不展示丢失的策略/内存。只证解锁，实际下一新局另验证，formal0。

## 正式首局1/3与未确认第二次尝试

62660/run `2d477883-61ab-46cd-ba59-82bd3fbd15fe`、Host `desktop-71769858-9d33-4c62-b7e7-70033b44d31a`为正式首局。C自然/normal报告 `D:/CodexScratch/ra3-native-strategic/formal-attempt1-62660-C-closed-review-20261030-v1/review.json` SHA `754200255edcfb3f9f93ac281708ac7b4f57d059fe9164c400b97f984c9aba96`；B前置/账本报告 `D:/CodexScratch/native5-formal-attempt1-62660-B-file-review-20261030-v1/review.json` SHA `fc4a8e50eade74370a4641b6e8c88316acc8c26e2cbe0fab5ea0b89129685fc9`；A payload/GUI/download `D:/CodexScratch/ra3-independent-next/62660-v9-payload-GUI-A-file-review-20261030-v1/review.json` SHA `cd7208be9da4ff2a83fd7fecd6973abf5d28d184c8f03a4aedeed2276a86aece`。

17真实完整请求／响应、17接受、7父7子ACK、normal归还三true，intrinsic7768→Host7771→STOP/proof7772。17wire最大15480B、memory1534B、context8587B，profile31/f94/840B普通traits与既存ordinary快照同；missing native.scout明确保缺，不补事实。实际下载924899B/hash529c…与归档/索引/时间线同。B实际completed工具661排他创建空roster→665 Popen62660，支持事前登记；**f94是effective profile hash，root早先误叫roster SHA已更正**。cleanup模板Nonformal/formal0旧文字及说明原封，不各自决定资格。自然finally没有GUI stop.json，strict marker工具如实unknown仅缺marker；另50行seq/binding/25成对scope均在Hoststop前、之后无新策略/Native请求，不新增每自然局必须GUI STOP门。

root实际headless播放报告 `D:/CodexScratch/native5-formal1-headless-root-20261030-v2/review.json` SHA `8451908cb8a3f2cd46fe5e378fa94294d3aa04c35e9a8ec1740419ff318a7eb6`：实际722events／518s，嵌入JSON逐项同、RAF/暂停/继续到末尾/rewind/seek以及最后战略与STOP行可达、无JS错误/外部页面请求，HTML/JSON未变；不验证原生Replay保真或另授正式。v1根测试CDP const重名夹具错误保failure.json，仅新v2用局部IIFE修测试，无产品修改。主执行计正式1/3，source/profile保持v9。

新v9 F04公开证据选择 `D:/CodexScratch/ra3-native-strategic/F04-62660-evidence-selection-C-20261030-v1/addendum.json` SHA `07173aca3550debe52b0b80a5a9cb0fb5ba9ea72feafe310f72229db3fd9fe3c`：seq8读waiting/noeffect后给empty/hold/assess但因objective ID被挡，不能说物理clear；seq10收到原expired.effectfalse后公开assess并选scout+economy，取得parent/childseq6，后续仍waiting／expirefalse，不叫任务成功或expiry独占导致新phase。461.733后来expiry不能倒推433.6声明。root另有85860 F02事实切片 `D:/CodexScratch/F02-85860-public-decision-scope-root-20261030-v1/review.json` SHA `894db86f83730cbf370a56d0190e40b08718ab57f85b1649a1e326c9ebab226e`，不以资源/role变化或获胜自动授全F02。

104984/run `542bc1f8-f335-4217-8b03-71da882c117d`、Host `desktop-2d7ecf44-daf0-477f-8750-ff0a641493a1`仍为事前正式attempt2，但未计入。C `D:/CodexScratch/ra3-native-strategic/formal-attempt2-104984-C-closed-review-20261030-v1/review.json` SHA `530615a125ee01728b6b98a4c5d49df1bb5b8f8dbb05e929a827146ecf4dd815`：historical P3胜有效，global/whole因unbound_tail_result_rewrite保持false；234@4743首绑定intrinsic4740，241@4846仍同，242@4862 participants[]时victory变4861，243真实frame0保留。Host4746→normal归还4747可靠，不是输了或清理失败，不删tail、不修旧评估门。

B该局 `D:/CodexScratch/native5-formal-attempt2-104984-B-file-review-20261030-v1/review.json` SHA `03f2460a2cd0d454288fe79d1fae3dec0eed77350e43f70682b13ec606dec350`：10真响应8接受2拒，regroup snapshot91／reinforce112均缺catalog要求home8_3，未对应Native派发；8父8子原ACK、18commands828events无未决，38admission/19scope自然stop前闭合，缺GUI marker同前仅工具范围。保持not_counted_unconfirmed_tail，不改称研究，不以归还true补自然true，补局继续同一v9/profile31。

可选清点CLI已更新到当前normal4df pin，位于 `D:/CodexScratch/native5-final-inventory-B-candidate-20261030-v2/native5_final_evidence_inventory_v2.py` SHA `a26187b5cae8d73fee565d5837378b5e32fb7d4f42d44b8fe5f7ab1a784460ae`，review SHA `8a78e29df093662da0c674a129a2b1ef75f657ac266df3ac7f067eb01933d6da`。只改pin／版本三串，反转逐字还原旧2709、业务AST同；两旧例不变，加85860后3distinct但混候选仍samefalse、研究排除/formal0。它仅引用显式已关闭文件，不自动授正式、不支持把orphan异常补作正常自然局，旧v1不改。

## 当前压缩版本的实际离线编码

主方第一条真实模型方案（budgeteconomy＋scout）已Native接收、独立归还；第二轮context_budget_exceeded后主方压缩反馈／目录，并优先保留native.* facts。A另对当前134／fafb做三组明确夹具的真实Audit→immutable prepared→实际SDK序列化→MockTransport：普通第二轮body14793B，四域人工压力DeepSeek14931B、OpenAI14911B；最高保守估算15834B。原帧、unknown、manager采用不等于完工均保留，0真实网络／模型／游戏。报告 `D:/CodexScratch/ra3-independent-next/unified-wire-budget-A-20261029-v1/review.json` SHA `c5935b6ba381abdfbb70853991c4f847b532fc065303b44743764ad604fbe069`。有限夹具及普通style不证明所有极端合同组合或4000字style均可装下，也不把此前fakewire6903B补称真实发包体。真正连续模型循环仍待主方重跑。

后续核实有效style合同实际为1200 UTF-8 bytes／custom≤800字符，旧4000仅存储输入上限，超过有效合同会在正常Profile门拒。合法1200B中文样本估算16047B通过；另合法1200B含大量引号／反斜杠的定例，在prepared预算门以估算16515B拒绝，SDK MockTransport调用0。legacy实际编码15612B仍未超16KiB，**不能称已证明真实SDK包超限**。静态run.check当前没有wire测量，Host先Native构造、后audit／prepare，因而此例是合法配置可在接管后的请求准备阶段拒绝的可用性边界。未实际接管、未造清理通过；只建议前置纯容量测量，保后续真正prepare，未实施。报告 `D:/CodexScratch/ra3-independent-next/style-escaped-boundary-A-20261029-v1/review.json` SHA `435c30fe89cfa86b1e18e8ed03290de8d534bfbef494bdb0aa35cfaf467114b0`。A03新dec1保context() AST不变，但这些旧134夹具不补称新源整链重验。

## 客户端与现场证据

已测 EXE `168ebbad…cc57aa` 在真 prepared 期间禁用 check／start／autoarm；人工派发前取消记录可实际恢复观察、查询、脱敏导出并下载。指定下载9261字节，SHA `330024…059d` 与导出逐字节一致，之后 GUI recover 重载及正常 Alt+F4 退出。它不是 active Host STOP 或真实 Native 归还证明。

NativeApp 两处源文案已更正：派发前取消称“未取得原生控制”；Blob 下载称“已生成，已发起下载”。修改时源 SHA `fc3a961894b7e2828a75eb9692c8c98df5a3c84c44441eb5c26ee6f074fb05dc`，不在上述旧 EXE 中。主执行方随后继续实现，当前源 SHA `5cfdc78d3440ef76300d50777bf512990d211030082bce5be5c9c304c26e54fb` 仍保留两处修正；其新构建和实机结果须另核，不能继承旧 EXE 的 GUI 证据。

PID52600 新冻结研究的文件交叉核对确认9次唯一指令与回执、24条解码日志、当前 OS／本方链、标志清空、hook／租约归还及宿主返回0。结算原始字段 `match_ended_verified=False`，没有模型决策，正式仍 **0/3**。记录 `reports/strategic-unified-terminal-file-corroboration-root-20261029-v1/`；其中0ns仅为粗粒度时钟下的记录值，不表示瞬时或原子采样。

完整支持进展见 `commander-strategic-product-integration-20261029.md`。

## 最新现场归属快照

owner 更新时间 `2026-10-29T14:30:03.637379Z` 为 `preparing_field`，游戏 PID104548，会话 `49604a99-feeb-4c63-b547-5306c7441a0b`，用途 `ordinary_desktop_integration`，正式仍0/3。主执行方最新进度为新客户端已编译，正走发现／预检／启动／观察／停止／诊断；这是准备和进行状态，不是流程通过结论。controller896c、transporte4d70e1d、observationcad727f6、feedback06eb4834、release7f4da08c 等已在冻结表中；本支持任务不修改这些文件或操作游戏。

随后正常发现曾因隔离 bridge 缺仓库根导入路径，在 Native attach 前拒绝。主执行方新增 Host 本地 `strategic_contract_v5`，按固定文件来源加载原纯合同，避免依赖仓库根的 import 搜索路径，并重新资格化；owner `2026-10-29T14:38:00.390918Z` 再次 `preparing_field`、`native_attach_started=false`。controller变为 `963de322a2f21d0238cc8943f5cd5f7106f29d9338591b6d69eda343f8bf9a1d`，feedback变为 `d1a48973576171067a2a57213f2365fea05734951609c63ecc929b2ef9d98c96`。并行候选的source guard因此如约拒绝，保留原拒绝，不自动重定基线；F04窗口修订仍须在最终实际合同下复核。

新快照 `2026-10-29T14:58:14.426789Z` 已为 `field_running`，PID102464，session `a0ac9e7d-c230-5056-9fc2-abc2ca98bbf0`，用途 `normal_GUI_real_model_trial`；`native_attach_started=null`，正式仍0/3。这是进行中的试运行登记，尚不证明模型调用、Native attach或完整流程通过。旧104548未接管局自然结束并由主执行方正常关闭，随后重开新进程，经普通客户端发现／准备／预检继续；并行方没有重开或控制游戏。所有候选继续只D，不改冻结源。
