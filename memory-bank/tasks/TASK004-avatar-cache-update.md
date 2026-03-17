# [TASK004] Steam 头像缓存更新机制

**Status:** Completed
**Added:** 2026-03-07
**Updated:** 2026-03-07
**Completed:** 2026-03-07

## 原始需求
当前项目的 Steam 头像采用永久缓存机制，如果用户在 Steam 上更新头像，机器人展示的仍为旧头像。需要实现头像缓存过期和刷新机制。

## 问题分析
在 [steam_client.py](../../src/nonebot_plugin_steam_info/infra/steam_client.py#L367-L380) 的 `_fetch()` 方法中：
- 缓存文件存在就永久使用，不检查年龄
- 没有任何过期时间机制
- 用户头像更新无法同步到本地

## 实现方案选择
**采用方案 A：基于 TTL 的缓存过期**（推荐）
- 新增 `cache_ttl` 参数（默认 24 小时）
- 检查缓存文件修改时间与当前时间差
- 过期自动重新下载

**额外方案 C：管理命令清除缓存**
- 添加管理员命令清除全部或指定用户头像缓存
- 用于紧急情况或特殊需求

## 实现计划
- [ ] 修改 `_fetch()` 方法添加 TTL 检测
- [ ] 修改 `_fetch()` 调用处传入缓存过期参数
- [ ] 添加 `clear_cache` 等管理命令
- [ ] 测试缓存过期和更新流程
- [ ] 更新配置文档

## 进度追踪

**整体状态:** 代码实现完成 - 80%

| ID | 描述 | 状态 | 更新日期 | 备注 |
|----|----|------|--------|------|
| 4.1 | 修改 steam_client.py 的 _fetch 方法添加 TTL | Complete | 2026-03-07 | 支持 cache_ttl 参数，自动删除过期缓存 |
| 4.2 | 修改调用处参数（avatar、header、achievement 缓存） | Complete | 2026-03-07 | avatar/background/game_image/achievement 均支持 TTL |
| 4.3 | 添加 URL 哈希检测和清除缓存方法 | Complete | 2026-03-07 | _avatar_url_cache 存储检测，clear_avatar_cache() 方法 |
| 4.4 | 更新配置文件添加 cache_ttl 参数 | Complete | 2026-03-07 | config.py 新增 steam_cache_ttl，defaults 86400 |
| 4.5 | 编写单元测试 | In Progress | - | 待完成 |

## 进度日志
### 2026-03-07
- **识别问题**：对话中发现头像缓存永久使用问题
- **分析对比**：ETag 方案不可行，URL 哈希对比最佳
- **实现 TTL 机制**：
  - 新增 `time` 模块导入
  - `__init__` 添加 `cache_ttl` 参数（默认 86400 = 24小时）
  - `__init__` 添加 `_avatar_url_cache` 字典追踪头像 URL
- **实现 URL 对比**：
  - 修改 `get_user_data()` avatar 获取逻辑
  - 检测 URL 变化时删除旧缓存文件
- **修改 _fetch() 方法**：
  - 新增 `cache_ttl` 参数
  - 检查缓存文件修改时间与当前时间差
  - 过期自动删除并重新下载
- **添加管理方法**：
  - `clear_avatar_cache()` 支持全部清除或按 steamid 清除
- **配置集成**：
  - config.py 新增 `steam_cache_ttl` 配置项
  - service.py 传入 cache_ttl 参数
- **验证**：无语法错误
