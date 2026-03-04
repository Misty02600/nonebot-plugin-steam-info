# Active Context

## 当前工作焦点
- TASK001 已完成：代码结构重构为三层架构 (core/infra/bot)
- TASK002 已完成：Steam API 限流优化
- **TASK003 方案已确定**：数据层强化 + SteamAPIClient 重构（待实施）

## 近期变更
- 2026-02-16: 创建记忆库，建立所有核心文件
- 2026-02-16: 完成 TASK001 — 全部文件迁移、handler 拆分、测试通过
- 2026-02-18: 完成 TASK002 — 限流优化（429/Retry-After/指数退避/分批延迟/16 个新测试）
- 2026-02-18: TASK003 方案讨论完成，最终架构确定

## 下一步
- **TASK003**（Pending）：数据层强化 + SteamAPIClient 重构
  - 合并 bind_data + parent_data + disable_parent_data → `GroupConfig`（单文件 `groups.json`）
  - `steam_info` 改为纯内存（`SteamInfoState`，不持久化）
  - `steam_api.py` 重构为 `SteamAPIClient` 类
  - 序列化方案：`msgspec.Struct`（新增依赖）
  - 启动时自动迁移旧数据（`migration.py`）
  - 群头像移到 `avatars/` 子目录

## 活跃决策与考虑
- 已采用三层分离架构：core / infra / bot
- **数据存储决策更新**（2026-02-18）：
  - ~~混合方案（steam_info → SQLite）~~ → **纯内存 + GroupConfig 合并**
  - ~~nonebot-plugin-orm~~ → 不需要
  - ~~boltons (atomic_save)~~ → 不需要（低频小文件直接 write_bytes）
  - 新增依赖仅 `msgspec`
- 已发现 bug（保留未修复）：`broadcast_steam_info` 中 error 类型 msg 未 append
- Steam API 限额：每日 10 万次/Key，GetPlayerSummaries 端点 ≈25 req/s
