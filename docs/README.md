# 弈核 Tacticore 文档索引

## 从这里开始

- [项目 README](../README.md)：当前工程、模块职责与开发入口。
- [未发布改动说明](../CHANGELOG.md)：本批源码、框架、桌面与破坏性变化。
- [Windows 同步与策略验证](windows-validation.md)：Windows 侧合并本侧变更、安装、离线回归、真实模型与实机验收顺序。

## 决策层与策略

- [PydanticAI 运行时](../agent_runtime/README.md)：依赖、后端与请求边界。
- [选型 ADR](agent-runtime/0001-pydantic-decision-runtime.md)：框架职责与决策理由。
- [模型层迁移交接](agent-runtime/migration-handoff.md)：实际改动清单和合并边界。
- [策略层 README](../strategy/README.md)：合同、记忆、任务及离线演示。
- [模型服务](../strategy/HTTP_SERVICE.md)：连接库、脱敏检查与文件快照服务。
- [持续 BattleAgent](../strategy/BATTLE_AGENT.md)：记忆、任务及执行反馈。

## 桌面与体验

- [React + Tauri 桌面](../desktop-ui/README.md)：唯一桌面工程的本地运行与构建。
- [Windows 原生接线合同](desktop-next/windows-handoff.md)：新 GUI 与宿主之间待实现的协议及验收。
- [玩家流程](desktop-next/player-guide.md)：当前离线体验与未来真实使用流程。
- [Feature 路线图](desktop-next/feature-roadmap.md)：备战、指挥风格、电台关怀与复盘，均按实施状态标记。
- [品牌与宣传边界](desktop-next/claims.md)：独立项目身份与能力表述。
- [本侧验证记录](desktop-next/verification.md)：macOS 已验证结果及 Windows 待验证范围。

## 游戏与原始证据

- [阶段状态](../acceptance/stage-report.md)、[视野与战术验收](../acceptance/vision-tactics-status.md)：按日期与构建阅读实际能力范围。
- [战术模块](../tactical/README.md)、[视野](../visibility/README.md)、[生产](../production/README.md)、[持续生产](../production/persistent/README.md)。
- [基准与对照](../benchmark/README.md)：场景与实验说明。

历史记录用于说明当时的实验，不能覆盖当前默认 PydanticAI、新桌面或新游戏构建的验收。框架离线通过、CLI 实机通过和 GUI 端到端通过分别记录。
