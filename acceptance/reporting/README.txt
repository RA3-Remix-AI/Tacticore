离线证据索引与复核工具
====================

用途
针对人工明确列出的冻结文件，检查来源SHA/大小、同局绑定、配置修订、记录标识及截断。
输出公开review.json，分别列出 configuration、model_consumption、production、task、effect、
physical_home、control_release、natural_settlement 八层材料状态。

provided = 存在能够解析、匹配pin和绑定的来源材料；不是游戏实效验证通过。
invalid = 已提供的材料不合法或不完整；missing = 没有提供相应材料。
所有层的 semantic_verification 都是 externally_unverified，full_goal_complete 始终false。
host_stopped 不能提供归还证明；native_result_candidate 只标为settlement_candidate。
最终status中的native_release_verified仅作为host_status_release_assertion保留，不能授执行权限。

本工具不启动游戏、客户端、模型、网络或原生执行器。只读输入，不改原始证据、不复制原始日志。
它补齐软件索引和一致性复核能力，不能代替G4/G6实际效果、G7自然整局和G8贡献验收。

唯一接入API
from acceptance.reporting import build_review_bundle
report = build_review_bundle(run_root, manifest_path, output_directory)

manifest可以放在独立工作目录，因而无需向历史run写入文件。
输出必须为全新目录，并位于run_root之外；不会覆盖已有报告。
每次产生新目录，不使用会把历史失败覆盖成成功的模式。

命令行（在bridge-probe根目录）
  .\.venv\Scripts\python.exe -B -m acceptance.reporting \
    --run-root <明确冻结run目录> --manifest <私有清单.json> --output <全新输出目录>
退出码：0表示所有八层均存在结构合法的材料；2表示有缺失或无效材料；3表示清单/路径/输出被拒绝。
三种结果都不代表实机或完整目标通过。

运行测试
  .\.venv\Scripts\python.exe -B -m unittest discover -s acceptance/reporting/tests -v

私有清单schema_version=1
{
  "schema_version": 1,
  "binding": {
    "run_id": "<规范非零UUID>",
    "session_id": "<规范非零UUID>",
    "player_id": 3,
    "commander_id": "<规范非零UUID>",
    "profile_revision": 3,
    "effective_hash": "<64个小写hex>"
  },
  "sources": [{
    "source_id": "source_001",
    "path": "downloaded-redacted-diagnostics.json",
    "sha256": "<对文件原字节计算的SHA256>",
    "bytes": 253755,
    "adapter": "host_diagnostics_v1"
  }]
}

source_id限定source_加3至6位数字，避免文件标签泄漏自由文本。
path仅接受run根目录内使用/分隔的相对路径；拒绝..、绝对路径、ADS、符号链接与Windows重解析点。
输入最多128份，单文件16MiB，总pin大小64MiB；JSON最多64层，公开包最多32MiB。
同一路径、内容、source_id重复拒绝；一份清单仅接受一个客户端诊断窗口，避免重复事件窗口累加。
完整性复核包括再次读取已接受输入，若构建期间变化则拒绝发布。
这是普通本地文件的一致性核验，不声称能防御拥有同一文件系统写权限的恶意并发攻击者。

真实客户端适配器 host_diagnostics_v1
只接受schema_version=1、kind=tacticore_redacted_diagnostics、redacted=true的客户端格式。
校验顶层run_id，binding的session/player/commander，effective_profile的revision/effective_hash，
若存在profile_id须与commander一致，status和已知事件中出现的绑定字段也不能冲突。
校验binding_hash、timeline_sha256、events数量/首尾、无截断，以及唯一且严格递增的seq。
SQLite seq为跨run全局序号，同一run允许有间隔，不要求从1开始或全局连续。
total_count和source_snapshot_sha256仍来自宿主导出；没有原SQLite就不能独立证明事件未丢。
时间线中未知事件不投影，来源自由文本、模型名称、provider payload、reason_code、文件路径等不进入输出。
只接受固定枚举、规范UUID/hash和有限数值/布尔白名单，保留为source_claims。
配置应用、模型返回、生产意图/回执、任务反馈与目标效果分开列示。
其中生产意图或任务反馈也仅是来源材料，不自动升级为付费/伤害或完成证明。

未来采集器适配器 evidence_envelope_v1
用于主线显式规范化的新采样，不猜测任意checkpoint、截图或原始日志的语义。
清单source需再指定layer（上述八层之一）。文件格式为：
{
  "schema_version": 1,
  "kind": "tacticore_evidence_envelope",
  "binding": {"同上六字段": "实际使用六字段对象"},
  "layer": "effect",
  "complete": true,
  "record_count": 1,
  "records": [{"event_id": "<UUID>", "facts": {"mission_effect_verified": false}}]
}
绑定必须完全一致；records数量匹配；event_id在本文件及不同来源间不得重复。
facts同样只做白名单投影，kind/complete/verified等标签本身都不会授予真实能力或验收信用。
如果采集格式不适配，新增明示适配器并补负例；不要用"相信此文件"开关跳过校验。

首份真实冻结资料的调用样例
输入根：acceptance/runs/20261027-134626-desktop-match
文件：downloaded-redacted-diagnostics.json
SHA256：daa6ce5846d3edcf68d03865101539b2dcfb69e226b7ac0e7fbd31479f485e8c
大小：253755字节；319条事件，seq 819..1148（其他run导致合法间隔）。
本轮私有清单和公开结果位于仓库外：
  ../parallel-development/20261027-saturday/evidence/actual-candidate13-input-manifest.json
  ../parallel-development/20261027-saturday/evidence/actual-candidate13-review-v2/review.json
首轮过严要求seq连续的拒绝报告保留在actual-candidate13-review，不改写。
v2对配置、模型、生产、任务、控制归还显示provided；效果、物理回家、自然结算显示missing。
来源是用户停止的局部复测，不能因统计页/host_stopped声称正式自然整局完成。
上述provided项仍只是宿主声明和来源一致性，不是独立游戏语义认证。

公开交付边界
公开包只包含review.json和说明，未包含输入文件或输入相对/绝对路径。
源文件名、任意trait/提示词/模型原文/凭据/地址一律不复制；原始文件留在私有run根。
公开索引可供后续审查者按source_id和hash对照私有清单，不提供可重放命令或游戏权限。
