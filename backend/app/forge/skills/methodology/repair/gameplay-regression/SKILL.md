---
id: repair/gameplay-regression
name: Gameplay Regression Repair
kind: methodology
nodes: [repair, code]
---

# 玩法回归修复方法论

- 对照设计稿验收项：输入、碰撞、胜负、关卡推进是否仍成立。
- 修回归时保留已正常的视觉与关卡结构，做最小必要改动。
- 禁止删除敌人/关卡/碰撞来规避失败检测。
- 键盘与触控路径都要回归验证，避免只修一种输入。
