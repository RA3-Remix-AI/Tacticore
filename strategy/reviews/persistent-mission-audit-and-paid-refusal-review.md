# 连续任务策略与正式审计独审

## 代码与测试

仅修改strategy，修复了模型保留旧请求时高优先级新任务可能抢同编队/预算的规划漏洞。现在先保留所有在途任务，再处理新意图，旧任务重复出现不二次计费。真实执行器原有单位reservation仍是实际控制的独立守卫。

策略全量168项与12项连续宿主桥接回归独立通过。新增审计器可检查同ID跨plan TTL、多次实际请求/压缩中的任务保留、唯一派发、阶段revision、accepted阶段的单位保留重叠和终态原始效果/释放。实际adapter调用前追加匿名context元数据；没有请求正文、XYZ、endpoint或key，不增加模型调用。哈希和测试细节见同名JSON。

运行：`python bridge-probe/strategy/mission_audit.py --session <run/session.json>`。脚本只读现成文件并输出JSON，调用本地纯校验器，不连接游戏或网络；不要将输出重定向覆盖原件。旧034721胜局实跑结果false/三目的false/来源伤害0，同时明确缺少context元数据与continuous记录，不追认历史整局效果。

## 最新真实paid拒绝

run135011的continuous-paid-formation01-formation.json被最后角色路线检查拒绝。独立pre-native helper全部绑定项通过：exit64、launch intent false、native空、events空、host_exit None；这是0SDK且从未取得单位控制，不是原生归还。父driver独立重算9正常付费完成、8拒绝、1305支出，生产真实5唯一入口字节恢复/31及回调清退均通过。战术效果没有发生。

## 验收边界

本次真实证据仅支持付款链、生产安全交接与派发前拒绝；匿名context的新增多轮测试是本地adapter夹具，不是实际付费模型或战场效果。正式全场必须另有同任务跨多个真实模型请求和压缩、三目的实际qualified效果、撤退及控制释放；伤害不能自动称经济压制，更不能归因胜利。旧V5/V6未自动进入独立legacy semantic route，当前Host/client未调用该未识别模块，继续锁定。

完整验收的多轮记忆证据还要求同一条TTL后已压缩context以唯一snapshot_id+游戏时间精确对应request_id及实际accepted plan；失败调用不能借用另一个TTL前成功计划，相同key重试歧义不作证明。
