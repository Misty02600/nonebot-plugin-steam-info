# 数据存储方案

> 调研于 2026-02-18，基于 `infra/data_source.py`、`core/models.py` 和实际数据文件分析。
> **2026-02-18 更新**：最终决策改为 GroupConfig 合并方案，详见 TASK003。

## 当前状态（重构前）

项目使用 **JSON 文件** 进行数据持久化，共4个文件 + 群头像图片：

```
data/nonebot_plugin_steam_info/
├── bind_data.json             # 绑定关系 dict[str, list[dict[str, str]]]
├── steam_info.json            # 玩家状态快照 list[ProcessedPlayer]
├── parent_data.json           # 群名称 dict[str, str]
├── disable_parent_data.json   # 禁用列表 list[str]
└── {parent_id}.png            # 群头像（与 JSON 混在同目录）
```

### 旧文件格式详情

#### 1. `bind_data.json`
```json
{
    "<parent_id>": [
        {"user_id": "<用户ID>", "steam_id": "<Steam64位ID>", "nickname": ""},
        ...
    ]
}
```
- Python 类型：`dict[str, list[dict[str, str]]]`
- 操作后需手动 `save()`

#### 2. `steam_info.json`
```json
[
    {
        "steamid": "76561198xxx",
        "personaname": "Player1",
        "personastate": 1,
        "gameextrainfo": "Counter-Strike 2",
        "gameid": "730",
        "game_start_time": 1708234567,
        ...
    }
]
```
- Python 类型：`list[ProcessedPlayer]`（TypedDict）
- 每次轮询完整替换
- `game_start_time` 是本项目添加的字段

#### 3. `parent_data.json`
```json
{"<parent_id>": "<群名称>"}
```
- Python 类型：`dict[str, str]`
- 群头像以 `{parent_id}.png` 独立文件保存在同目录

#### 4. `disable_parent_data.json`
```json
["<parent_id_1>", "<parent_id_2>"]
```
- Python 类型：`list[str]`
- `add()`/`remove()` 自动保存（与其他类不同）

---

## 最终方案（TASK003）

### 决策：合并 + 纯内存 + msgspec

| 旧文件                     | 新方案                                       |
| -------------------------- | -------------------------------------------- |
| `bind_data.json`           | 合并进 `groups.json`（GroupConfig.binds）    |
| `parent_data.json`         | 合并进 `groups.json`（GroupConfig.name）     |
| `disable_parent_data.json` | 合并进 `groups.json`（GroupConfig.disabled） |
| `{parent_id}.png`          | 移到 `avatars/` 子目录                       |
| `steam_info.json`          | **废弃** → 纯内存 `SteamInfoState`           |

### 新目录结构

```
data/nonebot_plugin_steam_info/
├── groups.json           # 所有群配置（绑定 + 名称 + 禁用）
└── avatars/              # 群头像
    ├── 123456789.png
    └── 987654321.png
```

### 新 JSON 格式
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

### 技术选型

- **`msgspec.Struct`**：替代 TypedDict + json 标准库，类型安全 + 高性能
- **不需要**：nonebot-plugin-orm、SQLAlchemy、boltons
- **启动时自动迁移**：`migration.py` 检测旧文件并合并到新格式

### 已解决的问题

| 旧问题                        | 解决方式                       |
| ----------------------------- | ------------------------------ |
| 手动 save() 不一致            | GroupStore 所有写操作自动保存  |
| steam_info 空数据覆盖         | 纯内存 + 空列表保护            |
| BindData 弱类型               | `BindRecord`（msgspec.Struct） |
| get_all_steam_id O(n²)        | set 去重                       |
| 文件混乱（JSON + PNG 同目录） | 头像移到 avatars/              |
| 3 个文件管同一实体            | 合并为 groups.json             |
