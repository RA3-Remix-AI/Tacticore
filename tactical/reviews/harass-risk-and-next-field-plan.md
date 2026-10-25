# 单兵骚扰风险与下一次实机计划（独立只读复核，2026-10-25）

结论：V6 已实证持续 AK 伤害与自然装填，但骚扰任务失败。对满血矿厂要求单兵站定打出 150 HP，然后再走约 1944 距离回家，当前证据不支持其生存预算。下一次应验证有限伤害后的完整撤退、归还；这只是战术闭环试验，不证明经济压制，也不授予能力。

## 硬证据

- 原始文件：`acceptance/runs/20261025-142348-commander/continuous-paid-v6-01-combat-v6.json`；SHA256 `4705b88bc368e1d9105244b3c67b53176c5e36e4b5d0721f81d3983485d18964`。独立复核参见同目录 `continuous-paid-v6-01-production-independent.json` 与 `tactical/reviews/v6-death-and-runtime-completion-boundary-20261025.json`。本复核没有改 raw、执行器、验收器、冻结文件或实机状态。
- 征召兵 773 → 矿厂 774：初距 2081.917；829 开始接近，1507 唯一 ScriptAttack，接敌距离约 147.984。1511…1641 有 18 个同源 AK/GUN packet、Body commit 与弹药下降对应的真实命中，每次 5 HP，共 90 HP；5 次自然 `0→3` refill。矿厂入场 2400 HP，实际目标 `min(150, .2×2400)=150`，未达；90/2400=3.75%。
- 1641 ownHP95，1643 ownHP0、error32；没有完整 retreat / normal return。8.047 秒死亡处置侧证只能证明 disposed 和独占控制释放，不能算返还活单位或任务完成。自身 incoming Body packet 未记录，不能据此归因熊、矿车或任何其他攻击者。
- 当前磁盘 `E:/RedRar3/Data/RA3_1.12.game` 的只读 SHA256 与 V6 记录一致：`ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`。V6 的真实武器绑定为 asset `0x447ea26e`，1507 的 reported entry/template/schema/header 链在 raw 中存在。
- SDK `E:/RA3Modding/SDK/SAGEXML/GlobalData/Weapon.xml:3556`：AK 射程150、clip3、GUN伤害5、不能移动射击、需要视线；reload .3–.5 秒。该文件 SHA256 `7a82e52aa6142f96271173195366227b21a552657bd683f7a33a22e770e1bad1`，与验收源证一致。`Armor.xml:196` 的 BaseFactionStructureArmor 对 GUN 为100%，SovietRefineryArmor 继承它，不能误套其他 StructureArmor 的50%。
- 当前 mod 源 `E:/RA3Modding/SDK/Mods/TriadFront/data/objects/SovietAntiInfantryInfantry.xml` 保留100 HP、速度50和原 AK 模板；征召兵价格为85（原版 SDK 是100，不能混用）。`objects/SovietRefinery.xml:350` 为2400 HP，与 raw 入场值相符。当前 mod XML 中未发现 AK/Molotov 模板或上述炼厂护甲的重定义。这是静态旁证，不单独证明当时加载的全部编译内容。
- V6 记录 package SHA256 `2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665`，对应 `native-ai/staging/compiled-commanders-20261024-182027-17286524/build-report.json`，审计记载842个 baseline资产保留、增加12个 commander资产。当前工作区 `Mods/TriadFront/TriadFront.big` 是 baseline SHA256 `8bada8d0…`，不能冒充 V6 加载包，也不能推断当前活动进程的包身份。

## 推断与未知

150 HP 需要30个实命中、10个弹夹；V6 到第18个命中时已距 ScriptAttack 134帧，随后2帧死亡。按这一次样本的节奏，150需要显著更久的站定暴露；不能把这个估算当稳定DPS或生存保证。SDK 的不能移动射击意味着单兵不能同时保持 AK 输出和拉开距离。

将低血量撤退阈值从 .4 提到 .8 仍抓不住这次95→0的跳变。真实死因、敌方接近路线、是否存在碾压/近战/瞬间伤害及撤退路安全均未知。未观察到敌收入、采矿周期、维修支出、矿车停工，故不能把90 HP称为经济压制。

SDK Molotov 的射程200、对建筑投射物和爆炸伤害提示后续可能更适合静态建筑；但现证据链仅验证 AK，本次不切换武器、不声称投掷物伤害或收益已经验证。

## 下一次最小实机方案

1. **选择目标**：1名满血、已落地且准入合格的征召兵；优先距离400–700的当前可见静态矿厂，回撤点取派单前实际自身位置。排除已观察到防御塔、近战/反步兵单位、车辆活动覆盖的接敌点和回撤走廊；必须记录筛选时刻与可见威胁，视野外情况保持未知。无合适接敌/回撤路线则 no-dispatch，不为过验收创造低血目标，不扩展到尚未验证的矿车动态追击。
2. **推荐独立新策略版本**：目标30 HP；达到同源伤害目标即正常 Stop→Move 回撤；首次 ScriptAttack 后60帧仍未达目标也撤退并记部分/失败；保留 `.8` 血量阈值作为额外早退条件。60帧只是风险上限，不是安全保证。V6前6次命中在1511/1518/1525/1539/1543/1549，30 HP于 attack+42帧可观察到、包含一次自然装填，支持先试两弹夹的假设；需新 raw 重证。
3. **冻结 V6 的合法替代**：现 `mission_contract.py` 强制 `.2/150`，`mission_tick.inc` 和 strict q 也硬编码相同公式；engage_frames 仅允许180–300。因此不能只传 `cap=30/engage=60` 并称 V6 合法通过。若不另做策略版本，只在自然遇到入场HP150–175的当前可见矿厂时沿用原公式（目标30–35，即6–7个5HP命中），达标即正常撤退；设置 engage_frames=180、retreat_hp_fraction=.8、保留原回撤预算。其未达目标的超时暴露仍有180帧，不能声称有60帧保护。无此目标就不派该试验；另找不同战术机会，旧150失败保持。
4. **验收预先固定**：同一新 raw 中必须有唯一正常 ScriptAttack；目标/自身绑定与可见性连续可信；至少6个确切同源 AK/GUN packet＋commit＋对应ammo下降、累计有效损血≥30；至少1个同entry自然 `0→3` refill且 refill 前后都有确切命中；正常 Stop 后实际回撤到事先锚点（连续3个不同帧在15半径、垂直差≤10），实际回撤位移至少120，期间没有死去；最终正常 Stop、活体 normal return、timer/hooks/control 完整释放。任何 deadline、HP早退或死亡只记录部分/失败。派单、耗弹、header damage_total、死亡disposal均不能替代这些证据。
5. **报告范围**：成功时仅称“短袭击造成≥30 HP且生还归还”。不能把它改写为旧150目标成功、整局压制或完整能力来源；严格 source 验收要求的记忆/隐形冻结/重新发现、长返回等仍需对应真实轨迹，不能合并旧失败片段或合成fixture补齐。整局对原生电脑的结果另行验证。

若下一版本需要被动死因观测，最小追加是：只在自身 Body 的实际健康提交时记录 frame/tick、pre/post HP、同包 source actor ID、weapon/warhead asset、damage/death type及 requested/actual damage，并绑定自身和来源对象当时的身份；无法解析就记 unknown。无需新做GUI、攻击命令或外部工具，也不能用全局hook计数推定攻击者。本复核未追加任何观测工具。
