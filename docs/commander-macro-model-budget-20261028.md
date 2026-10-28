# 真实模型宏观预算闭环

属于新版G2/G3/G4的限定研发通过，不是G0–G8完成，也没有发布新客户端。核心只选择原生预算策略，单位操作继续由原生AI执行。

## 配置与本局身份

- 当前桌面登记的指挥官为铁锤，UUID `57e668b4-4d89-43bd-bc92-0dd436f046ef`，模型 `deepseek-flash`，连接ID `23968c8e-25d3-47bd-8c84-5f0d5bbfd43b`。
- 通过正常ProfileStore API将旧单兵实验说明迁移为宏观指挥说明，修订由3变4；保留模型、连接、稳健风格及攻击2/风险1/经济4/侦察3/追击1。迁移前后公开原件在 `reports/macro-model-intake-20261028-v2/`。不改写受保护凭据或库连接。
- 修订4的effective hash为 `05877a505447b3650f2e3dee86c4c38fe4cca868c864f1d246233640698be395`；library hash为 `ce86a43480f2df54e95291937acbb11041f3bc144d2f6f1cf67a1b24216255fd`。
- 本局session `7b34e141-8398-4e54-909d-a0227a9c10f6`，PID71320，raw FILETIME134375983864796117，包SHA `2bb7bb23a448d962e25f7bc76f498c0aa5d9239ceb0a78e3a442c8457b842276`。P3试验人格对原生中等Oleg，观察者不操作部队。

真实请求只在本局身份/合法视野握手完成后，使用正常 `load_profile → apply_commander_draft → create_applied_backend(pydantic)` 路径；没有注入假transport。公开证据不包含密钥、DPAPI内容或endpoint。每次派发前重查当前配置修订、库登记SHA及effective hash。

## 已验证边界

`integration/host_runtime/macro_policy_runtime.py`重新读取冻结的经济预算、helper失联与到期试验，核对源副本SHA、原生制品、会话、13个标志清理及原生比例，才提供 `budgeteconomy` / `budgetarmy` 两个动作。建造、生产、侦察与任意区域调度不因此获准。

到期试验原件 `reports/macro-policy-expiry-71320-20261028-v1/`：60帧期限自动清零，运行中的自有hook/独占锁仍保留；随后正常stop，phase2/error0/active0/mask0/cleanup1/self_hook0/lease0，helper退出0。此次使用epoch7；后续模型试验分别使用epoch8、9、10，C++源相同，每个新制品均通过28个mask互斥检查。

## 真实模型试验

| 记录 | 真实返回/接受 | 原生结果 |
| --- | --- | --- |
| `reports/macro-model-budget-71320-20261028-v1/` | 3/3 | 三轮军费预算，52次匹配选中定义及比例；74次合法观测，无读错误，正常停止 |
| `reports/macro-model-budget-71320-20261028-v2/` | 2/1 | 一轮互斥预算被拒绝且不派发，下一轮经济预算实际采用；17次匹配，正常停止 |
| `reports/macro-model-budget-71320-20261028-v3/` | 4/4 | 经济→经济→军费→军费；59次匹配，90次合法观测，无读错误，正常停止 |

共9次真实返回、8个有效计划。v3四轮首个比例匹配帧依次为8696、8870、9054、9258。经济策略为投资40/生产25/防御10/科技15/备用10%，军费策略为投资10/生产70/防御10/科技5/备用5%，特殊行动均0。只读比较的是实际原生bank与选中定义，不是把模型计划中的budget数字当成写入结果，也不宣称证明了付款。

v3每轮请求的完整公开上下文在 `model-macro-events.jsonl`，记录发送前SHA和字节数，随后对应实际provider返回的HTTPS/expected-origin/nonloopback/HTTP200/完整响应回执及请求、响应SHA。后三轮公开上下文均含前轮模型策略及已采用的原生预算反馈。对话尾部因8192字节预算被压缩为空，前轮策略和原生反馈仍保留在working_memory中。队列/闲置工厂数仅为未观测的保守下界，每条反馈都明确标记；己方角色数只覆盖审计模板，不将未知信息伪装为已知。

修正宏观BattleAgent仍生成旧build/combined_arms提案的问题后，v3所有实际请求的active_goals及编队操作列表均为空；宏观动作由独立策略控制器处理。旧试验原件保留。

## 独立复核与停止

`acceptance/assess_macro_model_budget.py`重新连接配置、源副本、真实provider回执、逐轮计划、原生命令ID/seq/mask与原生比例观测。`v3/independent-assessment-v2.json` 的12项检查全部通过，包括反馈进入下一次模型请求、仅有效计划派发、stop后没有新增模型调用、原生清理和helper退出。停止后的原生预算已不再选中macro定义。

最初 `independent-assessment.json` 的两项false来自复核脚本：误要求Windows相邻事件时间戳严格不同，以及误要求对话尾部非空。已用严格日志顺序+非倒退时间戳、实际working_memory策略/反馈匹配修正，新增2项检查测试；原始失败报告和全部实机记录未修改。不是放宽原生效果或网络证明要求。

研究局随后自然进入统计资料页，局时约12分41秒；只读watcher保留536条生命周期记录，无读错误，最终frame归零且13个宏观标志表为空。`acceptance/runs/20261028-021306-macro-probe/` 保存结算图、信息页及50740字节回放 `Macro71320-model-budget-research.RA3Replay`，SHA `1db4684b9ab226c16f1ee95c4a2bbc0135ae543906518c3f69bab83132f480e4`。胜负索引到玩家的映射、回放播放和外部gate重现仍未核验，不报胜方，不计G7或基线样本。9次真实请求发生于本局的三个有界研究窗口，并非客户端从开局到结算持续指挥。

最终软件检查：strategy239项、原host_runtime442项、battle_host16项、新控制器/请求审计12项、公开投影2项、复核器2项通过。此前一次strategy回归发现静态测试以self=None调用旧请求投影，已修复并完整重跑通过；失败日志保留。

## 未完成

当前产品 `battle_host.py` 的macro动作列表仍为空；这里通过的是从当前配置读取的研究宿主，不是当前桌面启动、许可、停止、导出全链G5。预算策略不自动等于经济扩张、实际支付或科技建造已完成。还需施工/出厂关联与数量控制、侦察结果用于后续决策、部队区域改派、客户端发布和完整自然对局、回放重现、原生基线与风格对照。正在运行的研究局即使自然结算也不直接计为G7。目标保持active。
