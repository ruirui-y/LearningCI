# 04. 每日严格执行协议

## 1. 每天只推进一个节点

普通学习日只能有一个 ACTIVE 节点。

今天的目标不能写：

- 学 TCP
- 看 Linux
- 研究数据库

必须写成：

> 完成 `NET-TCP-STREAM-001` 的 Training + Verification。

## 2. 每日状态机

```text
PLANNED
  ↓
CHECKED_IN
  ↓
TRAINING
  ↓
VERIFYING
  ↓
PASSED / FAILED
```

不能直接从 PLANNED 跳到 PASSED。

## 3. 今日任务上限

每天最多：

- 1 个唯一目标
- 3 个训练/实验任务
- 1 个正式测试
- 1 个工程产物

目的：避免计划过大导致逃避。

## 4. 当天禁止做的事

普通学习日禁止：

- 重新设计整个学习路线
- 更换技术方向
- 因为发现新资料立刻切换
- 因为感觉某知识“没意义”就跳过
- 同时激活第二个节点
- 偷看 Verification Test 答案
- 把“看完”当作 PASS

## 5. Parking Lot

学习过程中所有新想法统一进入：

```text
Parking Lot
```

例如：

- 想研究 io_uring
- 想比较 QUIC
- 想换 Rust
- 想换教材
- 想重新规划服务器路线

普通学习日不处理。

## 6. 允许中断的条件

只有以下情况允许中断当前节点：

1. 前置能力缺失，无法继续
2. 参考资料存在事实错误
3. 环境无法运行且短期无法修复
4. 当前节点定义明显不可测试

中断必须留下记录。

## 7. FAIL 是合法结果

当天未通过不代表失败。

正确行为是：

```text
FAILED
→ 记录短板
→ 明天继续当前节点
```

错误行为是：

```text
FAILED
→ 觉得不适合
→ 换路线
```

## 8. 每日结束必须留下

- 今日 Capability Score
- PASS / FAIL
- 工程产物
- 错误点
- 明天第一件事
- Parking Lot 新条目
