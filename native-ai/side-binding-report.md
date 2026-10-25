# 自定义人格 Side 引用调查（2026-10-24）

更新：18:14主Agent使用同SHA的A短路径包成功启动，四个自定义Side和Random映射均有效。普通流绑定现已通过该探针验证；本文件下文保留此前静态调查阶段记录。最新真实UUID包、短路径限制与局内身份读取见 `commander-package-and-binding.md`。AdditionalMaps空引用根因尚未最终证明。

## 状态

尚未修复或验收运行时 NULL。已排除当前流切片导致 Side 索引/字节损坏，并准备四个未部署的单变量探针。未启动、停止、注入或操作当前生产实验游戏。TriadFront 正式源码和部署包未改。

## 可复现证据

`side-import-audit.json` 审计旧 CommanderLab 正常流及其 data/AdditionalMaps 副本：

- 三个自定义阵营人格的 Side 数量为 2，两份均是合法的强引用导入，不是序列化值 0。
- Side 导入位置均在 `.imp` 修复表内，1-based 引用索引在各资产的本地引用表范围内。
- 对应 PlayerTemplate 的类型 ID 为 `0xf231d60d`；Allies=`0x86051f0d`，Japan=`0x3d6743e8`，Soviet=`0xb610276b`，Null=`0x17052fac`。SDK 与零售 global.12 的这些目标 ID 一致。
- 正常流与 AdditionalMaps 副本中的三个记录，其 `.bin`、`.imp`、引用表逐字节相同；外部 manifest 引用也相同。引用类型字节为 1（REFERENCE），包括 `sagexml\global.manifest`。
- 因此，不能用“切片后引用索引忘记重排”解释这一次 NULL。每资产独立的 1-based 导入编码也可由本机 WrathEd 的 `SAGE/BinaryAsset.cs` 和 `SAGE.Compiler/StreamCompiler.cs` 交叉核验。

复现命令（工作目录为项目根）：

```powershell
$py='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py bridge-probe/native-ai/validate_side_imports.py --stream E:\RA3Modding\SDK\BuiltMods\mods\CommanderLab\data\mod.manifest --compare E:\RA3Modding\SDK\BuiltMods\mods\CommanderLab\data\AdditionalMaps\mapmetadata_commander.manifest --output bridge-probe/native-ai/side-import-audit.json
```

SDK `Schemas/xsd/Includes/Ref.xsd` 的 PlayerTemplateRef 继承 AssetReference；`Schemas/xsd/SkirmishAI/AssetTypeAIPersonalityDefinition.xsd` 的 Side 是该类型的无界数组。当前 SDK 目录没有可直接查阅的原生 PlayerTemplateRef 导入 C++ 实现，尚不能断言导入修复发生于哪个具体引擎阶段。

历史运行时证据为 `../reports/personalities-20261024-171421.json`：三个阵营人格两个 Side 都 NULL；普通流独有的 Random 人格 Null Side 有效。该旧工具未采 PersonalityMap，不能声称 Random 的三个映射引用也有效。注册数组的顺序也不是加载时间戳。

## 假说及边界

最有价值的待验证假说是：AdditionalMaps 加载上下文未绑定正常 Mod 使用的外部依赖，并且先登记/缓存的同 ID 人格使正常流实例未替换它。现有数据未证明前半段或后半段，也未严格区分物理 Mod/AdditionalMaps 与 BIG 内根/data 路径。不能将“加载早晚”当根因结论，也不能据此改写全局流或运行时补指针。

## 本轮改动

- `commander_assets.py` 删除重复追加 Side，恢复只继承一个 Side；修正旧报告 ID 和“替换原版槽位”的过时注释。此项只修重复声明，不称为 NULL 修复。未运行其 lab()，未重建旧 CommanderLab。
- `frontend_metadata.py` 改为可导入、可指定源/目的/前缀/是否包含 Random 的函数；复制流程仍保持每条记录原有导入。默认 CLI 路径兼容旧实验，导入模块不再自行写文件。
- `inspect_personalities.py` 增加 `--catalog`、`--output`、`--label`，记录原生 instance_id、目录文件 SHA256，并读回 PersonalityMap 内每组 Side/Personality 指针。读权限仍为 0x410，固定校验游戏 SHA256 和 store vtable。新 map 结构已按 SDK 与探针 Random 的二进制布局核验；本轮没有对运行游戏执行此工具。
- `build_side_probes.py` 使用专用 SDK 名称 CommanderSideProbe，三档配置构建成功，明确 `-NoDeploy`；每次输出新目录，防止旧元数据残留污染 A。

## 隔离包

最新包目录：`native-ai/side-probes/20261024-175800/`。每包有 BIG、skudef、未压缩 package 树和 SHA256，汇总在 `side-probes.json`。

| 变体 | BIG 内唯一元数据路径 | 复制人格 |
| --- | --- | --- |
| A_normal_only | 无 | 无 |
| B_root_metadata_three | AdditionalMaps | 三个阵营 |
| C_data_metadata_three | data/AdditionalMaps | 三个阵营 |
| D_root_metadata_four | AdditionalMaps | 三个阵营及 Random |

四包的正常流完全相同，Side 均为 1 且静态导入全部合法；只有额外元数据的路径/所含记录不同。包内有独立本地化标签 `SIDE BINDING PROBE`。这些仍使用旧实验的 4TFLLM* 身份，仅用于隔离故障，不能当作多指挥官最终注册设计。

重建：

```powershell
& $py bridge-probe/native-ai/build_side_probes.py
```

## 下一轮真机验证（由主 Agent 统一安排）

每次用全新进程，仅启用一个探针，不能叠加 CommanderLab、其他探针、外置 AdditionalMaps 副本或全局流覆盖。先读回 A，避免先进行元数据试验就占用同 ID 缓存。每次记录游戏/包 SHA256、PID、变体、主菜单/打开阵营列表的阶段和读取时间。

```powershell
& $py bridge-probe/inspect_personalities.py --pid <PID> --catalog bridge-probe/native-ai/side-probes/20261024-175800/A_normal_only/package/data/mod.manifest --label A_normal_only --output bridge-probe/native-ai/side-probes/20261024-175800/A_normal_only/runtime-menu.json
```

1. A 若三个 Side 有效：证明普通流可绑定；菜单是否出现另行记录，不能混同为运行时 NULL。
2. B/C 独立新进程：确认哪条 BIG 路径被发现，以及是否复现 NULL。若都不登记元数据，不能宣称加载路径正确。下一步才用 A 的 BIG 加仅一个物理 AdditionalMaps 副本，明确标记为新增变体，不叠加。
3. 如果某个三人格元数据变体稳定复现 NULL，运行同一路径包含 Random 的 D 对照：若 Random 的 Null/映射也变 NULL，支持加载上下文问题而非特定阵营 ID。D 不应先于 A/B；仍不单凭此证明缓存替换规则。
4. 成功条件包括三个阵营 Side 非空、Random 映射完整、各阵营列表有新条目；随后选择它进局，确认原生 AI 经济和生产，并读回电脑 Player 的已选人格 ID。无这些结果，不启用产品接管按钮。

多档案后续沿用 `commander-identity.md` 的稳定 UUID→每阵营资产→编译实例 ID 映射。桌面 `CommanderLibrary.cs` 现有 commander-bindings.json 导出已有 commander_id、connection_id、model 字段，可作为注册输入；不能用可修改的名字或全局 4TFLLM 人格绑定全部档案。密钥不进入 SDK 资产或注册表。
