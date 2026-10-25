# 原生AI接口：阶段1证据与后续实验

本报告的范围是接口探索与可复现证据，不是生产方向切换或完整接管验收。

## 已获得证据

- 游戏EXE SHA256固定为 `ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`。
- 主Agent管理的只读会话PID43656中，完整脚本动作表已读回；`actions-20261024-172021.json`包含动作名、参数数目、元数据字和实际分发case地址。
- `PLAYER_AI_CHANGEUNITBUILDER`真实存在，表索引443、2参数。反汇编显示它把组件enum1、玩家名、bool交给0x583a20；后者经真实Player+0x90进入AIPlayer的0x880e40开关。
- 同一会话内电脑Player=0x031954d0，AIPlayer=0x04645dc0；来源只读快照与实际字段见 `ai-player-20261024-172346.json`。这些地址随后随对局结束失效，禁止复用。
- enum1会切换两个嵌入组件：AIPlayer+0x4d4和+0x564，二者的虚表+4均指向0x885ae0；该函数只写this+0x10一字节。基线两者都为1。
- enum3（经济管理）单独切换第二个组件。因此关闭enum1不等于只关闭单位生产；若要保留经济，只试第一个组件仍须通过动态验收。
- 电脑矿车JapanMiner的AIUpdate+0x50只读值为2。SDK `Schemas/xsd/Includes/Common.xsd`将CommandSourceType按顺序声明为FROM_PLAYER、FROM_SCRIPT、FROM_AI、FROM_DOZER；移动函数确实把source参数写到AIUpdate+0x50。
- 这些证据确认了原生命令来源字段及组件开关候选，不证明开关后的游戏行为，也不证明模拟线程。

## API与ABI候选

详见 `native-symbols.json`，它记录实际文件入口字节、VA、RVA及明确的未调用标记。

| 能力 | 路径 | 限制 |
| --- | --- | --- |
| 原生AI组件开关 | Script action 442..449 → 0x583a20 → Player+0x90 → 0x880e40 | enum1同时影响单位与经济；尚未动态调用 |
| 单位交回/移出AI管理 | UNIT_AI_TRANSFER(451) → 0x583a70 → Player::0x838820(Thing,bool) | 必须确认对象与玩家、队伍关系及原生重招募行为 |
| 队伍交回/移出AI管理 | TEAM_AI_TRANSFER(450) → 0x57b130 | 队伍引用类型不可用裸Thing地址替代 |
| 使用真实生产按钮 | NAMED_USE_COMMANDBUTTON_ABILITY(192) → 0x590020 → Thing::0x790990 → 0x7904e0 | ScriptParam与CommandButtonInfo不是普通字符串/模板指针 |
| 真正UNIT_BUILD分支 | 0x7904e0按LogicCommandType-1跳转到0x790732 | 生产接口及队列ABI须继续读回 |
| 资源对象 | Player::0x83be10(index) | 读Player+0xe4/+0xe8的资源指针vector；战后为空正常 |

UNIT_BUILD分支要求Thing+0x310和Thing+0x3c0有效，取 `productionInterface = [[Thing+0x3b4]+0x14]`，调用其虚表+0x24，静态入参为 `(template,0,&0xcd7e84,0,0,0,0,0)`。这里只确认正常按钮调用路径，不确认8参数含义、队列布局或扣费时机。后续应先读电脑兵营/工厂的具体接口虚表、实际函数、返回清理，再逐级追到正常队列和资源花费。

资源显示链由游戏自身UI反汇编交叉验证：0xACFDEE调用Player::0x83be10(0)，之后把资源对象+0x04与+0x14相加显示。采样应保留两个raw值及sum；不能把Thing.owner+4当现金。收入与支出可能同时发生，单纯余额减少不能单独证明某笔生产扣费。

当前573个脚本动作中未发现可直接按名字启用任意AIStrategicState的接口。已找到的战略相关控制包括敌人优先级、建造时考虑哪些敌人、原生AI组件启停和合作信标；不能把它们描述为已支持模型任意切换战略状态。

## 被动观察器

`Build-Observer.ps1`已构建x86 `bin/observe.exe` 和 `bin/NativeMoveObserver.dll`。由主Agent统一运行：

    .\bridge-probe\native-ai\bin\observe.exe <当前PID> 30 > .\bridge-probe\native-ai\observer-run.json

它校验游戏SHA256和移动入口13字节签名，通过窗口消息线程控制回调安装MinHook，只观察source=2的自然移动，保留原参数和返回EAX；记录实际线程、this、caller和短调用栈。DLL内部watchdog在限定时长后关闭hook，并核对原字节。DLL及跳板明确固定到测试游戏退出，不释放仍可能被执行的代码。一次游戏进程只允许一次观察；控制程序退出不会释放远程DLL或跳板。

只有state=2、original_bytes_restored=true且active_detours=0才表示观察器正常停用；source2_moves=0属于没有获得自然AI样本，不能当线程通过。有样本且thread等于window_thread，也只能证明这些自然AI移动命令在窗口线程执行，不自动证明完整模拟更新线程或线程亲和性在其他接口上成立。

主Agent首次运行观察器的结果已保留在 `acceptance/runs/20261024-173329/observer-run.json`：state=2、error=0、original_bytes_restored=true、active_detours=0，window/callback线程为28636；total_moves和source2_moves均为0。它证明这次观察器安装/关闭/字节恢复成功，未获得自然AI调用样本，不能确认自然命令线程。需要等待矿车实际活动且游戏保持前台后，在新测试进程中重做。

同PID第二局的 `ai-player-20261024-173458.json` 中，owner地址被复用但AIPlayer改为0x04813c60，两生产相关组件为0x04814134与0x048141c4。此结果再次证明地址本身不是关卡会话身份。

## 人格Side空引用

已有历史报告说明自定义人格进入store而Side为空。当前研究提出但尚未验证的线索是：普通Mod流包含 `sagexml\\global.manifest` 等外部引用，前端AdditionalMaps元数据流的加载作用域或初始化时机可能不同。泛化随机人格的Null侧引用有效，并不能推出其映射到各阵营的引用都有效。

不要用热写Side指针掩盖加载/初始化问题；不要继续通过重复添加Side元素修复，因为它只会造成两个空引用。待主Agent提供独立人格实验会话，再对照完整imp/ref表、父人格依赖和元数据作用域进行单变量实验。正式TriadFront未被本Agent修改。

## 下一项验收的最小方案

1. 新对局重读owner/AIPlayer/工厂/资源vector，并保存会话ID、进程启动时间和Mod哈希。
2. 被动记录自然AI source=2和线程，主Agent判定观察器正常停用。
3. 一次性关闭单位生成管理候选（保留经济、基地与战术），确认flag读回；对比同一工厂的新入队行为，然后恢复。仅flag变化不足以通过。
4. 通过已确认ABI的正常生产按钮路径排入一个防空单位，不用spawn、不赠钱、不改造价。
5. 读取真实队列、模板、进度与资源交易，再观察出厂对象与所属玩家；保存事件对应关系，排除首次发现/变形/地址复用。
6. 还原原生开关并复读；失败必须保留原始日志，不能用反复覆盖生产或移动命令伪装接管成功。
