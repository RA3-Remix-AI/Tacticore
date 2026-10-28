# 近场原生准入、武器读取和构建策略

本阶段晚于实机只读采样。新代码尚未装入游戏，游戏SDK及模型请求均0；活动d168、NativeHost和candidate13未改。完整G0–G8继续active。

## 原控制器仍是租约来源

`Owner::original_lease_snapshot()`只读返回原Reserve捕获的home、起始帧/墙钟、截止帧、姿态、演员和当前持有状态。`accepted_attack_current()`同时检查原移动控制器仍处于Holding、命令及全局序号匹配、近场处于Prepared/WaitingDamage且未取消。停止请求立即取消这项资格，不等下一次tick。

新增`NativeAdmission`直接引用这个Owner、原`MemoryIO`和原生目标/武器读取器。它不接收调用者提供的Sample、ready或visible字段。Prepare可检查一个尚未接受的较新命令；真正facade/private边界还必须属于Owner已接受的同一个Intent。

每次复核独立读取实际演员、出生记录、队伍回链、原Stop94/source1、姿态2、空路径、foreign epoch、原租约900帧/120秒上限、工作期限及非暂停。目标必须仍是注册表中原key与完整身份，当前电脑视野完整可见；武器必须配对一致、AK47就绪。距离限制仍为120、home范围20–300、Z差2。最后再次采样演员及当前Owner，任何读取途中变化、时钟倒退/超过250毫秒、停止或序号变化均拒绝。

`NearNativeObserver`的原Stop见证现在保留到攻击实际交付：只提交或存储攻击请求不等于状态已经改变。否则设置attack_attempted后，facade/private的即时复核会被自己的见证提前清除而必然失败。实际交付后旧Stop不能再证明就绪；新的返回Stop仍须走原完整命令归属链。该改动尚未实机。

准入拒绝不等于已经撤销游戏中的待发命令。观察钩子仍转发每个原函数一次，延迟交付无法归属时保留foreign/unknown；真正取消必须使用已实现的正常Stop替换证明，并取得后续实机证据。

## 武器和构建策略

`WeaponReader`将上轮实机验证的身份关系落实为独立配对读取器。它从实际容器按原生活动槽遍历，核对Thing/ID/模板/update/owner、slot/entry/asset、WeaponStateMachine及反向指针；检查同帧、同线程、读完后的时钟和完整快照一致性。仅WeaponReadyState0、弹药1–3、请求标志0、状态机低位无标志才ready。当前request_limit原值照实保留，包括2147483647；它不是实际射击次数证明。其他武器和未知构建策略拒绝。

`NearBuildPolicy`没有公共构造器。Windows工厂独立验证当前进程ID、线程、创建FILETIME、游戏文件名/基址，以及固定SHA的游戏、mod、视野能力、模板审查、三层征召兵XML与Weapon.xml。八个已验证文件的只读句柄保持到策略销毁，期间不允许写入或替换。此策略仅提供精确构建/源审查范围；不会自行借兵或授攻击能力。

150射程来自固定源文件的AK47规格，近场硬上限仍120。它尚未成为当前运行时编译数据的独立射程证明；新读取器及策略的正向实机复核仍需完成，不能由源文件审查宣布当前武器参数或实际射击已验证。

## 本轮验证

- 8组新增C++检查在真实x86、x64执行，使用显式字节内存和模拟NativeCalls；实际`MemoryIO`、Incarnations、原移动控制器和Owner共同经过Reserve/移动/保持，再复核准入。覆盖未接受命令不能取得SDK边界许可、伪造home/命令、停止即时撤权、丢视野后旧key不复活、耗尽/非就绪武器、目标过远、实际来源/队伍/身份变化、过期/暂停以及复核途中变化。没有实际付款或游戏SDK。
- 原47组与新增8组共55组，双架构共110次组执行；PE machine独立核对。另4组Win32未安装边界含当前helper不能构造游戏构建策略，原51组移动/停止测试体对NearMoveLineage回归通过。
- runtime Python99项通过，包含冻结编译/链接/PE/SHA和原v1输入/输出核验。新政策只有helper进程拒绝路径的真实执行，正向游戏路径未验证。

下一步仍需新原生Owner/Execution工厂与目标key ABI接线，保留已验证付费出生和原180秒NativeHost边界；再补实际射击/伤害关联和正常交付、取消、丢视野、停止、死亡、双兵回家归还。G6三战术、G7模型自然整局及G8贡献对照均未完成。
