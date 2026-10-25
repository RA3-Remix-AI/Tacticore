# 验收项2：生产方向控制与只读证据

当前结论：**尚未通过真实建造方向切换**。已获得有效资源、工厂接口，并观测到2次自然AI入队及返回生产ID匹配真实节点。主动一次Flak实验已构建，由主控单独执行；本子Agent未执行游戏调用。

## 只读采样

    python observe_production.py --session ../acceptance/active-session.json --snapshot ../reports/snapshot-<当前局>.json --samples 10 --interval 0.25

脚本核对EXE SHA256、PID启动时间、记录的Mod哈希、明确session_id，以及活体电脑Player/AIPlayer、工厂类型/归属/生命。地址复用和同PID换局仍需由主控的会话变更与游戏时间标识进一步确认，故输出始终标记game_session_independently_verified=false。

资源向量为Player+0xe4/+0xe8，第0项的+4与+0x14之和来自原生UI调用链。记录余额变化不等于某笔生产花费，不能单独归因。

已采到：

- observation-20261024-174344.json：资源9340→9259→9174；苏联基地接口0x0591039c，虚表0xc3f8c8，UNIT_BUILD函数0x723f50。
- observation-20261024-174618.json：苏联兵营0x0571ee40，生产接口0x0467119c，同样调用0x723f50。
- 第二局旧地址与后续结束后的地址被身份校验拒绝，未把清空状态读成队列成功。

## 队列与ABI证据

unit-build-disassembly.txt确认正常命令按钮UNIT_BUILD分支提供8个栈参数。活体接口所指0x723f50入口明确以interface-0x24作为完整ProductionUpdate this，ret 0x20。参数1为模板，参数2为非零时批量5/否则1的标记，参数3被复制到节点坐标区，剩余参数尚未完整命名。直接调用不能替代完整按钮前置验证；尚未调用。

queue-xfer-disassembly.txt确认原生ProductionUpdate::xfer使用完整this+0x34队首/+0x38队尾，节点+0x54 next/+0x58 prev；kind=1的模板位于+0x10，kind=2的升级模板位于+0x14。节点+0x18为生产ID；正常enqueue赋值+0x30为计算后的cost（0x724207）。这些静态语义有证据，但动态任务关联、交易归因、出厂事件尚未通过。

曾用完整this0x05910378只读解析到链表节点0x040f7ad8，kind1、模板hash0xc45aaeab。按错误的interface直接加0x34则得到空队列，说明必须确认this偏移，不能把空值当成队列为空。

采样器仅在精确匹配0x723f50入口签名或识别出明确this-adjustor时尝试解析队列；循环/坏后向链接/未知kind/错误尾指针都会拒绝。队列语义依旧标记provisional，未达到生产验收。

## 被动生产观察器

    ./Build-Observer.ps1
    ./bin/observe_build.exe <当前PID> 30 > <当前run目录>/production-observer.json

观察器只对0x723f50安装一个有界MinHook。它验证EXE SHA256、19字节入口签名，原样传递8参数和返回值，记录自然调用的线程、接口、工厂、玩家、模板、caller、短栈、前后队首及按原生返回production_id匹配的节点和cost。

它不主动排队、不改参数、不更改资源。只有state2、error0、original_bytes_restored=true、active_detours=0才表示观察器正常停用；自然调用0仍是负结果。DLL和跳板PIN到当前测试进程退出，避免in-flight释放；同一进程只安装一次。主控统一注入执行，本子Agent未运行它。

## 下一受控实验

首选苏联电脑的真实兵营，防空单位SovietAntiVehicleInfantry。当前TriadFront源XML造价220，BuildTime6；仍需记录包哈希与实际队列cost，不能用源码值冒充扣费。

1. 游戏保持前台，确认已有真实兵营及活体电脑。先被动观察自然enqueue或其共同ProductionEntry构造0x70f2c0，核对调用线程与参数。
2. 正常队列为空时，以明确白名单、单次请求和会话守卫排入1个FlakTrooper。不得通过spawn或赠钱实现。
3. 关联同一生产ID/节点的模板、原生cost、进度与交易扣费来源，再确认对应出厂单位与归属；排除原生AI另行排队、变形、第一次发现和地址复用。
4. 单次enqueue通过也只能证明执行原语；宏观“优先防空”的方向切换还需对比基线并验证持续策略执行与恢复。

