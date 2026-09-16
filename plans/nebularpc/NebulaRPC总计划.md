---
title: "NebulaRPC 总体设计与学习路线"
subtitle: "冻结学习主线：从既有工程能力继续到可被面试证据证明的 C++20 Async RPC Runtime"
author: "Frozen Learning Route"
date: "v0.3-frozen · 2026-09-16"
lang: zh-CN
---

# 文档定位

NebulaRPC 是一个**学习型、实验型、可压测的 C++20 RPC Runtime**。它的目标不是尽快做出“业务功能齐全的服务器”，而是把 Linux 网络 I/O、并发模型、协程、协议解析、超时取消、资源治理、可观测性和性能优化串成一条完整的系统工程主线。

这份文档是 NebulaRPC 的**冻结学习总纲 / Master Plan**。从 v0.3-frozen 起，Stage 顺序、核心能力边界、主线毕业标准视为冻结路线；后续允许通过 ADR 修改**项目实现细节**，但不能因为临时兴趣、热门技术或“看起来更短”而改写学习主线。只有发现事实性前置错误或节点不可验证时，才允许进入 LearningCI 的正式路线复盘流程。

> 核心原则：**每增加一个功能，都必须回答一个明确的系统问题；每一次优化，都必须有基线和测量证据。**

NebulaRPC 不延续 DemandStation 的业务架构，也不迁移登录、支付、设备、上传、订单等已有业务。DemandStation 作为“工程能力作品”封版；NebulaRPC 用来构建“系统能力作品”。

**v0.2 起新增一条更重要的原则：NebulaRPC 不假装从零开始。** 现有 `MyMuduo` 与 `game_rpc_project` 已经证明你完成过 Reactor、Multi-Reactor、TcpClient、Buffer、增量 RPC 解析、Protobuf Service 分发、Request ID 与 `promise/future` PendingCall 等工作。因此前半段路线改为“快速恢复与重建”，真正的新主线从 **Event-Driven Async RPC → C++20 Coroutine → Exactly-Once Completion State Machine** 开始。

---


# 0. 求职目标与能力证明标准

这条路线的直接目标不是“把技术列表学完”，而是形成一套在 C++ 后端 / 高性能服务器 / RPC / 系统工程面试中可以被追问、复现和验证的能力证据。

目标薪资可以设为 **15k+**，学习与项目验收则按更高一档的证据强度准备；但薪资结果仍会受到城市、公司、岗位、工作年限、面试表现和市场变化影响，本文档只负责把技术实力做成可证明资产，不承诺具体 offer。

## 0.1 四个项目各自承担不同证明责任

### DemandStation：真实生产与交付证据

DemandStation 不作为 NebulaRPC 的重写来源，而作为“真实客户环境中交付、部署、长期运行”的工程证据。当前已知背景是：已有十余台客户购买并运行，服务端主要部署在 Windows；Linux 可以编译，但生产没有迁移，因为现有 MySQL / Redis 环境已经稳定配置在 Windows。

面试准备时，不把“线上没崩过”当成口号，而是尽量形成可匿名展示的证据：

- 客户部署规模与版本分布；
- 服务端进程、MySQL、Redis 的部署拓扑；
- 关键日志、监控或长期运行记录；
- 真实线上问题、定位过程和修复记录；
- Windows 生产选择与 Linux 可编译能力之间的工程取舍；
- 升级、回滚、配置管理、异常恢复等真实运维经验。

### MyMuduo：Linux 网络与高性能基础证据

MyMuduo 用来证明 Reactor、One Loop Per Thread、TcpConnection/TcpClient、Buffer、eventfd、定时器和性能分析等底层能力。README 中的性能数字只能作为入口，正式面试证据必须回到源码、压测命令、原始数据与可复现实验。

### NebulaRPC：系统深度主项目

NebulaRPC 是最终的技术深度作品，负责证明：事件驱动 Async RPC、C++20 coroutine、Exactly-Once Completion、Multi-Reactor ownership、Backpressure、Reliability、Observability、Benchmark 与性能工程。

### OmniBox：架构广度与产品化辅助证据

OmniBox 用来证明 Qt 客户端、微服务拆分、设备发现、Protobuf、自研 RPC、文件传输等跨层工程能力。它不是 NebulaRPC 主线的替代品，也不再因为“还能加新技术”无限扩张；面试时作为架构广度与完整系统设计的辅助项目。

## 0.2 面试证据优先级

每一个重要能力优先留下以下证据，强度从弱到强逐级增加：

```text
口头解释
  ↓
真实源码位置 / Git Commit
  ↓
自动测试 / 故障复现
  ↓
Benchmark 原始数据 / Profile
  ↓
ADR / Tradeoff / 失败方案记录
  ↓
生产运行 / 客户环境 / 真实故障处置
```

LearningCI 的分数不能替代这些证据。最终面试表达必须能够沿着：

```text
问题 → 约束 → 设计 → 代码 → 验证 → 数据 → 取舍 → 失败场景
```

完整展开，而不是只说“我用了 epoll / 协程 / 内存池”。

## 0.3 最终求职证据组合

主线完成后应能够同时拿出：

1. **生产实战**：DemandStation 的真实部署和长期运行故事；
2. **底层网络**：MyMuduo 的源码级 Reactor / Buffer / 生命周期 / 性能证据；
3. **现代系统深度**：NebulaRPC 的 Async RPC / Coroutine / Reliability / Performance 证据；
4. **系统广度**：OmniBox 的客户端 + 微服务 + 自研通信体系。

最终目标不是让四个项目都“功能更多”，而是让每一个项目都承担一个清晰、不可互相替代的证明责任。

## 0.4 CORE 节点的面试证明门槛

CORE 节点在 LearningCI 中拿到 PASS 只是第一层。真正准备求职时，重要节点还应尽量具备以下证明材料：

```text
60 秒闭卷解释
  +
5 分钟源码/状态机/调用链深挖
  +
至少一个真实源码位置或 Git Commit
  +
至少一个自动测试 / 故障复现 / 抓包 / Sanitizer 证据
  +
如果声称性能优势：原始 Benchmark + Profile
  +
至少一个设计取舍或失败方案
```

面试官继续追问时，回答应能从“概念”落到“我自己的项目里具体哪一段代码、什么测试、什么数据”。如果一个节点只有背诵答案，没有工程证据，则即使 LearningCI 分数很高，也不能作为强求职证据。

对于生产项目 DemandStation，还应优先补齐匿名化的部署、版本、运行记录、故障处置与升级证据；生产事实的证明强度高于单纯的 Demo。

---

# 1. 项目目标与非目标

## 1.1 最终目标

最终希望得到一个能够完成如下调用的 Runtime：

```cpp
auto result = co_await client.Call<UserRequest, UserResponse>(
    "UserService.GetUser",
    request,
    100ms
);

if (!result) {
    // timeout / cancelled / connection error / protocol error
}
```

服务端调用形态：

```cpp
server.Register<UserRequest, UserResponse>(
    "UserService.GetUser",
    [](const UserRequest& req) -> Task<UserResponse> {
        UserResponse rsp;
        rsp.set_id(req.id());
        co_return rsp;
    }
);
```

这两段 API 只是最终表象。真正需要掌握的是它们下面的完整链路：

```text
Application
    │
    ▼
RPC Client / RPC Server
    │
    ▼
Request ID / Dispatcher / PendingCall
    │
    ▼
Coroutine Runtime / Scheduler / Timer
    │
    ▼
Connection / Backpressure / Buffer
    │
    ▼
EventLoop / Channel / Poller
    │
    ▼
epoll / eventfd / timerfd
    │
    ▼
Linux TCP
```

## 1.2 必须掌握的核心能力

项目完成后，应能够脱离代码回答以下问题：

