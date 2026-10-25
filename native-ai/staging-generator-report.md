# 多档案 staging 生成器

`stage_commanders.py` 只读桌面导出的 commander-bindings.json，输出到新的 `native-ai/staging/` 子目录。不会编译、部署或操作游戏；拒绝覆盖已有目录和写入 staging 以外路径。

本轮输入：`bridge-probe/desktop/test-runs/20261024-180350-7135ea9d/library/commander-bindings.json`。

本轮输出：`bridge-probe/native-ai/staging/commanders-20261024-180958-9b8193dd/`，3 档案、12 个候选资产（每档案 Allies/Soviet/Japan/Random）：

- commander-registry.json：规范化 UUID、连接 UUID、模型路由、每阵营 asset_id/PersonalityType/instance_id/本地化 key。game_sync_verified、side_binding_verified、compiled_ids_verified 均为 false。
- LLMCommanders.xml：三个阵营继承原版 Balanced；Random 指向自己的三个阵营资产，不重复追加 Side。桌面 personality 预设保存在路由数据，未宣称改变原生战略。
- localization.json：稳定 key→显示名，UTF-8 JSON；尚未编译为 CSF。中文和 `&<>`、单双引号作为数据往返，显示名不拼接进 XML 语法，XML 属性由 ElementTree 序列化。
- generation-report.json：输入/工具/输出哈希和 35,322 条 SDK 基线的碰撞检查记录。端点和密钥不进入输出。

名称规则：`4LLM_<UUID32>_<Allied|Soviet|Japan|Random>`；本地化 key：`Personality:LLM_<UUID32>`。改名及重排不会改变身份。identity_revision 只反映身份映射，registry_revision 也反映显示名和路由。instance_id 是原生名称散列，不是 manifest 的构建指纹 InstanceHash。

```powershell
$py='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py bridge-probe/native-ai/stage_commanders.py --bindings bridge-probe/desktop/test-runs/20261024-180350-7135ea9d/library/commander-bindings.json
& $py bridge-probe/native-ai/test_stage_commanders.py
```

8/8 测试通过，父 Agent 已独立复跑：改名与 UUID 格式稳定、中文及标点、重复 UUID、生成内/基线散列冲突、已知编译 ID 复算、固定未验证状态及无端点密钥、非法 XML 控制字符与越界输出拒绝。额外正式 Mod 碰撞基线可用 `--baseline <mod.manifest>` 追加；检查范围不包括未提供的第三方包。

## A_normal_only 的精确启动参数

仅提供参数，本轮未启动：

```text
FileName: E:\RedRar3\Data\RA3_1.12.game
WorkingDirectory: E:\RedRar3
Arguments: -ui -win -xres 1600 -yres 900 -modConfig "C:\Users\Administrator\Documents\Red Alert 3\bridge-probe\native-ai\side-probes\20261024-175800\A_normal_only\A_normal_only_1.0.skudef" -config "E:\RedRar3\RA3_chinese_t_1.12.SkuDef"
```

skudef 引用同目录 A_normal_only.big，SHA256=`413ed45d53a01602740bf292d04e9d788fbc7ff6bad64980e77309dd8ac370c2`。更新：此前长路径启动发生CRT异常；同SHA复制到短Mods/TFProbeA路径后启动并读回Side成功，应使用短Mods路径，不再保证上面的长路径可运行。A仅含正常流三档配置和字符串，没有AdditionalMaps或TriadFront内容。普通流Side已通过探针，菜单可选性仍需单独验证。

不要使用旧 Launch-Lab.ps1 测 A：它打包旧 CommanderLab 并管理旧 Lab 进程。后续专门游戏验证由主 Agent 统一安排。
