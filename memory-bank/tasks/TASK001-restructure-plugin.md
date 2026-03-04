# TASK001 - 根据 jmdownloader 重构 Steam 代码结构

**Status:** Completed
**Added:** 2026-02-16
**Updated:** 2026-02-16

## Original Request
根据 jmdownloader 的三层架构（core / infra / bot），重构 steam-info 插件的代码结构。当前 steam-info 所有命令处理器、业务逻辑、定时任务全部混在 `__init__.py`（488 行）中，耦合度高，不利于维护和测试。

## Thought Process

### 当前结构（扁平式）
```
src/nonebot_plugin_steam_info/
├── __init__.py       # 入口 + 全部9个命令处理器 + 定时任务 + 播报逻辑 (~488行)
├── config.py         # 配置定义
├── data_source.py    # 数据持久化 (BindData, SteamInfoData, ParentData, DisableParentData)
├── draw.py           # 图片渲染 (~大量函数)
├── models.py         # TypedDict 类型定义
├── steam.py          # Steam API & 爬虫
├── utils.py          # 工具函数 (fetch_avatar, simplize_steam_player_data 等)
└── res/              # 资源文件
```

### 主要问题
1. `__init__.py` 承担了太多职责：命令注册、全部 handler 逻辑、播报业务逻辑、定时任务、服务实例化
2. 模块间缺乏清晰的分层结构

### 约束
- **不迁移数据模型**：保持 TypedDict，不引入 msgspec
- **不改变现有代码决策**：保留原有数据类（BindData, SteamInfoData 等）的 API 和实现
- **纯布局重构**：仅移动文件位置、拆分 handler，不改变任何功能行为

### 目标结构（参照 jmdownloader 三层架构）
```
src/nonebot_plugin_steam_info/
├── __init__.py              # 插件入口，仅注册元数据和导入 handlers
├── config.py                # Pydantic 配置模型（保持不变）
│
├── core/                    # 核心领域层（无 NoneBot 依赖）
│   ├── __init__.py
│   └── models.py            # 数据模型定义（原 models.py 原样迁移，保持 TypedDict）
│
├── infra/                   # 基础设施层
│   ├── __init__.py
│   ├── data_source.py       # 数据持久化（原 data_source.py 原样迁移，保留所有 Data 类）
│   ├── steam_api.py         # Steam Web API 封装（原 steam.py 原样迁移）
│   ├── draw.py              # 图片渲染（原 draw.py 原样迁移）
│   └── utils.py             # 工具函数（原 utils.py 原样迁移）
│
└── bot/                     # Bot 层（NoneBot 相关）
    ├── __init__.py           # 统一导出服务实例
    ├── service.py            # 服务实例化（data_manager, config 等单例）
    ├── nonebot_utils.py      # NoneBot 通用工具（get_target, to_image_data 等）
    │
    └── handlers/             # 命令处理器（每个职责一个文件）
        ├── __init__.py       # 统一注册所有 handler
        ├── help.py           # steamhelp
        ├── bind.py           # steambind / steamunbind
        ├── info.py           # steaminfo（个人主页）
        ├── check.py          # steamcheck（查看好友状态）
        ├── broadcast.py      # steamenable / steamdisable + 播报逻辑
        ├── parent.py         # steamupdate（更新群信息）
        ├── nickname.py       # steamnickname
        └── scheduled.py      # 定时任务（fetch_and_broadcast_steam_info）
```

### 设计决策
1. **纯布局重构**：仅改变文件位置和拆分 handler，不改变任何代码逻辑和 API
2. **保持数据模型不变**：TypedDict 原样保留，不迁移到 msgspec
3. **保持数据类不变**：BindData, SteamInfoData, ParentData, DisableParentData 保留各自独立的类和 API
4. **Handler 拆分**：每个命令（或相关命令组）一个文件，handler 内逻辑原样迁移
5. **工具函数原样迁移**：仅改变目录位置，不重构函数签名和实现
6. **导入路径更新**：所有模块间引用更新为新路径

## Implementation Plan

### 阶段一：基础骨架 + 核心层迁移
- [ ] 1.1 创建 `core/`、`infra/`、`bot/`、`bot/handlers/` 目录及 `__init__.py`
- [ ] 1.2 原样迁移 `models.py` → `core/models.py`（保持 TypedDict 不变）

