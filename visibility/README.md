# 受视野敌情采集：本机 RA3 1.12 实验接口

本目录只读进程与本地SDK/包；不调用游戏函数、注入、修改视野、控制GUI或发游戏命令。敌情默认关闭，现场证明和保守模板审阅完成后才可启用。

## 已取得的证据

本机EXE SHA256：`ec230c6ae1eaee30b0b4fa6ba29d417c974ecae46d6715dfbe786a815935c165`。

- `TheShroudManager=[0xCE2FA0]`，构造0x994070、vtable0xC6AEFC；内部实现指针manager+0x28。
- 原生点查询0x992130→0x9912F0，参数为原生Player索引和Coord3D指针。网格实现：originX/+4、originY/+8、scale/+38、width/+3C、height/+40、cells/+44；每cell0x34字节。cell+32非零直接shrouded3；`u16(cell+4+2*player)`为0→fogged0，为FFFF→全局默认状态[0xD074A4]，其他→clear1。SSE单精度运算后向零截断，不能误用Python floor。SDK W3DDeviceSettings.xsd 明示FOGGED0/CLEAR1/SHROUDED3。
- 对象级缓存：Thing+9C→record，record+24+4*player。6FBA90调用990370读取；0为失效/未计算，1表示原生缓存已判全清，2混合、3/4不允许；最终放行按下面完整footprint重构。**不能把对象缓存0当作地形fog0，也不能把任意非零当作当前可见**。原生lazy getter9903B0会写缓存和通知其他对象，本目录不会调用。
- 指定玩家关系：Player+FC是原生关系哈希表（844680→504E10），key=otherPlayerIndex，value0敌/1中立/2盟，缺失默认中立；self独立判断。不用“owner不相同”推断敌方。
- 原生活体对象链：GameLogic+B4起点、Thing+7C下一项（4E9C0B/4E9C9E）。内部枚举有vtable/环/数量上限；不会把全图对象导出给模型。
- 原生6FDA40检测Thing+C8 bit11/12表示两种活动隐形类别。本阶段两者均排除，**没有宣称实现按玩家隐形检测**。固有隐形/伪装模板另按源码继承审计保守排除；未审计模板全部排除。SDK枚举名不能直接当作运行时位偏移。

现场session `69444a96-7911-4cdd-9a50-99843623fc7f` / PID55596：`perspective-boundary-220820.json`连续三个采样frame340/pauseType3。蓝基地在电脑3视角terrain1/cache1、电脑4视角terrain0/cache4；红基地反向对应。观察者2两处terrain1但cache0，证实观察者全图视角不可借用。该文件含两个研究用隐藏真值位置，明确model_eligible=false，禁止进入模型上下文。

## 接入接口

```python
from projection import VisibilityProjection
from collector import VisibilityCollector
# memory 使用production.observe_production.Memory，包含版本、PID创建时间/session校验。
projection = VisibilityProjection(session['session_id'], 3, session['mod_sha256'], proof, safety)
collector = VisibilityCollector(memory, session, 3, projection)
battlefield = collector.collect(game_seconds)
```

public battlefield只有schema_version/viewer_player_id/visibility_verified/regions/contacts/formations，匹配strategy/battlefield.py；viewer必须是指挥的电脑，不接受人类观察者。没有对象地址、原生对象ID、模板hash、精确坐标或HP。region按512地图单位量化为region_X_Y（负数mN），角色来自审计KindOf大类，无武器射程/反制能力推断。

内部`collector.private_targets`每轮重建，只包含本轮合法可见contact，供本地执行器再次核验：contact_id→address/object_id/type_hash/owner/owner_player_id/xyz/hp/observed_frame/region_id。隐藏后的last_seen不在此映射里。`collector.region_points`只来源己方当前可见存活对象、当前可见contact，不包含隐藏敌方真值。失败时先前private映射已清空，不得复用旧副本。