- Linux 收到可读事件后，程序如何从 `epoll_wait()` 一路走到 RPC Handler？
- TCP 为什么没有消息边界？半包、粘包是如何在增量 Parser 中被处理的？
- 同一连接上存在数千个并发 RPC 时，如何把乱序 Response 匹配回正确调用？
- C++20 协程为什么“不等于线程”？一个协程在哪些时刻暂停、由谁恢复？
- Response、Timeout、Cancel、Connection Close 同时竞争时，如何保证一个 RPC 只完成一次？
- 为什么单 Reactor 会成为瓶颈？Multi-Reactor 中 fd、Connection 与线程的所有权如何定义？
- 为什么无界发送队列是系统事故隐患？背压应该施加在哪些层？
- 为什么平均延迟很好但 P99/P999 很差？尾延迟通常从哪里产生？
- 什么时候 `malloc/memcpy` 值得优化？如何证明 BufferPool 或 Buffer Chain 真正有效？
- 如何让自己的 benchmark 与 brpc / gRPC 的对比具有可重复性，而不是“跑一次截图”？

## 1.3 非目标

NebulaRPC 核心路线明确禁止把精力重新拉回业务开发：

- 不做登录、注册、JWT。
- 不做商城、订单、支付。
- 不做好友、聊天业务。
- 不做文件管理业务。
- 不做 MySQL CRUD 封装。
- 不做管理后台或 Web 前端。
- 不为了“看起来像完整产品”而堆无关功能。
- 不在没有性能证据前提前上“零拷贝”“对象池”“io_uring”等高级名词。

允许的内容只有：**Network、OS、Concurrency、Coroutine、Memory、Scheduling、Protocol、Reliability、Observability、Performance。**

---

# 2. 项目方法论

## 2.1 先出现问题，再引入抽象

新问题仍然遵循“先出现问题，再引入抽象”。但 v0.2 不再要求 Recovery Zone 故意退回最原始实现：`MyMuduo` 已经证明过 `EventLoop / Channel / Poller / TcpConnection / TcpClient` 这些抽象的必要性，可以直接以旧设计为参考快速恢复。

真正进入新领域后，每一个新增抽象仍然必须回答：

> 如果没有它，当前代码具体哪里开始变坏？

例如 `PendingCall`、`RpcAwaiter`、`CompletionState`、`Executor` 都应该由实际问题推动，而不是因为 brpc、Workflow、Seastar 中存在类似概念就照搬。

## 2.2 先建立基线，再优化

任何优化必须遵循：

```text
Baseline
   ↓
Profile
   ↓
Locate bottleneck
   ↓
Change one major variable
   ↓
Re-benchmark
   ↓
Keep or revert
```

禁止：

```text
感觉 malloc 很慢 → 写内存池
感觉 writev 很快 → 全部改 writev
感觉 io_uring 高级 → 重写网络层
```

## 2.3 所有资源必须有边界

最终 Runtime 中以下结构都不能无限增长：

- 单连接输入缓冲。
- 单连接输出缓冲。
- 全局 PendingCall 数。
- 单连接 Inflight RPC 数。
- 跨线程任务队列。
- Timer 数量。
- 连接数。
- Metrics 标签基数。
- Trace / Debug 数据保留量。

每个资源都要有：**上限、超限策略、指标、测试。**

## 2.4 生命周期优先使用状态机表达

凡是有竞争关系的对象，优先画状态机，而不是堆 `bool`：

```text
Pending → Completed
       → TimedOut
       → Cancelled
       → ConnectionClosed
```

核心要求：终态只允许成功进入一次。

## 2.5 单一所有权优先

典型规则：

- 一个 Connection 在生命周期内固定归属于一个 EventLoop。
- Socket 的读写状态只能由所属 EventLoop 线程直接修改。
- 其他线程想操作 Connection 必须投递任务。
- Completion 最终在哪个线程恢复协程必须有明确规则。

这样做是为了减少“到处加锁”的架构退化。

---

# 3. 推荐技术基线

## 3.1 核心环境

建议主开发环境：

```text
OS            Linux x86_64
Language      C++20
Compiler      GCC 13+ / Clang 17+
Build         CMake + Ninja
Network       POSIX socket + epoll
Wakeup        eventfd
Timer         timerfd + min-heap（第一版）
Serialization raw bytes → Protobuf adapter
Test          GoogleTest 或 Catch2（二选一）
Benchmark     自研压测器 + hdr/histogram 思路
Profiling     perf / FlameGraph / pidstat / strace
Sanitizer     ASan / UBSan / TSan
```

开发可以在 WSL2 / Linux 虚拟机开始，但正式 benchmark 最好使用原生 Linux，并记录机器与内核信息。

## 3.2 依赖策略

核心 Runtime 尽量少依赖：

- 网络层：只依赖 Linux syscall 与 STL。
- RPC Runtime 内部首先面向 bytes/frame；Stage 2 即可接回旧项目已经使用过的 Protobuf adapter。
- Protobuf 不再作为独立学习阶段；重点是让序列化层与 Transport / PendingCall / Coroutine 解耦。
- Metrics：先内部实现计数器/直方图抽象，导出格式后加。
- benchmark 对照组中的 brpc/gRPC 不属于 NebulaRPC Runtime 依赖。

---

# 4. 既有项目基线与新的起跑线

NebulaRPC v0.2 的路线建立在两个已经存在的仓库上，而不是建立在“从未写过网络库/RPC”的假设上。

参考仓库：

```text
MyMuduo
https://github.com/ruirui-y/MyMuduo

game_rpc_project
https://github.com/ruirui-y/game_rpc_project
```

## 4.1 MyMuduo 已经证明的能力

当前仓库已经具备或实现过：

```text
Acceptor
Buffer
Channel
Connector
EPollPoller
EventLoop
EventLoopThread
EventLoopThreadPool
Poller
Socket
TcpClient
TcpConnection
TcpServer
Timer / TimerQueue
ThreadSwitcher
SSLContext
```

并且 README / Notes 已经覆盖：

- Reactor / One Loop Per Thread。
- epoll ET。
- `eventfd` 跨线程唤醒。
- MainReactor + SubReactor。
- `readv` 与自适应 Buffer。
- 时间轮。
- TcpClient / Connector / Retry。
- TcpConnection 生命周期与 `shared_ptr/weak_ptr` 问题。
- 异步发送：socket 暂时写不完时，把剩余数据放入 Buffer，等待 EPOLLOUT。
- 异步日志和性能压测。

因此 NebulaRPC **不再把“手写一个完整 muduo”当成主要学习目标**。

## 4.2 game_rpc_project 已经证明的能力

旧 RPC 项目已经实现过：

```text
Gateway / Login / Match / Chat 服务拆分
Protobuf RpcChannel
RpcHeader
Service Registry
增量 Frame 解析
Request ID / seq_id
PendingCall map
promise / future
Receiver Thread
基础 Timeout
ConnectionPool
```

尤其是以下链路已经真实存在：

```text
CallMethod
  ↓
seq_id++
  ↓
pending_calls_[seq_id] = promise
  ↓
send()
  ↓
future.wait_for()
  ↓
ReceiverThread recv()
  ↓
response seq_id
  ↓
promise.set_value()
```

这已经完成了“同一连接上的请求/响应匹配”这一核心概念的第一版。

## 4.3 两个旧项目之间真正的断点

MyMuduo 的 Notes 已经记录过写 TcpClient 的直接动机：旧 RPC 调用会阻塞业务线程；每个服务共用 socket 时写入需要竞争；大包发送会进一步拉长其他请求延迟。因此你后来把客户端 socket 放进 EventLoop，让读写都由 Reactor 驱动。

也就是说历史开发路径实际上已经走到：

```text
game_rpc_project
同步 RPC
promise/future
ReceiverThread
write mutex
        │
        │ 发现阻塞与共享 socket 的问题
        ▼
MyMuduo
TcpClient
Connector
EventLoop 驱动读写
非阻塞发送
        │
        ▼
????????????????????
```

NebulaRPC 就从这个问号继续。

新的主线是：

```text
Event-Driven TcpClient
        +
RequestId / PendingCall
        ↓
真正的 Async RPC
        ↓
C++20 co_await RPC
        ↓
Timeout / Cancel / Disconnect / Response
Exactly-Once Completion
        ↓
多核、背压、资源治理、性能工程
```

## 4.4 旧实现中值得重新研究的技术债

这些不是为了批评旧项目，而是 NebulaRPC 最好的题目来源。

### 旧客户端一次 `send()` 假设

旧 `MyChannel::CallMethod()` 直接对完整 RPC 字符串调用一次 `send()`。非阻塞/高负载 socket 不能假定一次 `send()` 必然写完全部数据。

NebulaRPC 必须把：

