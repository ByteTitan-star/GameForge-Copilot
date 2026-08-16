---
id: repair/runtime-error
name: Runtime Error Repair
kind: methodology
nodes: [repair, code]
---

# 运行时错误修复方法论

- 先定位 `pageerror` / 控制台栈，区分初始化失败与交互后崩溃。
- 优先修空引用、未定义函数、错误的 DOM id、状态机名不一致。
- 不通过吞掉全部异常或删除功能来“消音”。
- 修复后仍须保证主菜单—游玩—暂停—失败/通关—重开闭环可走通。