collect要求调用者game_seconds与当时native frame/15相差不超过0.25秒（本机时钟换算已有独立生产验证），过旧时间参数拒绝。last_seen只保留真正见过的过去事实；失去视野后不更新位置、地区、时间、血量或生死；60秒模拟时间后过期。新Agent必须先见过当前contact，才能接收其历史；新对局或帧回退重建collector/projection。

proof需要同session_id/target_player_id/package_sha256，并且terrain_view_live_verified、object_view_live_verified、conservative_stealth_exclusion_reviewed、no_observer_fallback全真；缺失任何字段contacts固定为空。该proof为现场验收记录，不应自动根据脚本存在、函数地址存在或测试通过而生成。`template-safety-2d7873e1.json`仅源码审计候选，声明source_audit_only=true；不是反编译证明编译字节无隐形能力。当前111候选、58拒绝，未知原版未覆写模板亦排除。

## 可复现命令

```powershell
$python = 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -m unittest discover -s bridge-probe/visibility -p 'test_*.py'
& $python bridge-probe/visibility/sample_visibility.py --session bridge-probe/acceptance/active-session.json --player 3 --output bridge-probe/visibility/readback.json
& $python bridge-probe/visibility/watch_natural.py --session bridge-probe/acceptance/active-session.json --player 3 --seconds 30 --interval .5 --output bridge-probe/visibility/natural.json
```

sample_visibility只导出己方对象和显式研究点，敌contact恒空。watch_natural观察自然遭遇：敌对象在首次terrain1/cache1后才出现在研究报告，可回附一条之前的不可见状态；隐藏后不输出当前位置。watch报告含研究原生ID与曾可见坐标，model_eligible=false。

`audit_templates.py --manifest <编译mod.manifest> --package <精确TFNames.big> --output <新审计JSON>`重建模板候选；读取SDK SAGEXML与SDK Mods/TriadFront/data，不修改其文件或游戏包。

## 待现场验收

1. 同一普通对象未侦察→完全可见→离开视野，分别记录terrain与object cache变化；不能以相邻不同对象代替。
2. collector/projection实际输出：进入时新contact，离开时历史位置/时间冻结，private_targets移除，过期后删除。
3. 有固有隐形或活动隐形的对象即使地形clear也被排除；当前不开放detected模式。
4. 遭遇战真人观察者全图与电脑视角保持隔离；模型传输最终审计不能包含研究报告或private映射。

71个单元测试已通过，覆盖网格边界/float32向零截断、玩家隔离、模板未知/活动隐形拒绝、对象缓存失效拒绝、关系哈希、原生链环失败、历史冻结/TTL、私有目标移除和公共字段不泄漏。测试不能代替以上真实视野进出结果。

## 占地重构与惰性缓存：新增证据

新session65bb88da-f5dc-48be-a3c1-5b6ee83cb017，`census-223120-a.json`在frame920内完成，grid稳定无读错。电脑3视角敌方terrain1/cache1/foot1有5项，terrain1/cache0/foot1有3项；terrain1/cache0/foot2有1项。这分别直接支持“缓存0可漏掉当前可见对象”和“中心点clear不能代替整个对象可见”。研究census只有分布，不是模型敌情。

最新`object_footprint_status(memory,thing,player_index,grid)`从record+1C的16字节cell-reference数组及+20长度完整重算9903B0的clear分支：有效引用cell全部clear，且F9=0才返回1；F8待几何重建则unknown，缺record不走引擎全图fallback。对象cell引用必须在当前grid内，边界/循环/长度不符拒绝。原生渲染回调可能修改非可见3/4状态，本实现均排除，不把这两种状态的细分宣称等价。

collector与projection最新强制`object_shroud_reconstructed==1`，同时center terrain1；缓存仅作为诊断，cache1不能覆盖重构mixed2，cache0不再错误地遮掉完整可见对象。该重构未修改缓存、图像或视野。

最终接入/新session自动握手/私有recon指标见INTEGRATION.md。build能力和session proof为schema2，明确object_visibility_method=native_footprint_reconstruction、footprint_live_verified。当前stage通过71测试；primitive/source/catalog仍不支持隐形探测。
