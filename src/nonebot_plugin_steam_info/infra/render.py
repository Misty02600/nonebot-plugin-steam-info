from __future__ import annotations

from typing import Literal

from nonebot import require
from nonebot.log import logger
from PIL import Image

from ..core.models import FriendStatusData
from .draw import draw_friends_status, draw_start_gaming

RenderMode = Literal["pil", "htmlkit", "htmlrender"]


def preload_render_plugin(mode: RenderMode) -> None:
    if mode == "htmlkit":
        require("nonebot_plugin_htmlkit")
    elif mode == "htmlrender":
        require("nonebot_plugin_htmlrender")


async def render_friends_status(
    parent_avatar: Image.Image,
    parent_name: str,
    data: list[FriendStatusData],
    mode: RenderMode,
) -> Image.Image:
    if mode == "htmlkit":
        try:
            from .html_render import render_friends_status_html

            return await render_friends_status_html(parent_avatar, parent_name, data)
        except Exception as exc:
            logger.warning(f"HTMLKit 渲染好友状态失败，回退到 PIL: {exc}")
    if mode == "htmlrender":
        try:
            from .htmlrender_render import render_friends_status_htmlrender

            return await render_friends_status_htmlrender(
                parent_avatar, parent_name, data
            )
        except Exception as exc:
            logger.warning(f"HTMLRender 渲染好友状态失败，回退到 PIL: {exc}")

    return draw_friends_status(parent_avatar, parent_name, data)


async def render_start_gaming(
    avatar: Image.Image,
    friend_name: str,
    game_name: str,
    nickname: str | None,
    mode: RenderMode,
) -> Image.Image:
    if mode == "htmlkit":
        try:
            from .html_render import render_start_gaming_html

            return await render_start_gaming_html(
                avatar,
                friend_name,
                game_name,
                nickname,
            )
        except Exception as exc:
            logger.warning(f"HTMLKit 渲染开始游戏卡片失败，回退到 PIL: {exc}")
    if mode == "htmlrender":
        try:
            from .htmlrender_render import render_start_gaming_htmlrender

            return await render_start_gaming_htmlrender(
                avatar,
                friend_name,
                game_name,
                nickname,
            )
        except Exception as exc:
            logger.warning(f"HTMLRender 渲染开始游戏卡片失败，回退到 PIL: {exc}")

    return draw_start_gaming(avatar, friend_name, game_name, nickname)
