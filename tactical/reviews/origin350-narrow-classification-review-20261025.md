# Exact 四类的狭窄 fire 类别：独立结论

**结论：当前 exact 编译包中的 SovietConstructionYard / SovietBarracks / SovietPowerPlant / SovietRefinery，已有足够独立实例证据支持“无自主直接火力或驻军开火模块”这一狭窄类别。** 依据是完整原生模块清单和 exact 源链相互印证，不是null指针推论。四类属于独立同帧实例证据，不声称它们构成一份全局原子战场快照。

这个结论不等于safe origin、零乘员或经济无威胁。实时敌方排除还须对**当前full-footprint可见的同一实例**进行模块双采、身份和时刻复核。已提供独立pure helper；本次没有改350 guard、freeze或任何执行器，没有SDK/GUI操作。

## 实证及编译绑定

源：`origin350-own-inventory-fresh01.json`，PID63904、session `95907ea7-26bf-4d4f-9a98-08d92e26273f`。Reader以只读权限打开进程并验证其启动时刻/EXE hash，verify_session_package复核权威session指定的实际BIG文件hash，采集后session/包/logic稳定。包为`2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665`，EXE为`ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`。

| exact 实例 | frame起止 | 完整模块数 | WeaponSet注册引用 | 全部Contain类 |
|---|---|---:|---|---|
| ConYard763 / c16ff13f | 469→469 | 31 | 0，无WeaponSetUpdate模块 | EngineerContain、InfiltratorContain×2 |
| Barracks765 / 80d4ea1e | 469→469 | 25 | 0，无WeaponSetUpdate模块 | EngineerContain、InfiltratorContain |
| PowerPlant767 / cf8d9f20 | 469→469 | 27 | 0，无WeaponSetUpdate模块 | EngineerContain、InfiltratorContain |
| Refinery769 / c45aaeab | 470→470 | 29 | 0，无WeaponSetUpdate模块 | EngineerContain、InfiltratorContain |

逐个均通过Thing地址/ID/type/template/owner/Body/HP身份核对、完整null终止module数组双采、所有module反向Thing指针、每个primary-vtable+8常量名称getter的只读解码。所有module都被枚举并识别，未以字符串筛选代替完整遍历。武装Scout/Conscript对照显示实际WeaponSetUpdate及有效六模式entry矩阵；Scout768恰好跨帧的那一行保守保留为无效，未影响独立有效结构行及Scout770/Conscript771对照。

`origin350-independent-per-type-fresh01-review.json`重建四个实例的原始检查，四类instance_evidence均verified。原采样文件整体状态仍是unknown（整组469→470），保留不改；该全局状态不会抹掉有效的逐实例双采。

`origin350-exact-structure-audit-20261025.json`绑定该包和manifest `aec863b2e91cecaa4031f87a124c8d04e6bd45862d38fa76a823b69e9a8fafc5`，列出四个exact编译asset instance及源继承/fragment。`origin350-source-module-tag-inventory-20261025.json`重新校验这些源文件hash，全部仍匹配。这里没有声称对整个编译module-data payload逐字节反编译；针对“模块类别存在/缺席”，真实full-module清单直接覆盖当前实例，源链用于解释该类语义与条件危险。

## 为什么驻军阴性足够狭窄成立

四类完整运行时module清单没有Open/Garrison/Transport/Horde或其他未知Contain类，只有原生EngineerContain和InfiltratorContain。SDK schema二者扩展ContainModuleData，而GarrisonContain扩展OpenContainModuleData；exact源配置是工程师捕获/维修及间谍效果，不是普通乘员射击入口。原生名字的类型区分已有EXE常量getter与factory注册依据。不存在已配置普通驻军开火module时，无需再凭“当前乘员数=0”证明这种路径不能开火。

自然场景没有己方武装结构或可驻军结构阳性，覆盖缺口如实保留。它们可以增强通用reader覆盖，**不是这四个exact实例类别的必需前提**：当前结论限定到四个已完整列出、与固定包源链一致的module multiset；其他类型，包括已知驻军楼，默认仍威胁。没有外推通用“Contain都不射击”或“null容器都不射击”规则。

## pure helper 与实时输入边界

`origin350_exact_structure_classification.py`不执行I/O，不调用SDK或游戏函数。`facts_from_sample(report, row, visibility)`构造输入；`instance_evidence(facts)`仅复核独立实例证据；`classify(facts)`还要求：exact包/EXE/type、完整模块类multiset精确匹配、全部同帧双采及活体身份稳定、注册武器容器为0，且同session/PID/frame的`VisibilityCollector.private_targets` enemy proof对同一address/ID/owner/type/template/Body/HP具有full-footprint与stealth-safe证明。getter复杂、module增加/未知、武器引用非0、跨帧、过时FOV、身份改变、未知或移动类型均keep threat。

成功结果仅为`exclude_from_immediate_direct_fire_only=true`；`safe_origin_verified`、`zero_occupants_proven`、`capability_granted`始终false，radius维持350。未提供真实当前敌方proof的四个己方源样本，分类器仍不发实时排除permit。可见实例adapter必须从可信collector取得输入，不能接受模型自填“可见”或把己方样本地址搬给敌方。

32项离线边界测试通过，包含原子实例跨组帧保留、index5/空entry反例、增加驻军模块、复杂getter、错误包、移动类型、FOV过时/部分可见、owner改变等。测试中构造的FOV为显式synthetic fixture，不计真实当前敌方许可。

条件危险持续保留：CATALYST死亡爆炸200、radius100、delay1.5s；摧毁/出售spawn；兵营正常生产；ConYard变成移动MCV；矿厂生成/停靠矿车。矿车及所有其他移动/碾压实体始终独立算威胁。建筑退出“即时自主直接火力”集合不取消这些风险检查，也不允许放宽附近移动威胁或350半径。