```text
partial write
EAGAIN
剩余数据所有权
EPOLLOUT enable/disable
write complete
```

做成明确的不变量。

### ReceiverThread + MSG_WAITALL

旧模型依赖一个后台线程阻塞收包。它能工作，但与新的目标冲突：

```text
一个 Channel 一个 Receiver Thread
业务线程 future.wait_for
网络线程模型与 RPC Completion 分裂
```

NebulaRPC 的第一个关键里程碑就是**彻底删除这个模型**。

### 超大 Response 的流失步问题

旧 Receiver 在读到超大 `response_size` 后直接 `continue`，但没有消费对应 body。这样下一个循环可能把 body 前 4 字节误当成新的长度头。

NebulaRPC 对非法 Frame 必须明确二选一：

```text
1. 可安全 skip：完整消费 frame 后继续；
2. 不可信/过大：立即关闭连接。
```

不能让 Parser 静默失去同步。

### RPC Server 的异步生命周期

旧服务端在 `CallMethod()` 返回后释放 request/response。如果未来 Handler 或 `done` 真正异步执行，response 的所有权会变得危险。

NebulaRPC 必须回答：

```text
谁拥有 Request？
谁拥有 Response？
Handler suspend 后对象是否还活着？
Connection 关闭后 response 还能不能发送？
Completion 后谁负责释放？
```

这会直接连接到后面的 Coroutine 与 Completion State Machine。

---

# 5. v0.2 仓库演进原则

## 5.1 不复制整个 MyMuduo

NebulaRPC 不应该把 `MyMuduo` 全量复制进来，也不应该再次花几周重写所有网络组件。

推荐方案：**提取/重写一个最小网络 Runtime**，只保留 RPC 真正需要的能力：

```text
EventLoop
Channel
EPollPoller
Socket
Buffer
TcpConnection
TcpServer
Connector
TcpClient
EventLoopThread / ThreadPool（Stage 6 再启用）
Timer 基础接口（Stage 5 完善）
```

目标不是“再造 MyMuduo 2.0”，而是给 RPC Runtime 一个你完全掌控的网络地基。

## 5.2 Recovery Zone 必须限时

Stage 0~2 属于 **Recovery Zone**。

这些阶段的目的：

```text
找回上下文
修复旧设计中明显的问题
建立新仓库的最小骨架
为新的 Async RPC 铺路
```

它们不是为了再次证明你会 epoll、半包粘包、Protobuf。

原则：

> 如果一个问题你在旧仓库里已经完整解决过，就通过测试和说明快速重建，不进行无收益的“完美重构”。

## 5.3 New Knowledge Zone

真正需要投入主要时间的是 Stage 3 之后：

```text
Stage 3  Event-Driven Async RPC
Stage 4  C++20 Coroutine Runtime
Stage 5  Exactly-Once Completion / Deadline / Cancel
Stage 6  Multi-Reactor Ownership
Stage 7  Backpressure / Resource Boundaries
Stage 8  Client Runtime / Pool / LB / Retry
Stage 9  Observability
Stage 10 Reliability / Fault / Shutdown
Stage 11 Performance Engineering
Stage 12 brpc / gRPC Benchmark
```

如果时间有限，优先把 Stage 3~5 做深，而不是把 Stage 13~14 做全。

## 5.4 第一版目录

```text
NebulaRPC/
├─ CMakeLists.txt
├─ README.md
├─ docs/
│  ├─ MASTER_PLAN.md
│  ├─ adr/
│  └─ why/
│
├─ nebula/
│  ├─ net/
│  │  ├─ event_loop.*
│  │  ├─ channel.*
│  │  ├─ epoll_poller.*
│  │  ├─ socket.*
│  │  ├─ buffer.*
│  │  ├─ tcp_connection.*
│  │  ├─ tcp_server.*
│  │  ├─ connector.*
│  │  └─ tcp_client.*
│  │
│  ├─ protocol/
│  │  ├─ frame.h
│  │  ├─ frame_codec.*
│  │  └─ frame_parser.*
│  │
│  └─ rpc/
│     ├─ pending_call.*
│     ├─ rpc_client.*
│     ├─ rpc_server.*
│     └─ dispatcher.*
│
├─ examples/
│  ├─ echo_server.cpp
│  └─ echo_client.cpp
│
├─ benchmark/
└─ tests/
```

Coroutine 目录等到 Stage 4 再创建。

---

# 6. v0.2 总体阶段地图

路线分为“恢复区”和“新知识区”。

| Stage | 名称 | 状态/来源 | 核心产物 |
|---:|---|---|---|
| 0 | 历史基线审计 + 可重复实验环境 | 旧项目复盘 | 可 build/test/bench 的新仓库 |
| 1 | 最小网络 Runtime 恢复 | MyMuduo 已做过 | EventLoop + TcpClient/TcpServer |
| 2 | Protocol + RequestId + PendingCall 恢复 | game_rpc_project 已做过 | 无阻塞线程前的 RPC 基础 |
| **3** | **Event-Driven Async RPC** | **真正的新断点** | 删除 ReceiverThread / wait_for |
| **4** | **C++20 Coroutine Runtime** | **新领域** | `co_await client.Call()` |
| **5** | **Exactly-Once Completion** | **核心难点** | Response/Timeout/Cancel/Close 状态机 |
| 6 | Multi-Reactor 与所有权 | MyMuduo 有基础，重新系统化 | 多核扩展与线程归属 |
| 7 | Backpressure 与资源治理 | 深化 | 所有关键队列/Buffer 有界 |
| 8 | Client Runtime / Pool / LB / Retry | 旧 Pool 的工业化升级 | endpoint 管理与失败语义 |
| 9 | Observability | 新系统化 | Metrics / Histogram / EventLoop Lag |
| 10 | Reliability / Fault / Shutdown | 深化 | 故障矩阵与优雅退出 |
| 11 | Performance Engineering | 核心作品化 | perf 驱动的真实优化 |
| 12 | brpc / gRPC Benchmark | 核心作品化 | 公平 benchmark 报告 |
| 13 | 高级研究分支 | 可选 | io_uring / NUMA / per-core 等 |
| 14 | API / Codegen / 兼容性收束 | 可选 | 更成熟的使用层 |
| 15 | v1.0 封版与技术叙事 | 必做 | README / ADR / 数据 / 简历材料 |

关键认知：

> Stage 0~2 是“把过去找回来”；Stage 3 才是 NebulaRPC 真正的新起点。

---

# 7. Stage 0：历史基线审计与实验环境

## 7.1 目标

用最短时间回答：

```text
我过去到底做过什么？
哪些知识已经掌握？
哪些实现只能作为历史参考？
哪些问题必须在 NebulaRPC 重新解决？
```

## 7.2 必做动作

建立 `docs/history/`：

```text
docs/history/
├─ MYMUDUO_AUDIT.md
├─ GAME_RPC_AUDIT.md
└─ BREAKPOINT.md
```

`BREAKPOINT.md` 只需要明确：

```text
旧 RPC：RequestId + promise/future + ReceiverThread
旧网络：EventLoop + TcpClient + 非阻塞读写
新的断点：把二者合并成 Event-Driven Async RPC
```

## 7.3 工程基线

第一天就配好：

```text
C++20
CMake + Ninja
Debug / Release
-Wall -Wextra -Wpedantic
ASan + UBSan
CTest
benchmark 目录
scripts/ 统一启动脚本
```

记录环境：

```text
CPU
RAM
Linux distro
kernel
compiler
CMake
build type
CPU governor
```

## 7.4 Exit Criteria

```text
[ ] 新仓库能一键 configure/build/test
[ ] 两个旧项目的能力矩阵写完
[ ] 明确“不会重新做”的内容
[ ] 明确 Stage 3 是新的技术断点
```

建议投入：**1~2 天**。

---

# 8. Stage 1：最小网络 Runtime 恢复

## 8.1 目标

不是重新学习 Reactor，而是快速恢复足够支撑 RPC 的网络层。

最终只有两条路径必须稳定：

```text
Server:
epoll_wait → Channel → TcpConnection::handleRead → message callback

Client:
RpcClient → TcpClient/TcpConnection::send → output buffer → EPOLLOUT
```

## 8.2 必须保留的能力

