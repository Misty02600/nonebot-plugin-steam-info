from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, cast

from PIL import Image

from ..core.models import Player, ProcessedPlayer


class BindData:
    def __init__(self, save_path: Path) -> None:
        self.content: dict[str, list[dict[str, str]]] = {}
        self._save_path = save_path

        if save_path.exists():
            self.content = json.loads(Path(save_path).read_text("utf-8"))
        else:
            self.save()

    def save(self) -> None:
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4)

    def add(self, parent_id: str, content: dict[str, str]) -> None:
        if parent_id not in self.content:
            self.content[parent_id] = [content]
        else:
            self.content[parent_id].append(content)

    def remove(self, parent_id: str, user_id: str) -> None:
        if parent_id not in self.content:
            return
        for data in self.content[parent_id]:
            if data["user_id"] == user_id:
                self.content[parent_id].remove(data)
                break

    def update(self, parent_id: str, content: list[dict[str, str]]) -> None:
        self.content[parent_id] = content

    def get(self, parent_id: str, user_id: str) -> dict[str, str] | None:
        if parent_id not in self.content:
            return None
        for data in self.content[parent_id]:
            if data["user_id"] == user_id:
                if not data.get("nickname"):
                    data["nickname"] = ""
                return data
        return None

    def get_by_steam_id(self, parent_id: str, steam_id: str) -> dict[str, str] | None:
        if parent_id not in self.content:
            return None
        for data in self.content[parent_id]:
            if data["steam_id"] == steam_id:
                if not data.get("nickname"):
                    data["nickname"] = ""
                return data
        return None

    def get_all(self, parent_id: str) -> list[str]:
        if parent_id not in self.content:
            return []

        result = []

        for data in self.content[parent_id]:
            if data["steam_id"] not in result:
                result.append(data["steam_id"])

        return result

    def get_all_steam_id(self) -> list[str]:
        result = []
        for parent_id in self.content:
            for data in self.content[parent_id]:
                if data["steam_id"] not in result:
                    result.append(data["steam_id"])
        return result


class SteamInfoData:
    def __init__(self, save_path: Path) -> None:
        self.content: list[ProcessedPlayer] = []
        self._save_path = save_path

        if save_path.exists():
            self.content = json.loads(save_path.read_text("utf-8"))
            if isinstance(self.content, dict):
                self.content = []
                self.save()
        else:
            self.save()

    def save(self) -> None:
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4)

    def update(self, player: ProcessedPlayer) -> None:
        self.content.append(player)

    def update_by_players(self, players: list[Player]) -> None:
        # 将 Player 转换为 ProcessedPlayer
        processed_players: list[ProcessedPlayer] = []
        for player in players:
            old_player = self.get_player(player["steamid"])
            pp = cast(ProcessedPlayer, player)

            if old_player is None:
                if player.get("gameextrainfo") is not None:
                    pp["game_start_time"] = int(time.time())
                else:
                    pp["game_start_time"] = None
                processed_players.append(pp)
            else:
                old_pp = cast(ProcessedPlayer, old_player)
                if (
                    player.get("gameextrainfo") is not None
                    and old_player.get("gameextrainfo") is None
                ):
                    # 开始游戏
                    pp["game_start_time"] = int(time.time())
                elif (
                    player.get("gameextrainfo") is None
                    and old_player.get("gameextrainfo") is not None
                ):
                    # 结束游戏
                    pp["game_start_time"] = None
                elif (
                    player.get("gameextrainfo") is not None
                    and old_player.get("gameextrainfo") is not None
                ):
                    if player.get("gameextrainfo") != old_player.get("gameextrainfo"):
                        # 切换游戏
                        pp["game_start_time"] = int(time.time())
                    else:
                        # 继续游戏
                        pp["game_start_time"] = old_pp.get("game_start_time")
                else:
                    pp["game_start_time"] = None
                processed_players.append(pp)

        self.content = processed_players

    def get_player(self, steam_id: str) -> ProcessedPlayer | None:
        for player in self.content:
            if player["steamid"] == steam_id:
                return player
        return None

    def get_players(self, steam_ids: list[str]) -> list[ProcessedPlayer]:
        result = []
        for player in self.content:
            if player["steamid"] in steam_ids:
                result.append(player)
        return result

    def compare(
        self,
        old_players: list[Player] | list[ProcessedPlayer],
        new_players: list[Player] | list[ProcessedPlayer],
    ) -> list[dict[str, Any]]:
        result = []

        for player in new_players:
            for old_player in old_players:
                if player["steamid"] == old_player["steamid"]:
                    if player.get("gameextrainfo") != old_player.get("gameextrainfo"):
                        if (
                            player.get("gameextrainfo") is not None
                            and old_player.get("gameextrainfo") is not None
                        ):
                            result.append(
                                {
                                    "type": "change",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
                        elif old_player.get("gameextrainfo") is not None:
                            result.append(
                                {
                                    "type": "stop",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
                        elif player.get("gameextrainfo") is not None:
                            result.append(
                                {
                                    "type": "start",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
                        else:
                            result.append(
                                {
                                    "type": "error",
                                    "player": player,
                                    "old_player": old_player,
                                }
                            )
        return result


class ParentData:
    def __init__(self, save_path: Path) -> None:
        self.content: dict[str, str] = {}  # parent_id: name
        self._save_path = save_path

        if not save_path.exists():
            save_path.parent.mkdir(parents=True, exist_ok=True)
            self.save()
        else:
            self.content = json.loads(save_path.read_text("utf-8"))

    def save(self) -> None:
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4)

    def update(self, parent_id: str, avatar: Image.Image, name: str) -> None:
        self.content[parent_id] = name
        self.save()
        # 保存图片
        avatar_path = self._save_path.parent / f"{parent_id}.png"
        avatar.save(avatar_path)

    def get(self, parent_id: str) -> tuple[Image.Image, str]:
        if parent_id not in self.content:
            return (
                Image.open(Path(__file__).parent.parent / "res/unknown_avatar.jpg"),
                parent_id,
            )
        avatar_path = self._save_path.parent / f"{parent_id}.png"
        return Image.open(avatar_path), self.content[parent_id]


class DisableParentData:
    """储存禁用 Steam 通知的 parent"""

    def __init__(self, save_path: Path) -> None:
        self.content: list[str] = []
        self._save_path = save_path

        if save_path.exists():
            self.content = json.loads(save_path.read_text("utf-8"))
        else:
            self.save()

    def save(self) -> None:
        with open(self._save_path, "w", encoding="utf-8") as f:
            json.dump(self.content, f, indent=4)

    def add(self, parent_id: str) -> None:
        if parent_id not in self.content:
            self.content.append(parent_id)
            self.save()

    def remove(self, parent_id: str) -> None:
        if parent_id in self.content:
            self.content.remove(parent_id)
            self.save()

    def is_disabled(self, parent_id: str) -> bool:
        return parent_id in self.content
