"""NoneBot 通用工具函数"""

from io import BytesIO

import anyio
import httpx
from nonebot_plugin_alconna import Image
from nonebot_plugin_uninfo import Session


def get_parent_id(session: Session | None) -> str | None:
    if session is None or session.scene.is_private:
        return None

    if session.scene.parent is not None:
        return session.scene.parent.id

    return session.scene.id


def is_admin(session: Session | None) -> bool:
    if session is None or session.member is None:
        return False

    return any(role.level > 1 for role in session.member.roles)


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
