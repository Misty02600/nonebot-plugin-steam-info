import asyncio

import nonebot
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler

from ...core.models import ProcessedPlayer
from ..service import client, config, group_store, steam_state
from .broadcast import broadcast_steam_info


async def update_steam_info():
    steam_ids = group_store.get_all_steam_ids_global()

    steam_info = await client.get_users_info(steam_ids)

    old_players_dict: dict[str, list[ProcessedPlayer]] = {}

    for parent_id in group_store.get_all_parent_ids():
        pid_steam_ids = group_store.get_all_steam_ids(parent_id)
        old_players_dict[parent_id] = steam_state.get_players(pid_steam_ids)

    if steam_info["response"]["players"] != []:
        steam_state.update_by_players(steam_info["response"]["players"])

    return old_players_dict


@scheduler.scheduled_job(
    "interval", minutes=config.steam_request_interval / 60, id="update_steam_info"
)
async def fetch_and_broadcast_steam_info():
    old_players_dict = await update_steam_info()
    parent_ids = group_store.get_all_parent_ids()

    for index, parent_id in enumerate(parent_ids):
        old_players = old_players_dict[parent_id]
        new_players = steam_state.get_players(group_store.get_all_steam_ids(parent_id))
        try:
            sent = await broadcast_steam_info(parent_id, old_players, new_players)
        except Exception as exc:
            logger.exception(f"群 {parent_id} Steam 播报失败: {exc}")
            continue

        if (
            sent
            and config.steam_broadcast_send_delay > 0
            and index < len(parent_ids) - 1
        ):
            await asyncio.sleep(config.steam_broadcast_send_delay)


if not config.steam_disable_broadcast_on_startup:
    nonebot.get_driver().on_bot_connect(update_steam_info)
else:
    logger.info("已禁用启动时的 Steam 播报")
