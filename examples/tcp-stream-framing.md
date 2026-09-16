# Example Node — TCP 字节流与消息边界

## Metadata

- Node ID: NET-TCP-STREAM-001
- Domain: Network / TCP
- Priority: CORE
- Estimated Training Time: 1～2 days
- Prerequisites:
  - Socket 基础
- Reference Project:
  - C++ TCP Server / RPC

## Capability Definition

在不查资料的情况下，我能够：

> 解释 TCP 字节流与应用层消息的区别，预测 send/recv 的可能行为，独立实现可靠的 length-prefix framing，并诊断半包、粘包、错误长度和断连相关问题。

## Must Learn

- TCP 是字节流
- send 调用边界不是消息边界
- recv 返回值语义
- 半包
- 多帧合并
- length-prefix framing
- buffer 累积与消费
- 最大 frame 长度保护
- EOF / connection close

## Out of Scope

- TCP 拥塞控制
- TCP 重传算法
- TLS record
- HTTP/2 framing
- QUIC

## Project Anchor

在参考项目中实现：

```text
FrameDecoder
FrameEncoder
```

要求：

- 支持任意拆分
- 支持多帧合并
- 最大消息限制
- 错误长度拒绝
- EOF 清理

## Scoring

### Explanation / 15

能够解释：

- 为什么 TCP 没有消息边界
- 为什么两次 send 不对应两次 recv
- framing 为什么属于应用层

### Prediction / 15

给：

```cpp
send(fd, "AAAA", 4, 0);
send(fd, "BBBB", 4, 0);
```

预测不同 recv buffer 和调度下可能结果。

### Implementation / 25

实现：

```text
4-byte big-endian length
+
payload
```

随机测试：

- 1-byte chunk
- random chunk
- merged frames
- empty payload
- max payload
- invalid length

### Diagnosis / 25

定位：

- decoder 死循环
- buffer 不消费
- length 溢出
- OOM
- partial header
- EOF 后残留 frame

### Transfer / 20

设计新的游戏服务器 framing：

- 最大 8 MB
- 心跳
- 版本号
- 消息类型
- 可选压缩

要求说明字段和取舍。

## PASS

- Total >= 80
- 各维度满足最小门槛
- 100000 条随机消息测试无错误
- 无越界
- 无死循环
- 恶意 length 正确拒绝
