"""数据持久化 Store"""

from __future__ import annotations

from pathlib import Path
from typing import Generic, TypeVar

import msgspec
from PIL import Image

from ..core.data_models import BindRecord, GroupConfig, GroupDataStore

T = TypeVar("T", bound=msgspec.Struct)


class JsonStore(Generic[T]):
    """JSON 持久化基类"""

    def __init__(self, path: Path, cls: type[T]) -> None:
        self._path = path
        self._cls = cls
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.data: T = self._load()

    def _load(self) -> T:
        if self._path.exists():
            return msgspec.json.decode(self._path.read_bytes(), type=self._cls)
        return self._cls()  # type: ignore[call-arg]

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
        return list(
            {r.steam_id for config in self.data.groups.values() for r in config.binds}
        )

    def get_all_parent_ids(self) -> list[str]:
        return list(self.data.groups.keys())

    # endregion

    # region 群信息

    def update_info(self, parent_id: str, avatar: Image.Image, name: str) -> None:
        """设置群名 + 头像（/steamupdate 命令）"""
        config = self._get_or_create(parent_id)
        config.name = name
        self.save()
        avatar.save(self._avatars_dir / f"{parent_id}.png")

    def get_info(self, parent_id: str) -> tuple[Image.Image, str]:
        """获取群头像 + 名称"""
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
