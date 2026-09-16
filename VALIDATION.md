# Validation

v0.2.0 生成时已执行：

```text
python -m compileall -q learningci tools tests
python -m unittest discover -s tests -v
```

结果：

```text
15 tests
OK
```

覆盖：

- 计划 Hash 冻结
- 68 个 Node Bundle 校验
- Bundle 修改后拒绝静默导入
- NRPC-S0-01 详细任务数量
- 五维评分 Gate
- 叶子任务初始化
- required evidence Gate
- 任务独立计时
- 固定 Verification FAIL 后复用同一试卷
- FAIL 不推进主线
- PASS 推进并建立 Review
- OPTIONAL 不阻塞 CORE
- SQLite snapshot backup / restore roundtrip

当前生成环境未安装 PyQt6，因此没有执行真实 GUI 启动 smoke test。PyQt 源码已通过 Python compileall；需要在用户本地 PyQt6 环境做视觉验收。
