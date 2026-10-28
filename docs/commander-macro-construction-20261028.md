# 反应堆建造偏好与宏观反馈

承接 `commander-macro-production-choices-20261028.md`，继续新版宏观目标。具体选址、施工、寻路和局部交战由原生 AI 执行；没有单兵命令或微操接口。

## 当前接口

`macro_construction_feedback.py`从成对、同局的原生 builder 与己方存活 census 生成反馈。新增施工队列、付款字段及己方施工对象分别统计。原生队列与施工对象没有精确创建回调，因此即便对象满生命值，也不声称建筑已完成。原始地址、模板、生产者、队列和 Thing ID 不进入模型上下文。

模型通过现有 `macro_actions` 选择 `buildreactor`，不附加兵种数量意图。只有当前唯一己方原生建设基地可读、其队列为空、目标建筑不存在、采样在允许时效内时才提供该动作。一个建造或生产意图活动期间不新增第二个意图。原生建设基地被替换时，不能把新建设基地的队列算入旧意图。

控制器在首次新匹配队列、目标对象出现、建设基地变化、有效期到期或停止时撤销偏好。重复计划不延长偏好；已提交原生工作可继续，不自动取消施工。投递结果未知时停止并保留未决记录，不补发。下一轮真实模型请求通过单独的 `macro_construction_feedback` 获得最新反馈，历史记忆压缩不会将其丢弃。

## 资格证据及限制

schema 4 的本机 bootstrap bundle 在现有预算及生产资格之上添加反应堆证据和当前建造源码哈希。模型或 WebView 不能提供文件路径来授予能力。它只授予反应堆建造偏好，不授予任意建筑、科技完成、矿点扩张或区域任务。

`reports/macro-construction-qualification-20261028-v1/qualification.json`重放旧 PID69152 的659次有效原生采样：正评分1807帧，匹配队列及己方施工对象2288帧，原策略清除2785帧。仍为1条队列、1个施工对象、0条观察到付清的队列，model_calls=0。旧固定驱动在首次队列出现后继续保持偏好；新控制器首次队列后立即释放的时序必须由新实机验证。此报告没有把重放伪报成新的模型或桌面试验。

58项宏观控制/反馈检查通过，其中11项覆盖新建造接口和真实历史重放；452项宿主、244项策略及51项前端检查通过。前端和桌面开发构建通过。初次从错误工作目录执行的检查失败日志保留，最终正确目录的检查见 `macro-construction-control-tests-20261028-v3.log`、`macro-construction-host-runtime-tests-20261028-v2.log` 等报告。

## 第一轮真实客户端试验（已停止）

当前 PID75008，raw FILETIME134376102791259663，session `14953a8f-f85d-48e4-bcf0-330717f8ea6f`，run目录 `acceptance/runs/20261028-053118-macro-probe/`。epoch23 native 制品继续使用相同2bb7bb23宏观包；28项mask检查通过。实际客户端通过预检后启动 Host，run `dc61806b-7255-4b20-b7a4-fdd3f5949b11`、Host PID68528。

当轮公开配置为铁锤修订4、deepseek-flash、有效哈希05877a50…。实际客户端SHA `edcc5d2b7cd126c567ddc465fb49ece86aba53bf1817db14a4e8b9ce03ecca4f`，前端JS `index-D6BU5mI3.js`，启动后制品快照在 `executed-client.json` 和 `executed-client-dist/`。9次真实返回、7个实际原生计划，正常user_stop及原生清理通过；没有建造派发，不能算建造效果通过。评审在 `reports/macro-desktop-construction-75008-20261028-v1/`。保留非自然结束标记，结束fixture前核对13标志均清除、lease不存在。

## 提前决策与合同修复

模型决策起点从120秒提前为30秒，原生OpeningMove和资源/前置条件继续生效。PID69944/session0614b42e…实际从早期持续请求，5次真实返回、3次原生预算计划；模型随后选择了预算＋反应堆＋征召兵的组合。模型合同原先允许跨建造和生产组合，而控制器只接受一项有界工作，导致 `macro_construction_action_not_qualified`。该组合没有原生建造派发，宿主fault及正常清理原样保留。实际模型组合在其run目录 `construction-contract-mismatch.json`；不能将这次模型提出建造误报为建造执行。

修复在模型catalog、实际提示词和引擎校验中明确“建造或生产合计最多一项，可附加预算”。冲突响应在接受前拒绝，保留可用的旧策略并继续下轮；没有拆开模型组合后冒称完整执行。60项宏观控制检查、244项策略检查和新增真实组合的Agent生命周期回归通过；后者验证冲突后仍可接受下一轮合法建造决定。两个独立评审回归确保未派发的模型建造和原生自主建造不能被算作G6效果。

修复后PID49156/sessiona5e7c306…，run `3deef6ff-70a1-457e-ab17-11e23f7e96e4` 连续10次真实返回、10个实际原生计划、无相同合同fault，user_stop清理通过。该轮仍未派发建造；评审在 `reports/macro-desktop-construction-49156-20261028-v1/`。截至该轮累计61次真实宏观模型返回、50个实际原生计划；未把引擎接受但未派发的计划混入原生数量。

## 明确标记的科技建设风格对照（已结束）

