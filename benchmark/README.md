# 固定地图性格比较：基准设施与验收项5

**真实验收未通过。** 本轮没有启动游戏、控制游戏、请求真实模型或开展玩家盲测。已完成的是证据聚合软件、合成测试和待执行的3个角色×3场矩阵。`synthetic-demo/`中的9场均为本地合成事件，不能报告为打了9场游戏。

## 运行

在本目录使用Python 3.10+标准库：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest -v test_aggregate
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' demo.py
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' aggregate.py .\synthetic-demo\synthetic-assault-1
```

`test-results.txt`记录自动测试结果。`demo.py`只生成合成fixture和汇总，不联网、不读密钥、不调用游戏执行器。

## 证据契约

每个run目录包含`manifest.json`、`events.jsonl`，真实run还需要事件引用的原始采集文件。完整样例在`synthetic-demo/synthetic-assault-1/`。

manifest冻结会话UUID、电脑玩家索引、指挥官稳定UUID与性格配置哈希、地图、阵营、对手协议、难度、游戏/Mod哈希、供应商/模型名、基础提示模板哈希和观察时间窗。真实绑定验证由采集器负责，聚合器不将任意owner当电脑。显示名可修改，角色配置在同一实验中不能悄悄漂移。

`source_kind`只能是`synthetic`或`live_game`。同一run、同一次比较不能混用。live_game还需`live_control_verified=true`；这个布尔值须来自已通过的真实接管验收，不能由演示模式自行设为true。聚合器仍不把标签、布尔值或文件哈希当作完整真实控制证明。

事件公共字段：

```json
{
  "event_id": "event-1",
  "kind": "decision_requested",
  "run_id": "synthetic-assault-1",
  "session_id": "示例实际需规范UUID",
  "player_id": 3,
  "commander_id": "示例实际需规范UUID",
  "source_kind": "synthetic",
  "game_time_seconds": 1,
  "data": {"request_id": "request-1"},
  "evidence": null
}
```

真实事件的`evidence`必须含run目录内相对文件路径和SHA256。文件存在、大小在限制内、解析后的路径位于run目录、内容哈希匹配才接受。**同一个文件可以支撑多个相关事件，但文件内容的含义仍需可信采集器或人工复核。** 聚合器不会验证截图里是否真的出厂，也不会根据某个地址出现就认定单位已生产。原始证据不是日志秘密内容的存放处。

严格拒绝重复JSON键、NaN、未知字段、跨绑定事件、重复事件或结果、游戏时间倒退、重复单位ID。支持以下有限事件：

| 类型 | data字段 |
| --- | --- |
| decision_requested | request_id |
| decision_result | request_id, status：accepted/rejected/timeout/adapter_error |
| plan_activated | plan_id, intent_sha256 |
| production_requested | production_id, unit_type |
| queue_observed | production_id |
| spend_observed | production_id, amount |
| unit_produced | production_id, unit_id |
| production_failed | production_id |
| task_planned / task_started | task_id |
| task_result | task_id, status：completed/failed/cancelled |
| blind_vote | observer_id, guessed_style：assault/economic/raider/unknown |

`intent_sha256`应由可信宿主对规范化战略意图计算，排除plan_id、时间和解释文本。相同意图刷新不算变化。原始策略服务日志需由专门适配器绑定run/证据后转换，本聚合器不会直接将策略服务的模拟status当真实事件。

## 指标语义

- 无效决策率：rejected / (accepted + rejected)。超时和适配器错误单独报告，待返回请求单独计数。
- 策略变化：首个计划不算变化，仅后续意图哈希变化计数；相同意图刷新不算。没有任何计划观测时，变化频率为null，而不是0。
- 真实生产确认：同一请求必须关联已入队、可归因花费、实际出厂三类证据。只观察到单位或只看到资源净减少都不够。一次请求按一个期望单位设计；批量订单应拆为多个请求ID。
- 生产完成率：已确认生产 / (已确认生产 + 明确失败)。另报排队中、未入队、出厂但花费未确认，以及确认出厂/排队请求比例，避免隐藏未完成情况。
- 任务完成率：completed / (completed + failed)。未启动任务不能报完成或失败；执行中任务保持pending；取消单独报告。
- 玩家辨认率：正确猜测数/有效投票数，unknown计入总数但不算正确。没有真实投票时为null；合成演示没有生成虚构玩家投票。
- 缺少分母或证据时为null，不填0。计数只表示已观测事件，不表示采集覆盖完整。

## 匹配比较

`compare()`要求地图、阵营、对手协议、难度、游戏/Mod版本、供应商、模型、基础提示版本、时间窗和种子控制状态一致。角色性格是待比较因素；若要比较模型，应另建以模型为因素的实验，不混进性格比较。

拒绝重复run、重复角色/轮次、同一会话冒充独立对局、同一角色中途改变性格配置。若已有受控种子接口，则同一轮的各性格必须使用相同种子。当前没有已验证的种子接口，预注册明确设置`uncontrolled`与`seed=null`，不声称随机轨迹相同。

按性格汇总使用累计分子/分母，不对比例做不加权平均。`minimum_three_by_three_matrix_complete`只说明每种性格有某个稳定角色至少3次独立记录，不能据此自动宣称性格可辨认或因果成立。真实结论标志始终false，需完成下述人工与游戏验收。

## 待执行矩阵与盲测

`preregistered-matrix.json`安排铁锤/堡垒/幽灵各3场，工业区、旭日角色、固定盟军空中施压对手协议、中等难度、10000资源、600游戏秒观察窗，按拉丁方顺序平衡场次顺序。**对手协议尚未实现或验证，九场均未开始。** 游戏/Mod/模型/提示版本必须在实际启动时记录并冻结。

盲测至少以5位未接触标签的观察者为试点，隐藏名字、性格标签、模型信息和泄漏身份的语音，展示相同时长和阶段、相同镜头处理的片段。记录随机观察者ID，不记录联系方式。只报告正确/总数与unknown数量；小样本不能自动声称统计显著。胜率可作为附加结果，不能替代生产、任务、策略稳定性和可辨认性指标。

## 旧移动实验审阅

`legacy-trace-review.json`复核两份既有游戏坐标实验：一次距目标5.62，另一次最接近31.31后离开至523.17。它们属于单单位命令与坐标证据，没有多角色固定协议、真实队列与花费、同条件重复场次或盲测投票，因此不能作为验收项5通过的依据。

## 真实验收尚缺

1. 可恢复且可靠的持续控制权和模拟线程接入。
2. 运行时建造方向切换，以及真实队列、可归因资源花费、出厂单位的关联采集。
3. 经过核验的角色/电脑玩家绑定、固定对手协议与模型版本。
4. 至少9场独立的匹配真实对局。
5. 隐藏角色标签的实际玩家辨认记录。

所有新增文件只位于benchmark目录；未修改正式Mod或其他Agent代码。
