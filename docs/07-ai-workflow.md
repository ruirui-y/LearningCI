# 07. AI 使用协议

AI 在 LearningCI 中不只是教师。

它依次扮演：

- Architect：生成能力树
- Planner：制定每日唯一计划
- Coach：Training 阶段帮助
- Examiner：Verification 阶段闭嘴
- Reviewer：根据证据评分
- Auditor：阻止绕开冻结路线

## 1. AI 不能做的事

普通学习日 AI 不得：

- 主动推荐新的学习路线
- 因为存在更高级技术而改方向
- 在 Verification Test 中提前泄露答案
- 用模糊语言打分
- 把“看完”作为 PASS
- 给出大量额外建议导致分心

## 2. AI 生成能力树

要求 AI：

1. 先抽象领域
2. 再拆叶子节点
3. 叶子节点必须 1～3 天可训练和测试
4. 明确前置依赖
5. 标记 CORE/IMPORTANT/OPTIONAL
6. 不按书籍目录生成

## 3. AI 每日计划

每天输入：

- 当前节点
- 当前分数
- 参考项目
- 可用时间
- 昨日记录

只允许输出：

- 今日唯一目标
- 闭卷预测测试
- 最多 3 个学习任务
- 工程产物
- Verification Test
- PASS / FAIL 标准
- Parking Lot
- 明日继续点

## 4. AI 考试规则

Verification 阶段：

- 禁止提示
- 禁止逐步引导
- 禁止提前告诉正确答案
- 可以澄清题意
- 考试完成后才允许讲解

## 5. AI 评分规则

每一个分数必须关联：

- 用户回答
- 测试结果
- 代码
- benchmark
- 日志
- pcap
- Git commit
- 复现步骤

没有证据就不能给高分。
