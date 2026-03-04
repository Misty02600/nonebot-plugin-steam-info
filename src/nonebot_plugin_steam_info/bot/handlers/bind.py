from nonebot import on_command
from nonebot.adapters import Event, Message
from nonebot.params import CommandArg, Depends
from nonebot_plugin_alconna import Target

from ...core.data_models import BindRecord
from ..nonebot_utils import get_target
from ..service import client, group_store

bind = on_command("steambind", aliases={"绑定steam"}, priority=10)
unbind = on_command("steamunbind", aliases={"解绑steam"}, priority=10)


@bind.handle()
async def bind_handle(
    event: Event, target: Target = Depends(get_target), cmd_arg: Message = CommandArg()
):
    parent_id = target.parent_id or target.id

    arg = cmd_arg.extract_plain_text()

    if not arg.isdigit():
        await bind.finish(
            "请输入正确的 Steam ID 或 Steam好友代码，格式: steambind [Steam ID 或 Steam好友代码]"
        )

    steam_id = client.get_steam_id(arg)

    if steam_id is None:
        await bind.finish("无法解析 Steam ID，请检查输入")
        return

    existing = group_store.get_bind(parent_id, event.get_user_id())
    if existing is not None:
        existing.steam_id = steam_id
        group_store.save()
        await bind.finish(f"已更新你的 Steam ID 为 {steam_id}")
    else:
        group_store.add_bind(
            parent_id,
            BindRecord(user_id=event.get_user_id(), steam_id=steam_id),
        )
        await bind.finish(f"已绑定你的 Steam ID 为 {steam_id}")


@unbind.handle()
async def unbind_handle(event: Event, target: Target = Depends(get_target)):
    parent_id = target.parent_id or target.id
    user_id = event.get_user_id()

    if group_store.get_bind(parent_id, user_id) is not None:
        group_store.remove_bind(parent_id, user_id)
        await unbind.finish("已解绑 Steam ID")
    else:
        await unbind.finish("未绑定 Steam ID")
