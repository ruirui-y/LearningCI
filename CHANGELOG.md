# Changelog

## v0.1.1 - 2026-09-16

- 修正 NebulaRPC 项目路径语义：`docs/history/*` 明确为目标项目路径，而不是 LearningCI/docs。
- 使用用户提供的 NebulaRPC Master Plan v0.2 重新编译完整 Frozen Plan。
- Frozen Plan 扩展为 68 个最小节点；Stage 13~14 标记 OPTIONAL，不阻塞 CORE 主线。
- Verification 粘贴试卷后自动渲染 5 个问题卡片，每题下面直接生成独立回答框。
- 回答按 question id 保存，并以结构化逐题 JSON 构建评分 Prompt。
- FAIL 后可立即生成不同试卷重新验证，包括复测场景。
- 补齐按钮 hover / pressed / disabled / focus 细节。
- Today 明确显示目标项目产物路径，避免和 LearningCI/docs 混淆。
- 增加 NebulaRPC history 空模板、Plan Overview 与 v0.1.0 本地数据重置脚本。