```text
nonblocking socket
epoll
Channel
EventLoop
eventfd wakeup
TcpConnection
Buffer
TcpServer
Connector
TcpClient
partial read/write
EPOLLOUT 动态开关
connection close lifecycle
```

第一阶段可以只运行单 Reactor；Multi-Reactor 延迟到 Stage 6。

## 8.3 不应该重做的东西

暂时不要：

```text
SSL
时间轮
异步日志
HTTP
复杂 ThreadPool
kqueue
Production feature parity
```

这些在 MyMuduo 已经证明过，不是当前价值中心。

## 8.4 关键不变量

### Socket 写入

```text
write until EAGAIN / partial write
        ↓
remaining bytes → output buffer
        ↓
enable EPOLLOUT
        ↓
writable event
        ↓
continue flush
        ↓
output buffer empty
        ↓
disable EPOLLOUT
```

禁止一直监听 EPOLLOUT。

### Connection 所有权

```text
一个 TcpConnection 只属于一个 EventLoop
其他线程只能 queue/post 操作
```

## 8.5 测试

```text
[ ] 1 byte echo
[ ] 1KB echo
[ ] 1MB echo
[ ] 人工降低 socket send buffer 触发 partial write
[ ] 对端中途 close
[ ] 重复 connect/disconnect
[ ] 1000 长连接
[ ] ASan/UBSan 无错误
```

## 8.6 Exit Criteria

你能不用看代码解释：

> 一个 1MB payload 在第一次 `send/write` 只写出一部分时，剩余 bytes 到底归谁、何时继续写、谁启用/关闭 EPOLLOUT、连接中途关闭时 Buffer 如何销毁。

建议投入：**2~5 天，严格限时。**

---

# 9. Stage 2：Protocol + RequestId + PendingCall 快速重建

## 9.1 目标

把 `game_rpc_project` 已经验证过的核心能力迁移为更清晰、更安全的 V2，不重新沉迷业务服务。

## 9.2 Frame V2

建议第一版协议：

```text
+----------------------+
| Magic        4 bytes |
| Version      1 byte  |
| Type         1 byte  |
| Flags        2 bytes |
| HeaderLen    4 bytes |
| BodyLen      4 bytes |
| RequestId    8 bytes |
+----------------------+
| Header / Method Meta |
+----------------------+
| Payload              |
+----------------------+
```

所有整数明确网络字节序。

必须定义硬限制：

```text
MAX_HEADER_SIZE
MAX_BODY_SIZE
MAX_FRAME_SIZE
```

## 9.3 Incremental Parser

Parser 只从 Connection 的 input Buffer 消费完整 Frame：

```text
不足固定头 → NeedMore
非法 magic/version → ProtocolError
长度越界 → CloseConnection
完整头但 body 不够 → NeedMore
完整 frame → emit Frame，然后继续 while
```

必须支持：

```text
一个 frame 被拆成任意 N 段
一次 read 收到多个 frame
header/body 任意边界切片
```

## 9.4 PendingCall V1

先不加 coroutine。

```cpp
struct PendingCall {
    uint64_t request_id;
    // callback / completion slot
};
```

客户端：

```text
allocate RequestId
  ↓
register PendingCall
  ↓
encode Frame
  ↓
TcpConnection::send
```

收到 Response：

```text
parse frame
  ↓
request_id
  ↓
pending_calls.find(id)
  ↓
complete callback
  ↓
erase
```

Stage 2 可以使用 callback 验证，不允许再创建 ReceiverThread。

## 9.5 Protobuf

Protobuf 不再单独占一个大阶段，因为旧项目已经做过。

只提供 adapter：

```text
Message → bytes
bytes → Message
Service/Method metadata → frame header
```

先保证 RPC Runtime 与序列化层解耦。

## 9.6 必做错误测试

```text
[ ] 1 frame 分 100 次写
[ ] 100 frame 一次写
[ ] 随机切片
[ ] magic 错
[ ] version 错
[ ] header_len 越界
[ ] body_len 越界
[ ] request_id 不存在
[ ] duplicate response
[ ] response 在 pending 注册前不允许发生
```

## 9.7 Exit Criteria

```text
[ ] 无 ReceiverThread
[ ] EventLoop 收到 response 后能匹配 PendingCall
[ ] 一条连接 1000 inflight，乱序 response 全部正确
[ ] Parser 不会因恶意长度无限分配
[ ] 非法 frame 不会让 stream 静默失步
```

建议投入：**3~6 天。**

---

# 10. Stage 3：Event-Driven Async RPC —— 真正的新起点

这是 v0.2 最重要的分界线。

## 10.1 要删除的旧模型

NebulaRPC 必须彻底摆脱：

```text
std::thread ReceiverTask
MSG_WAITALL
std::future::wait_for
业务线程阻塞等待 RPC
共享 socket 的 write_mutex 作为核心同步手段
```

## 10.2 目标 API V1

先做 callback 异步 API：

```cpp
RpcCallHandle h = client.CallAsync(
    method,
    request,
    [](RpcResult result) {
        // completion
    }
);
```

调用立即返回，不阻塞调用线程。

## 10.3 完整数据流

```text
Application Thread
    │
    │ CallAsync()
    ▼
RpcClient
    │ allocate request_id
    │ create PendingCall
    ▼
post to Connection EventLoop
    │
    ▼
TcpConnection::send
    │
    ├─ immediate write
    └─ output buffer + EPOLLOUT

Network response
    │
    ▼
epoll_wait
    ↓
TcpConnection::handleRead
    ↓
FrameParser
    ↓
RpcClient::OnFrame
    ↓
PendingCall(request_id)
    ↓
Completion callback
```

## 10.4 这一阶段真正要研究的问题

- `CallAsync()` 可以从任意线程调用吗？
- PendingCall map 属于哪个线程？
- 如果 PendingCall map 只属于 EventLoop，调用线程如何注册？
- callback 在 EventLoop 线程执行，还是回到调用方 executor？
- Connection 在注册 PendingCall 后立刻关闭怎么办？
- `send()` 只是“进入发送队列”还是“已经发到内核”？
- 请求发送失败和请求响应失败如何区分？
- pending 注册与网络发送谁先谁后？为什么？

## 10.5 推荐线程模型 V1

第一版尽量简单：

```text
PendingCall map
FrameParser
TcpConnection
RpcClient network state

全部归 Connection 所在 EventLoop
```

外部线程调用：

```text
CallAsync()
  ↓
生成轻量 command
  ↓
EventLoop::queueInLoop()
  ↓
真正 register pending + send
```

这样可以先避免给 PendingCall map 加锁。

## 10.6 Callback Executor

第一版可以明确规定：

> Completion callback 默认在 Connection EventLoop 线程执行。

但必须记录这个限制。后续可以添加：

```text
InlineExecutor
EventLoopExecutor
ThreadPoolExecutor
Coroutine continuation executor
```

## 10.7 压测目标

```text
1 connection
1000 / 10000 inflight
response 随机乱序
业务线程不发生 wait_for
无 ReceiverThread
```

观察：

```text
threads
context switches
QPS
P99
pending_call_count
output_buffer_bytes
```

并与旧 `promise/future + ReceiverThread` 做一次对照实验。

## 10.8 Exit Criteria

```text
[ ] CallAsync 不阻塞调用线程
[ ] 所有收包由 EventLoop 驱动
[ ] 所有发送支持 partial write
[ ] Request/Response multiplexing 正确
[ ] 连接关闭能失败所有 PendingCall
[ ] 不依赖 future.wait_for
[ ] 不依赖 ReceiverThread
```

完成这里，NebulaRPC 才真正超过旧项目断点。

---

# 11. Stage 4：C++20 Coroutine Runtime

## 11.1 目标

把 Stage 3 的异步 Completion 机制换一种更自然的表达：

```cpp
auto result = co_await client.Call(method, request);
```

核心不是“API 更漂亮”，而是理解：

> callback completion 如何变成 coroutine suspension / resume。

## 11.2 先写最小 Task

只实现真正需要的能力：

```text
Task<T>
Task<void>
promise_type
co_await Task
DetachedTask（如确有需要）
```

必须理解：

```text
coroutine frame
initial_suspend
final_suspend
await_ready
await_suspend
await_resume
coroutine_handle
continuation
```

