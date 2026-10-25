# 引用、借鉴与第三方来源

本文区分接口研究、辅助代码复用、运行依赖、构建工具与游戏素材。来源记录描述本仓库中的实际使用范围，不表示已经完成所有依赖及发布产物的许可证审计，也不为整个仓库指定统一许可证。

## 游戏接口研究与辅助工具复用

### Ra3-Copilot

- 上游：[ProbiusOfficial/Ra3-Copilot](https://github.com/ProbiusOfficial/Ra3-Copilot)。
- 历史研究记录固定到提交 [`2d31f7cc0ce47e257a5ecb95cc4f44a8b26f8015`](https://github.com/ProbiusOfficial/Ra3-Copilot/tree/2d31f7cc0ce47e257a5ecb95cc4f44a8b26f8015)，详见[早期开发记录](history/readme-development-records.md)。这是当时的研究基线，不等于确认每台开发机器上的参考目录都处于该提交。
- 使用范围：游戏对象布局、偏移、函数入口的研究假设，以及部分目录数据和离线辅助工具。Tacticore 没有编译或加载该项目的完整修改器，不应描述为其完整移植或 fork。

本仓库仍存在直接读取或导入参考目录的脚本，因此不只是概念借鉴：

| 上游文件或数据 | 本仓库使用位置 | 用途 |
| --- | --- | --- |
| `ra3-copilot/src/battle_catalog.h` | [probe.py](../probe.py)、[integration/own_candidates.py](../integration/own_candidates.py) | 候选单位名称、类型与模板分类辅助识别 |
| `unit-codes/tools/sage_hash.py` | [native-ai/stage_commanders.py](../native-ai/stage_commanders.py) | 生成指挥官实验资源所需的 SAGE 哈希 |
| `ra3-copilot/tools/precheck_aob.py` 等研究工具 | [native-ai/pe_xrefs.py](../native-ai/pe_xrefs.py)、[native-ai/extract_symbols.py](../native-ai/extract_symbols.py)、[visibility/capability.py](../visibility/capability.py)、[tactical/analyze_hit_stack.py](../tactical/analyze_hit_stack.py) | PE 地址转换、特征检查与离线分析 |

这些路径依赖本机 `reference/Ra3-Copilot/`，该目录由 [.gitignore](../.gitignore) 排除。普通克隆不包含完整上游源码，运行相应研究脚本需另行准备其依赖。上游目录来自其他 Mod 的研究语境，不能当作 Remix 037 的权威单位表；偏移与候选匹配也不能替代目标游戏版本的实机验证。

### MinHook

上游：[TsudaKageyu/minhook](https://github.com/TsudaKageyu/minhook)，Windows x86/x64 API hook 库。本仓库多处原生构建脚本使用参考目录中的 `ra3-copilot/third_party/minhook-1.3.3/`，把其 `buffer.c`、`hook.c`、`trampoline.c` 与 `hde32.c` 编译进实验 DLL；这属于实际代码依赖，而非仅引用说明。

可核对的入口包括 [native-ai/Build-Observer.ps1](../native-ai/Build-Observer.ps1)、[production/Build-Observer.ps1](../production/Build-Observer.ps1)、[production/Build-Trace.ps1](../production/Build-Trace.ps1) 与 [production/persistent/Build.ps1](../production/persistent/Build.ps1)。部分观察器构建会复制上游 `LICENSE.txt` 为 `MinHook-LICENSE.txt`，但尚不能据此声称所有原生输出都已统一附带许可文件。发布含该代码的产物时，需要保留对应版本的许可及版权通知。

### pySAGE / sage_apt

上游：[ClementJ18/pySAGE](https://github.com/ClementJ18/pySAGE)，本仓库使用其中的 [sage_apt](https://github.com/ClementJ18/pySAGE/tree/master/sage_apt) 离线转换器。

[native-ai/decompile_frontend.py](../native-ai/decompile_frontend.py) 从本机 `native-ai/frontend-reference/pySAGE-master/` 导入 `sage_apt.aptfile.apt_bytes_to_xml`，将提取的 APT/Core 数据转换为 XML，用于研究旧游戏前端格式。脚本注释记录其 MIT 来源；未运行上游 viewer/server，也未将其作为当前 React 客户端。该参考目录不入库，目前未记录固定上游提交，后续整理可复现工具包时需要补齐版本记录。

### 尚需补齐来源的本机研究工具

[native-ai/build_commander_package.py](../native-ai/build_commander_package.py) 与 [patch_global.py](../patch_global.py) 还引用本机 `E:\RA3Modding\Reference`、相邻 `TriadFront/tools` 或 `E:\RA3Modding\Analysis\Remix037` 中的 `inspect_data`、`read_remix_meshes`、`manifest` 模块，用于 BIG/CSF、RefPack 与 manifest 数据处理。现有记录不足以确认各模块的原作者、公开仓库、版本和许可，应在独立分发这些工具前补齐，不能为它们推定许可证。

## 当前运行与界面依赖

精确安装版本以 [Python 锁文件](../agent_runtime/requirements-pydantic.lock)、[前端锁文件](../desktop-ui/package-lock.json) 和 [Rust 锁文件](../desktop-ui/src-tauri/Cargo.lock) 为准。下面只列核心用途，不代替完整依赖清单或其各自许可证。

| 工程 | 本仓库用途与边界 |
| --- | --- |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | [agent_runtime](../agent_runtime/pyproject.toml) 直接依赖 `pydantic-ai-slim[openai]==2.61.0`；负责模型接口与有界调用，输出仍由原严格解析器检验，不获得游戏操作权限。 |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | 通过 PydanticAI 的 OpenAI provider 使用兼容模型接口；锁文件记录 `openai==3.37.0`。这是 Python SDK，不能据此称为采用了 OpenAI Agents SDK。 |
| [React](https://github.com/facebook/react) | 当前桌面界面的组件和状态管理，声明版本 `19.3.1`。 |
| [Vite](https://github.com/vitejs/vite)、[TypeScript](https://github.com/microsoft/TypeScript) | 前端开发、类型检查与构建；当前声明分别为 `8.3.5`、`7.0.2`。 |
| [Tauri](https://github.com/tauri-apps/tauri) | 桌面 WebView 外壳，使用 Tauri 2 系列；当前外壳没有实现 Windows 游戏宿主桥接，不能把界面演示视为游戏已接入。 |
| [Phosphor Icons](https://github.com/phosphor-icons/react) | `@phosphor-icons/react` 提供界面图标；应用图标基于 Circuitry 符号配色制作，见下方版权通知。 |

OpenAI Agents SDK、LangGraph 与 CrewAI 仅出现在[框架选型对照](agent-runtime/0001-pydantic-decision-runtime.md)中，不是当前采用的运行框架。锁文件中的 `pydantic-graph` 是框架依赖，也不表示已经为游戏实现多 Agent 编排图。

## 构建工具链

[w64devkit](https://github.com/skeeto/w64devkit) 提供 Windows 原生实验组件的 GCC 工具链。[Build.ps1](../Build.ps1) 使用本机 `toolchain/w64devkit/bin/g++.exe`，其他原生构建脚本也使用该工具目录。

[历史记录](history/readme-development-records.md)记录的是 [x86 v2.10.1](https://github.com/skeeto/w64devkit/releases/tag/v2.10.1) 及本地包哈希；这是历史构建环境，不应改写为上游当前最新版。`toolchain/` 不入库。编译器、其组件与链接运行库各有自己的许可，工具包版本记录不能替代最终发布产物的通知整理。

## 游戏、Mod 与视觉素材

- 《命令与征服：红色警戒 3》、相关游戏名称、阵营标识、原始美术及游戏资源的权利属于 Electronic Arts（EA／艺电）及相应权利人；游戏与 SDK 不作为本仓库的自有作品。Tacticore 是独立开发项目，不代表 EA 官方发布或认可。
- Remix Mod 的原创内容及改动属于原作者和贡献者。Tacticore 的当前验证背景包含 Remix 037 及本地实验 Mod，不能由兼容研究推导出对 Remix 内容的所有权或再许可权。
- 桌面准备室的阵营图来自相邻 Remix-Ai 宣传网站已使用的用户参考素材，本地副本位于 `desktop-ui/public/games/ra3/factions/`；它们不属于 Phosphor 图标授权范围。具体说明见 [桌面第三方通知](../desktop-ui/THIRD_PARTY_NOTICES.md)。
- README 的桌面截图展示本仓库当前界面及本地预览数据，用于说明软件设计与功能进度，不是当前客户端已接入真实对局的证据。后续引入电台音视频、配音或游戏宣传素材时，还需分别记录来源和使用范围。

本项目仅用于学习、研究与交流，不开展商业化或盈利活动。此用途声明不会改变游戏、Mod、开源依赖及第三方素材各自的权利归属。

## 已保留的通知与后续维护

[desktop-ui/THIRD_PARTY_NOTICES.md](../desktop-ui/THIRD_PARTY_NOTICES.md) 保留了 Phosphor 的 MIT 许可全文、应用图标来源以及阵营素材说明。该 MIT 通知只覆盖对应图标，不能扩展为整个 Tacticore 工程、EA 游戏或 Remix 素材的许可证。

引入或更新外部源码时，请同步记录上游链接、固定版本或提交、使用位置以及所需版权通知；生成发布包时核对实际进入包内的依赖与素材。尚未记录版本的 pySAGE、本机解析工具，以及各原生构建产物的第三方通知，是当前需补齐的来源记录。
