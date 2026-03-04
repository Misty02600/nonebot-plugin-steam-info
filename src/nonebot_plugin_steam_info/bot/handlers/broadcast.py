from __future__ import annotations

import time

import nonebot
from nonebot import on_command
from nonebot.log import logger
from nonebot.params import Depends
from nonebot_plugin_alconna import Image, Target, Text, UniMessage
from PIL import Image as PILImage

from ...core.models import ProcessedPlayer
from ...infra.draw import (
    draw_friends_status,
    draw_start_gaming,
    vertically_concatenate_images,
)
from ...infra.utils import (
    convert_player_name_to_nickname,
    fetch_avatar,
    image_to_bytes,
    simplize_steam_player_data,
)
from ..nonebot_utils import get_target
from ..service import (
    cache_path,
    config,
    group_store,
    steam_state,
)

enable = on_command("steamenable", aliases={"启用steam"}, priority=10)
disable = on_command("steamdisable", aliases={"禁用steam"}, priority=10)


@enable.handle()
async def enable_handle(target: Target = Depends(get_target)):
    parent_id = target.parent_id or target.id

    group_store.enable(parent_id)

    await enable.finish("已启用 Steam 播报")


@disable.handle()
async def disable_handle(target: Target = Depends(get_target)):
    parent_id = target.parent_id or target.id

    group_store.disable(parent_id)

    await disable.finish("已禁用 Steam 播报")


async def broadcast_steam_info(
    parent_id: str,
    old_players: list[ProcessedPlayer],
    new_players: list[ProcessedPlayer],
):
    if group_store.is_disabled(parent_id):
        return None

    bot = nonebot.get_bot()

    play_data = steam_state.compare(old_players, new_players)

    msg = []
    for entry in play_data:
        player: ProcessedPlayer = entry["player"]
        old_player: ProcessedPlayer | None = entry.get("old_player")

        if entry["type"] == "start":
            msg.append(
                f"{player['personaname']} 开始玩 {player.get('gameextrainfo', '')} 了"
            )
        elif entry["type"] in ["stop", "change"] and old_player is not None:
            time_start = old_player.get("game_start_time") or 0
            time_stop = time.time()
            hours = int((time_stop - time_start) / 3600)
            minutes = int((time_stop - time_start) % 3600 / 60)
            time_str = (
                f"{hours} 小时 {minutes} 分钟" if hours > 0 else f"{minutes} 分钟"
            )

            if entry["type"] == "change":
                msg.append(
                    f"{player['personaname']} 玩了 {time_str} {old_player.get('gameextrainfo', '')} 后，开始玩 {player.get('gameextrainfo', '')} 了"
                )
            else:
                msg.append(
                    f"{player['personaname']} 玩了 {time_str} {old_player.get('gameextrainfo', '')} 后不玩了"
                )
        elif entry["type"] == "error":
            msg.append(
                f"出现错误！{player['personaname']}\nNew: {player.get('gameextrainfo')}\nOld: {old_player.get('gameextrainfo') if old_player else 'N/A'}"
            )
        else:
            logger.error(f"未知的播报类型: {entry['type']}")

    if msg == []:
        return None

    if config.steam_broadcast_type == "all":
        steam_status_data = [
            convert_player_name_to_nickname(
                (await simplize_steam_player_data(player, config.proxy, cache_path)),
                parent_id,
                group_store,
            )
            for player in new_players
        ]

        parent_avatar, parent_name = group_store.get_info(parent_id)
        image = draw_friends_status(parent_avatar, parent_name, steam_status_data)
        uni_msg = UniMessage([Text("\n".join(msg)), Image(raw=image_to_bytes(image))])
    elif config.steam_broadcast_type == "part":
        images: list[PILImage.Image] = []
        for entry in play_data:
            if entry["type"] == "start":
                bind_info = group_store.get_bind_by_steam_id(
                    parent_id, entry["player"]["steamid"]
                )
                nickname = bind_info.nickname if bind_info else None
                img = draw_start_gaming(
                    (await fetch_avatar(entry["player"], cache_path, config.proxy)),
                    entry["player"]["personaname"],
                    entry["player"].get("gameextrainfo", ""),
                    nickname,
                )
                images.append(img)
        if images == []:
            uni_msg = UniMessage([Text("\n".join(msg))])
        else:
            image = (
                vertically_concatenate_images(images) if len(images) > 1 else images[0]
            )
            uni_msg = UniMessage(
                [Text("\n".join(msg)), Image(raw=image_to_bytes(image))]
            )
    elif config.steam_broadcast_type == "none":
        uni_msg = UniMessage([Text("\n".join(msg))])
    else:
        logger.error(f"未知的播报类型: {config.steam_broadcast_type}")
        return None

    await uni_msg.send(
        Target(parent_id, parent_id, True, False, "", bot.adapter.get_name()), bot
    )
