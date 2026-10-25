# Support 原地 Move 失效：正常 Stop 链的独立核验

## 原始事件证据

`acceptance/runs/20261024-234355-commander/formation02.json`，SHA256 `e5d48d68a6b4fe01b7b52a9c3e4da74fbd459bb6838b0bb24d7f90bae7636239`：

* 同一租约 1016..1196，front 779 原始目标为 3009.512939,2869.675293，最终 3010,2870，最小偏差 0.585374。
* support 792 的 hold 请求为自身初始 2910,2890。它在 frame 1034 首次离开 hold 半径 15，最终 2890,2910，偏移 28.284271；未进入下一阶段。
* 两单位 `native_move=0`。这仅说明已钩住的 privateMove 没有新外部覆盖，不证明旧 Path/locomotor 状态已经停止，也不区分“旧路径继续”与“新目标投影到邻格”。

同目录 `movement-hold-evidence.json` 和 `movement-audit.py` 可重算。front 按设计在 stage1 移动，其离开 initial hold 的距离不是失败依据；support 的保持和两角色 joint 条件仍失败，不能用 front 成功代替组合成功。

## 独立核验的正常 SDK Stop 调用链

从同 SHA 的 EXE 重新读取指令和表指针，未调用函数：

1. 脚本 handler 分支 `0x5a7777` 调 `0x590ca0` 解析单位；`0x590cbe` 把参数明确写为 1，`0x590cc6` 把 this 设为 `AIUpdate+0x24`，尾跳 `0x54b0a0`。
2. `0x54b0a0` 构造 kind 5 命令，调用接口首虚方法。本机文件指针 `0xc48528 -> 0x787500`。
3. 命令分发表 `0x787d4c[5] -> 0x787784`，这里将 source 入栈并调用实际 AIUpdate vtable `+0x8c`。受检 vtable `0xc48670+0x8c -> 0x721ad0`。
4. `0x721ad0` 有对象模板/状态/容纳运输等守卫。在执行分支 `0x721c4d` 调状态机虚 `+0x38` 清当前状态，再经虚 `+0x20` 切 state0，`0x721ca8` 写 `Update+0x50=source`；函数 `ret 4`。
5. 本机 SDK `Schemas/xsd/Includes/Common.xsd` 的 CommandSourceType 顺序是 `FROM_PLAYER, FROM_SCRIPT, FROM_AI, FROM_DOZER`。脚本调用强制 1 和枚举顺序相互支持 `source=1` 的 SCRIPT 语义。它是命令来源，不是精度参数。不要仅把旧直接 Move 的参数从0换1就声称修好了 hold。

这些证明链与 ABI，不证明现场调用一定接受、队列已经排空、旧运动已经停止。优先让 producer 的新独立 revision 使用正常 facade，保留全部原生守卫；不要直接把 `0x6efa70` 内部路径清理函数当公共 Stop。

## 两种不同状态守卫和时序

* `SM+0x78` 非零时 `0x603a70` 跳过 XYZ 更新，`0x601890` 也跳过目标浮点字段。`0x601850` 将其置1；`0x601860` 置0；`0x601870` 临时置0、调用 SM 虚+38，再置1。这是目标更新抑制的静态证据，当前旧报告未采这个字段，不能认定本次它一定为1，更不能直接改内存清位绕守卫。
* `SM+0x79` 是另一字段：`0x787567` 检查它，非零跳 `0x787d36`，将整个命令经 `0x830220` 交到接口 `+0x2ec` 的容器。它支持正常 facade 可能推迟处理的判断。
* 因而不能在同一个 callback 内做 `facadeStop(); directMove();`，只凭 facade 返回推定 Stop 已执行。若 Stop 被延后，新 Move 可能先执行、又被迟到 Stop 取消。阶段门应是实际 privateStop 回调之后的后置证据，再在后续模拟 tick 发 Move。
* `0x6efa70` 的静态效果确实包括释放 `Update+0x150` 的引用计数路径对象、将该指针归零、清 `+0x430/+0x43a`，再调虚 `+0x270`。但它没有正常 facade 的全部约束和命令来源处理，不应直接调用替代 Stop。

## 新窄 revision 应采集和判定

由唯一现场 runner 在 producer 的新校准构建中执行；本研究未操作 SDK 或 GUI。

* Stop facade 前、实际 privateStop 进入/退出、后续模拟 tick：记录同一 actor 身份、source/caller/thread/frame，SM+78/+79、current state 指针及 ID、requested/effective XYZ、Update+168 XYZ、Update+150 旧路径及经过界定的节点坐标。
* 若 facade 没到 privateStop，或 privateStop 后未进入预期静止状态/旧路径未清且几何仍在推进，不进入新的 Move 阶段。
* 支援 actor 保持采用原始 hold 点和原始半径15的连续原始坐标证据；Stop/Move 调用次数、函数返回或单帧静止都不代表保持成功。
* 自己的自然局部攻击/避让/碰撞仍可能在 Idle 中发生。正常 Stop 不是永久冻结机制；继续记录所有自然干扰并用几何条件判断，不屏蔽这些日志。
* 任何 Stop→Move 新 revision 都是新校准；旧4a4226/32dc58构建的失败报告不回填、不改评估结果。两个角色的阶段、同 tick 几何与恢复证据必须重新完整通过。

附 `movement-disassembly.txt` 已扩展收入主要 Stop、SM 锁与命令排队分支，便于不依赖 producer 的文字结论复核。
