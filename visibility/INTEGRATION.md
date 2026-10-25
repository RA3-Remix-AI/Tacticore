# LiveBattleState最短接入

当前可直接复用：`capability.bind_session(memory, session, player_id)`、`VisibilityProjection`、`VisibilityCollector.collect(game_seconds)`。不用手写或复制proof的true值。

```python
# sys.path加入bridge-probe/visibility；Memory仍由宿主管理。
from capability import bind_session
from projection import VisibilityProjection
from collector import VisibilityCollector

# LiveBattleState.__init__
self.visibility = None
self.visibility_projection = None
self.private_targets = {}
self.region_points = {}

# collect里，当前有效Memory且inspect_player/UUID已确认后：
# 首次bind有SHA/source核验开销，放在own=sample(...)之前；之后重新采己方时钟。
if self.visibility is None:
    proof, safety = bind_session(memory, self.session, self.player_id)
    self.visibility_projection = VisibilityProjection(
        self.session['session_id'], self.player_id,
        self.session['mod_sha256'], proof, safety,
        ttl_seconds=60)
    self.visibility = VisibilityCollector(
        memory, self.session, self.player_id, self.visibility_projection)
    # proof仅作本地验收日志，绝不附进模型snapshot。
else:
    self.visibility.m = memory  # 使用本轮未关闭的Memory

# 在己方快照/时钟新鲜时立即读取；game_seconds必须在native frame/15±0.25秒内。
battlefield = self.visibility.collect(snapshot['game_time_seconds'])
snapshot['battlefield'] = battlefield
snapshot['capabilities']['regions'] = sorted(
    set(snapshot['capabilities']['regions']) |
    {r['region_id'] for r in battlefield['regions']} |
    {c['region_id'] for c in battlefield['contacts']})
self.private_targets = dict(self.visibility.private_targets)
self.region_points = dict(self.visibility.region_points)
# 当前Memory关闭后，上面私有映射也只是过去的采样；执行前须重新核验。
```

collector最多公开64联系人；策略层再选12当前/4历史。历史region保留旧时间、currently_visible=false、role_counts={}；不能从隐藏敌对象更新历史位置。新Agent首次启动不继承未曾收到的last_seen，重建projection即可。

任何bind/collect错误：私有目标映射清空，当前轮不发敌情/战术命令；使用schema1 battlefield空对象并viewer_player_id=目标电脑。不要把observer2的视角当作失败备用。不要沿用旧session proof或旧private_targets。Session文件变化、GameLogic/Player/AI/shroud指针变化、帧回退会拒绝旧绑定；宿主原有active-session不可变检查应保留。

## 新正式对局自动绑定

相同EXE/BIG/源码/实现/Safety保持不变时，`bind_session`会先重验build能力的6项真实实验与SHA，再核对9段原生签名、当前电脑UUID与Side、当前玩家至少1个完整clear的己方占地。全部通过才产出schema2、method=native_footprint_reconstruction的session proof。早期敌contacts为空合法；之后同一个持续projection会接收真正进入视野的对象。没有来自UI的unlock flag。

build能力文件为 `build-capability-2d7873e1.json`；实现代码或模板审计改变会拒绝旧能力，不可只复制true。改变能力实现应重跑相应验证再重新构建capability。SIG/PID/start_time/包SHA不支持的游戏不启用。

## Recon本地验收数据

- `visibility.vision_metrics`：viewer_player_id、observed_frame、clear_cell_count、total_cell_count、clear_cells_by_region。
- `visibility.private_clear_cells`：当前指定电脑clear网格线性索引frozenset。前后`len(after-before)`可证明新增可见网格；须绑定同session/grid/player，不把其他原生侦察的效果全归因于lease。
- `visibility.frontier_points`：最多12地区的原生位置，来源仅为该电脑CLEAR相邻的FOGGED格及公开地图网格边界；没有读取隐藏敌对象。可达性、水陆和高度未验证，交由原生路径反馈/执行器失败处理。
- `visibility.frontier_regions`：对应region_id、relation=unknown、currently_visible=false、空role_counts。recon开放时可加入public地区列表和capabilities.regions，并在本地将frontier_points并入只供recon使用的目的点表。默认region_points仍只含己方/当前可见contact。

原始bitset、点、地址、HP都不能写入模型上下文。只有有限抽象region标识可见。attack需要本轮private_targets及native再次完整footprint/敌我/隐形检查；历史contact和frontier区域不能伪造已知敌人。

## 当前现场验收文件

session65bb88da-f5dc-48be-a3c1-5b6ee83cb017，frame10211，PID55596，Iron电脑3：

- `session-proof-223120.json`：30己方完整clear占地握手；schema2/method明确。
- `public-live-223120.json`：5当前可见敌contact，strategy Battlefield.from_dict通过。
- `private-live-223120.json`：对应5个private_targets、10已知地区点、4800clear cells、11frontier地区；model_eligible=false。
- `census-223120-a.json`：惰性缓存漏报、中心与占地不同的原生分布；研究总计，不是模型情报。
- `natural-transition-223120-b.json`：30秒57样本/22首次可见/11失去可见/6条可见前状态。尚未用同一个对象在单个窗口覆盖完整隐藏→可见→再次隐藏周期，不拼接不同对象。

当前采用“完整clear + 活动隐形排除 + 已审计固有能力排除”，隐形探测/detected模式未支持。root已明确接受此保守首版。
