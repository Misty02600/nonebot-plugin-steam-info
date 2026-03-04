from __future__ import annotations

from io import BytesIO

from nonebot import on_command
from nonebot.adapters import Bot, Event, Message
from nonebot.params import CommandArg, Depends
from nonebot_plugin_alconna import At, Image, Target, UniMessage
from PIL import Image as PILImage

from ...infra.draw import draw_player_status
from ...infra.steam_client import SteamAPIClient
from ...infra.utils import image_to_bytes
from ..nonebot_utils import get_target
from ..service import cache_path, client, group_store

info = on_command("steaminfo", aliases={"steam信息"}, priority=10)


@info.handle()
async def info_handle(
    bot: Bot,
    event: Event,
    target: Target = Depends(get_target),
    arg: Message = CommandArg(),
):
    parent_id = target.parent_id or target.id

    uni_arg = await UniMessage.generate(message=arg, event=event, bot=bot)  # type: ignore[attr-defined]
    at = uni_arg[At]

    if len(at) != 0:
        user_id: str = at[0].target
        bind_record = group_store.get_bind(parent_id, user_id)
        if bind_record is None:
            await info.finish("该用户未绑定 Steam ID")
        steam_id = bind_record.steam_id
        steam_friend_code = str(int(steam_id) - SteamAPIClient.STEAM_ID_OFFSET)
    elif arg.extract_plain_text().strip() != "":
        steam_id_int = int(arg.extract_plain_text().strip())
        if steam_id_int < SteamAPIClient.STEAM_ID_OFFSET:
            steam_friend_code = steam_id_int
            steam_id_int += SteamAPIClient.STEAM_ID_OFFSET
        else:
            steam_friend_code = steam_id_int - SteamAPIClient.STEAM_ID_OFFSET
        steam_id = str(steam_id_int)
    else:
        bind_record = group_store.get_bind(parent_id, event.get_user_id())

        if bind_record is None:
            await info.finish(
                '未绑定 Steam ID, 请使用 "steambind [Steam ID 或 Steam好友代码]" 绑定 Steam ID'
            )

        steam_id = bind_record.steam_id
        steam_friend_code = str(int(steam_id) - SteamAPIClient.STEAM_ID_OFFSET)

    player_data = await client.get_user_data(int(steam_id), cache_path)

    draw_data = [
        {
            "game_header": game["game_image"],
            "game_name": game["game_name"],
            "game_time": f"{game['play_time']} 小时",
            "last_play_time": game["last_played"],
            "achievements": game["achievements"],
            "completed_achievement_number": game.get("completed_achievement_number"),
            "total_achievement_number": game.get("total_achievement_number"),
        }
        for game in player_data["game_data"]
    ]

    image = draw_player_status(
        PILImage.open(BytesIO(player_data["background"])),
        PILImage.open(BytesIO(player_data["avatar"])),
        player_data["player_name"],
        str(steam_friend_code),
        player_data["description"],
        player_data["recent_2_week_play_time"],
        draw_data,  # type: ignore[arg-type]
    )

    await info.finish(
        await UniMessage(
            Image(raw=image_to_bytes(image)),
        ).export(bot)
    )
