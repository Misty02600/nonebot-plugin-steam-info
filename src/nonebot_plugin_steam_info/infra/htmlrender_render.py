from __future__ import annotations

from pathlib import Path

from nonebot import require
from PIL import Image

require("nonebot_plugin_htmlrender")

import nonebot_plugin_htmlrender as htmlrender

from ..core.models import FriendStatusData
from .html_render_common import (
    START_GAMING_HEIGHT,
    START_GAMING_WIDTH,
    build_sections,
    friends_status_height,
    friends_status_template_context,
    load_image_from_bytes,
    start_gaming_template_context,
)

TEMPLATE_DIR = Path(__file__).parent.parent / "res" / "templates_htmlrender"


async def render_friends_status_htmlrender(
    parent_avatar: Image.Image,
    parent_name: str,
    data: list[FriendStatusData],
) -> Image.Image:
    sections = build_sections(data)
    image_bytes = await htmlrender.template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="friends_status.html",
        templates=friends_status_template_context(
            parent_avatar,
            parent_name,
            sections,
        ),
        pages={
            "viewport": {"width": 400, "height": friends_status_height(sections)},
            "base_url": TEMPLATE_DIR.resolve().as_uri(),
        },
        device_scale_factor=1,
        type="png",
    )
    return load_image_from_bytes(image_bytes)


async def render_start_gaming_htmlrender(
    avatar: Image.Image,
    friend_name: str,
    game_name: str,
    nickname: str | None,
) -> Image.Image:
    image_bytes = await htmlrender.template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="start_gaming.html",
        templates=start_gaming_template_context(
            avatar,
            friend_name,
            game_name,
            nickname,
        ),
        pages={
            "viewport": {"width": START_GAMING_WIDTH, "height": START_GAMING_HEIGHT},
            "base_url": TEMPLATE_DIR.resolve().as_uri(),
        },
        device_scale_factor=1,
        type="png",
    )
    return load_image_from_bytes(image_bytes)
