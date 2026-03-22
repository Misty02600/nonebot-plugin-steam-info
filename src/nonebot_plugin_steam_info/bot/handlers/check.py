from nonebot import on_command
from nonebot.adapters import Bot, Message
from nonebot.log import logger
from nonebot.params import CommandArg
from nonebot_plugin_alconna import Image, UniMessage
from nonebot_plugin_uninfo import Uninfo

from ...infra.render import render_friends_status
from ...infra.utils import (
    convert_player_name_to_nickname,
    image_to_bytes,
    simplize_steam_player_data,
)
from ..nonebot_utils import get_parent_id
from ..service import cache_path, client, config, group_store

check = on_command("steamcheck", aliases={"查看steam", "查steam"}, priority=10)


@check.handle()
async def check_handle(bot: Bot, session: Uninfo, arg: Message = CommandArg()):
    if arg.extract_plain_text().strip() != "":
        return None

    parent_id = get_parent_id(session)
    if parent_id is None:
        await check.finish("暂不支持在私聊中使用该命令")

    steam_ids = group_store.get_all_steam_ids(parent_id)
    if steam_ids == []:
        await check.finish("本群还没有绑定 Steam 账号，请先使用 steambind 进行绑定")
        return

    steam_info = await client.get_users_info(steam_ids)
    if steam_info["response"]["players"] == []:
        logger.warning(
            f"steamcheck 获取到空 players，parent_id={parent_id}, steam_ids={steam_ids}"
        )
        await check.finish("连接 Steam API 失败，请稍后重试")
        return

    logger.debug(f"{parent_id} Players info: {steam_info}")

    parent_avatar, parent_name = group_store.get_info(parent_id)

    steam_status_data = [
        convert_player_name_to_nickname(
            (await simplize_steam_player_data(player, config.proxy, cache_path)),
            parent_id,
            group_store,
        )
        for player in steam_info["response"]["players"]
    ]

    image = await render_friends_status(
        parent_avatar,
        parent_name,
        steam_status_data,
        config.steam_render_mode,
    )

    await check.finish(await UniMessage(Image(raw=image_to_bytes(image))).export(bot))
