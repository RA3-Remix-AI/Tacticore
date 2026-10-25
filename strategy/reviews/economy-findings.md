# 经济目标可用性：独立源审计

本次审计记录的旧 catalog SHA256 为 `8420d115fbaf6b098a557bf8d8f781e91541e4da018de3769791efacb3c116b9`。它实际有 111 个允许模板（不是 57），`role=economy` 为零。因此旧版冻结表无法产生合法经济联系人；单纯延长比赛、等待敌方矿车不会使严格 `harass_economy` 成为可派任务。完整机器可复算证据在 `economy-evidence.json`。

## 两个模板缺席/分类的原因不同

`SovietRefinery` 已在安全表中，type hash `0xc45aaeab`，当前旧角色为 `structure`。`audit_templates.py` 的角色分支仅在继承后的 KindOf 包含 `HARVESTER` 时输出 economy；炼矿厂继承 `STRUCTURE`，所以落到 structure 分支。这是功能分类缺口，不是可见性或隐形审计拒绝。

`SovietMiner` 既不在允许表，也不在 rejected。按旧安全表精确 manifest SHA `aec863b2e91cecaa4031f87a124c8d04e6bd45862d38fa76a823b69e9a8fafc5` 找到原始编译流 `native-ai/staging/compiled-commanders-20261024-182027-17286524/package/data/mod.manifest`：854 条记录中没有任何 `GameObject:*Miner`。审计器只遍历这个编译流内记录，故从未进入该模板的源链检查。源 XML 作为外部基游戏引用存在，不等于已对当前加载的 compiled identity/capability 做证明。矿车继续 unknown 并排除，不能因为原 SDK 没扫出风险就直接暴露。

离线重走原审计规则，`SovietMiner -> BaseMiner -> BaseVehicle -> BaseObject` 均无 duplicate source，现有风险规则返回空；它具有 `HARVESTER`，BaseMiner 提供 `OreMinerBehavior DeliveryCapacity=250 DeliveryTime=2s` 与 `OreMinerStateMachine`。这些证明源功能，但不能替代编译流/加载身份和运行时隐形门控。

## SovietRefinery 的精准功能证据

当前 mod 源 `E:/RA3Modding/SDK/Mods/TriadFront/data/objects/SovietRefinery.xml`，SHA256 `9b8bbf7bf5e083f1aa1ae90df63526a4c3fdb5af7ce6f7424d9a9cf26f86442a`：

* 第 12 行 KindOf 显式加入 `SUPPLY_GATHERING_CENTER`、`FS_MONEY_STORAGE`、`REFINERY`。
* 第 21 行 `SkirmishAIInformation BaseBuildingLocation=NEAR_RESOURCE_NODE NearResourceNodeType=ORE`。
* 第 329–330 行 one-shot `SpawnBehavior` 在 unpack 时生成 `SovietMiner`。
* 第 342 行包含 `InfiltratorContainEconomic.xml`；对应 SDK include 的效果是 `STEAL_MONEY`，金额 2000。
* 继承 `BaseSovietStructure -> BaseStructure -> BaseObject` 保留物理 `STRUCTURE`。完整源链及 SHA 在 JSON 中。

这个 mod Refinery **没有** `OreRefineryBehavior` 节点；不能凭一般游戏知识给它编造这个源行为。上述精确标签、资源节点定位、矿车生成与经济入侵行为已足以支持“经济设施”的功能分类。

## 建议与证明迁移

由目录所有者在安全测试窗口生成新 catalog revision：仅精确 `SovietRefinery` / `0xc45aaeab`，且已安全审计、有效继承 KindOf 同时含 `REFINERY` 与 `SUPPLY_GATHERING_CENTER` 时，赋功能 `role=economy`；保留 catalog 私有元数据 `physical_role=structure`。不把所有建筑变成经济目标，不按编辑名的 Ref 字串猜测，不把仅有 emergency-no-income 的其他模板当经济设施。

现有模型契约已允许 `economy`，所以这个精准分类可以先不增加公开字段。若模型需要同时理解“建筑物”和“经济功能”，再另行版本化增加公开 `physical_role` / 有限 `functional_tags`，并同步快照验证、last-seen、客户端和输入预算；不要直接往当前严格字段合同加未支持标签。

这次不需要改 NativeFootprint 或任何视野算法。分类代码、catalog、安全审计和源 include 证据应重新哈希，新建 build capability 与当前 session proof；旧 SHA 证明不得继续声称覆盖新标签。源功能分类被证明，不等于 `harass_economy` 的实际开火/归因/归还已经通过，后者仍需目的级原始实验证据。

runner 的 `--economy` 精确筛选目标可用于独立校准，但 CLI 名字本身不是角色/能力授权。旧安全表仍会让 native 报告 `request.target_role=structure`，旧严格 purpose verifier 应拒绝；新分类与证明正当重建后才能把新角色用到最终验收。

## 复算

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' bridge-probe/strategy/reviews/economy-audit.py
```

脚本只读现有 manifest、SDK XML 和安全表，研究输出仅位于 strategy/reviews。含一个精准正例及五个拒绝边界断言；不更改冻结 catalog，不使用 GUI、API 或 SDK 原生命令。