## 11.3 RpcAwaiter

逻辑：

```text
co_await client.Call()
        ↓
await_ready = false
        ↓
await_suspend(handle)
        ↓
创建 PendingCall
保存 coroutine_handle / continuation
        ↓
发送 Request
        ↓
协程 suspend

Response arrives
        ↓
PendingCall complete
        ↓
写入 RpcResult
        ↓
resume(handle)
        ↓
await_resume()
        ↓
返回 RpcResult
```

## 11.4 不要把 coroutine_handle 当普通指针

必须解决：

```text
协程等待期间谁拥有 coroutine frame？
调用者提前销毁 Task 怎么办？
Connection close 时如何恢复？
Runtime shutdown 时如何收尾？
已经完成的 PendingCall 是否还能 resume 第二次？
```

## 11.5 Resume 线程语义

第一版明确：

> RPC coroutine 默认在完成该 RPC 的 EventLoop 线程恢复。

后续如果支持 executor migration，再单独设计，不要第一版就做复杂 scheduler。

## 11.6 验收

```text
[ ] co_await RPC 正常返回
[ ] 1000 并发 coroutine RPC
[ ] coroutine suspend 时不占线程
[ ] response 到达后准确恢复一次
[ ] connection close 可以恢复并返回错误
[ ] ASan/UBSan 无 coroutine frame 生命周期问题
```

---

# 12. Stage 5：Exactly-Once Completion、Deadline、Timeout 与 Cancellation

这是 NebulaRPC 第一处真正需要严肃状态机的地方。

## 12.1 Completion Sources

一个 RPC 至少可能被以下事件完成：

```text
Response
Timeout / Deadline
User Cancel
Connection Close
Protocol Error
Runtime Shutdown
Send Failure
```

它们可能并发发生。

## 12.2 核心不变量

> **每个 RPC 只能完成一次，每个 coroutine 只能 resume 一次。**

这比“有 timeout 功能”重要得多。

## 12.3 推荐状态机

```text
                 ┌── Response ─────────→ Completed
                 │
Pending ─────────┼── Deadline ─────────→ TimedOut
                 │
                 ├── User Cancel ──────→ Cancelled
                 │
                 ├── ConnectionClose ──→ Unavailable
                 │
                 └── Shutdown ─────────→ Shutdown
```

终态之间不能再次迁移。

## 12.4 V1 可以采用单 EventLoop 串行化

如果 PendingCall、Timer、ConnectionClose 都归同一个 EventLoop，第一版可以利用单线程事件序列保证 exactly-once，而不是一开始就 `atomic<CAS>` 到处飞。

这本身就是一个需要记录的架构决策：

> 用线程归属减少同步，而不是先设计无锁状态机。

如果后续 completion sources 真正跨线程，再演进 CAS 状态机。

## 12.5 Timer

第一版：

```text
min-heap + timerfd
```

或复用最小 TimerQueue。

不要因为 MyMuduo 做过时间轮，就第一天把时间轮搬回来。

只有 profile 证明大量 Timer 成为瓶颈，再比较：

```text
heap
hashed wheel
hierarchical wheel
```

## 12.6 Deadline 优于孤立 Timeout

内部统一传递绝对 Deadline：

```text
client call timeout = 100ms
now = T0
absolute deadline = T0 + 100ms
```

下游如果再次调用其他服务，传剩余预算，而不是重新给 100ms。

## 12.7 Late Response

已经超时的 response 到达：

```text
找不到 PendingCall
  ↓
计数 late_response_total
  ↓
丢弃
```

不能重新创建状态，更不能恢复已经结束的 coroutine。

## 12.8 Race Test

必须主动构造：

```text
response 比 timeout 早 1us
response 比 timeout 晚 1us
response 与 cancel 同时
cancel 与 close 同时
shutdown 与 response 同时
大量 timeout 后 late response 洪峰
```

## 12.9 Exit Criteria

```text
[ ] 所有 completion source 统一进入 CompleteOnce
[ ] 不存在 double callback
[ ] 不存在 double resume
[ ] 不存在 PendingCall 泄漏
[ ] late response 可观测
[ ] 连接关闭会一次性完成所有挂起调用
[ ] shutdown 不留下悬空 coroutine
```

Stage 5 是 NebulaRPC 的核心面试章节之一。

---

# 13. Stage 6：Multi-Reactor 与线程所有权

## 13.1 为什么仍然要做

MyMuduo 已经做过 One Loop Per Thread，但 NebulaRPC 要从 RPC Runtime 角度重新回答：

```text
Connection 属于谁？
PendingCall 属于谁？
Timer 属于谁？
Coroutine 在哪个 loop resume？
Client endpoint 如何分片？
跨线程 Call 如何投递？
```

## 13.2 推荐架构

```text
Acceptor / Client Dispatcher
        │
        ├──────────┬──────────┐
        ▼          ▼          ▼
    Reactor 0  Reactor 1  Reactor 2
      │          │          │
 Connection   Connection   Connection
 PendingCall  PendingCall  PendingCall
 Timer        Timer        Timer
```

每个 Connection 生命周期固定绑定一个 Reactor。

## 13.3 跨线程操作

```text
foreign thread
    ↓
MPSC/locked bounded command queue
    ↓
eventfd wakeup
    ↓
owner EventLoop executes
```

第一版不追求 lock-free。

先测 contention，再决定是否需要无锁。

## 13.4 实验矩阵

```text
1 Reactor
2 Reactor
4 Reactor
8 Reactor
16 Reactor
```

记录：

```text
QPS
P50/P99/P999
CPU
context switch
run queue
cache miss（可选）
```

## 13.5 Exit Criteria

```text
[ ] Connection 不跨 loop 漂移
[ ] PendingCall ownership 明确
[ ] 跨线程 command 有明确边界
[ ] 1/2/4/8 Reactor 扩展曲线有数据
[ ] 能解释扩展停止的原因
```

---

# 14. Stage 7：Backpressure、Bounded Queue 与资源治理

高性能 Runtime 不能只研究“快”，还必须研究“过载时怎么死得可控”。

## 14.1 必须有界的资源

```text
per-connection input buffer
per-connection output buffer
per-connection inflight RPC
per-client total pending RPC
cross-thread command queue
accept backlog
connection count
timer count
metrics cardinality
```

## 14.2 Output Watermark

建议：

```text
Low Watermark
High Watermark
Hard Limit
```

行为示例：

```text
< High    正常
>= High   backpressure / reject new request
>= Hard   close slow consumer or fail fast
```

## 14.3 Inflight Limit

客户端不能无限创建 PendingCall。

达到上限时定义明确策略：

```text
Reject
Queue bounded
Wait asynchronously
Load shed
```

默认优先 fail-fast，不创建无界等待队列。

## 14.4 Slow Consumer Test

服务端/客户端故意不读：

```text
peer recv = 0
持续 send RPC response
```

观察：

```text
RSS
output_buffer_bytes
pending calls
rejected calls
connection close
```

## 14.5 Exit Criteria

```text
[ ] 所有关键资源有 limit
[ ] limit 有 metric
[ ] limit 有测试
[ ] slow consumer 不导致 RSS 无限增长
[ ] overload 行为可预测
```

---

# 15. Stage 8：Client Runtime、Connection Pool、Load Balancing 与 Retry

旧项目有 ConnectionPool，但 NebulaRPC 要把它升级成真正异步语义下的 Client Runtime。

## 15.1 Client Runtime 的职责

```text
Endpoint
Connection lifecycle
Connection pool
Pending budget
Load balancing
Health state
Retry policy
Deadline propagation
Metrics
```

## 15.2 ConnectionPool 不只是 fd 池

一个 endpoint 可维护 N 条 Connection：

```text
Endpoint A
  ├─ Connection 0
  ├─ Connection 1
  └─ Connection 2
```

选择依据可以实验：

```text
Round Robin
Least Pending
Power of Two Choices
```

## 15.3 Retry 必须建立在语义上

不能“失败就 retry”。

需要区分：

```text
请求是否已经写入 socket？
服务端是否可能已经执行？
Method 是否幂等？
Deadline 还有多少？
Retry 是否造成放大流量？
```

默认：非幂等 RPC 不自动 retry。

## 15.4 Service Discovery

