from io import BytesIO

from nonebot import on_command
from nonebot.adapters import Bot, Event, Message
from nonebot.params import CommandArg, Depends
from nonebot_plugin_alconna import Image, Target, Text, UniMessage
from PIL import Image as PILImage

from ..nonebot_utils import get_target, to_image_data
from ..service import group_store

update_parent_info = on_command("steamupdate", aliases={"更新群信息"}, priority=10)


@update_parent_info.handle()
async def update_parent_info_handle(
    bot: Bot,
    event: Event,
    target: Target = Depends(get_target),
    arg: Message = CommandArg(),
):
    msg = await UniMessage.generate(message=arg, event=event, bot=bot)  # type: ignore[attr-defined]
    info = {}
    for seg in msg:
        if isinstance(seg, Image):
            raw = await to_image_data(seg)
            info["avatar"] = PILImage.open(
                BytesIO(raw) if isinstance(raw, bytes) else raw
            )
        elif isinstance(seg, Text) and seg.text != "":
            info["name"] = seg.text

    if "avatar" not in info or "name" not in info:
        await update_parent_info.finish("文本中应包含图片和文字")

    group_store.update_info(target.parent_id or target.id, info["avatar"], info["name"])
    await update_parent_info.finish("更新成功")
