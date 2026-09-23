# v0.4 路线迁移说明

v0.4 是一次明确的主线重构：旧的 68 节点冻结路线被替换为 14 节点简化路线，因此旧本地数据库中的 plan hash 与新路线不兼容。

当前项目自带的 `sync/learningci.db` 已按新路线重建，并把已经完成过的 MyMuduo / game_rpc_project 回顾节点标记为 `SKIPPED`，启动后主线直接从：

`NRPC-B0-01 建立 NebulaRPC 可工作的 Baseline`

开始。

如果本机仍保留旧 `data/learningci.db`，升级后请运行：

`reset_local_data.bat`

脚本会先备份旧本地数据库，再删除本地运行库；下次启动会自动从新的 `sync/learningci.db` 恢复。

旧数据库不会被脚本直接覆盖，备份位置为 `data/learningci.backup.db`。
