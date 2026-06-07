# 测试与联调清单

## 1. 后端健康检查

- 启动后端：`powershell -ExecutionPolicy Bypass -File .\scripts\run_backend.ps1`
- 访问：`GET /health`
- 期望：返回 `{"status":"ok","env":"dev"}`

## 2. 水鱼接口

- `POST /players/query`，请求体：`{"username":"xxx","b50":"1"}`
- 期望：返回 `rating/charts` 等字段
- 异常：隐私关闭时返回 400 与可读错误信息

## 3. Token 存储与 records

- `POST /players/token/import` 保存 token
- `GET /players/records` 不传 token 也可读取本地 token

## 4. 知识库

- `GET /knowledge/songs`
- `GET /knowledge/songs?tags=style:tech&min_ds=13.5`
- `GET /knowledge/songs?version=PRiSM`
- `GET /knowledge/tags/distribution`

## 5. 六维分析

- `POST /analysis/b50`
- 期望包含：`radar.dimensions[6]`、`shortfalls`、`advice[3]`
- 期望支持参数：
  - `evaluation_model=legacy|s4`
  - `include_records=true|false`
  - `import_token`（可选）
- `s4` 模式期望新增字段：
  - `w_tier`、`stage`
  - `skill_gaps`
  - `training_strategy`
  - `records_summary`

## 6. 前端联调

- 启动前端：`powershell -ExecutionPolicy Bypass -File .\scripts\run_frontend.ps1`
- 页面输入用户名或QQ点击“开始分析”
- 验证雷达图、维度排行与建议卡片展示

## 7. Bot 联调

- 启动 Bot：`powershell -ExecutionPolicy Bypass -File .\scripts\run_bot.ps1`
- 指令：
  - `舞萌帮助`
  - `舞萌ping`
  - `b50分析 用户名`
  - `b50摘要 用户名`
  - `今日推荐`
  - `b50分析 用户名 mode:s4`
  - `b50摘要 用户名 mode:s4`

## 8. B50 视觉强化回归

- 前端查询成功后应支持：
  - B35/B15 分栏切换
  - 评价显示标准化（如 `sssp` -> `SSS+`）
  - 一键导出 B50 总览图（PNG）

## 9. S4 评价体系回归

- 前端支持选择 `legacy/s4` 模式
- `s4` 模式展示 W 值分层、阶段、策略与短板诊断
- `/analysis/recommend` 在 `s4` 模式可返回 `evaluation_model` 与 `w_tier`
- records 不可用时应有可解释降级，不影响主流程