v1.0 只需要一个简单接口：

```cpp
std::vector<Endpoint> Resolve(ServiceName);
```

可以先 StaticResolver。

不要为了完整性上 etcd / consul。

## 15.5 Exit Criteria

```text
[ ] endpoint 多连接稳定
[ ] connection close 自动摘除
[ ] 至少两种 LB 有对照实验
[ ] retry 有 deadline/幂等约束
[ ] pool 不会产生无界 pending
```

---

# 16. Stage 9：Observability —— 让 Runtime 内部可见

## 16.1 Metrics

Counter：

```text
rpc_started_total
rpc_completed_total
rpc_timeout_total
rpc_cancelled_total
rpc_connection_error_total
late_response_total
protocol_error_total
rejected_total
bytes_sent_total
bytes_received_total
```

Gauge：

```text
connections
pending_calls
output_buffer_bytes
input_buffer_bytes
command_queue_depth
timers
```

Histogram：

```text
rpc_latency
queue_delay
serialization_time
network_wait_time（如能准确分解）
```

## 16.2 EventLoop Lag

定期投递预期在 T 执行的任务：

```text
lag = actual_run_time - expected_run_time
```

这是定位“EventLoop 被同步操作卡住”的重要指标。

## 16.3 Debug Trace

不做全量重型分布式 Trace，先支持按 RequestId 输出关键阶段：

```text
created
queued
write begin
write complete
response received
completion
resume
```

## 16.4 Cardinality

不能把每个 request_id 都当 Metrics Label。

Metrics 标签必须有限集合。

## 16.5 Exit Criteria

> 给你一次 P99 突增，你应该能先从 metrics 判断是 queue、event-loop、network、timeout 还是 output backlog，而不是先加 printf。

---

# 17. Stage 10：Reliability、Fault Injection 与 Graceful Shutdown

## 17.1 Fault Matrix

系统化测试：

```text
connect refused
connect timeout
peer RST
peer FIN
half close
partial frame then close
invalid magic
oversized frame
slow read
slow write
server handler stall
packet delay / loss（tc netem）
runtime shutdown with pending calls
```

## 17.2 Graceful Shutdown

推荐状态：

```text
Running
  ↓
Draining
  ↓
StopAccepting / StopNewCalls
  ↓
WaitInflightUntilDeadline
  ↓
CancelRemaining
  ↓
CloseConnections
  ↓
Stopped
```

## 17.3 Connection Close

Connection close 不是单纯 `close(fd)`。

必须处理：

```text
remove from poller
stop new writes
fail pending calls
cancel timers
release output/input buffers
notify pool
destroy on owner loop
```

## 17.4 Exit Criteria

```text
[ ] fault suite 自动运行
[ ] 任何异常都不会留下 pending 泄漏
[ ] shutdown 后无悬空 coroutine
[ ] sanitizer 下 fault test 稳定
```

---

# 18. Stage 11：Performance Engineering —— 只优化真实瓶颈

## 18.1 基线纪律

```text
Baseline
  ↓
Profile
  ↓
Hypothesis
  ↓
One major change
  ↓
Benchmark
  ↓
Keep / Revert
```

## 18.2 工具

```text
perf stat
perf record / report
FlameGraph
pidstat
strace
ss
sar
ASan/UBSan/TSan（正确性，不用于正式性能数字）
```

## 18.3 首轮检查

```text
malloc/free
memcpy
syscall count
write/read batch size
wakeups
mutex contention
cross-thread queue
cache misses
context switches
```

## 18.4 Buffer 演进

V1：连续 Buffer。

V2：更少 compaction / 更合理 read/write index。

V3：如果 memcpy 真的是热点，再实验 segmented buffer / buffer chain。

V4：如果 allocation 真的是热点，再实验 Pool / Slab。

不要提前写“零拷贝”。

## 18.5 实验报告模板

每个优化必须记录：

```text
Problem:
Evidence:
Hypothesis:
Change:
Workload:
Before:
After:
Tradeoff:
Decision:
```

至少保留一个“优化失败后回退”的案例。

## 18.6 旧 MyMuduo 作为实验参考，而不是答案

可以重新验证：

```text
readv 是否值得？
时间轮是否优于 heap timer？
异步日志是否影响 P99？
多 Reactor 在当前 RPC workload 上扩展到哪里？
```

但不因为旧项目做过就直接默认它仍然是最佳方案。

---

# 19. Stage 12：与 brpc / gRPC 的统一 Benchmark

## 19.1 目的

不是为了证明“自研比大厂框架快”。

真正的问题：

> 在相同 workload 下，差距在哪里？为什么？

## 19.2 统一 Workload

Payload：

```text
64B
256B
1KB
16KB
1MB
```

Concurrency：

```text
1
8
32
128
512
1024
```

Connections：

```text
1
10
100
```

模式：

```text
Unary Echo
CPU-light handler
固定服务端延迟 handler
```

## 19.3 输出

```text
QPS
P50
P90
P99
P999
CPU
RSS
context switches
network throughput
error/timeout rate
```

必须记录机器、编译参数、框架版本、协议、payload 与测试持续时间。

## 19.4 差距分析

例如：

```text
NebulaRPC P99 比 brpc 高 35%
        ↓
perf + metrics
        ↓
发现 wakeup / allocation / memcpy / scheduler 某项突出
        ↓
提出假设
        ↓
优化并复测
```

这才是 benchmark 的学习价值。

---

# 20. Stage 13：高级研究分支（可选）

这些内容只有主线稳定以后再做。

## 20.1 io_uring

不要重写全部 Runtime。

先做独立 transport backend 实验，与 epoll 对照。

## 20.2 Timing Wheel

Stage 5 的 heap timer 确认成为瓶颈后，再把 MyMuduo 的时间轮经验重新带回来。

比较：

```text
insert cost
cancel cost
expiration cost
memory
precision
```

## 20.3 Per-Core Sharding

进一步减少：

```text
shared maps
cross-core wakeup
global allocator contention
```

## 20.4 NUMA

只有在多 socket / 多 NUMA node 机器上才值得正式研究。

## 20.5 Adaptive Concurrency Control

根据：

```text
latency
queue depth
inflight
error rate
```

动态限制请求，而不是固定阈值。

## 20.6 TLS / Compression

作为性能与资源 tradeoff 实验，不作为主线必做。

---

# 21. Stage 14~15：API 收束、封版与作品化

## 21.1 Stage 14：API / Codegen / Service Model（可选）

只有 Runtime 主线稳定后，才改善使用体验：

```cpp
auto rsp = co_await client.Call<EchoRequest, EchoResponse>(
    "EchoService.Echo",
    req,
    deadline
);
```

可选：

```text
Protobuf adapter
protoc plugin / codegen
Typed Stub
RpcController
Error model
```

不要让 codegen 反客为主。

## 21.2 Stage 15：v1.0 封版

最终仓库必须证明三类能力，同时把既有项目整理成一套可直接用于面试追问的证据组合。NebulaRPC 负责系统深度；DemandStation 负责生产交付；MyMuduo 负责网络底层；OmniBox 负责完整系统广度。

最终仓库必须证明：

### 正确性

```text
unit
integration
fuzz
sanitizer
fault injection
race test
```

### 系统设计

```text
ownership
state machine
backpressure
bounded resources
shutdown
retry semantics
```

### 性能工程

```text
reproducible benchmark
perf evidence
before/after optimization
brpc/gRPC comparison
```

## 21.3 README 不再写“功能列表作文”

README 建议顺序：

```text
1. What problem this project studies
2. Historical context: MyMuduo + game_rpc_project → NebulaRPC
3. Architecture
4. Async RPC flow
5. Coroutine / Completion state machine
6. Correctness guarantees
7. Resource boundaries
8. Benchmark methodology
9. Performance results
10. Failure experiments
11. Design tradeoffs / ADR
12. Build & run
```

## 21.4 最终项目叙事

一句话：

> 我没有第三次重写 muduo，而是从自己过去的同步 RPC + Reactor TcpClient 断点继续，实现了一个事件驱动、协程化、可取消、资源有界、可观测并经过真实性能分析的 C++20 RPC Runtime。

---

# 22. 最终核心架构参考

