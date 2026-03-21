from __future__ import annotations

import calendar
import datetime
import re
import time
from io import BytesIO
from pathlib import Path
from typing import Protocol, cast

import anyio
import httpx
import pytz
from PIL import Image

from ..core.models import FriendStatusData, Player


class BindEntryLike(Protocol):
    nickname: str | None


class GroupStoreLike(Protocol):
    def get_bind_by_steam_id(
        self, parent_id: str, steam_id: str
    ) -> BindEntryLike | None: ...

STEAM_ID_OFFSET = 76561197960265728
MINIPROFILE_FRAME_NONE_SUFFIX = "none"


async def _fetch_avatar(avatar_url: str, proxy: str | None = None) -> Image.Image:
    async with httpx.AsyncClient(proxy=proxy) as client:
        response = await client.get(avatar_url)
        if response.status_code != 200:
            return Image.open(Path(__file__).parent.parent / "res/unknown_avatar.jpg")
        return Image.open(BytesIO(response.content))


async def fetch_avatar(
    player: Player, avatar_dir: Path | None, proxy: str | None = None
) -> Image.Image:
    if avatar_dir is not None:
        avatar_path = (
            avatar_dir / f"avatar_{player['steamid']}_{player['avatarhash']}.png"
        )

        if avatar_path.exists():
            avatar = Image.open(avatar_path)
        else:
            avatar = await _fetch_avatar(player["avatarfull"], proxy)

            avatar.save(avatar_path)
    else:
        avatar = await _fetch_avatar(player["avatarfull"], proxy)

    return avatar


def _load_image(path: Path, mode: str | None = None) -> Image.Image:
    image = Image.open(path)
    return image.convert(mode) if mode else image.copy()


async def _fetch_image_to_cache(
    url: str,
    cache_file: Path,
    proxy: str | None = None,
) -> Image.Image | None:
    async with httpx.AsyncClient(proxy=proxy, follow_redirects=True) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return None
        await anyio.Path(cache_file).write_bytes(response.content)
    return _load_image(cache_file, "RGBA")


async def fetch_avatar_frame(
    steam_id: str, cache_dir: Path | None, proxy: str | None = None
) -> Image.Image | None:
    if cache_dir is not None:
        cached_frames = sorted(
            [Path(str(path)) async for path in anyio.Path(cache_dir).glob(f"avatar_frame_{steam_id}_*.png")]
        )
        if cached_frames:
            return _load_image(cached_frames[0], "RGBA")

        none_marker = cache_dir / f"avatar_frame_{steam_id}_{MINIPROFILE_FRAME_NONE_SUFFIX}"
        if await anyio.Path(none_marker).exists():
            return None

    account_id = int(steam_id) - STEAM_ID_OFFSET
    if account_id <= 0:
        return None

    async with httpx.AsyncClient(proxy=proxy, follow_redirects=True) as client:
        response = await client.get(
            f"https://steamcommunity.com/miniprofile/{account_id}/json"
        )
        if response.status_code != 200:
            return None
        data = response.json()

    frame_url = data.get("avatar_frame")
    if not frame_url:
        if cache_dir is not None:
            await anyio.Path(none_marker).touch(exist_ok=True)
        return None

    frame_key = frame_url.rsplit("/", 1)[-1].split("?", 1)[0]
    cache_file = (
        cache_dir / f"avatar_frame_{steam_id}_{frame_key}"
        if cache_dir is not None
        else None
    )

    if cache_file is not None and cache_file.exists():
        if await anyio.Path(cache_file).exists():
            return _load_image(cache_file, "RGBA")

    if cache_file is None:
        async with httpx.AsyncClient(proxy=proxy, follow_redirects=True) as client:
            response = await client.get(frame_url)
            if response.status_code != 200:
                return None
            return Image.open(BytesIO(response.content)).convert("RGBA")

    return await _fetch_image_to_cache(frame_url, cache_file, proxy)