## 本地测试

    python -m unittest -v test_observation

9项解析守卫测试通过，仅验证软件在坏链表/未知代码下不误判，不是游戏行为证据。主控负责将实际observer结果合入本目录验收状态。

## 新局自然入队实证

`../acceptance/runs/20261024-175301/production-observer.json`记录PID33852的2次自然调用，线程58012与窗口线程相同，caller0x4f49e7。8.515秒排入苏联兵营hash0x80d4ea1e，返回ID1、匹配节点0x06d6ffc8、原生cost500；28.343秒返回ID2、节点0x04a86538、hash0xcf8d9f20、cost800。两次均为空队列变为匹配节点，参数均为template,0,0xcd7e84,0,0,0,0,0。停用state2/error0、恢复字节、活动回调0均通过。它确认该自然生产命令的线程，不能推断全部模拟系统线程或安全调用时机。

`observation-20261024-175546.json`来自同局有效快照`../reports/snapshot-20261024-175542.json`：10个样本资源6954→6741；基地队列ID3/hash0xc45aaeab/cost2000；兵营0x058a7690、HP1200、接口0x06d6b94c、空队列。没有把余额下降归因为某个节点扣款，也未将首次发现兵营冒充严格出厂事件。

## 单次真实Flak入队实验（仅主控执行）

    ./Build-OneShot.ps1
    python run_flak.py --session ../acceptance/active-session.json --snapshot ../reports/snapshot-<当前局>.json --factory <当前苏联电脑兵营地址> --natural-observation <同进程自然observer.json>

这是独立DLL和host；不安装代码detour，WH_GETMESSAGE仅调度到已观测自然生产线程。Python预检session_id、Mod哈希、EXE、进程启动时间、同进程已恢复的自然8参样本与活体兵营/玩家。DLL再次核验进程启动时间/线程/10秒期限、AIPlayer、owner3、兵营hash/HP/+310/+3c0、接口/vtable/函数签名、空队列和资金≥220。模板经已签名0x7e4230正常lookup读取，再核对Flak hash0x2c358c61；0x723f50仅调用一次，原样使用自然8参。DLL和共享映射PIN到进程退出，防重复执行。无spawn、改钱、改价格或停经济。

输出当前run目录的`flak-enqueue-*.json`，包含前后现金、返回ID、匹配节点与原生cost；同步返回时现金不变不能代表免费生产，因为扣费可能随进度发生。必须继续采节点/资金与真实单位创建，单次入队成功也不代表持续方向切换通过。

DLL error：1线程/期限，2启动时间，3PIN失败，4代码签名，5电脑身份，6兵营身份，7HP/生产组件，8接口，9非空队列/余额不足，10模板库，11目标模板，12调用后未匹配队列。错误1–11均在enqueue之前拒绝；12可能已调用，禁止重试。其他错误同样不得换DLL绕过一次性守卫。

## 本次主动实验结果与证据落盘修正

主控曾尝试运行旧版包装器，但工具输出未保留，run目录没有`flak-enqueue`报告，因此主动调用是否发生、是否成功均为**未知**。PID33852随后仍可按PID检出，不能从一次按名称查询无结果推断游戏退出或崩溃。18:05:16只读打开一次性映射`Local\\RA3FlakOneShot_33852`返回ERROR_FILE_NOT_FOUND(2)，见`oneshot-mapping-read-20261024-180516.json`；没有可恢复的队列返回状态。没有重试旧地址。

旧包装器仅在子进程正常返回后写报告，这是证据缺口，已修正：启动即在production目录持久写尝试记录，读到session后镜像run目录；dispatch前先原子替换、flush/fsync记录`dispatch_pending`与结果未知；timeout、进程启动失败、无有效JSON或包装异常均在finally落盘。若包装器被强杀，dispatch前记录仍能表明执行可能发生，禁止自动重试。原生结果丢失时不会从exit0推断成功。

本地共13项测试通过：原队列解析9项，新增不启动进程的4项mock测试涵盖dispatch前可见证据、timeout部分输出、启动失败、exit0但无JSON与合法结果保留。它们不能代替真实游戏实验。当前验收2仍未通过，主动结果未知，不计入真实建造方向/花费/出厂证据。

## 支付与出厂的严格追踪（2026-10-24继续验证）

