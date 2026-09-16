# 06. Reference Project 驱动学习

## 1. 为什么必须有参考项目

纯知识节点会碎片化。

Reference Project 负责把：

- 网络
- Linux IO
- 并发
- RPC
- 存储
- 消息
- 分布式
- 性能

重新汇总到一个可运行系统。

## 2. 参考项目不是“照着抄”

参考项目包含两层含义：

### Reference Implementation

已有成熟项目，用于：

- 架构参考
- 功能参考
- Benchmark 基线

### Personal Implementation

自己实现的项目。

目标不是完全复制，而是达到明确能力和性能标准。

## 3. 推荐项目评分

```text
Correctness      25
Performance      20
Reliability      15
Architecture     15
Debuggability    10
Testability      10
Documentation     5
──────────────────
Total           100
```

项目达到 80 分才视为阶段完成。

## 4. “达到参考项目 80%”必须可测

不能写：

> 性能大概达到 80%。

必须固定环境：

- CPU
- RAM
- Linux Kernel
- Compiler
- Build Type
- Network
- Benchmark Tool
- Message Size
- Connection Count

记录：

- QPS
- P50
- P95
- P99
- CPU
- RSS
- Context Switch
- Throughput

例如：

```text
Reference QPS: 500k
Mine QPS:      420k

Throughput ratio = 84%
```

## 5. 项目不能只看性能

高 QPS 不能掩盖：

- 数据错误
- 崩溃
- 内存泄漏
- 不可诊断
- 无测试
- 重试造成重复写
- 异常无法恢复

因此项目必须是多维验收。

## 6. 故障注入

参考项目必须逐步加入：

- 客户端异常断开
- 服务端 crash
- 网络延迟
- 丢包
- 重复请求
- 请求乱序
- 磁盘写慢
- 依赖超时
- follower 宕机
- 消息重复

学习目标从：

> 正常情况下能跑

升级为：

> 出问题以后能解释、定位和恢复。

## 7. 项目阶段

建议：

```text
Lv1 TCP Echo Server
Lv2 epoll + Reactor
Lv3 Thread Pool + Framing + RPC
Lv4 Timeout + Retry + Idempotency
Lv5 KV + WAL + Snapshot
Lv6 Replication + Raft
Lv7 Metrics + Tracing + Benchmark + Fault Injection
```

最终形成一个 Mini Distributed Backend Platform。
