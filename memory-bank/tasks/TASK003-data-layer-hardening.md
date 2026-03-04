# [TASK003] - 数据层强化 + SteamAPIClient 重构

**Status:** Pending
**Added:** 2026-02-18
**Updated:** 2026-02-18

## Original Request
评估是否需要迁移到数据库，重构数据层。

**最终结论：**
1. `steam_info` 不需要持久化 → 改为**纯内存**状态管理
2. `bind_data` + `parent_data` + `disable_parent_data` → 合并为 **`GroupConfig`** 单文件
3. `steam_api.py` 散落函数 → 重构为 **`SteamAPIClient` 类**
4. 序列化方案采用 **`msgspec.Struct`**（参考 jmdownloader）
5. 启动时自动执行**旧数据迁移**

## Thought Process

### steam_info 不需要持久化的推导

1. `steam_info.json` 的核心用途：保存"上一轮 API 轮询的玩家状态快照"
2. 默认配置下 bot 启动后立即跑 `update_steam_info()` 种子
3. 种子完成后 JSON 里读的旧数据立即被 API 新数据覆盖
4. 持久化的唯一价值：`game_start_time` 跨重启 → 小代价可接受
5. 去掉持久化后：零磁盘 I/O、没有空数据覆盖 bug

### 三个 JSON 合并为一个的推导

三个旧文件都以 `parent_id`（群号）为主键：
- `bind_data.json` → `{parent_id: [{user_id, steam_id, nickname}]}`
- `parent_data.json` → `{parent_id: name}`
- `disable_parent_data.json` → `[parent_id, ...]`

合并为 `GroupConfig`（name + disabled + binds）后：
- 1 个 Struct 代替 3 个 → 数据模型简洁
- 1 个 Store 代替 3 个 → 代码量减少
- 1 个 JSON 文件代替 3 个 → 文件系统整洁
- 群头像放 `avatars/` 子目录 → 与 JSON 分开

### JSON 序列化采用 msgspec

参考 `nonebot-plugin-jmdownloader` 的 `DataManager` 实现：
- **`msgspec.Struct`**：类型安全 + 极快序列化
- **`msgspec.json.encode/decode`**：替代 `json.dump/load`
- **`omit_defaults=True`**：省略默认值，JSON 更紧凑
- **不需要原子写入**：低频用户操作，文件极小

### SteamAPIClient 类的必要性

当前每次调用要传 5-6 个相同参数（api_keys, proxy, retries...），封装为类后一次初始化到处复用。

## 旧数据文件格式（用于迁移）

### 1. `bind_data.json`

```json
{
    "parent_id_1": [
        {"user_id": "111", "steam_id": "76561199xxx", "nickname": ""},
        {"user_id": "222", "steam_id": "76561198yyy", "nickname": "小B"}
    ],
    "parent_id_2": [
        {"user_id": "111", "steam_id": "76561199xxx", "nickname": "小A"}
    ]
}
```

Python 类型：`dict[str, list[dict[str, str]]]`

### 2. `parent_data.json`

```json
{
    "parent_id_1": "群名称A",
    "parent_id_2": "群名称B"
}
```

Python 类型：`dict[str, str]`（parent_id → name）
头像文件：同目录下 `{parent_id}.png`

### 3. `disable_parent_data.json`

```json
["parent_id_1", "parent_id_3"]
```

Python 类型：`list[str]`

### 4. `steam_info.json`（将被废弃，不迁移）

```json
[
    {
        "steamid": "76561199xxx",
        "personaname": "Player1",
        "profileurl": "...",
        "avatar": "...",
        "personastate": 1,
        "gameextrainfo": "Counter-Strike 2",
        "gameid": "730",
        "game_start_time": 1708234567,
        ...
    }
]
```

Python 类型：`list[ProcessedPlayer]`（TypedDict）

## Implementation Plan

### 阶段一：依赖与数据模型

#### 1. 添加依赖

```toml
# pyproject.toml
dependencies = [
    ...
    "msgspec>=0.18.0",
]
```

#### 2. 定义 msgspec.Struct 数据模型

在 `core/data_models.py`（新建）中定义：

