# V6 单任务目标与能力源资格独立审阅

只读代码、纯测试和已有原始报告，不调用游戏/SDK/GUI/模型，不修改旧q、Native、wrapper或raw。本结论不授source能力。

新runtime q SHA：`a0caa550d1085389fa7df2468103eb78de2c574cf9664a67e48e7fe5b51d92ff`。冻结strict q仍为 `11db71035259efa285e3516224e95fc220b85eb360d1046c4b88de3c9388f692`，wrapper仍a8f48bc2、DLL仍ed17953b，实际文件hash独立核对未变。

runtime仅委托strict再复制checks，移出 `sustained_source_effect`。每次任务其余全部来源包/目标/goal-or-lethal/当前FOV/记忆/接近/期限/干扰/撤退/真实归还/版本绑定仍是必需。原始sustained、reload、hits、时间和strict status事实保留；单发达成目标或来源击杀不能被说成持续burst。

独立运行7项新runtime与3项原V6client测试，10项全过。另直接逐一将其余50个mandatory strict check改False，runtime全部拒绝；strict原结果不被修改，缺少预期check契约也拒绝。实际调用纯 `evidence.verify_purpose` 测synthetic单5伤害目标与单来源击杀，两者都在strict source资格阶段 `raw_purpose_evidence_failed`，不能凭runtime完成升级capability。

源码确认source仍调用strict q6，并要求实际多hit、reload、记忆丢失/重获/位移和完整原链，另把runtime q文件SHA作为supplemental锁定；client只从可信schema选择V6 runtime q用于progress/final，仍需child exit0、native phase3/error0、16383/active0与return。Host的终态重算使用相同runtime q，未把异常exit或未知控制状态放行。

真实run142348/continuous-paid-v6-01-combat-v6.json重算仍失败：raw damage_total90、目标150，但phase4/error32/return0；runtime_goal=False、restoration=False，完整链qualification.source_damage_amount=0。90是原始观测计数，不能直接混入完成任务的qualified damage或全场效果。旧失败未改写。

synthetic短目标完成只证明协议语义边界，不是新现场战术效果。实际能力授证与后续整局验收仍须真实source完整链及每任务目标、撤退和控制释放；经济干扰与胜利因果不由此推出。
