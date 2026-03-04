# Tech Context

## 技术栈

### 核心框架
- **NoneBot2** (>=2.2.0) - Python 异步聊天机器人框架
- **Python** (>=3.9)

### NoneBot 插件依赖
- **nonebot-plugin-alconna** (>=0.54.2) - 跨平台消息处理（支持多适配器）
- **nonebot-plugin-apscheduler** (>=0.4.0) - 定时任务调度
- **nonebot-plugin-localstore** (>=0.6.0) - 本地数据存储路径管理

### 图片渲染
- **Pillow** (>=10.2.0) - 图片生成与处理
- **numpy** (>=1.24.4) - 颜色计算、渐变生成

### 网络请求
- **httpx** (>=0.27.0, <0.28.0) - 异步 HTTP 客户端
- **beautifulsoup4** (>=4.12.3) - HTML 解析（Steam 个人主页爬取）

### 其他
- **pytz** (>=2024.2) - 时区处理
- **pydantic** - 配置模型（NoneBot2 内置）

## 构建工具
- **PDM** - 包管理器（pdm-backend 构建后端）
- **pyproject.toml** - 项目元数据与依赖定义

## 开发配置

### 必需配置项
| 配置项          | 说明                                |
| --------------- | ----------------------------------- |
| `STEAM_API_KEY` | Steam Web API Key（支持单个或多个） |

### 可选配置项
| 配置项                               | 默认值                   | 说明                    |
| ------------------------------------ | ------------------------ | ----------------------- |
| `PROXY`                              | None                     | HTTP 代理地址           |
| `STEAM_REQUEST_INTERVAL`             | 300                      | 轮询间隔（秒）          |
| `STEAM_BROADCAST_TYPE`               | "part"                   | 播报类型：all/part/none |
| `STEAM_DISABLE_BROADCAST_ON_STARTUP` | False                    | 启动时是否禁用播报      |
| `STEAM_FONT_REGULAR_PATH`            | fonts/MiSans-Regular.ttf | Regular 字体路径        |
| `STEAM_FONT_LIGHT_PATH`              | fonts/MiSans-Light.ttf   | Light 字体路径          |
| `STEAM_FONT_BOLD_PATH`               | fonts/MiSans-Bold.ttf    | Bold 字体路径           |

### 字体依赖
- MiSans 字体族（Regular、Light、Bold）
- 字体文件需放在 Bot 运行目录的 `fonts/` 文件夹下

### 资源文件 (`res/` 目录)
| 文件                            | 用途               |
| ------------------------------- | ------------------ |
| `bg_dots.png`                   | 默认背景图         |
| `busy.png`                      | 忙碌状态图标       |
| `default_achievement_image.png` | 默认成就图标       |
| `default_header_image.jpg`      | 默认游戏头图       |
| `friends_search.png`            | 好友列表搜索栏     |
| `gaming.png`                    | 游戏中通知卡片背景 |
| `parent_status.png`             | 群信息头部背景     |
| `unknown_avatar.jpg`            | 默认头像           |
| `zzz_gaming.png`                | 打盹+游戏中图标    |
| `zzz_online.png`                | 打盹+在线图标      |

## 外部 API
- **Steam Web API** - `GetPlayerSummaries/v0002` 获取玩家摘要
- **Steam 社区主页** - 爬取 `steamcommunity.com/profiles/{id}` 页面

### Steam Web API 限额详情（调研于 2026-02-18）

#### 官方限额
| 指标             | 数值                  |
| ---------------- | --------------------- |
| **每日请求上限** | 100,000 次/天/API Key |
| 折算每小时       | ≈4,166 次/小时        |
| 折算每分钟       | ≈69 次/分钟           |

> Valve 可根据 API Terms of Use 合规情况授予更高的每日配额。

#### 非官方短时限额（社区观测）
Steam 除每日总量限制外，还存在**未公开的短时频率限制**，超出后即返回 `429 Too Many Requests`：
- 建议保守速率：**每 5 分钟不超过 200 次请求**
- 观测到的触发阈值：5 秒内 ≈20 次请求即可触发限流
- 安全建议：≈1 次/11 秒（极保守）

#### ⚠️ 2025 年 6 月起 `GetPlayerSummaries` 端点收紧（重要）
自 **2025-06-01** 起，Steam 对 `ISteamUser/GetPlayerSummaries` 等个人资料端点实施了**显著更严格**的限流：

| 时期            | 容忍速率                       | Retry-After 头              | 备注                           |
| --------------- | ------------------------------ | --------------------------- | ------------------------------ |
| 2025-06-01 之前 | ≈100 req/s，突发 ≈1000 req/min | 几乎不返回                  | 限流主要集中在库存端点         |
| 2025-06-01 之后 | **≈25 req/s**，硬性突发锁定    | **几乎必返回**（60-120 秒） | 个人资料端点与库存端点同等严格 |

**关键变化：**
- 超出 25 req/s 后**立即**触发 429 错误（硬突发锁定）
- 429 响应附带 `Retry-After` 头，建议等待 60-120 秒
- 持续重试不遵守 `Retry-After` 可能升级为临时 **503 封禁**
- 部分开发者报告即使每 120 秒请求一次也遭遇限流（疑似"影子封禁"）

#### 对本项目的影响分析
本项目使用 `GetPlayerSummaries/v0002`，**直接受 2025 年限流收紧影响**：
- ✅ **批量查询已支持**：每次最多 100 个 Steam ID，减少请求次数
- ✅ **多 API Key 轮换**：分散请求压力
- ⚠️ **轮询间隔**：默认 300 秒（5 分钟），在合理范围内
- ⚠️ **需关注**：当绑定用户数量增长时（如 >500），分批请求频率可能触发短时限流
- ❌ **缺失**：目前无 `Retry-After` 头解析和指数退避重试机制
- ❌ **缺失**：无请求速率跟踪和自适应限流

#### 建议改进项
1. 在 `steam_api.py` 中添加 `Retry-After` 响应头解析
2. 实现指数退避重试（exponential backoff）
3. 考虑添加请求速率计数器，控制短时请求频率
4. 大量用户场景下，分批请求间增加延迟（如 1-2 秒间隔）

## 技术约束
- httpx 版本限制在 `<0.28.0`（可能存在兼容性考虑）
- Steam API 每次最多查询 100 个 Steam ID（需分批）
- Steam 个人主页爬取依赖特定 HTML 结构（可能因 Steam 更新而失效）
- 图片渲染使用绝对像素尺寸（WIDTH = 400）