```python
"""领域数据模型"""

from __future__ import annotations

import msgspec


class BindRecord(msgspec.Struct, omit_defaults=True):
    """单条绑定记录"""
    user_id: str
    steam_id: str
    nickname: str = ""


class GroupConfig(msgspec.Struct, omit_defaults=True):
    """单个群/频道的完整配置"""
    name: str = ""
    disabled: bool = False
    binds: list[BindRecord] = msgspec.field(default_factory=list)


class GroupDataStore(msgspec.Struct, omit_defaults=True):
    """所有群配置（JSON 顶层结构）"""
    groups: dict[str, GroupConfig] = msgspec.field(default_factory=dict)
```

新 JSON 格式：
```json
{
    "groups": {
        "group_A": {
            "name": "我的群",
            "binds": [
                {"user_id": "111", "steam_id": "7656119xxx"},
                {"user_id": "222", "steam_id": "7656119yyy", "nickname": "小B"}
            ]
        },
        "group_B": {
            "name": "另一个群",
            "disabled": true,
            "binds": [
                {"user_id": "111", "steam_id": "7656119xxx", "nickname": "小A"}
            ]
        }
    }
}
```

> `disabled` 默认 `false`，`omit_defaults=True` 让未禁用的群省略该字段。
> `nickname` 默认 `""`，未设置昵称的记录也会省略该字段。
> 现有 `core/models.py` 中的 `Player`, `ProcessedPlayer` 等 TypedDict 保留不变。

### 阶段二：JsonStore 基类 + GroupStore

#### 3. 实现 `JsonStore` 基类 + `GroupStore`

在 `infra/stores.py`（新建）中：

```python
"""数据持久化 Store"""

from __future__ import annotations

from pathlib import Path

import msgspec
from PIL import Image

from ..core.data_models import BindRecord, GroupConfig, GroupDataStore


class JsonStore[T: msgspec.Struct]:
    """JSON 持久化基类"""

    def __init__(self, path: Path, cls: type[T]) -> None:
        self._path = path
        self._cls = cls
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.data: T = self._load()

    def _load(self) -> T:
        if self._path.exists():
            return msgspec.json.decode(self._path.read_bytes(), type=self._cls)
        return self._cls()

    def save(self) -> None:
        self._path.write_bytes(msgspec.json.encode(self.data))


class GroupStore(JsonStore[GroupDataStore]):
    """群配置管理 — 合并了绑定、群信息、禁用状态

    文件结构：
    - groups.json        → 群配置（名称 + 禁用 + 绑定列表）
    - avatars/{id}.png   → 群头像
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path, GroupDataStore)
        self._avatars_dir = path.parent / "avatars"
        self._avatars_dir.mkdir(parents=True, exist_ok=True)
        self._default_avatar = Image.open(
            Path(__file__).parent.parent / "res/unknown_avatar.jpg"
        )

    def _get_or_create(self, parent_id: str) -> GroupConfig:
        """获取或创建群配置"""
        if parent_id not in self.data.groups:
            self.data.groups[parent_id] = GroupConfig()
        return self.data.groups[parent_id]

    # region 绑定管理

    def add_bind(self, parent_id: str, record: BindRecord) -> None:
        self._get_or_create(parent_id).binds.append(record)
        self.save()

    def remove_bind(self, parent_id: str, user_id: str) -> None:
        config = self.data.groups.get(parent_id)
        if config:
            config.binds = [r for r in config.binds if r.user_id != user_id]
            self.save()

    def get_bind(self, parent_id: str, user_id: str) -> BindRecord | None:
        config = self.data.groups.get(parent_id)
        if not config:
            return None
        for r in config.binds:
            if r.user_id == user_id:
                return r
        return None

    def get_bind_by_steam_id(self, parent_id: str, steam_id: str) -> BindRecord | None:
        config = self.data.groups.get(parent_id)
        if not config:
            return None
        for r in config.binds:
            if r.steam_id == steam_id:
                return r
        return None

    def get_all_steam_ids(self, parent_id: str) -> list[str]:
        config = self.data.groups.get(parent_id)
        if not config:
            return []
        return list({r.steam_id for r in config.binds})

    def get_all_steam_ids_global(self) -> list[str]:
        return list({
            r.steam_id
            for config in self.data.groups.values()
            for r in config.binds
        })

    def get_all_parent_ids(self) -> list[str]:
        return list(self.data.groups.keys())

    # endregion

    # region 群信息

    def update_info(self, parent_id: str, avatar: Image.Image, name: str) -> None:
        """设置群名+头像（/steamupdate 命令）"""
        config = self._get_or_create(parent_id)
        config.name = name
        self.save()
        avatar.save(self._avatars_dir / f"{parent_id}.png")

    def get_info(self, parent_id: str) -> tuple[Image.Image, str]:
        """获取群头像+名称"""
        config = self.data.groups.get(parent_id)
        if config is None or not config.name:
            return self._default_avatar, parent_id
        avatar_path = self._avatars_dir / f"{parent_id}.png"
        if not avatar_path.exists():
            return self._default_avatar, config.name
        return Image.open(avatar_path), config.name

    # endregion

    # region 禁用管理

    def disable(self, parent_id: str) -> None:
        self._get_or_create(parent_id).disabled = True
        self.save()

    def enable(self, parent_id: str) -> None:
        config = self.data.groups.get(parent_id)
        if config:
            config.disabled = False
            self.save()

    def is_disabled(self, parent_id: str) -> bool:
        config = self.data.groups.get(parent_id)
        return config.disabled if config else False

    # endregion
```