### 阶段二：基础设施层迁移
- [ ] 2.1 原样迁移 `steam.py` → `infra/steam_api.py`（仅更新内部 import）
- [ ] 2.2 原样迁移 `data_source.py` → `infra/data_source.py`（仅更新内部 import）
- [ ] 2.3 原样迁移 `draw.py` → `infra/draw.py`（仅更新内部 import）
- [ ] 2.4 原样迁移 `utils.py` → `infra/utils.py`（仅更新内部 import）

### 阶段三：Bot 层搭建
- [ ] 3.1 创建 `bot/service.py`，集中管理服务实例化（config, data paths, data 实例）
- [ ] 3.2 创建 `bot/nonebot_utils.py`，迁移 `get_target`、`to_image_data` 等 NoneBot 工具函数
- [ ] 3.3 拆分 `__init__.py` 中的 handler 到各个文件（逻辑原样迁移）：
  - `handlers/help.py` - steamhelp
  - `handlers/bind.py` - steambind / steamunbind
  - `handlers/info.py` - steaminfo
  - `handlers/check.py` - steamcheck
  - `handlers/broadcast.py` - steamenable / steamdisable + broadcast_steam_info
  - `handlers/parent.py` - steamupdate
  - `handlers/nickname.py` - steamnickname
  - `handlers/scheduled.py` - 定时任务（fetch_and_broadcast_steam_info）
- [ ] 3.4 重写 `__init__.py` 为瘦入口（仅注册 PluginMetadata + 导入 handlers）

### 阶段四：验证与收尾
- [ ] 4.1 确保所有命令正常工作
- [ ] 4.2 更新现有测试适配新 import 路径
- [ ] 4.3 更新 Memory Bank 文档

## Progress Tracking

**Overall Status:** Completed - 100%

### Subtasks
| ID | Description | Status | Updated | Notes |
|----|-------------|--------|---------|-------|
| 1.1 | 创建目录骨架 | Complete | 2026-02-16 | core/, infra/, bot/, bot/handlers/ |
| 1.2 | 原样迁移 models.py → core/ | Complete | 2026-02-16 | 保持 TypedDict 不变 |
| 2.1 | 原样迁移 steam.py → infra/ | Complete | 2026-02-16 | 更新 import，res 路径 parent.parent |
| 2.2 | 原样迁移 data_source.py → infra/ | Complete | 2026-02-16 | 保留所有 Data 类 |
| 2.3 | 原样迁移 draw.py → infra/ | Complete | 2026-02-16 | 更新 import，res 路径 parent.parent |
| 2.4 | 原样迁移 utils.py → infra/ | Complete | 2026-02-16 | 更新 import |
| 3.1 | 创建 bot/service.py | Complete | 2026-02-16 | 服务实例化 |
| 3.2 | 创建 bot/nonebot_utils.py | Complete | 2026-02-16 | NoneBot 工具函数 |
| 3.3 | 拆分 handlers | Complete | 2026-02-16 | 8 个文件，逻辑原样迁移 |
| 3.4 | 重写 __init__.py | Complete | 2026-02-16 | 瘦入口 |
| 4.1 | 功能验证 | Complete | 2026-02-16 | 2 passed, 0 failed |
| 4.2 | 更新测试 | Complete | 2026-02-16 | 无需修改，import 路径兼容 |
| 4.3 | 更新 Memory Bank | Complete | 2026-02-16 | |

## Progress Log
### 2026-02-16
- 创建任务文件
- 分析了 jmdownloader 三层架构：core（领域模型）/ infra（基础设施）/ bot（NoneBot 交互）
- 分析了 steam-info 当前扁平结构的问题
- 制定了详细的重构计划和目标目录结构
- 用户明确约束：不迁移数据模型、不改变现有代码决策、纯布局重构
- 移除 msgspec 迁移、DataManager 整合、comparator 抽取等涉及功能变更的子任务
- 简化为 4 个阶段 13 个子任务

### 2026-02-16 (实施)
- 完成目录骨架创建
- 完成所有文件迁移（core/models.py, infra/steam_api.py, infra/data_source.py, infra/draw.py, infra/utils.py）
- 创建 bot/service.py（集中管理 config, data paths, data 实例, font check）
- 创建 bot/nonebot_utils.py（get_target, to_image_data）
- 拆分 __init__.py 中 9 个命令处理器到 8 个 handler 文件
- 重写 __init__.py 为瘦入口（仅 PluginMetadata + require + import handlers）
- 删除旧的 models.py, steam.py, data_source.py, utils.py, draw.py
- 测试验证通过：2 passed, 0 failed (uv run pytest)