为验证G8配置偏好与建造选择的关系，已通过当前客户端保存临时修订5，只在补充要求中增加科技基础设施优先的阶段目标。五维轴、模型、连接和原有原生操作边界不变；不是固定策略驱动，也没有修改模型返回。该试验结果只归于此配置，不归到修订4。

原配置公开快照 `reports/macro-construction-style-baseline-profile-20261028.json` 已保留。对照公开快照 `reports/macro-construction-builder-style-profile-20261028.json`：957 UTF-8字节，有效哈希 `3e6306e626ed57f7cc9dc014f63e8303714849cc3fcc25e21ef32b29a73585e2`。客户端保存截图 `reports/macro-construction-builder-style-saved-20261028.png`；没有读取或复制凭据。

PID26652/sessionde55d452…，run `df9a88ca-c504-4a39-bd6b-de713881fc06`：10次真实返回、8个实际原生计划，0条建造派发，正常user_stop及清理通过。没有验证出自由决策下的建造风格差异。原件 `reports/macro-desktop-construction-26652-20261028-v1/` 保持这个负结果，不以保存配置替代行为效果。

## 明确建造阶段目标：真实模型施工与反馈链

随后通过当前客户端保存临时修订6，1053 UTF-8字节，有效哈希 `841c0d9440a3b5edcd301213691390e5a9ff6438c6a4b6d8877b9893d228e2ef`，补充要求明确标记“本轮建造链路验收场景”。模型需要把指定的反应堆阶段目标转成当前合法意图；不是自由对战自主选建筑的证据，也不是固定策略或伪造模型返回。公开配置在 `reports/macro-construction-directed-scenario-profile-20261028.json`。

实际PID80688、raw FILETIME134376122947869789，session `8021ffbd-f90b-415d-bb06-629929ec7262`，run `ff9fcc7a-dfe8-419a-ac1e-c551a3cefcf1`，Host PID77384，epoch23。当前客户端SHA edcc5d2b…；该run保留启动后客户端制品、执行前Host源码、配置、精确请求与HTTPS provider回执。

- 12次真实返回、10个引擎接受计划、9个实际原生计划；其中2条建造偏好。
- 第一条建造seq4：出现正建造评分，但有效期内没有新施工队列，正常到期清除；第6次真实模型请求收到该到期、0队列的反馈，没有自动补发旧命令。
- 模型据此作出新的建造决定seq6。原生出现正评分、新目标施工队列和1个己方施工对象，控制器在观察到队列后及时清除偏好。第7至12次真实模型请求收到相应的有界反馈，后续模型继续作出预算决定。
- 正常user_stop；phase2/error0/active0/mask0/cleanup1/self_hook0/lease0、helper退出0、unknown[]，没有单兵jobs。独立只读采样10481帧确认13标志均清除、selected_macro_flag=null、0新模型调用/原生指令/进程写入。

独立评审 `reports/macro-desktop-construction-80688-20261028-v1/assessment.json`：`some_model_construction_effect_verified`、`bounded_construction_lifecycle_verified`、`durable_construction_loop_verified`、后续请求反馈及停止通过。严格的“所有建造意图均排入队列”仍为false，因为第一份意图确实到期；没有把到期当作建筑完成。最终付款、建筑完工、精确queue→对象回调及排他因果仍未验证，整体G5/G6/G7/G8也没有因此完成。

实际客户端显示“新增排队1，己方施工对象观测1；建造偏好已释放。建筑完工尚未验证”，画面保存在run目录 `client-construction-feedback-stopped.png`。实际下载脱敏诊断371783字节，SHA `32dc2f4a796685cba6c53a6ab9c5813a3cf1eb12ee4aa2229d9a16b5379fd9d5`，与原生export逐字节相同；副本及下载证明在评审目录。外层自证字段仍按合同为false，嵌套status的独立归还投影为true，没有篡改导出来让其“变绿”。

试验后已通过客户端恢复原 `draft.custom_traits`、模型、连接、doctrine和五维轴。当前修订7，657字节，有效哈希 `d22d1f8289de9b2b503d31ecbe16df5c20a352b9399460a392a1043c203c7390`，公开核对在 `reports/macro-construction-restored-profile-20261028.json`。修订号已前进，不冒用旧修订4的哈希。

截至本轮累计83次真实宏观模型返回、67个实际原生计划。目标仍active；下一步继续科技投入、合法侦察与区域调度，保留指定验收场景与自主决策之间的证据界限。

## 上一局自然结算归档

PID68212研究局自然进入统计界面，watcher1480条记录、0读错误。结算截图和97706字节回放保存在 `acceptance/runs/20261028-050458-macro-probe/research-settlement.json` 的索引中；回放SHA `627d7ac15e0ffaa141e1491db6e8f27035e1d57e72ccd1d13798b6aa327081cb`。胜负映射、回放播放和宏观重现仍未验证。模型前段10次真实返回、7次原生派发，停止试验后原生 AI 自行运行到结算，不能算整局持续模型指挥或正式G7。归档并核对13标志清理、lease不存在后，才按精确PID/raw FILETIME句柄结束研究fixture。

整体目标保持active。建造新的实机闭环、科技/扩张、合法侦察反馈、部队区域部署与改派、发布组件、整局模型指挥和回放核验、基线与风格比较仍需继续完成。
