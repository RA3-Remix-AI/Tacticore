# 真实指挥官包与局内人格读取

实机更新：主Agent在短Mods目录运行本包后，已真实拖动下拉弹出列表滚动条并选择铁锤；此前滚轮/单击箭头未有效滚动，撤回“UI缺项”假说。`acceptance/runs/20261024-183816-commander/iron-binding.json` 已从AIPlayer+0x8b0读回铁锤苏联人格ID `0x7664d9d9`、wrapper `0xe9da020`，解析到UUID `57e668b4-4d89-43bd-bc92-0dd436f046ef`，注册表包哈希一致。以下“未通过”描述指构建时的静态边界；局内身份绑定现已有独立实机证据，仍不代表所有宏观命令可用。

菜单证据：[已选铁锤](</C:/Users/Administrator/Documents/Red Alert 3/bridge-probe/acceptance/runs/20261024-182145-commander/iron-selected-lobby.png>)；[对局暂停菜单的简单铁锤](</C:/Users/Administrator/Documents/Red Alert 3/bridge-probe/acceptance/runs/20261024-183816-commander/iron-pause-menu.png>)。没有保存展开滚动过程截图，不能把这两图当成三个人名同时展开的截图。

## 最新产物

真实桌面输入只读自 `C:\Users\Administrator\AppData\Local\TriadFrontCommander\commander-bindings.json`，没有读取密钥文件。三个 UUID 分别为铁锤 `57e668b4-4d89-43bd-bc92-0dd436f046ef`、堡垒 `0818f564-06af-4053-a5ac-87bcbbe904f8`、幽灵 `697a5df8-bb98-47a4-ba68-923a8589e371`。

- 原始生成目录：`staging/commanders-20261024-182026-231af882/`。
- 已编译合并目录：`staging/compiled-commanders-20261024-182027-17286524/`。
- 包：`TFNames.big`，SHA256=`2d7873e1b2d2c79950ff9da70b5452b1210370a6d6cbec1eaa69201a7d3d0665`。
- 同目录：`TFNames_1.0.skudef`、`commander-registry.json`、`build-report.json`、SDK构建日志。

`build_commander_package.py` 仅写专用 SDK Mods/TFUUIDProbe、其构建输出和新的 native-ai/staging 子目录。正式 TriadFront BIG 作为只读基线，SHA256 前后保持 `8bada8d088427a3a38016b53e07c50b4e8df7277ca5fd1beba15bea8be7f6c30`。未调用 remix_art.merge_path，未部署和启动游戏。

三档配置各保留原842条资产的全部 bin/imp/relo、引用、名称、来源、类型/实例ID及flags，追加12个经真实编译核对的UUID人格。引用表使用每资产本地导入索引，不重写原资产引用；外部 manifest 引用与基线相同。CSF保留所有原有文案并增加三个人名。BIG重新读开后逐文件SHA256与打包源匹配。没有AdditionalMaps。

注册表 compiled_ids_verified=true，包含该包 package_sha256；game_sync_verified/side_binding_verified=false。它证明编译和静态保留，不证明本包菜单选择或控制能力。

```powershell
$py='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py bridge-probe/native-ai/stage_commanders.py --bindings 'C:\Users\Administrator\AppData\Local\TriadFrontCommander\commander-bindings.json'
& $py bridge-probe/native-ai/build_commander_package.py --staging <上一步输出目录> --base-big Mods/TriadFront/TriadFront.big
```

主 Agent 可把 BIG 和 skudef 两文件复制到单独的短路径 Mods/TFCommanderPlay，保留文件名；不要复制 baseline 或 package 树，不覆盖正式 TriadFront。部署和游戏会话由主 Agent 管理。

## 原生读取链

在固定 SHA256 的1.12 EXE中，Player创建AI的调用路径保存在 `player-create-ai.txt`：0x8449d3从人格store查得wrapper至EDI，0x844a33依次push人格/参数/Player，调用0x8d5650，并于0x844a3f保存AIPlayer至Player+0x90。

`ai-constructor-identity.txt` 显示构造函数0x8d5727将该EDI保存到AIPlayer+0x8b0；0x8d5733将Player存入AIPlayer+0x8a8。

只读链：`Player+0x90 → AIPlayer+0x8b0 → personality wrapper+0x18 → instance_id`。此为局内**有效人格**，随机选择可能已经解析成具体阵营人格，不能当作原始大厅下拉框序号。四个同UUID资产都映射回同一档案。

```powershell
& $py bridge-probe/native-ai/read_selected_personality.py --pid <PID> --player <电脑Player地址> --session bridge-probe/acceptance/active-session.json --registry bridge-probe/native-ai/staging/compiled-commanders-20261024-182027-17286524/commander-registry.json --output <run目录>/selected-personality.json
```

采样器只有OpenProcess(0x410)/ReadProcessMemory：校验EXE哈希、两处构造签名、Player/AIPlayer vtable、双owner回链、store成员资格、instance_id唯一性、Side非空且匹配Player模板；读取完成重查链。session校验PID及真实进程创建时间。UUID解析再要求唯一注册映射及session包哈希相同、编译ID已核对，才能标 personality_binding_verified=true。game_sync_verified和strategic_control_verified仍为false。

5/5纯内存测试通过：有效链、owner不符拒绝、未注册人格拒绝、错误Side拒绝、包哈希不符及重复UUID映射拒绝。尚待主Agent在实际对局读回，不能把测试当真实进程绑定成功。

## Side与启动路径新证据

主Agent在 `acceptance/runs/20261024-181450-A_short_path/runtime-menu.json` 已读回A短路径包14个人格：4个自定义Side均有效，Random三组映射也完整。普通Mod流可绑定已经得到实机证据，应停止对其依赖进行猜测性改写。

此前长路径A于18:13:31发生WER BEX/MSVCR80 invalid CRT argument；同SHA包缩短到Mods/TFProbeA后可运行。长短路径同时改变了目录位置，尚不能单独证明长度是唯一根因。旧说明中“无需部署”的保证撤回，应采用已验证的短Mods路径。

AdditionalMaps副本的NULL根因仍未最终证明；当前实际修复候选是完全避免该副本，仅正常流注册。不要覆盖global.12、强写Side指针或先启动B/C污染同进程缓存。
