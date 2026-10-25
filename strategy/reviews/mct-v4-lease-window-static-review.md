# MCT4 租约计数边界独审

只读审阅，不调用 SDK/GUI/模型，不修改 V1/V2/V3 原件或新执行器。DLL：`79f5f45529e428b3ba30c172d401a13d05060212bd5bf95ccb470286a92f91dc`；host：`3cf68785eaa07276986366920f5cb0f269c6d4b0ce3025f4a4215c586a0d3a48`；核心 qualifier：`46c62060e7ab983f1a3db39aa9efeccba0a4b281f3503e63dd79024331a639715`。

逐行对比确认原生变化仅为五个 Move/normalMove/Attack/Add/Remove hook 增加 `actor_lease_active` 门控，以及新版本命名、消息和映射隔离。`mission_tick.inc` 与 V3 字节相同。借出前与返回后的原生动作仍记录 raw，但不污染本演员租约计数。issued 与 detach_calls 均真实设置后才计数，returned_frame 设置后关闭；真实 Transfer 调用期间仍有 tagged 上下文。

校验器按真实 Transfer(false) 入口 seq 至 Transfer(true) 完成 seq 定义覆盖审计窗口；私有 Stop 使用发起 return 前的 exclusive 窗口，避免同帧自然 Stop 混入。额外核原始覆盖事件计数与 native 计数相符，不能仅把计数写零隐藏命令。

独立运行正式 `test_mission_combat_v4`：6 项全过。另在 main-mct3-02 的内存复制件上核对 pre/post Move 正确排除；旧 counter2 不互证，改为预期 counter0 只让边界检查通过，整体效果仍失败。五类租约内同帧外来事件均拒绝，伪 counter0 不能掩盖；原始文件未改。

结论：没有发现阻止 Root 批准首次现场诊断的静态问题。仍需新版本真实接近、来源命中、撤退和恢复完整 raw 后才授证。此版本仍为 `single_source_hit_validation`，不证明持续交战或经济压制。语义层暂按 Root 要求冻结，待新 source 合格后再明确登记 V4。
