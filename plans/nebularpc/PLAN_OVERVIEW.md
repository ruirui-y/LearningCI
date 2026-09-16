# NebulaRPC Frozen Plan Overview

Plan version: `0.3-learningci-full`

本文件用于人工快速审查 `plan.json`。真正执行合同仍然是 `plan.json`。

## Stage 0

- `NRPC-S0-01` · **MyMuduo 历史能力审计** · CORE · 来源：§4.1 / §7 / §30
- `NRPC-S0-02` · **game_rpc_project 历史能力审计** · CORE · 来源：§4.2 / §4.4 / §7 / §30
- `NRPC-S0-03` · **历史断点与新起跑线确认** · CORE · 来源：§4.3 / §5.2 / §5.3 / §6
- `NRPC-S0-04` · **可重复 Build / Test 基线** · CORE · 来源：§7.3 / §7.4
- `NRPC-S0-05` · **Benchmark 环境记录基线** · CORE · 来源：§3 / §18 / §25
## Stage 1

- `NRPC-S1-01` · **EventLoop 可读事件完整路径** · CORE · 来源：§8.1~§8.6
- `NRPC-S1-02` · **Partial Write 与 EPOLLOUT 生命周期** · CORE · 来源：§8.4 / §8.5 / §4.4
- `NRPC-S1-03` · **Connection Close 生命周期** · CORE · 来源：§8.5 / §17
- `NRPC-S1-04` · **Connector/TcpClient 事件驱动恢复** · CORE · 来源：§8 / §35
- `NRPC-S1-05` · **最小网络 Runtime Stage 1 验收** · CORE · 来源：§8.5 / §8.6
## Stage 2

- `NRPC-S2-01` · **Frame V2 协议边界与硬限制** · CORE · 来源：§9.2
- `NRPC-S2-02` · **Incremental Frame Parser** · CORE · 来源：§9.3 / §9.6
- `NRPC-S2-03` · **RequestId 与 PendingCall V1** · CORE · 来源：§9.4 / §9.6
- `NRPC-S2-04` · **1000 Inflight 乱序响应验证** · CORE · 来源：§9.7 / §6
- `NRPC-S2-05` · **Protobuf Adapter 与 Runtime 解耦** · CORE · 来源：§3.2 / §9.5
- `NRPC-S2-06` · **Stage 2 恢复区验收** · CORE · 来源：§9.7 / §6
## Stage 3

- `NRPC-S3-01` · **CallAsync 线程语义与所有权设计** · CORE · 来源：§10.4~§10.6
- `NRPC-S3-02` · **Event-Driven CallAsync 最小实现** · CORE · 来源：§10.2 / §10.3
- `NRPC-S3-03` · **Connection Close 失败所有 PendingCall** · CORE · 来源：§10.4 / §10.8
- `NRPC-S3-04` · **删除 ReceiverThread / wait_for 主执行模型** · CORE · 来源：§10.1 / §10.8
- `NRPC-S3-05` · **Async RPC 高 Inflight 与旧模型对照** · CORE · 来源：§10.7 / §10.8
## Stage 4

- `NRPC-S4-01` · **最小 Task<T>/Task<void> 协程对象** · CORE · 来源：§11.2
- `NRPC-S4-02` · **RpcAwaiter suspend/resume 链路** · CORE · 来源：§11.3
- `NRPC-S4-03` · **Coroutine Frame 生命周期与提前销毁** · CORE · 来源：§11.4
- `NRPC-S4-04` · **Coroutine Resume 线程语义** · CORE · 来源：§11.5
- `NRPC-S4-05` · **1000 并发 Coroutine RPC 验收** · CORE · 来源：§11.6
## Stage 5

- `NRPC-S5-01` · **Completion Sources 与终态状态机** · CORE · 来源：§12.1~§12.4
- `NRPC-S5-02` · **Timer + Absolute Deadline** · CORE · 来源：§12.5 / §12.6
- `NRPC-S5-03` · **Cancel / Late Response 语义** · CORE · 来源：§12.7
- `NRPC-S5-04` · **Completion Race Suite** · CORE · 来源：§12.8 / §12.9
- `NRPC-S5-05` · **Shutdown 下挂起调用收尾** · CORE · 来源：§12.9 / §17
## Stage 6

