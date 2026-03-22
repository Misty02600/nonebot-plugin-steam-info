from __future__ import annotations

from pathlib import Path

from nonebot import require
from PIL import Image

require("nonebot_plugin_htmlkit")

import nonebot_plugin_htmlkit as htmlkit

from ..core.models import FriendStatusData
from .draw import WIDTH
from .html_render_common import (
    START_GAMING_HEIGHT,
    START_GAMING_WIDTH,
    build_sections,
    friends_status_height,
    friends_status_htmlkit_template_context,
    load_image_from_bytes,
    start_gaming_htmlkit_template_context,
)

TEMPLATE_DIR = Path(__file__).parent.parent / "res" / "templates"

_htmlkit_ready = False


def _ensure_htmlkit_ready() -> None:
    global _htmlkit_ready
    if _htmlkit_ready:
        return
    htmlkit.init_fontconfig()
    _htmlkit_ready = True


async def _local_only_img_fetcher(url: str) -> bytes | None:
    return await htmlkit.data_scheme_img_fetcher(url)


async def _local_only_css_fetcher(url: str) -> str | None:
    return await htmlkit.data_scheme_css_fetcher(url)


async def render_friends_status_html(
    parent_avatar: Image.Image,
    parent_name: str,
    data: list[FriendStatusData],
) -> Image.Image:
    _ensure_htmlkit_ready()

    sections = build_sections(data)

    image_bytes = await htmlkit.template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="friends_status.html",
        templates=friends_status_htmlkit_template_context(
            parent_avatar, parent_name, sections
        ),
        max_width=WIDTH,
        device_height=friends_status_height(sections),
        img_fetch_fn=_local_only_img_fetcher,
        css_fetch_fn=_local_only_css_fetcher,
        allow_refit=False,
        image_format="png",
    )
    return load_image_from_bytes(image_bytes)


async def render_start_gaming_html(
    avatar: Image.Image,
    friend_name: str,
    game_name: str,
    nickname: str | None,
) -> Image.Image:
    _ensure_htmlkit_ready()

    image_bytes = await htmlkit.template_to_pic(
        template_path=str(TEMPLATE_DIR),
        template_name="start_gaming.html",
        templates=start_gaming_htmlkit_template_context(
            avatar,
            friend_name,
            game_name,
            nickname,
        ),
        max_width=START_GAMING_WIDTH,
        device_height=START_GAMING_HEIGHT,
        img_fetch_fn=_local_only_img_fetcher,
        css_fetch_fn=_local_only_css_fetcher,
        allow_refit=False,
        image_format="png",
    )
    return load_image_from_bytes(image_bytes)