### 阶段三：SteamAPIClient 类

#### 4. 重构 `steam_api.py` → `SteamAPIClient`

```python
"""Steam API 客户端"""

STEAM_ID_OFFSET = 76561197960265728

class SteamAPIClient:
    """Steam Web API 客户端 — 封装配置，一次初始化到处复用"""

    def __init__(
        self,
        api_keys: list[str],
        proxy: str | None = None,
        max_retries: int = 3,
        batch_delay: float = 1.5,
        backoff_factor: float = 2.0,
    ) -> None:
        self._api_keys = api_keys
        self._proxy = proxy
        self._max_retries = max_retries
        self._batch_delay = batch_delay
        self._backoff_factor = backoff_factor

    async def get_users_info(self, steam_ids: list[str]) -> PlayerSummaries:
        """获取多个用户信息（自动分批 + 重试 + key 轮换）"""
        ...

    async def get_user_data(
        self, steam_id: int, cache_path: Path | None = None
    ) -> PlayerData:
        """通过爬取个人主页获取详细用户数据"""
        ...

    async def _request_with_retry(self, steam_ids: list[str]) -> PlayerSummaries | None:
        ...

    async def _fetch(
        self, url: str, default: bytes, cache_file: Path | None = None
    ) -> bytes:
        ...

    @staticmethod
    def get_steam_id(steam_id_or_code: str) -> str | None:
        ...

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        ...
```

### 阶段四：SteamInfoState 纯内存

#### 5. `SteamInfoData` → `SteamInfoState`（纯内存）

```python
class SteamInfoState:
    """玩家状态快照（纯内存，不持久化）"""

    def __init__(self) -> None:
        self.content: list[ProcessedPlayer] = []

    def update_by_players(self, players: list[Player]) -> None:
        if not players:
            return  # 空数据保护
        # ...existing game_start_time logic...

    def get_player(self, steam_id: str) -> ProcessedPlayer | None: ...
    def get_players(self, steam_ids: list[str]) -> list[ProcessedPlayer]: ...
    def compare(self, old, new) -> list[dict[str, Any]]: ...
```

### 阶段五：数据迁移模块

#### 6. 实现 `migration.py`（启动时自动运行）

