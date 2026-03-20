# Active Context

## 当前工作焦点
- TASK001 已完成：代码结构重构为三层架构 (core/infra/bot)
- TASK002 已完成：Steam API 限流优化
- **TASK003 已完成**：数据层强化 + SteamAPIClient 重构

## 近期变更
- 2026-02-16: 创建记忆库，建立所有核心文件
- 2026-02-16: 完成 TASK001 — 全部文件迁移、handler 拆分、测试通过
- 2026-02-18: 完成 TASK002 — 限流优化（429/Retry-After/指数退避/分批延迟/16 个新测试）
- 2026-02-18: **完成 TASK003** — 数据层强化
  - 合并 bind_data + parent_data + disable → GroupConfig（groups.json）
  - steam_info 改为纯内存（SteamInfoState）
  - steam_api.py 重构为 SteamAPIClient 类
  - 序列化：msgspec.Struct
  - 启动时自动迁移旧数据 migration.py
  - 删除旧代码 data_source.py + steam_api.py
  - 修复 info.py 引号语法错误
  - 测试全部通过（20/20）

## 下一步
- 无明确待完成任务（等待用户需求）

## 活跃决策与考虑
- 已采用三层分离架构：core / infra / bot
- 数据存储：GroupConfig 合并方案（groups.json + avatars/），steam_info 纯内存
- 序列化：msgspec.Struct
- 已发现 bug（保留未修复）：`broadcast_steam_info` 中 error 类型 msg 未 append → 已在 TASK003 中修复（加入 msg.append）
- Steam API 限额：每日 10 万次/Key，GetPlayerSummaries 端点 ≈25 req/s
- 测试中 SteamAPIClient 的 import 需延迟到 fixture 内，避免 collection 阶段触发 require()
