"""Steam 玩家状态快照（纯内存，不持久化）"""

from __future__ import annotations

import time
from typing import Any, cast

from ..core.models import Player, ProcessedPlayer


class SteamInfoState:
    """玩家状态快照（纯内存，不持久化）"""

    def __init__(self) -> None:
        self.content: list[ProcessedPlayer] = []

    def update_by_players(self, players: list[Player]) -> None:
        """将 Player 列表更新为 ProcessedPlayer 快照，维护 game_start_time"""
        if not players:
            return  # 空数据保护，不覆盖现有快照
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