```python
"""旧数据迁移模块 — 启动时自动执行"""

import json
import shutil
from pathlib import Path

from nonebot.log import logger

from .core.data_models import BindRecord, GroupConfig
from .infra.stores import GroupStore


def migrate_legacy_data(
    data_dir: Path,
    group_store: GroupStore,
) -> None:
    """检测并迁移旧版 JSON 数据

    旧文件格式：
    - bind_data.json         → dict[str, list[dict[str, str]]]
    - parent_data.json       → dict[str, str]  (parent_id → name)
    - disable_parent_data.json → list[str]
    - {parent_id}.png        → 群头像（在数据根目录）

    迁移后旧文件重命名为 .json.migrated
    """
    migrated = False

    # 1. 迁移 bind_data.json
    bind_path = data_dir / "bind_data.json"
    if bind_path.exists():
        logger.info("检测到旧版 bind_data.json，开始迁移...")
        old_bind = json.loads(bind_path.read_text("utf-8"))
        for parent_id, records in old_bind.items():
            config = group_store._get_or_create(parent_id)
            for record in records:
                config.binds.append(BindRecord(
                    user_id=record["user_id"],
                    steam_id=record["steam_id"],
                    nickname=record.get("nickname", ""),
                ))
        bind_path.rename(bind_path.with_suffix(".json.migrated"))
        migrated = True

    # 2. 迁移 parent_data.json
    parent_path = data_dir / "parent_data.json"
    if parent_path.exists():
        logger.info("检测到旧版 parent_data.json，开始迁移...")
        old_parent = json.loads(parent_path.read_text("utf-8"))
        avatars_dir = data_dir / "avatars"
        avatars_dir.mkdir(exist_ok=True)
        for parent_id, name in old_parent.items():
            config = group_store._get_or_create(parent_id)
            config.name = name
            # 迁移头像文件到 avatars/ 子目录
            old_avatar = data_dir / f"{parent_id}.png"
            if old_avatar.exists():
                shutil.move(str(old_avatar), str(avatars_dir / f"{parent_id}.png"))
        parent_path.rename(parent_path.with_suffix(".json.migrated"))
        migrated = True

    # 3. 迁移 disable_parent_data.json
    disable_path = data_dir / "disable_parent_data.json"
    if disable_path.exists():
        logger.info("检测到旧版 disable_parent_data.json，开始迁移...")
        old_disable = json.loads(disable_path.read_text("utf-8"))
        for parent_id in old_disable:
            group_store._get_or_create(parent_id).disabled = True
        disable_path.rename(disable_path.with_suffix(".json.migrated"))
        migrated = True

    # 4. 保存合并后的数据
    if migrated:
        group_store.save()
        logger.info("旧数据迁移完成")

    # 5. steam_info.json 直接忽略（不需要迁移）
    steam_info_path = data_dir / "steam_info.json"
    if steam_info_path.exists():
        steam_info_path.rename(steam_info_path.with_suffix(".json.migrated"))
        logger.info("旧版 steam_info.json 已标记为 migrated（数据由 API 重新获取）")
```

### 阶段六：集成

#### 7. 修改 `service.py`

```python
from ..infra.stores import GroupStore
from ..infra.steam_api import SteamAPIClient
from ..infra.steam_state import SteamInfoState
from ..migration import migrate_legacy_data

# Config
config = nonebot.get_plugin_config(Config)

# Data
data_dir = store.get_data_dir("nonebot_plugin_steam_info")
cache_path = store.get_cache_dir("nonebot_plugin_steam_info")

# Group store（合并了绑定 + 群信息 + 禁用状态）
group_store = GroupStore(data_dir / "groups.json")

# 启动时自动迁移旧数据
migrate_legacy_data(data_dir, group_store)

# 纯内存状态
steam_state = SteamInfoState()

# Steam API Client
client = SteamAPIClient(
    api_keys=config.steam_api_key,
    proxy=config.proxy,
    max_retries=config.steam_api_max_retries,
    batch_delay=config.steam_api_batch_delay,
    backoff_factor=config.steam_api_backoff_factor,
)
```

#### 8. 修改 handlers 适配

主要变化：
- `bind_data.get(pid, uid)` → `group_store.get_bind(pid, uid)`
- `bind_data.add(pid, {...})` → `group_store.add_bind(pid, BindRecord(...))`
- `bind_data.get_all(pid)` → `group_store.get_all_steam_ids(pid)`
- `bind_data.get_all_steam_id()` → `group_store.get_all_steam_ids_global()`
- `bind_data.content.keys()` → `group_store.get_all_parent_ids()`
- `parent_data.update(pid, avatar, name)` → `group_store.update_info(pid, avatar, name)`
- `parent_data.get(pid)` → `group_store.get_info(pid)`
- `disable_parent_data.is_disabled(pid)` → `group_store.is_disabled(pid)`
- `disable_parent_data.add(pid)` → `group_store.disable(pid)`
- `disable_parent_data.remove(pid)` → `group_store.enable(pid)`
- `steam_info_data` → `steam_state`（移除 `.save()` 调用）
- `get_steam_users_info(ids, key, proxy, ...)` → `client.get_users_info(ids)`

### 阶段七：清理