- `NRPC-S6-01` · **Multi-Reactor RPC 所有权模型** · CORE · 来源：§13.1 / §13.2
- `NRPC-S6-02` · **跨线程 Command Queue + eventfd** · CORE · 来源：§13.3
- `NRPC-S6-03` · **1/2/4/8 Reactor 扩展实验** · CORE · 来源：§13.4 / §13.5
- `NRPC-S6-04` · **CPU Affinity 可选实验与 Stage 6 验收** · CORE · 来源：§13.5
## Stage 7

- `NRPC-S7-01` · **Output Watermark 与 Slow Consumer 边界** · CORE · 来源：§14.1 / §14.2 / §14.4
- `NRPC-S7-02` · **Inflight / Pending 上限与 Fail-Fast** · CORE · 来源：§14.3
- `NRPC-S7-03` · **跨线程队列与 Timer 等资源边界** · CORE · 来源：§14.1 / §14.5
- `NRPC-S7-04` · **Overload 隔离验收** · CORE · 来源：§14.5
## Stage 8

- `NRPC-S8-01` · **异步 Connection Pool** · CORE · 来源：§15.1 / §15.2
- `NRPC-S8-02` · **Load Balancing 对照实验** · CORE · 来源：§15.2
- `NRPC-S8-03` · **Retry 幂等 / Deadline 语义** · CORE · 来源：§15.3
- `NRPC-S8-04` · **Static Resolver 与 Client Runtime 验收** · CORE · 来源：§15.4 / §15.5
## Stage 9

- `NRPC-S9-01` · **核心 Metrics：Counter/Gauge/Histogram** · CORE · 来源：§16.1 / §16.4
- `NRPC-S9-02` · **EventLoop Lag** · CORE · 来源：§16.2
- `NRPC-S9-03` · **RequestId Debug Trace** · CORE · 来源：§16.3
- `NRPC-S9-04` · **仅靠指标定位一次 P99 异常** · CORE · 来源：§16.5
## Stage 10

- `NRPC-S10-01` · **Fault Matrix：连接与协议异常** · CORE · 来源：§17.1
- `NRPC-S10-02` · **Connection Close 完整资源清理** · CORE · 来源：§17.3
- `NRPC-S10-03` · **Graceful Shutdown 状态机** · CORE · 来源：§17.2
- `NRPC-S10-04` · **自动化 Fault + Shutdown 验收** · CORE · 来源：§17.4
## Stage 11

- `NRPC-S11-01` · **性能 Baseline + Profile 闭环** · CORE · 来源：§18.1~§18.3
- `NRPC-S11-02` · **第一个真实性能优化案例** · CORE · 来源：§18.4 / §18.5
- `NRPC-S11-03` · **第二个独立性能优化案例** · CORE · 来源：§18.5
- `NRPC-S11-04` · **失败优化案例与回退** · CORE · 来源：§18.5 / §19
## Stage 12

- `NRPC-S12-01` · **统一 Framework Benchmark Harness** · CORE · 来源：§19.1~§19.3
- `NRPC-S12-02` · **Payload/Concurrency/Connections Matrix** · CORE · 来源：§19.2 / §19.3
- `NRPC-S12-03` · **框架差距定位与解释** · CORE · 来源：§19.4
- `NRPC-S12-04` · **Framework Benchmark Stage 验收** · CORE · 来源：§19
## Stage 13

- `NRPC-S13-01` · **io_uring Transport Prototype** · OPTIONAL · 来源：§20.1
- `NRPC-S13-02` · **Timing Wheel 对照实验** · OPTIONAL · 来源：§20.2
- `NRPC-S13-03` · **Per-Core / NUMA 研究** · OPTIONAL · 来源：§20.3 / §20.4
- `NRPC-S13-04` · **Adaptive Concurrency / TLS / Compression 选题** · OPTIONAL · 来源：§20.5 / §20.6
## Stage 14

- `NRPC-S14-01` · **Typed API / Protobuf Service Model 收束** · OPTIONAL · 来源：§21.1
- `NRPC-S14-02` · **protoc Codegen 可选实验** · OPTIONAL · 来源：§21.1
## Stage 15

- `NRPC-S15-01` · **v1.0 正确性与系统设计证据收束** · CORE · 来源：§21.2 / §33
- `NRPC-S15-02` · **README / Architecture / Benchmark 作品化** · CORE · 来源：§21.3 / §21.4 / §34
- `NRPC-S15-03` · **v1.0 封版与技术叙事验收** · CORE · 来源：§29 / §33 / §34
