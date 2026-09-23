# NebulaRPC 简化主线 v0.4

## 1. 目标

NebulaRPC 的目的不是完成一套繁琐学习流程，而是把已有经验升级成一个能够证明 C++ 后端 / RPC / 高性能服务器能力的真实项目。目标岗位按 **15~20k 技术证据强度**准备，但不把薪资结果当成软件能保证的结果。

主线只遵循一条规则：

```text
旧项目回顾 → AI 辅助迁移形成可工作 Baseline → 新能力逐项开发 → 测试/故障/性能证据 → 与 bRPC/gRPC 公平验证 → v1.0 求职证据
```

不再为了“完成节点”重复手写已经在 MyMuduo 或 game_rpc_project 中做过的基础能力。

## 2. Recovery：只回顾，不重写

### 2.1 MyMuduo

快速回顾 EventLoop/Poller/Channel、TcpConnection、Buffer、Connector/TcpClient、partial write/EPOLLOUT、生命周期和 One Loop Per Thread。目标是恢复理解和修改能力，不重新实现 Reactor，也不要求额外写大篇审计文档。

### 2.2 game_rpc_project

快速回顾 Frame/Parser、Protobuf Service 分发、RequestId/PendingCall、promise/future、ReceiverThread/wait_for。目标是确认旧 RPC 已做到哪里，以及真正异步 RPC 的断点在哪里。

## 3. Baseline：AI 辅助迁移，不从零造轮子

AI 同时阅读两个旧项目和 NebulaRPC 当前骨架，选择可复用部分迁移到新项目。学习者负责审查架构、理解关键调用链、编译、测试和修复；不要求手工逐行重写旧实现。

Baseline 最低标准：

- 干净的 `nebula/net` 与 `nebula/rpc` 模块边界；
- localhost echo 跑通；
- 最小 protobuf RPC 跑通；
- CMake 可重复构建；
- ASan/UBSan 至少完成一次基础验证；
- Git 有清晰 baseline commit。

## 4. 新能力一：真正的 Event-Driven Async RPC

### 4.1 Async RPC

删除 ReceiverThread + wait_for 作为主执行模型。响应从 EventLoop read path 进入 parser，通过 RequestId 找到 PendingCall，并由完成路径触发 callback。必须验证高 inflight、乱序响应和 EventLoop 不阻塞。

### 4.2 Deadline / Cancel / Exactly-Once

Response、Timeout、Cancel、Connection Close 等完成源会竞争。系统必须以显式 completion state 保证一次调用只完成一次，并正确清理 PendingCall。

## 5. 新能力二：C++20 Coroutine

### 5.1 Coroutine RPC API

在稳定 Async RPC 上增加 `Task<T>` / `RpcAwaiter`。协程只是异步完成模型的语法与生命周期抽象，不是线程。

### 5.2 生命周期与 Resume 线程

必须能解释和验证 coroutine frame、PendingCall、connection、timeout/cancel/shutdown 之间的生命周期，以及 coroutine 在哪个线程/Executor 恢复。

## 6. 新能力三：并发与资源治理

### 6.1 Multi-Reactor

明确 fd/Connection/PendingCall 的 owner loop，通过 command queue + eventfd 做跨线程提交，并用 1/2/4/8 Reactor 数据验证扩展性。

### 6.2 Backpressure

输出缓冲、inflight、跨线程队列和慢消费者都必须有明确边界与过载策略，避免无界内存和 P99 失控。

## 7. 新能力四：可用的 Client Runtime 与可靠性

### 7.1 Connection Pool / Load Balancing / Retry

建立异步连接池、静态解析、基础负载均衡，以及受幂等和 absolute deadline 约束的 retry。

### 7.2 Observability / Fault / Shutdown

用 metrics、EventLoop lag、RequestId trace、fault matrix 和 graceful shutdown 证明系统能定位问题并正确收尾资源。

## 8. 性能与框架验证

### 8.1 Benchmark / Profile

固定环境与 workload，记录 QPS、P50/P99/P999、CPU、内存、线程。优化必须由 profile 驱动，并保留有效优化和失败优化案例。

### 8.2 bRPC / gRPC 对照

统一 benchmark harness 比较 NebulaRPC、bRPC、gRPC。目标不是“跑赢”，而是能解释线程模型、连接模型、可靠性语义和性能差距。

## 9. v1.0 求职证据

最终每个核心能力尽量能够沿着：

```text
问题 → 约束 → 设计 → 代码 → 测试/故障 → 数据 → 取舍 → 失败场景
```

完整展开，并绑定真实 commit、测试、原始 benchmark/profile、ADR 和可复现命令。

## 10. LearningCI 执行规则

- REVIEW：只回顾旧项目，4~6 个动作足够，不要求重写。
- MIGRATE：允许 AI 直接搬运和整理旧代码；学习者负责审查、编译、测试和理解。
- BUILD：新能力必须产生真实代码、测试、故障或性能证据。
- VALIDATE：以可复现数据和求职证据为主。
- 节点执行包默认可直接开始，不再强制先做 20~30 个叶子任务细化。
- 只有当前节点确实太大或边界不清时，才使用“节点准备”重新细化。
