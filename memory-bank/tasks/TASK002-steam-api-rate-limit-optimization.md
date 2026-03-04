# [TASK002] - Steam API 限流优化

**Status:** Completed
**Added:** 2026-02-18
**Updated:** 2026-02-18

## Original Request
基于 Steam Web API 限额调研结果（详见 techContext.md），对 `steam_api.py` 中的 API 请求逻辑进行限流优化，以应对 2025 年 6 月起 `GetPlayerSummaries` 端点的限流收紧。

## 背景

### 当前代码问题（已修复 ✅）
1. ~~**无 429 状态码处理**~~：已实现
2. ~~**无 `Retry-After` 头解析**~~：已实现
3. ~~**分批请求无间隔**~~：已添加可配置延迟
4. ~~**无指数退避**~~：已实现
5. ~~**错误分类粗糙**~~：已细化为 429/403/5xx/网络错误

### Steam API 限额（2025-06-01 之后）
- 每日上限：100,000 次/Key
- `GetPlayerSummaries` 短时限制：≈25 req/s，硬突发锁定
- 429 响应附带 `Retry-After` 头（60-120 秒）
- 持续违规可能升级为 503 临时封禁

## Thought Process

### 设计考量
1. **最小侵入性**：保持原有函数签名兼容，新增参数有默认值
2. **渐进增强**：先实现必须的限流保护
3. **可测试性**：`_request_with_retry` 和 `_parse_retry_after` 可独立测试
4. **配置化**：关键参数通过 `config.py` 可调

### 最终决定
采用**方案 A**，直接在 `get_steam_users_info()` 中增强，辅以 `_request_with_retry()` 辅助函数封装重试逻辑。

## Implementation Summary

### 修改的文件
| 文件                        | 修改内容                                                                                  |
| --------------------------- | ----------------------------------------------------------------------------------------- |
| `config.py`                 | +3 个配置项：`steam_api_max_retries`、`steam_api_batch_delay`、`steam_api_backoff_factor` |
| `infra/steam_api.py`        | 新增 `_request_with_retry()`、`_parse_retry_after()`，重写 `get_steam_users_info()`       |
| `bot/handlers/scheduled.py` | 传入限流配置参数                                                                          |
| `bot/handlers/check.py`     | 传入限流配置参数                                                                          |
| `tests/test_rate_limit.py`  | 新增 16 个单元测试                                                                        |

### 限流策略
| 状态码   | 处理方式                                             |
| -------- | ---------------------------------------------------- |
| 200      | 成功返回                                             |
| 429      | 解析 `Retry-After` 头（默认 60s），同 key 等待后重试 |
| 403      | 认证失败，切换下一个 key                             |
| 5xx      | 指数退避（`backoff_factor ** retry_count`）后重试    |
| 网络错误 | 指数退避后重试                                       |

### 新增配置项
| 配置项                     | 默认值 | 说明                  |
| -------------------------- | ------ | --------------------- |
| `steam_api_max_retries`    | 3      | 单个 key 最大重试次数 |
| `steam_api_batch_delay`    | 1.5    | 分批请求间隔（秒）    |
| `steam_api_backoff_factor` | 2.0    | 指数退避因子          |

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID  | Description                                                 | Status   | Updated    | Notes        |
| --- | ----------------------------------------------------------- | -------- | ---------- | ------------ |
| 2.1 | 重构 `get_steam_users_info()`：提取 `_request_with_retry()` | Complete | 2026-02-18 | ✅            |
| 2.2 | 实现 429 状态码识别和 `Retry-After` 头解析                  | Complete | 2026-02-18 | ✅            |
| 2.3 | 实现指数退避重试（exponential backoff）                     | Complete | 2026-02-18 | ✅            |
| 2.4 | 分批请求间添加延迟                                          | Complete | 2026-02-18 | ✅ 默认 1.5s  |
| 2.5 | 细化错误分类（429/403/5xx/网络错误）                        | Complete | 2026-02-18 | ✅            |
| 2.6 | 在 `config.py` 中添加限流配置项                             | Complete | 2026-02-18 | ✅ 3 个配置项 |
| 2.7 | 编写单元测试                                                | Complete | 2026-02-18 | ✅ 16 个测试  |
| 2.8 | 更新记忆库文档                                              | Complete | 2026-02-18 | ✅            |

## Progress Log
### 2026-02-18
- 创建任务文件
- 完成代码分析和方案设计
- 实现所有子任务：
  - `config.py`：添加 3 个限流配置项
  - `steam_api.py`：新增 `_request_with_retry()`、`_parse_retry_after()`、`STEAM_API_URL` 常量
  - `scheduled.py` 和 `check.py`：传入限流参数
  - `test_rate_limit.py`：16 个单元测试（全部通过）
- 全部 18 个测试通过（2 原有 + 16 新增）
- 标记任务完成
