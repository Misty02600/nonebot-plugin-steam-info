import asyncio

import nonebot
from nonebot.adapters import Bot
from nonebot.log import logger
from nonebot_plugin_apscheduler import scheduler
from nonebot_plugin_uninfo import SceneType, get_interface

from ...core.models import ProcessedPlayer
from ..service import client, config, group_store, steam_state
from .broadcast import broadcast_steam_info


async def prune_departed_groups(bot: Bot | None = None):
    if bot is None:
        try:
            bot = nonebot.get_bot()
        except ValueError:
            return

    interface = get_interface(bot)
    if interface is None:
        logger.debug(
            f"适配器 {bot.adapter.get_name()} 不支持 uninfo 查询，跳过 Steam 群同步"
        )
        return

    try:
        active_parent_ids = {
            scene.id for scene in await interface.get_scenes(SceneType.GROUP)
        } | {scene.id for scene in await interface.get_scenes(SceneType.GUILD)}
    except Exception as exc:
        logger.debug(f"通过 uninfo 获取场景列表失败，跳过 Steam 群同步: {exc}")
        return

    disabled_parent_ids, restored_parent_ids = group_store.sync_current_parents(
        active_parent_ids
    )

    for parent_id in disabled_parent_ids:
        logger.warning(
            f"群 {parent_id} 已不在当前 Bot 群列表中，已自动禁用 Steam 播报"
        )

    for parent_id in restored_parent_ids:
        logger.info(
            f"群 {parent_id} 已重新出现在当前 Bot 群列表中，已恢复 Steam 播报同步状态"
        )


async def update_steam_info():
    steam_ids = group_store.get_all_enabled_steam_ids_global()

    steam_info = await client.get_users_info(steam_ids)

    old_players_dict: dict[str, list[ProcessedPlayer]] = {}

    for parent_id in group_store.get_enabled_parent_ids():
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
    parent_ids = group_store.get_enabled_parent_ids()

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


nonebot.get_driver().on_bot_connect(prune_departed_groups)

if not config.steam_disable_broadcast_on_startup:
    nonebot.get_driver().on_bot_connect(update_steam_info)
else:
    logger.info("已禁用启动时的 Steam 播报")
