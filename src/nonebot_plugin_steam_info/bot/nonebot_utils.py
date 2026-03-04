"""NoneBot 通用工具函数"""

from io import BytesIO

import anyio
import httpx
from nonebot_plugin_alconna import Image, MsgTarget, Target


async def get_target(target: MsgTarget) -> Target | None:
    if target.private:
        # 不支持私聊消息
        return None

    return target


async def to_image_data(image: Image) -> BytesIO | bytes:
    if image.raw is not None:
        return image.raw

    if image.path is not None:
        return await anyio.Path(image.path).read_bytes()

    if image.url is not None:
        async with httpx.AsyncClient() as client:
            response = await client.get(image.url)
            if response.status_code != 200:
                raise ValueError(f"无法获取图片数据: {response.status_code}")
            return response.content

    raise ValueError("无法获取图片数据")
