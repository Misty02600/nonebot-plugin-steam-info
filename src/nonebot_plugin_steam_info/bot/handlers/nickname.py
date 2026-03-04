from nonebot import on_command
from nonebot.adapters import Event, Message
from nonebot.params import CommandArg, Depends
from nonebot_plugin_alconna import Target

from ..nonebot_utils import get_target
from ..service import group_store

set_nickname = on_command("steamnickname", aliases={"steam昵称"}, priority=10)


@set_nickname.handle()
async def set_nickname_handle(
    event: Event, target: Target = Depends(get_target), cmd_arg: Message = CommandArg()
):
    parent_id = target.parent_id or target.id

    nickname = cmd_arg.extract_plain_text().strip()

    if nickname == "":
        await set_nickname.finish("请输入昵称，格式: steamnickname [昵称]")

    bind_record = group_store.get_bind(parent_id, event.get_user_id())

    if bind_record is None:
        await set_nickname.finish(
            "未绑定 Steam ID，请先使用 steambind 绑定 Steam ID 后再设置昵称"
        )

    bind_record.nickname = nickname
    group_store.save()

    await set_nickname.finish(f"已设置你的昵称为 {nickname}，将在 Steam 播报中显示")
