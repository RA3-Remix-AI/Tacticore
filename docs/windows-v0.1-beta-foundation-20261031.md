# Windows beta 发布基础设施：第一批结果

本批在 `release/windows-v0.1-beta` 从 `5238c9cb` 独立开发。它交付 Python 运行环境阶段包及发布检查，**不代表 Windows 游戏 beta 已完成，也不增加正式自然局通过数**。完整后续工作见[执行清单](windows-v0.1-beta-execution.md)。

## 实际变更

- 新增 `stage-python-runtime.py` 和共享打包库：只收集精确版本锁中的 26 个 distribution，直接解析 RECORD，核对每个运行文件的 SHA-256 和大小。拒绝缺失资源、重复/冲突、路径逃逸、重解析点和 `.pth` 导入钩子。不能依赖会过滤缺失文件的 `importlib.metadata.Distribution.files` 来判断完整性。
- 应用 Python 源码从 Git 清单收集，排除未跟踪的临时脚本、JSON 和测试。包内记录实际应用源码、解释器、依赖、版本锁、构建工具及许可证文件清单。构建过程中工具或输入变化会拒绝产包。
- 使用固定 `_pth`、受控编译缓存和全部文件摘要，不借用系统/开发环境 Python。包明确标记为 `locked_python_stage`，没有战略 Native 运行组件或游戏控制资格。
- 新增 `probe-python-stage.py`：在仓库外临时目录，用受限环境和全新临时本机配置验证 SDK 导入及真实本地配置/RPC。不会继承提供方密钥环境或读取现有用户配置。
- 新增发布预检，并接到 Windows release 构建入口。旧 Native1 打包器默认拒绝，须显式指定 `--legacy-research`。Rust 构建阶段也拒绝没有运行清单的 release，以及误用 Python 阶段包的 release。

## 验证结果

| 检查 | 本次结果 |
| --- | --- |
| 发布基础回归 | 14/14，包括 RECORD 篡改/缺资源、版本/文件冲突、未跟踪脚本排除、额外代码/二进制修改及路径异常 |
| Rust 本地桥接回归 | 13/13；包含配置隔离、停止控制通道、完整文件清单及未知操作拒绝 |
| 独立包实际运行 | SDK 导入、首次配置初始化、档案查询、关闭进程后重开读取通过 |
| 导入隔离 | 错误 PYTHONHOME/PYTHONPATH、cwd 同名假模块被忽略；已导入模块均位于包内 |
| 包运行后的完整性 | 8,949 个文件清单未变，无新缓存或额外代码 |
| 发布阻断 | 预检返回 2；Windows 构建脚本在编译前拒绝阶段包；实际编译的 Rust 构建脚本分别拒绝缺清单与 Python 阶段清单 |
| 游戏、真实模型、原用户密钥 | 未访问；真实模型请求为 0 |

最终阶段包内容为 137,926,750 字节（不计清单自身），清单 SHA-256：

`49761e189e921bf4c04df5707bb6a97c84c665127e6735b3dfb1d0c2e7f56861`

本机原件保存在 `D:\CodexScratch\tacticore-beta-foundation-20261031-135407`：最终包为 `runtime-v4`，最终烟测 `smoke-v4-clean-env.json`、预检 `preflight-final.json`、构建门禁 `build-guards-final.json`，另有 `foundation-tests.log` 和 `rust-tests.log`。这些本机原件不随 Git 源码分发。

早期阶段包和试错记录保留。第一次 Rust 测试因新 worktree 缺少开发 `.venv` 有两项 `runtime_layout_unavailable`，创建正常的独立开发环境后原断言全部通过；首次导入探针把本项目实际的 `httpx2` 写成了 `httpx`，纠正探针后完成以上最终烟测。未删除断言、跳过失败或修改原正式验收记录。

## 尚未完成

预检当前列出 9 项阻断。核心是 Native5 helper 的固定游戏路径、DLL 的绝对输入锁/日志/Mod 路径、SDK 仓库写入、schema13 的开发原件依赖，以及尚未接入的新便携资格合同。beta 版本、完整战略 Native 制品和安装器也未完成；Python 阶段包本身不能发布。

当前依赖版本锁没有 wheel 下载摘要，不宣称跨机器逐字节可重建。许可证清单如实标记 `pending`，其中 `logfire-api` 的安装 RECORD 未提供单独许可证文件；收集清单不代表完成再分发审查。游戏、Mod、编译器、SDK 和美术不在本阶段包的收集范围。

下一批应同时处理新 Native 候选、SDK、只读归还读取器、用户数据根目录及资格加载合同，保留完整身份、合法视野、输入上限、未知不重发和停止归还约束。不能以删除源锁、伪造便携证书或沿用旧三局来通过。
