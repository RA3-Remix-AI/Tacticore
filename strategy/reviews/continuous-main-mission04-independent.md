# 首个连续主攻校准独审

原件：`acceptance/runs/20261025-095141-commander/main-mission04.json`，SHA256 `52d1de2a627fac62a94454d1ad0cc984b8ee330ba7e0463d2948400324f4d929`。本目录同名 Python 脚本不调用 producer 的 qualifier，仅读取原始事件、固定文件与被动终态侧证，生成同名 JSON；没有 GUI、游戏命令、模型或 API 调用，原件不改。

**允许将本例作为 continuous main_attack 的长程能力来源。** 骚扰仍需要另一条独立指令及原始记录，不能把本例改名计作第二个案例；这也不是正式整局的 LLM 战术完成证据。

24 项原始事件检查、7 项冻结构建比较、6 项被动终态检查全真。零伤害、错来源演员、无撤退、同帧伪到达、错武器 entry、破坏 DamageInfo 六个独立反例均被拒绝。

- 同一会话 `478a4a5d-b18e-4d03-9bea-9415f4d02256` / PID63320 / player3 的征召兵830，目标为当前视野下的敌方精确 SovietRefinery774。
- 3392 帧移出 AI，3398 帧初始 Stop 清态后进入接近。此时到可见目标 429.374；从真实 stage2 起点到准备点的租约内实际位移 **315.512**，不是采样前的原生移动。两个 source1 正常 Move 链齐全。
- 普通 Toggle 一次及三个不同帧闲置 AK 后，fresh Stop 清态，3527 帧唯一正常 ScriptAttack，source1 / INTMAX。三个调用层均指向指定目标、同一实际 AK entry。
- 3531 帧 setter 和 Body 同 tick：来源830 → 目标774，HP **2400→2395**。Body 调用参数指针精确指向 rawstack 内的当前 DamageInfo，头 BE9508/BE9318、Actor830、双 AK asset447ea26e、GUN21、金额5；没有仅凭某个孤立栈常数认定因果。
- 3532 帧同一 active entry 的弹量 **3→2**，位于新订单之后、撤退之前，符合零延迟 AK 直伤的同次发射窗口。actual getter 对应模板/asset 的现场绑定也一致。
- 3532 帧进入撤退，两个正常 Move 经已记录 checkpoint 返回自己的真实起点附近。实际撤退位移 **311.364**；3648/3649/3651 三个不同帧均到点≤15，最终距原点 **4.406**。
- 五次 Stop 各有三个不同帧清态。3656 帧真实 Transfer(true) 与 native pool add/return 链齐全，`phase3/error0/16383/active0/return1`。租约内未见原生覆盖，归还后的自然重招募不算覆盖。
- 独立比对 `main-mission04-terminal-readonly.json`：源报告 SHA/session/PID 相符，timer0，14 个实际入口字节逐一匹配该 DLL SHA 固定的 inert-layout 地址集合及原字节，不只相信 restore_mask 汇总。

总期限7884帧保持不变，实际3392→3656的全链处于该窗口内。本例证明一次真实有界接近、指定来源伤害、撤退及恢复控制，范围仅为已核验征召兵正常准备后的 AK 地面目标战斗。
