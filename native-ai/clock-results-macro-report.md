# 时钟、暂停、结果与有限宏观接口

所有地址限本机 RA3_1.12.game SHA256 `ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`。本子任务只读检查和离线反汇编，没有发出信标、修改战略字段、暂停游戏或注入。

## 时钟与暂停

- GameLogic全局指针：`[0xcd8ce4]`；模拟帧：`GameLogic+0x50`。主Agent的天然生产链验证见 `production/clock-validation-20261024-182801.json`，约15.1模拟帧/墙钟秒，不能硬编码按30帧换算本轮实际等待时间。
- PauseManager嵌入 `GameLogic+0x150`。0x5373a5/0xac7f8c等将此this传到DoPause 0x4e03f0；该函数将pauseType写manager+0xc。Unpause 0x4e062e清该值，0x4e0635清manager+0x10。故读取PauseType地址为`GameLogic+0x15c`。
- 主Agent实测：`acceptance/runs/20261024-183816-commander/clock-pre-pause.json`帧2374/type0；Escape输入未生效仍为0，不能算暂停；真实点击任务菜单后`clock-pause-2.json`帧2670/type3，175秒后`clock-pause-3.json`仍2670/type3；截图iron-pause-menu.png与之对应。继续按钮恢复对照由主Agent安排。
- 可将type非0作为本机原生暂停状态证据；类型1/2的具体UI含义和失焦导致的帧停止尚未单独验收，不要只因帧不变就宣称玩家主动暂停。

`read_match_state.py --pid <PID> --seconds 5 --label paused --output <run>/state.json` 提供只读有界采样，默认单样本，最多30秒。包含帧、暂停原始值和下述结果记录；不自动把候选结果升级为整场完成。

## 结果字段候选

原生0x600600按index0..5返回`0xce3378+index*0x20`，0x600620初始化六条记录。离线代码与0x60bd50的debug文案相互对应：

| 记录内偏移 | 含义/证据 |
|---|---|
| +4 | Quit frame，debug文案明确 |
| +8 | Defeat frame，setter0x600650及debug分支支持 |
| +0xc | Victory frame，setter0x600670、debug明确Victory frame |
| +0x10 | disconnect frame候选，setter0x600690，语义仍需结算验证 |

setter写入的都是当前GameLogic+0x50。记录非0可表示该事件被登记，不保证所有玩家都已结束；原生index与大厅槽位/Player+0x20的映射必须结算对照，不能自行减2。尚未用本轮有效整局胜负校验，工具固定match_ended_verified=false。

补充：TheVictoryConditions全局0xcdd1a0、vtable0xc07ab8，构造0x575c60。其+0x48为20个Player指针，+0xa0为20个逐玩家败旗（0x575c00 getter和0x570c95败方路径），c0/c4及c8..cd原始字段可供结算对照。读取器也会采这些。`match-state-46760.json`采样时已经是frame0/mode9、participants=[]、所有结果frame清零，属于离局/重置后的负结果；不能作为活体对局基线或判定哪方获胜。应在结算画面退出前读。GameLogic地址本次并未变化，frame回退也必须使旧session失效。

## 信标/战略指令候选与限制

SDK `Includes/AIBeaconType.xsd`：Assault=0、HoldPosition=1、HoldObject=2。`SkirmishAI/AIStrategicDirective.xsd`：Normal=0、Assault=1、HoldPosition=2、HoldObject=3、Help=4；没有独立Raid枚举。

真实动作表571 `PLACE_AI_BEACON_LOCATION`（player、BeaconType字符串、waypoint字符串），case0x5acfa4→0x586240；572 `PLACE_AI_BEACON_OBJECT`（player、BeaconType字符串、namedObject），case0x5ad015→0x592c90。二者创建原生MSG_PLACE_AI_BEACON（0x21e），添加坐标/对象ID和type，再送入MessageStream [0xce2fb8]。

但不能直接当作敌方AI桥接API：构造消息0x60c440默认msg+0x10取PlayerList的本地人类Player索引；脚本封装的player参数仅用于迭代，没有观察到把该索引改为指定电脑。接收链0x4f51xx将BeaconType映射directive后，在0x4f526b检查Player::0x83b330所返回的co-op关联AI是否等于候选AI。该getter通过Player+0x94关联索引查Player+0x90，具有协同指挥官关系限制。未检验通过前不允许消息错发给人类或宣称独立电脑已响应。

AIPlayer+0x8ec可只读为AIStrategicDirective：序列化0x8d1f1c用明文类型名写该偏移；构造初始化为Normal。原生setter0x8a0940不仅写enum，还清状态、清相关信标/事件、重设时限与反馈；wrapper0x8a0a90负责额外完成/取消反馈。目标位置、信标所有者、阵营关系与来源语义仍需进一步确认，不可强写字段替代调用。有限攻击/骚扰实验应等完整验证目标电脑及可见动作结果后再开放；当前只确认生产执行原语，不称为全部战术接管。

## 独立AI的原生敌方优先级候选

动作459 SKIRMISH_AI_SET_FAVORED_ENEMY→0x583c80；515 SET_ENEMY_PLAYER_PRIORITY→0x583d00。链为Player+0x90→AIPlayer+0x6f8→对象+0x34（enemy selector），没有co-op关联限制。

- 0x8bdb50：thiscall(selector, enemyPlayerIndex, priority)，ret8。检查selector+0x30的u16枚举锁必须为0，原生验证敌方Player后更新集合和dirty状态。
- 0x8af990：清所有优先级，设置手动模式；459随后对指定敌人设置10。
- 0x8af9c0：清指定敌人；0x8bdbc0设置自动方案；0x8bdbe0恢复默认方案。
- selector+0x08/+0x0c是8字节条目的begin/end，每条(priority,playerIndex)；0x8af950按条目+4比较enemyIndex，确认顺序。+0x20为自动方案，+0x24/+0x25为模式原始旗，+0x30为枚举锁。

真实只读样本 `strategy-46760-validated-layout.json`：铁锤人格ID7664d9d9，Player+0x94=FFFFFFFF（没有co-op关联），Normal0、OnGuard13；selector=0x4cb2b80，锁0，自动方案3（SDK StrongestFirst_AllowTies），priority4对应敌方Player2。`read_ai_strategy.py`可复现，只读，不调用上述任何方法。早期`strategy-46760.json`候选解码中的priority/index顺序相反，已标记弃用，以validated-layout文件为准。

这提供影响原生目标选择的有限方向，仍不是突袭指定矿车或完整小队任务接口。两人局只有一个敌人，不适合拿“目标未变”验收多敌优先级策略。调用前还须复核原生线程、输入对象身份和枚举锁；调用后至少读回真实集合及原生任务目标变化，不能只看函数返回。

## 前端枚举调查已关闭

只读 `personality-indexes-40632.json` 证实vector/tree均22项、无丢失，新旧阵营Side指针一致且Skirmish=true。native0xb26630按Side动态枚举，Core9覆盖的GameSetupBase AS按AI_PERSONALITY_OPTIONS的数组length迭代，没有发现固定三项上限。主Agent实际拖动滚动条后看到堡垒/铁锤/幽灵，确认此前是输入未生效。未制作或部署任何APT补丁。

为核验AS，仅在native-ai/frontend-assets中提取并离线反编译原版APT及Core5/8/9覆盖流；使用[pySAGE的MIT转换器](https://github.com/ClementJ18/pySAGE/tree/master/sage_apt)。源码存frontend-reference/pySAGE-master，未安装插件/包或运行其viewer/server。它只提供格式解码；结论以本机提取字节和原生反汇编为依据。