已构建并真机被动验证5个入口，源文件`production_trace.cpp`和`trace_shared.h`，构建`Build-Trace.ps1`。所有参数/返回值原样转发，只在原生回调中记录；不对enqueue入口安装detour，因此兼容OneShot严格签名守卫。

| 入口 | ABI / 证据 |
| --- | --- |
| 0x7ba770 | thiscall无栈参数；this=完整ProductionUpdate+0x10，原生生产更新。TLS保存本次更新所属module。 |
| 0x70f440 | thiscall(node, Player)，ret4。node+0x68是累计实付；调用资源扣款后把返回实际金额加到此字段。 |
| 0x849220 | thiscall(resource, 8参数)，ret0x20。仅caller0x70f578且同步支付TLS的node/id匹配时归因；记录实际返回金额。 |
| 0x73e390 | thiscall(完整module, template, creation*, 0, xyz*)，ret0x10。仅caller0x7baffe且同生产更新TLS的node/id/template匹配时，把返回Thing关联到订单。 |
| 0x789bf0 | thiscall(完整module, node)，ret4。完整module是正确this，非interface；正常tick结单caller0x7bb7b6。 |

完整module在tick入口EDI-0x10，保存于push EBP后的[ESP+0x28]；create和complete均从此槽取得ECX。代码签名、EXE、PID启动、session/Mod哈希、已自然观测线程、电脑/兵营归属均校验。只记录选中兵营的Flak，计数溢出、字段/ID/线程或会话不一致均不能通过离线验收。5个hook停止须restore_mask31、active0、error0；DLL/跳板PIN至进程退出。

`trace_production.py`输出持续flush/fsync的JSONL：原生事件、0.25秒队列/资源只读样本，以及独立持久派单回执。原生create之后按Thing指针+对象ID+owner+hash复核真实活体与坐标，不使用首次扫描发现冒充创建。`assess_trace.py`把原生debit返回累计、node+68连续累计、创建、结单和活体链逐项核对。

    python trace_production.py --session ../acceptance/active-session.json --snapshot ../reports/<当前snapshot>.json --factory <当前兵营> --natural-observation <同PID已恢复的natural-production.json> --seconds 45 --enqueue-once --queue-limit 2
    python assess_trace.py <production-trace-*.json>
    python assess_trace.py <production-trace-*.json> --natural-only

`--queue-limit`默认0；显式允许最多2个已有订单时，只能尾部追加一个Flak，禁止取消/覆盖。Python和DLL均核对头尾/next/prev、node->module->factory->owner、类型、唯一生产ID、模板白名单（征召兵/防空兵/战熊/工程师）与已付不超过cost。native调用后再次核对原订单ID/模板/成本/已付和顺序未改变，新ID/新节点唯一且位于尾部、初始已付0。error13表示调用后保留校验失败，可能已经入队，禁止重试。单进程仍一次claim。

包定位支持session明确`mod_big`，或`mod_config`/arguments中唯一modConfig的唯一相邻add-big。拒绝目录穿越、多BIG歧义与哈希不符。旧未知session有显式拒绝清单，不会重试33852。

## 已完成的天然闭环实证

PID40632/session ba6ce741-341e-4bf6-998c-086a1df3feef，独立TFNames包SHA256 2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665。run `../acceptance/runs/20261024-182145-commander/production-trace-20261024-182801-e05b157f`停止恢复通过、事件连续无丢失。本轮主动请求在Python队列非空守卫前拒绝，明确active_enqueue_attempted=false。

离线`-natural-assessment.json`确认4条天然Flak链：ID21/22/23/24各成本220、90笔同步节点扣款总额220、累计实付从0到220、原生create返回对象ID797/799/801/803、同订单结单并有5–27个活体样本（HP/归属/hash一致），距兵营约91.46单位。天然链通过不能算桥接主动入队或宏观建造方向切换。

`clock-validation-20261024-182801.json`：4条链各100次支付更新，相邻GameLogic+0x50步长1，首次支付到创建99帧，墙钟6.547–6.563秒，当前运行段约15.08–15.12逻辑帧/秒；进度0→100、90笔正扣款与10次零增量更新。此实测比例不替代暂停/其他运行段的时钟核验。

最新本地37项测试通过（9队列、4失败留证、10严格关联、7包定位、7短队列）。仍需主控在fresh session实测一次短队列追加，并完成真实模型策略选择与有效整局；本目录不会据天然闭环把验收2改成通过。
