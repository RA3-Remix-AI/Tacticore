# 胜率评估：模型指挥是否比原生AI赢得更多

本目录回答一个问题：**在同一地图、同一对手难度下，由大模型指挥的电脑玩家，胜率是否高于只用原生AI的同一玩家？**

只用Python标准库，Windows与其他系统都能运行；测试全部离线（合成对局目录，不启动游戏、不调用模型、不联网）。

| 文件 | 作用 |
| --- | --- |
| `evaluate.py` | 汇总多个已完成对局目录，按配置输出胜率（Wilson 95%区间）、中位时长、决策数、拒绝/未知率、模型延迟，并与原生基线做Fisher精确检验。输出Markdown与JSON。 |
| `record_result.py` | 给对局目录写配置标签 `eval-tag.json`；对没有宿主日志的原生基线对局，补写只含 `run_start` + `match_end` 的 `decisions.jsonl`。 |
| `cua_skirmish.js` | 在 Codex Computer Use 中按已确认的屏幕启动、配置无限岛双人局及启用弈核自动发现。 |
| `test_evaluate.py` | 离线单元测试。 |

## Windows 开局脚本

把 `cua_skirmish.js` 加载到 Codex Computer Use 的 JavaScript 会话，传入已绑定的 Red Alert 3 和弈核窗口来创建 `createSkirmishControls({game, client})`。脚本使用已验证的游戏 2557×1440 和客户端 1363×931 窗口。

先从游戏与 Mod 设置页调用 `launchFromGameSettings()`。在游戏主菜单调用 `gameStep('openSkirmishMenu')`，确认出现遭遇战后调用 `gameStep('enterSkirmish')`。需要时分别选择无限岛、关闭额外席位并指定出生点，按 `cua_skirmish.js` 中的屏幕步骤核对结果。在大厅确认观战席、两名中等电脑、席位与队伍、10000 初始资金和关闭宝箱。

模型组通过 `openMatchPage()` 打开对局页，再调用 `armModelFromMatchPage()`。若该按钮的无障碍节点没有坐标，传入最新截图上按钮的位置。单层组需在启动客户端时配置 `TACTICORE_DECISION_MODE=single`。原生组直接跳过这一步。回到可见的游戏大厅并确认配置后，调用 `gameStep('startVerifiedLobby')`。结算后核对游戏画面和运行日志并记录结果。模型组独立确认归还，原生组确认无指挥宿主，然后用 `leaveVerifiedSettlement({resultConfirmed: true, controlReturned: true})` 从统计页返回主菜单。确认主菜单已显示后，调用 `gameStep('exitFromMainMenu')` 并核对游戏进程退出。

## 数据来源：decisions.jsonl

模型指挥的对局由宿主（`integration/macro_host.py`）自动写出 `<运行目录>/battle-host/decisions.jsonl`。桌面版的运行目录在会话根目录下（`desktop-<id>`）。每行一个JSON对象，`schema_version` 为1，`kind` 为：

- `run_start`：提示版本、模型、地图、对手难度；
- `decision`：每个模型决策周期一条，含局势（己方资金/兵力/建筑、敌方各玩家最后可见时间与可见数量、威胁）、决策（意图、目标、模型自述理由≤300字、有效期）、结果（applied/rejected/expired/unknown、原生是否确认、之后观察到的效果）、模型调用（供应商、模型、延迟、字节数、错误）；
- `effects`：某个决策之后追加的观察效果，读取时合并进该决策；
- `match_end`：宿主停止时写一次，`result` 为 victory / defeat / unknown。只有原生结果槽给出终局胜负才写 victory/defeat；`visually_confirmed` 默认 false，需要人工看结算画面确认。

读取接口：`integration/host_runtime/decision_log.py` 的 `read_decisions(run_dir)` / `read_run_log(run_dir)`；桌面后端RPC `run.decisions`。

## 配置标签 eval-tag.json

放在对局目录（`battle-host/` 的上一级）：

```json
{"arm": "model", "prompt_version": "v2", "model": "deepseek-chat",
 "map": "map_mp_2_feasel6", "opponent_difficulty": "brutal", "label": "第3批"}
```

