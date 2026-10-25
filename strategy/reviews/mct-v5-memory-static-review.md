# MCT5 目击记忆最小版本独审

只读静态审阅及本地纯测试，不调用 SDK、游戏 GUI、模型 API，不改变执行器或原始现场报告。结论限于建议 Root 批准首次现场诊断，不能代替真实效果授证。

最终候选 DLL：`ae795d2838b2c00db1110882ee1d6cb5ae5d6c82864592b414539b3a5aab4e9a`；host：`8705dc41e824ed748dbe82df319c9a69f86a16f0ba45b6c615fd04b01db087d4`；wrapper：`5d899ccee768fce81b79a83fc15658baf7d8b16a2fea313ad5c238af94dc4319`；核心 qualifier：`2fa543daaee3773e4b650fe2325960df355a93df7d62bab42ac9d462a710d8d8`。先前未装候选261bf不沿用。

## 通过的静态边界

- 初始合法可见记录 event64；后续只在完整当前视野检查通过的 kind3 发布时更新记忆位置与帧。隐藏段冻结历史点，公开 visible_target_xyz 为零，不更新隐藏 HP或断言死亡。
- 视野检查先完成关系、隐形排除、footprint cell与记录检查，再读取目标 XYZ和HP并复核中心。记忆接近只下正常 Move，prepare和Attack仍要求重新获得完整当前视野。
- 900帧记忆 TTL依据最后合法目击计算，不由 Move、进度或模型刷新延长；记忆点附近未重见仅等待45帧，然后走正常撤退。engage失视野仍退出。
- 初审发现45帧等待的 return 曾在总 approach期限检查前。作者在零安装窗口将总阶段期限提到 TTL与等待之前；最终独立重读已确认修复，原2100/hard4500总限不延长。
- 校验器逐事件重建身份、可见记忆更新、隐藏冻结、Move目标、TTL、重获与攻击门槛，不信 mutable header 自证记忆正确。

独立运行 `python -m unittest -v test_mission_combat_v5`：最终11项全部通过。另对 hidden-memory 事件分别注入 bool/string目击帧、float逻辑帧、NaN/string坐标及错目标ID，6个额外 typed/nonfinite 反例全部拒绝。

## 现场仍须证明

必须观察同任务真实合法目击、失视野后沿冻结点接近、同ID完整FOV重获、实际normal Attack和来源伤害、原点回撤及正常控制释放。只有未见期间走得更远不构成完整效果。MCT5仍是single-source-hit验证，未证明持续交战、经济压制或胜利因果；旧MCT4失视野失败不追认。

## 追加：独立 qv2 路由复核

Root 在任务终态后批准新增 `mission_combat_v5_qualification_v2.py`，SHA `fc467262b9830241f3c4b1d007ae93ca3e38786659cf1ce82aceb3c55bbd5591`。旧q、DLL、wrapper和原始raw保持原样。逐行差异仅为正常Move四联组从所有事件改取真实exclusive租约内且tag6的执行器命令，并增加 `qualification_revision`。

原始租约内tag0外来命令仍由完整 `no_native_override` 与counter互证单独拒绝，没有因为筛选自己的四联链而被忽略。记忆、FOV、来源伤害及撤退恢复要求未改。独立运行 `test_mct5_qualification_v2` 7项全部通过，包含真实client工作函数的fakechild路由测试（旧wrapper assessment不被调用）、同帧租约前后自然动作、在途外来Move、伪零计数、断链，以及真实0命中报告仍失败。

这次纯校验修正不构成新实机效果证据；尚需真实新case。后续正式Host/client核验必须一致选择该明确qv2，不能只修改某一边缓存结果。
