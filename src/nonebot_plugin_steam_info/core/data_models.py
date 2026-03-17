"""领域数据模型（msgspec.Struct）"""

from __future__ import annotations

import msgspec


class BindRecord(msgspec.Struct, omit_defaults=True):
    """单条绑定记录"""

    user_id: str
    steam_id: str
    nickname: str | None = None


class GroupConfig(msgspec.Struct, omit_defaults=True):
    """单个群/频道的完整配置"""

    name: str = ""
    disabled: bool = False
    binds: list[BindRecord] = msgspec.field(default_factory=list)


class GroupDataStore(msgspec.Struct, omit_defaults=True):
    """所有群配置（JSON 顶层结构）"""

    groups: dict[str, GroupConfig] = msgspec.field(default_factory=dict)