- `arm`：`baseline_native`（原生AI独自作战）或 `model`（模型指挥）。
- 模型对局缺少标签时，从日志的 `run_start` 推断 `arm=model`、提示版本、模型和地图；原生基线对局必须有标签。
- 同一配置由 `arm`、`prompt_version`、`model`、`map`、`opponent_difficulty` 和 `decision_mode` 共同确定。决策模式以 `run_start` 为准，旧日志缺少该字段时单独汇总。模型配置与**同地图同难度**的基线配对。

## 操作步骤：同一地图/难度跑 N 局原生 vs N 局模型

1. **定实验条件**：选一张地图、一个对手难度、一个对手阵容（例如1v2凶残），以及要比较的模型与提示版本。整个实验中游戏版本、Mod、己方阵营与AI人格保持不变。
2. **定局数 N**：胜率区间很宽，20局时约±20个百分点。建议每组至少20局。按5%显著性、80%把握估算：要分辨50%对70%（差20个百分点）每组约90局，分辨50%对60%每组约400局。两组交替进行（原生、模型、原生……），减少时间段造成的偏差。
3. **原生基线局**：在大厅中按相同方式配置电脑玩家（同一槽位、同一人格），**不启动** Tacticore 指挥，让原生AI自己打完。
   - 推荐：比赛期间运行 `integration/watch_match.py --session <session.json>` 记录原生结算，结束后：

     ```powershell
     python benchmark/eval/record_result.py <对局目录> --arm baseline_native --map map_mp_2_feasel6 `
         --opponent-difficulty brutal --native-state <对局目录>/settlement-watch/result-candidate.json `
         --opponents 4,5
     ```
   - 或者看结算画面后手动录入（并声明已目视确认）：

     ```powershell
     python benchmark/eval/record_result.py <对局目录> --arm baseline_native --map map_mp_2_feasel6 `
         --opponent-difficulty brutal --result defeat --duration-s 812 --visually-confirmed
     ```
4. **模型指挥局**：用桌面应用开始指挥（或 `integration/macro_host.py`）。提示版本默认 v2；要跑 v1，在启动桌面应用前设置环境变量 `TACTICORE_PROMPT_VERSION=v1`（或给 `macro_host.py` 传 `--prompt-version v1`）。比赛打完后宿主自动写 `match_end`。随后写标签：

   ```powershell
   python benchmark/eval/record_result.py <对局目录> --arm model --map map_mp_2_feasel6 `
       --opponent-difficulty brutal --prompt-version v2 --model deepseek-chat
   ```

   若宿主中途崩溃、日志没有 `match_end`，可同时加 `--result victory --visually-confirmed` 补录，结果会追加到原日志。
5. **汇总**：

   ```powershell
   python benchmark/eval/evaluate.py --runs-root <存放所有对局目录的文件夹> --out reports/eval-20261120
   ```

   得到 `reports/eval-20261120.md` 与 `.json`。也可以直接列出对局目录：`evaluate.py <目录1> <目录2> ...`。

## 指标含义

- **胜率**：胜 /（胜+负）；结果未知的对局（未终局、宿主停止、对局退出）不计入分母，单列为“未知”，另给出“未知按负计”的保守胜率（JSON字段 `win_rate_counting_unknown_as_loss`）。
- **95%置信区间**：Wilson区间，样本少时比正态近似可靠。
- **中位时长**：`match_end.duration_s`，为宿主最后观察到的游戏时间（秒）。
- **决策数**：每局 `decision` 记录数的中位数。
- **拒绝率**：rejected + expired 占全部决策的比例（模型输出不合法、过期、宿主拒绝派发）。**未知率**：送达原生AI与否不确定的决策比例。
- **模型错误率**：带 `model.error`（超时、HTTP错误等）的决策比例。**延迟**：模型调用耗时的中位数与P90。
- **对比结论**：Fisher精确检验 p<0.05 时给出 `model_better` / `model_worse`，否则 `inconclusive`（需要更多对局）。

## 不能下的结论

- 观察效果（native task active、己方兵力变化等）只是决策之后看到的现象，不证明因果。
- 原生结果槽的胜负仍需人工目视确认；报告中 `visually_confirmed` 计数说明有多少局经过确认。
- 合成测试数据不能当作真实对局结果报告。

## 旧工具

`benchmark/aggregate.py`、`contribution.py`、`review_host_run.py` 面向性格辨识与证据归因，不衡量胜负，已退役（保留以便复核历史报告）。判断“AI能否赢”请使用本目录。