async def fetch_game_icon(
    app_id: str, cache_dir: Path | None, proxy: str | None = None
) -> Image.Image | None:
    if cache_dir is not None:
        cache_file = cache_dir / f"game_icon_{app_id}.png"
        if cache_file.exists():
            return _load_image(cache_file, "RGBA")
    else:
        cache_file = None

    async with httpx.AsyncClient(proxy=proxy, follow_redirects=True) as client:
        response = await client.get(f"https://steamcommunity.com/app/{app_id}")
        if response.status_code != 200:
            return None

    match = re.search(
        r'<div class="apphub_AppIcon"><img src="([^"]+)"',
        response.text,
    )
    if match is None:
        return None

    icon_url = match.group(1)
    if cache_file is None:
        async with httpx.AsyncClient(proxy=proxy, follow_redirects=True) as client:
            icon_response = await client.get(icon_url)
            if icon_response.status_code != 200:
                return None
            return Image.open(BytesIO(icon_response.content)).convert("RGBA")

    return await _fetch_image_to_cache(icon_url, cache_file, proxy)


def convert_player_name_to_nickname(
    data: FriendStatusData, parent_id: str, group_store: GroupStoreLike
) -> FriendStatusData:
    bind_entry = group_store.get_bind_by_steam_id(parent_id, data["steamid"])
    nickname = bind_entry.nickname.strip() if bind_entry and bind_entry.nickname else ""
    data["nickname"] = nickname or None
    return data


async def simplize_steam_player_data(
    player: Player, proxy: str | None = None, avatar_dir: Path | None = None
) -> FriendStatusData:
    avatar = await fetch_avatar(player, avatar_dir, proxy)
    avatar_frame = await fetch_avatar_frame(player["steamid"], avatar_dir, proxy)
    game_name = player.get("gameextrainfo")
    game_id = player.get("gameid")
    game_icon = (
        await fetch_game_icon(game_id, avatar_dir, proxy) if game_id is not None else None
    )

    if player["personastate"] == 0:
        if not player.get("lastlogoff"):
            status = "离线"
        else:
            time_logged_off = player.get("lastlogoff", 0)  # Unix timestamp
            time_to_now = calendar.timegm(time.gmtime()) - time_logged_off

            # 将时间转换为自然语言
            if time_to_now < 60:
                status = "上次在线 刚刚"
            elif time_to_now < 3600:
                status = f"上次在线 {time_to_now // 60} 分钟前"
            elif time_to_now < 86400:
                status = f"上次在线 {time_to_now // 3600} 小时前"
            elif time_to_now < 2592000:
                status = f"上次在线 {time_to_now // 86400} 天前"
            elif time_to_now < 31536000:
                status = f"上次在线 {time_to_now // 2592000} 个月前"
            else:
                status = f"上次在线 {time_to_now // 31536000} 年前"
    elif player["personastate"] in [1, 2, 4]:
        status = (
            "在线"
            if player.get("gameextrainfo") is None
            else player.get("gameextrainfo", "在线")
        )
    elif player["personastate"] == 3:
        status = (
            "离开"
            if player.get("gameextrainfo") is None
            else player.get("gameextrainfo", "离开")
        )
    elif player["personastate"] in [5, 6]:
        status = "在线"
    else:
        status = "未知"

    return {
        "steamid": player["steamid"],
        "avatar": avatar,
        "avatar_frame": avatar_frame,
        "name": player["personaname"],
        "status": status,
        "personastate": player["personastate"],
        "game_icon": game_icon,
        "game_name": game_name,
    }


def image_to_bytes(image: Image.Image) -> bytes:
    with BytesIO() as bio:
        image.save(bio, format="PNG")
        return bio.getvalue()


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    return cast(
        tuple[int, int, int],
        tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4)),
    )


def convert_timestamp_to_beijing_time(timestamp: int) -> str:
    beijing_timezone = pytz.timezone("Asia/Shanghai")
    date_utc = datetime.datetime.fromtimestamp(timestamp, pytz.utc)
    date_beijing = date_utc.astimezone(beijing_timezone)
    return date_beijing.strftime("%Y-%m-%d %H:%M:%S")
    # example: 2021-09-06 21:00:00