```text
┌────────────────────────────────────────────────────────────┐
│                        User API                            │
│        RpcClient                  RpcServer                │
└───────────────┬──────────────────────┬─────────────────────┘
                │                      │
                ▼                      ▼
        ┌──────────────┐       ┌──────────────┐
        │ Pending Calls│       │ Dispatcher   │
        │ Deadline     │       │ Services     │
        └───────┬──────┘       └───────┬──────┘
                │                      │
                └──────────┬───────────┘
                           ▼
                 ┌──────────────────┐
                 │ Protocol / Codec │
                 │ Frame / Serializer│
                 └─────────┬────────┘
                           ▼
                 ┌──────────────────┐
                 │   Connection     │
                 │ Buffer/Pressure  │
                 └─────────┬────────┘
                           ▼
        ┌──────────────────────────────────────┐
        │ Coroutine / Timer / Completion       │
        └───────────────────┬──────────────────┘
                            ▼
      ┌────────────────────────────────────────────┐
      │ EventLoop 0 │ EventLoop 1 │ ... │ Loop N │
      │ epoll       │ epoll       │     │ epoll  │
      │ eventfd     │ eventfd     │     │eventfd │
      │ timerfd     │ timerfd     │     │timerfd │
      └────────────────────────────────────────────┘
                            ▼
                         Linux TCP
```

这张图不是第一阶段的代码结构，而是主线完成后的参考目标。

---

# 23. 关键状态机

## 23.1 PendingCall

```text
                    Response
                       │
                       ▼
                   Completed
                       ▲
                       │
Pending ───────────────┼──────────────
  │                    │
  ├─ Deadline ───────► TimedOut
  │
  ├─ User Cancel ───► Cancelled
  │
  └─ Conn Close ────► ConnectionClosed
```

不变量：**终态只能进入一次。**

## 23.2 Connection

第一版可简化为：

```text
Connecting → Open → Closing → Closed
```

后续如果真正需要 Half-Close，再扩展，不要第一天制造复杂状态。

## 23.3 Runtime Shutdown

```text
Running
   ↓
Draining
   ↓
Closing
   ↓
Stopped
```

每次状态变化必须定义允许的新操作、已有操作的处理方式与最大等待时间。

---

# 24. 测试体系

## 24.1 Unit Test

覆盖：

```text
Buffer
Codec
Frame Parser
Timer Queue
PendingCall State
Load Balancer
Metrics primitives
```

## 24.2 Integration Test

真实 localhost socket：

```text
client ↔ server
```

覆盖连接、RPC、timeout、cancel、shutdown。

## 24.3 Fuzz Test

优先目标：

```text
Frame Parser
Protocol decoder
Metadata decoder
```

## 24.4 Sanitizer

建议 CI 形成独立配置：

```text
ASan + UBSan
TSan
```

TSan 可能较慢，不必每次本地默认跑。

## 24.5 Stress Test

场景：

- 数千长连接。
- 高 inflight。
- 大量 timeout。
- 快速 connect/disconnect。
- slow consumer。
- server repeatedly start/stop。

## 24.6 Fault Test

至少保存为脚本而不是手工记忆：

```text
network_delay.sh
server_kill_loop.sh
slow_client.sh
shutdown_race.sh
```

---

# 25. Benchmark 纪律

## 25.1 测试前

- Release build。
- 关闭 Debug Log。
- 固定核心参数。
- Warm-up。
- 记录环境。

## 25.2 测试中

禁止只看平均值。至少输出：

```text
QPS
P50
P90
P99
P999
Max
Errors
CPU
RSS
```

## 25.3 测试后

每次优化结果保存：

```text
docs/benchmark/YYYY-MM-DD-topic.md
```

并记录：

```text
commit before
commit after
command
raw result
interpretation
```

---

# 26. ADR：重要设计不要靠记忆

建议重大设计使用：

```text
docs/adr/ADR-0001-one-loop-per-thread.md
```

模板：

```markdown
# ADR-0001: One Loop Per Thread

## Context
为什么需要决定这个问题？

## Options
A / B / C

## Decision
选择什么？

## Reasons
为什么？

## Tradeoffs
付出了什么代价？

## Revisit When
出现什么证据时重新评估？
```

推荐至少对这些决定写 ADR：

- LT vs ET。
- Connection ownership。
- Timer 实现。
- Coroutine resume thread。
- PendingCall completion model。
- Backpressure 策略。
- Retry 语义。
- Buffer representation。

---

# 27. Why Notes：记录“为什么”，不是流水账

建立：

```text
docs/why/
```

好笔记：

```text
为什么 EPOLLOUT 默认关闭？
为什么 Timeout 必须与 Response 竞争终态？
为什么 Connection 固定归属一个 EventLoop？
为什么 Retry 可能造成重复执行？
为什么 P99 比平均值更重要？
```

不建议只写：

```text
今天完成了 Channel 类。
今天写了 Timer。
```

半年后，前一类内容才是知识资产。

---

# 28. 每阶段统一 Definition of Done

任何阶段只有同时满足以下条件才算完成：

1. **功能正确**：核心功能可运行。
2. **异常正确**：至少覆盖主要错误路径。
3. **有测试**：不是只靠 example 手测。
4. **有边界**：新增 queue/buffer/table 有容量策略。
5. **可观测**：关键状态至少可 debug/统计。
6. **能解释**：可以不看代码解释设计原因。
7. **有记录**：Why/ADR/Benchmark 至少留下对应材料。
8. **不偷跑**：没有为了“显得高级”提前引入后续阶段复杂度。

---

# 29. 推荐 Git 里程碑（v0.2）

Recovery Zone 的 tag 不需要装成“全新发明”，名称直接体现恢复：

```text
v0.1-history-baseline
v0.2-network-runtime-recovered
v0.3-rpc-core-rebuilt
```

从真正的新断点开始：

```text
v0.4-async-rpc
v0.5-coroutine-rpc
v0.6-exactly-once-completion
v0.7-multi-reactor
v0.8-backpressure
v0.9-client-runtime
v0.10-observability
v0.11-reliability
v0.12-performance
v0.13-framework-benchmark
v1.0-release
```

每个 tag 对应一组明确的 Exit Criteria 与 benchmark/fault 记录。

---

# 30. 源码阅读策略（v0.2）

因为你已经写过 MyMuduo，不能再套用“完全不看 muduo、先从零撞墙”的策略。

## Stage 0~2

直接把自己的两个旧仓库当第一手教材：

```text
MyMuduo
  → EventLoop / TcpConnection / TcpClient / Connector / Buffer

game_rpc_project
  → MyChannel / RPCServer / ConnectionPool / RpcHeader
```

目标不是复制，而是回答：

```text
当时为什么这样写？
哪些问题已经解决？
哪些问题当时没有意识到？
如果改成事件驱动 Completion，边界怎么变化？
```

## Stage 3

开始对比成熟 Async RPC 实现，但先完成自己的 callback Async RPC。

可看：

```text
brpc client/channel/socket 基本调用链
Sogou Workflow task model
muduo TcpClient（仅作边界对照）
```

## Stage 4~5

重点阅读：

```text
C++ coroutine 标准机制
成熟 coroutine Task 的生命周期设计
brpc timeout/cancellation/completion 思路
Workflow / Seastar 的 continuation 思路
```

原则仍然是：先拥有自己的状态机，再看别人怎么取舍。

## Stage 6~8

阅读：

```text
brpc connection / socket ownership
bthread / scheduling concepts
load balancer
connection pool
retry / controller semantics
```

## Stage 11 之后

深入：

```text
brpc IOBuf
Seastar shard-per-core
io_uring examples
allocator / kernel networking materials
```

---

# 31. 建议阶段时间分配（v0.2）

重点变化：不再把大量时间浪费在已经做过的 Stage 1~2。

