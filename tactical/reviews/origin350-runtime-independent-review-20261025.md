# 350-origin 四类结构：独立运行时证据复核

当前结论：**尚不能授予排除**。已取得四类己方结构的稳定 null WeaponSet 指针样本、武装步兵的六模式矩阵，以及 EXE 的注册/构造语义；尚缺完整实例模块清单、firing-contain 阴性及已知武装结构/驻军结构的运行时阳性对照。guard、半径350、旧freeze和执行器均未修改；没有SDK调用或GUI操作。

## 已完成的真实只读观察

`origin350-own-slot-matrix-20261025.json` 绑定 PID53720、session `a9ea5dec-52a5-4770-b747-a692c625cf37`，起止 frame3280、paused3。使用现有 `Memory`（OpenProcess 0x410，只读）及 `own_candidates(...,3,...)`；未读取隐藏敌方对象。全部记录有自身地址/ID/owner/template/weapon-container 前后身份复核，session前后相同。

| exact 类型 | 实例ID | Thing+37c | 证据边界 |
|---|---|---|---|
| SovietConstructionYard / c16ff13f | 763 | null | 不是“零武器”证明 |
| SovietBarracks / 80d4ea1e | 765 | null | 同上 |
| SovietPowerPlant / cf8d9f20 | 767、786、804 | null | 同上 |
| SovietRefinery / c45aaeab | 769、776 | null | 同上 |

武装对照770（熊）、771/774（征召兵）的 WeaponSet 容器均有正确Thing反向指针，每slot vtable为c3a6e0，getter为6dbe80/6f88e0，六个模式均逐个读取；非零entry的vtable c2e324、slot反向指针及WeaponTemplate资产链均验证。

| 对照 | selected index | mode0 | mode1 | mode2…5 |
|---|---:|---|---|---|
| Scout770 | 0 | c3957a1d，ammo1 | null | 全null |
| Conscript771 | 1 | **null** | Molotov 41872ecc，ammo1 | 全null |
| Conscript774 | 1 | **null** | Molotov 41872ecc，ammo1 | 全null |

这个对照尤其重要：征召兵源模板还配置AK，当前mode0却为null。因此**完整六个当前entry指针也不是完整的配置武器清单**；不能把模式实例的暂缺解释为模板没有该武器。可能存在按状态实例化/重建，具体生命周期未由本样本唯一确定。需要槽配置schema与所有条件Weapon定义的独立绑定。

第二次模块清单采样时比赛已自然结算，读取 frame0、own rows为空。`origin350-own-module-inventory-20261025.json` 如实保留这个结果；它不是任何结构的阴性证据。旧enemy地址没有用于复读。

## EXE 已确认的语义与剩余界限

`origin350-native-layout-evidence-20261025.json` 保存离线objdump片段；EXE SHA256 `ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`。

- Thing构造 `7c1c90` 在`7c1cf8`写入实际Thing vtable c4db60，`EBX=0`，随后`7c1ee9`将Thing+37c清零。因此null是合法初始化状态，不能仅据此断言已完成实例永远没有武器模块。
- 模块注册 `79d530` 的`79d975…79d9b7`以原生名称ID识别 **WeaponSetUpdate** 后写Thing+37c。`51e3b0`另有设置该字段的入口。样本的null意味着当时该引用不存在；结合完整模块数组才可核对该类模块确实缺席。
- 原生`775a11…775a54`从Thing+310读取full-module指针数组，每次+4，遇null结束；full-module+0xc为behavior接口（注册函数`79d5d2…`也使用此接口）。这支持下一次逐项读取并复核数组，而非猜测Thing+238是乘员容器。
- `6f7c60`遍历container+24…28的slot向量；`6dbe80`在selected index=5时直接返回null；`6f88e0`读取slot+94的指定模式entry。三者均是当前实例选择/entry语义，不能替代全配置证明。
- 当前运行时WeaponSet primary vtable=c45a18；**名称getter在primary vtable+8**，为775900，字节`b8 70 5a c4 00 c3`，返回字符串WeaponSetUpdate。primary vtable+0xc为缓存nameID函数775910，不能误用。`origin350-native-name-getters-20261025.json`列出其余类的常量名称getter与候选primary vtable；只有WeaponSet的candidate已与3280实例交叉验证。

| native名称 | 名称getter | 候选primary vtable（需实例/构造对照） |
|---|---|---|
| WeaponSetUpdate | 775900 | c45a18（已与实例交叉） |
| EngineerContain | 7078c0 | c31210 |
| InfiltratorContain | 6e8760 | c24dd0 |
| OpenContain | 782a70 | c461e0 |
| GarrisonContain | 794b00 | c48450 |
| TransportContain | 782ec0 | c466f0 |
| HordeContain | 7939e0 | c48058 |
| HordeGarrisonContain | 7b3280 | c4cf80 |
| ContestableGarrisonContain | 7b37d0 | c4d3f8 |

原版SDK的WeaponSetUpdate.xsd允许一个hardpoint多个条件Weapon（Ordering排序，含Upgrade/ObjectStatus/ForbiddenObjectStatus），且还有Turret/HierarchicalTurret/Contained等slot类别。当前校验只支持c3a6e0 getter的slot；遇其他slot vtable必须unknown，不能按同一布局读空。

## 下一次最小补证与可实现边界

只采己方初始四类实例和已有的可见控制对象。逐实例：绑定same session/PID/start/EXE/package、Thing/template/owner/id；读取Thing+310完整null终止module数组（有限上界、无重复、每full-module+8反指Thing），镜像primary-vtable+8已验证的常量名称getter；读前后数组及身份、frame稳定。getter不是已验证形式、数组不终止、存在未知模块/指针或替换过程，均unknown。记录全部真实模块名称、behavior接口和对应编译schema，而非只筛“不含Garrison”几个字符串。

然后用已知有火力的结构与已知可驻军结构做阳性：前者必须识别出完整WeaponSet/槽配置，后者必须识别Garrison/Open/Transport/Horde相关模块；即使其当前没有乘员也继续算威胁。3280只有武装步兵阳性，没有这两个结构阳性，不能声称已完成。

若完整实例清单与exact编译模板链一致，确认没有自主武器更新/其他自主攻击模块及firing-contain路径，才可以提出狭窄的 `no_autonomous_direct_fire_or_firing_garrison_verified` 分类。该分类只排除**即时直接火力**，不称no_weapons、安全原点或零乘员，不在本报告授予。敌方采用前必须来自当前full-footprint FOV通过的VisibilityCollector.private_targets，且派单前重验身份、模式及替换状态；旧源证/己方对照不单独成为敌方实时permit。

条件危险仍保留：Catalyst死亡武器、摧毁/出售生成单位、兵营生产、矿厂生成/停靠移动矿车、ConYard打包成MCV等；所有移动物体（含无普通枪炮的矿车、碾压车）、未知对象、武装结构和firing-garrison都留在威胁集合。这里没有证据改变350半径或当前判定。