#### 9. 移除旧代码
- 删除 `data_source.py`（所有类已迁移到 stores.py / steam_state.py）
- 新文件: `infra/stores.py`（JsonStore + GroupStore）
- 新文件: `infra/steam_state.py`（SteamInfoState）
- 新文件: `core/data_models.py`（BindRecord + GroupConfig + GroupDataStore）
- 更新 `migration.py`（旧数据迁移）
- 更新 `__init__.py` 导出

#### 10. 更新测试

## 最终架构

```
service.py
├── group_store: GroupStore        → groups.json + avatars/
├── steam_state: SteamInfoState   → 纯内存
└── client: SteamAPIClient        → Steam API

data/nonebot_plugin_steam_info/
├── groups.json                   # 所有群配置（绑定 + 名称 + 禁用）
└── avatars/                      # 群头像
    ├── 123456789.png
    └── 987654321.png
```

## 与其他 Task 的关系

- **TASK002**（限流优化）已完成 → `SteamAPIClient._request_with_retry` 包含该逻辑

## 注意事项

### 新增依赖
- `msgspec>=0.18.0`：高性能序列化

### 不再需要
- ~~`nonebot-plugin-orm`~~ / SQLAlchemy / Alembic
- ~~`boltons`~~
- ~~`steam_info.json`~~
- ~~`bind_data.json`~~（合并进 groups.json）
- ~~`parent_data.json`~~（合并进 groups.json）
- ~~`disable_parent_data.json`~~（合并进 groups.json）

### 向后兼容
- 启动时 `migrate_legacy_data()` 自动检测旧文件并迁移
- 旧文件重命名为 `.json.migrated`（不删除，可手动恢复）
- `steam_info.json` 直接标记 migrated（不需要迁移数据）
- 旧的 `{parent_id}.png` 自动搬到 `avatars/` 目录

## Progress Tracking

**Overall Status:** Not Started - 0%

### Subtasks
| ID   | Description                                  | Status      | Updated    | Notes                         |
| ---- | -------------------------------------------- | ----------- | ---------- | ----------------------------- |
| 3.1  | 添加 `msgspec` 依赖                          | Not Started | 2026-02-18 | 🔴 核心                        |
| 3.2  | 定义数据模型（BindRecord + GroupConfig）     | Not Started | 2026-02-18 | 🔴 核心                        |
| 3.3  | 实现 `JsonStore` 基类 + `GroupStore`         | Not Started | 2026-02-18 | 🔴 核心 — 合并绑定+群信息+禁用 |
| 3.4  | 重构 `steam_api.py` → `SteamAPIClient`       | Not Started | 2026-02-18 | 🔴 核心 — 封装配置             |
| 3.5  | `SteamInfoData` → `SteamInfoState`（纯内存） | Not Started | 2026-02-18 | 🔴 核心 — 去掉 JSON 持久化     |
| 3.6  | 实现 `migration.py` 旧数据迁移               | Not Started | 2026-02-18 | 🔴 核心 — 启动时自动执行       |
| 3.7  | 修改 `service.py` 初始化                     | Not Started | 2026-02-18 | 🔴 核心 — 接入新组件           |
| 3.8  | 修改 handlers 适配新接口                     | Not Started | 2026-02-18 | 🔴 核心 — 全部 handler         |
| 3.9  | 删除旧代码 + 整理文件                        | Not Started | 2026-02-18 | 🟡 推荐                        |
| 3.10 | 更新测试                                     | Not Started | 2026-02-18 | 🟡 推荐                        |

## Progress Log
### 2026-02-18
- 创建任务（初始版本：纯 JSON 强化）
- 评估后改为混合方案（steam_info → SQLite + nonebot-plugin-orm）
- 发现 steam_info 根本不需要持久化 → 改为纯内存
- 确认 JSON 序列化采用 msgspec.Struct（参考 jmdownloader）
- 去掉 boltons 依赖（原子写入对低频小文件没必要）
- 拆分 DataManager 为 JsonStore 基类 + 独立 Store 类
- 合并 ParentInfo + DisableList 为 ParentConfig
- 群头像移到 avatars/ 子目录
- 合并 bind_data + parent_data + disable 为统一 GroupConfig
- 记录旧数据文件格式，设计 migration.py 启动时自动迁移
- 最终架构：GroupStore（1 个文件）+ SteamInfoState（内存）+ SteamAPIClient（API）