| Stage | 建议投入 | 结束信号 |
|---:|---:|---|
| 0 | 1~2 天 | 历史断点 + build/test/bench 基线完成 |
| 1 | 2~5 天 | 最小 TcpClient/TcpServer Runtime 稳定 |
| 2 | 3~6 天 | Parser + PendingCall + 1000 inflight 正确 |
| **3** | **5~10 天** | **无 ReceiverThread / wait_for 的 Async RPC** |
| **4** | **7~14 天** | **co_await RPC 生命周期讲透** |
| **5** | **7~14 天** | **Exactly-once race suite 稳定** |
| 6 | 5~10 天 | 1/2/4/8 Reactor 扩展曲线 |
| 7 | 5~10 天 | slow consumer 下资源有界 |
| 8 | 5~10 天 | pool/LB/retry 语义稳定 |
| 9 | 3~7 天 | 能用 metrics 定位一次延迟问题 |
| 10 | 5~10 天 | fault + shutdown 自动化 |
| 11 | 持续迭代 | 至少 2 个真实性能优化案例 |
| 12 | 5~10 天 | 公平对比报告完成 |
| 13 | 可选 | 单独研究课题 |
| 14 | 可选 | API/codegen 收束 |
| 15 | 3~5 天 | v1.0 可展示 |

主线预计不是“再做半年业务”，而是把最有知识密度的 Stage 3~5 做深。

---

# 32. 防止再次“越做越迷茫”的机制

每开始一个新功能前，必须填写四句话：

```text
1. 我现在观察到了什么问题？
2. 如果不解决，会造成什么后果？
3. 我准备验证什么假设？
4. 什么结果说明这个功能/优化值得保留？
```

如果四句话写不出来：

> **先不写这个功能。**

例如：

错误动机：

```text
brpc 有对象池，所以我也写对象池。
```

正确动机：

```text
perf 显示 Frame allocation 占 CPU 13.7%，
64B workload 中每 RPC 平均发生 5 次 heap allocation。
假设使用固定块池可以减少 allocator contention。
如果 CPU/QPS/P99 没有明显改善，则回退。
```

---

# 33. NebulaRPC v1.0 毕业标准（v0.2）

注意：`Reactor / TcpClient / Protobuf` 本身不再是最重要的毕业项，它们只是基础。

```text
历史与基础
[ ] 明确记录 MyMuduo + game_rpc_project → NebulaRPC 的演进关系
[ ] 最小 epoll EventLoop/TcpClient/TcpServer Runtime
[ ] Frame Parser 支持半包/粘包/恶意长度
[ ] RequestId / multiplexing / PendingCall
[ ] Protobuf adapter

新的核心能力
[ ] Event-Driven CallAsync，不阻塞业务线程
[ ] 无 ReceiverThread
[ ] 无 std::future::wait_for 作为 RPC 主模型
[ ] C++20 co_await RPC
[ ] Completion sources 统一状态机
[ ] Response/Timeout/Cancel/Close Exactly-Once
[ ] Late Response 语义明确
[ ] Deadline propagation

系统工程
[ ] Multi-Reactor ownership
[ ] 跨线程任务投递
[ ] output/inflight/queue/timer 等资源有界
[ ] Connection Pool + 至少一种 LB
[ ] Retry 有幂等与 deadline 约束
[ ] Metrics + latency histogram + EventLoop lag
[ ] Graceful Shutdown
[ ] Fault Injection

正确性与性能
[ ] Parser fuzz
[ ] ASan / UBSan / TSan 流程
[ ] perf / FlameGraph 分析
[ ] 至少两个带 Before/After 的真实优化案例
[ ] 至少一个失败优化案例
[ ] 与 brpc / gRPC 的公平 Benchmark
[ ] ADR + Why Notes
[ ] 完整 README
```

达到这些后优先封版，而不是继续加业务能力。

---

# 34. 项目完成后的技术叙事（v0.2）

最终不要讲成：

> “我照着 muduo 又写了一个 RPC 框架。”

应该讲真实演进：

```text
我之前有两个独立项目：
一个是自己实现的 Reactor 网络库 MyMuduo，
另一个是基于 promise/future + ReceiverThread 的同步 RPC 项目。

旧 RPC 已经解决 RequestId、Protobuf、半包粘包和响应匹配，
但调用线程仍然 wait_for，客户端收包依赖后台线程，
共享 socket 的发送也有阻塞和生命周期问题。

后来我在 MyMuduo 中实现 TcpClient，让客户端 socket 进入 EventLoop，
但当时没有继续把两套设计真正合并。

NebulaRPC 就从这个历史断点开始：
先把 TcpClient 的事件驱动网络模型和 PendingCall 合并，
删除 ReceiverThread 与 future.wait_for，完成真正 Async RPC；
随后实现 C++20 Task/RpcAwaiter，让 CallAsync 变成 co_await；
再把 Response、Timeout、Cancel、ConnectionClose、Shutdown
统一到 Exactly-Once Completion State Machine。

之后扩展 Multi-Reactor、Backpressure、资源边界、Client Runtime、
Observability 与 Fault Injection，最后用 perf 和统一 workload
与 brpc/gRPC 对比，针对真实瓶颈完成优化。
```

这个故事的价值在于：每一步都是被前一步的真实问题推动的。

---

# 35. 下一步：现在从哪里正式开工（v0.2）

不再从 `Socket.h` 开始漫长重写。

## 第 1 步：2 天内完成历史审计

建立：

```text
docs/history/MYMUDUO_AUDIT.md
docs/history/GAME_RPC_AUDIT.md
docs/history/BREAKPOINT.md
```

重点重新阅读：

```text
MyMuduo:
EventLoop
TcpConnection
Connector
TcpClient
Buffer

Game RPC:
MyChannel
RPCServer
ConnectionPool
RpcHeader proto
```

## 第 2 步：恢复一个最小网络骨架

只让下面这条链工作：

```text
TcpClient
  ↓
EventLoop
  ↓
TcpConnection
  ↓
async read/write
```

不要搬时间轮、SSL、异步日志。

## 第 3 步：直接实现 `RpcClient::CallAsync`

第一版目标：

```cpp
client.CallAsync(method, request, [](RpcResult r) {
    // no wait_for
});
```

内部：

```text
RequestId
PendingCall callback
EventLoop driven receive
FrameParser
TcpConnection::send
```

**第一个真正的验收点：进程里不再需要 RPC ReceiverThread。**

## 第 4 步：再进入 Coroutine

只有 CallAsync 正确后：

```cpp
auto rsp = co_await client.Call(...);
```

这样 coroutine 只是 Completion 的表达层，不会把网络、协议、状态机问题混在一起。

当前最值得写在仓库首页的 TODO 不是“实现 Echo Server”，而是：

```text
MILESTONE-1:
Merge event-driven TcpClient with request-id PendingCall.
Remove ReceiverThread and future.wait_for from the RPC execution path.
```

这就是 NebulaRPC v0.2 的正式开工点。

---

# 36. 冻结规则与修订边界

从 v0.3-frozen 起，本文件的**学习主路线被冻结**。实现细节、性能数据、ADR、真实实验结论可以持续补充，但 Stage 顺序、核心能力边界和毕业标准不再因为临时兴趣改变。只有发现事实性错误、不可执行前置关系或无法验收的节点时，才能通过 LearningCI 正式 Route Review 提交变更。

版本记录：

| 版本 | 日期 | 修改内容 | 原因 |
|---|---|---|---|
| v0.1 | 2026-09-09 | 建立完整主线：Reactor → RPC → Coroutine → Multi-Reactor → Performance | 初始总纲 |
| v0.2 | 2026-09-09 | 根据 MyMuduo 与 game_rpc_project 的真实历史进度重排路线；Stage 0~2 改为恢复区，Stage 3 改为 Event-Driven Async RPC 新起点；前移 Coroutine 与 Exactly-Once Completion | 避免第三次重复手写 Reactor/RPC 基础，把时间集中到真正未完成的系统问题 |
| v0.3-frozen | 2026-09-16 | 冻结学习主路线；新增求职证据标准与 DemandStation / MyMuduo / NebulaRPC / OmniBox 四项目证明分工 | 把“学过什么”改成“面试时能拿什么证据证明能力” |

后续修订建议：

```text
小修：直接更新对应章节，并补 changelog。
架构决策：先写 ADR，再同步本文件。
阶段完成：补真实 benchmark、问题记录与最终结论。
计划改变：删除已经被证伪的路线，不保留“为了完整而存在”的功能。
```

最重要的原则仍然是：

> **NebulaRPC 不是第三次手撕 Muduo，也不是把旧 RPC 换个名字重写。它的价值在于从过去真实的断点继续，把“会写网络库”和“会写同步 RPC”推进到现代异步 RPC Runtime。**
