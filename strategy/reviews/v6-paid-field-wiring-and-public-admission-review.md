# V6 现场驱动接线与公开编队资格独审

只读审阅、本地纯测试，没有SDK/GUI/模型请求，没有修改冻结组件或原始run。按Root预授权，对下面精确候选已直接通知唯一runner可进行首次串行现场诊断；不授证。

- paid driver：`ca8e8b4a4af180ebe19680cdf06bf5df22843c2a615f9b72b1b7909403cc373a`
- 独立 field_combat_v6：`df3b2a7cbebee80df1565eda503f33d341d415ff52d81198ed36957d889ebea8`
- role_route_planner：`897fea98260b4a81122da9da03e120584dc427c35cf99a9f5504b3015cbad9bf`
- Root live_state 最终检查版本：`f803de99a9ada2844ed5e5dd1a3cd34fda1e5caa2aa046b0e6b0c571bfe88c84`

## V6 驱动

paid-driver新增明确 `--mission combat-v6` 分支，默认formation保留。V6规划helper不带execute，只作玩家3视野内、精确静态economy目标与当前可接管Cons的只读选择。实际执行仍先通过相同4000预算/1000保留、paid+created+live链、生产stop、phase2/error0/31/active0及5个唯一真实入口字节；之后最多一个独立V6 helper，显式指定actor/target ID再重采。

独立helper只接受mission-combat-v6，无静默旧版fallback，重新ground/admission、HP、当前完整FOV、可见敌方350范围原点排除以及1800..2600现场选择窗口。未使用隐藏目标位置或替换派发后的目标。child死亡后附加的disposal采集是只读侧证，不是第二次战术派发或效果完成。

独立运行role-route、paid gates与one-child测试21项全部通过；这些是现成共同边界，不冒称已在游戏中覆盖V6分支。额外直接测试独立helper的legacy V5参数，断言在readiness之前argparse exit2，未触游戏读写。首段100..120仅作为搜索优先级，首段60..140、后段40..160、正逆held-clearance门槛保持；不宣称任意边可走。

## 给模型公开的available formations

Root在mission_history模式也采用相同groundV2+idle16/normalMove1入场守卫，核对actor identity与Update；己方总兵数仍保留，reserved在途Roster仍以既有反馈版本追踪，不把旧动作54/驻军77当可派单位。

独立重跑最终18项 `test_live_visibility` 全部通过，含真实已采early01五正例、paused02四负例的纯重放，以及错owner拒绝；重放没有新现场采样。扫描结束一次读取frame：回退硬ValueError，跨度>3或pause不一致仅RetryableSample，不消费旧private lookup派令。此修正仅提高公开资格质量，不授予新执行能力。

当前MCT6 DLL/wrapper/q本体未修改；任何真实新能力仍须按实际raw的有记忆接近、重新可见、持续来源伤害、装填、撤退和控制释放完整链独立验收。
