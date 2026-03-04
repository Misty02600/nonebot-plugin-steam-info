from nonebot import on_command

from ..service import config  # noqa: F401 - ensure service is initialized

help = on_command("steamhelp", aliases={"steam帮助"}, priority=10)


@help.handle()
async def help_handle():
    from nonebot_plugin_steam_info import __plugin_meta__

    await help.finish(__plugin_meta__.usage)
