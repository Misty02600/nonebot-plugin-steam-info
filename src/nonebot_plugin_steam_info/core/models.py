from __future__ import annotations

from typing import TypedDict
from typing_extensions import NotRequired

from PIL import Image


class Player(TypedDict):
    steamid: str
    communityvisibilitystate: int
    profilestate: int
    personaname: str
    profileurl: str
    avatar: str
    avatarmedium: str
    avatarfull: str
    avatarhash: str
    lastlogoff: NotRequired[int]
    personastate: int
    realname: str
    primaryclanid: str
    timecreated: int
    personastateflags: int
    gameextrainfo: NotRequired[str]
    gameid: NotRequired[str]


class PlayerSummariesResponse(TypedDict):
    players: list[Player]


class PlayerSummaries(TypedDict):
    response: PlayerSummariesResponse


class ProcessedPlayer(Player):
    game_start_time: NotRequired[int | None]  # Unix timestamp or None


class PlayerSummariesProcessedResponse(TypedDict):
    players: list[ProcessedPlayer]


class Achievements(TypedDict):
    name: str
    image: bytes


class GameData(TypedDict):
    game_name: str
    play_time: str  # e.g. 10.2
    last_played: str  # e.g. 10 月 2 日
    game_image: bytes
    achievements: list[Achievements]
    completed_achievement_number: int
    total_achievement_number: int


class PlayerData(TypedDict):
    steamid: str
    player_name: str
    background: bytes
    avatar: bytes
    description: str
    recent_2_week_play_time: str
    game_data: list[GameData]


class DrawPlayerStatusData(TypedDict):
    game_name: str
    game_time: str  # e.g. 10.2 小时（过去 2 周）
    last_play_time: str  # e.g. 10 月 2 日
    game_header: bytes
    achievements: list[Achievements]
    completed_achievement_number: int
    total_achievement_number: int


class FriendStatusData(TypedDict):
    steamid: str
    avatar: Image.Image
    avatar_frame: Image.Image | None
    name: str
    status: str
    personastate: int
    nickname: NotRequired[str | None]
    game_icon: Image.Image | None
    game_name: NotRequired[str | None]


__all__ = [
    "DrawPlayerStatusData",
    "FriendStatusData",
    "Player",
    "PlayerSummaries",
    "PlayerSummariesProcessedResponse",
    "PlayerSummariesResponse",
    "ProcessedPlayer",
]
