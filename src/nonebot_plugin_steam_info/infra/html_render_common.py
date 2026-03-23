from __future__ import annotations

import base64
import html
from functools import cache
from io import BytesIO
from math import ceil, floor
from mimetypes import guess_type
from pathlib import Path
from typing import TypedDict

from PIL import Image, ImageDraw, ImageFont

from ..core.models import FriendStatusData
from . import draw as draw_module
from .draw import (
    AVATAR_FRAME_PADDING,
    AVATAR_SLOT_SIZE,
    GAME_ICON_SIZE,
    MEMBER_AVATAR_SIZE,
    PARENT_AVATAR_SIZE,
    WIDTH,
    _format_friend_display_name,
    _get_friend_status_fill,
    busy_path,
    friends_search_path,
    gaming_path,
    parent_status_path,
    zzz_gaming_path,
    zzz_online_path,
)

SECTION_TITLE_HEIGHT = 64
SECTION_BOTTOM_PADDING = 16
ONLINE_ROW_HEIGHT = 64
GAMING_ROW_HEIGHT = 78
PARENT_STATUS_HEIGHT = 120
FRIENDS_SEARCH_HEIGHT = 50
START_GAMING_WIDTH = 424
START_GAMING_HEIGHT = 105
CARD_BACKGROUND = "rgb(30, 32, 36)"
DETAIL_GAMING_COLOR = "rgb(142, 190, 86)"
ONLINE_BAR_COLOR = "rgb(76, 145, 172)"
SECTION_DIVIDER_COLOR = "rgb(51, 52, 57)"


class SerializedRowBase(TypedDict):
    gaming: bool
    row_height: int
    avatar_slot_left: int
    avatar_slot_top: int
    avatar_slot_size: int
    avatar_left: int
    avatar_top: int
    avatar_size: int
    avatar_src: str
    avatar_frame_src: str | None
    text_left: int
    text_top: int
    text_height: int
    name: str
    detail: str
    name_color: str
    detail_color: str
    name_font_size: int
    detail_font_size: int
    name_line_height: int
    detail_line_height: int
    badge_src: str | None
    badge_margin_left: int
    badge_height: int


class SerializedRow(SerializedRowBase, total=False):
    game_icon_src: str | None
    game_icon_left: int
    game_icon_top: int
    game_icon_size: int
    bar_left: int
    bar_top: int
    bar_width: int
    bar_height: int
    bar_color: str
    name_sprite: "TextSprite"
    detail_sprite: "TextSprite"


class SerializedSection(TypedDict):
    title: str
    count_text: str | None
    count_left: int
    rows: list[SerializedRow]
    height: int
    divider_height: int
    title_sprite: "TextSprite"
    count_sprite: "TextSprite | None"
    divider_color: str | None


class TextSprite(TypedDict):
    src: str
    width: int
    height: int


def image_to_data_uri(
    image: Image.Image,
    size: tuple[int, int] | None = None,
    image_format: str = "PNG",
) -> str:
    if size is not None and image.size != size:
        image = image.resize(size, Image.Resampling.BICUBIC)
    converted = image.convert("RGBA") if image_format == "PNG" else image.convert("RGB")
    with BytesIO() as buffer:
        converted.save(buffer, format=image_format)
        data = base64.b64encode(buffer.getvalue()).decode("ascii")
    mime = "image/png" if image_format == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{data}"


@cache
def static_file_to_data_uri(path_str: str) -> str:
    path = Path(path_str)
    mime = guess_type(path.name)[0] or "application/octet-stream"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


@cache
def _font_faces_css_for_paths(
    regular_path: str | None,
    light_path: str | None,
    bold_path: str | None,
) -> str:
    font_specs = [
        ("SteamInfoRegular", regular_path, 400),
        ("SteamInfoLight", light_path, 300),
        ("SteamInfoBold", bold_path, 700),
    ]
    rules: list[str] = []
    for family, raw_path, weight in font_specs:
        if raw_path is None:
            continue
        path = Path(raw_path)
        if not path.exists():
            continue
        src = static_file_to_data_uri(str(path))
        rules.append(
            "@font-face {"
            f"font-family: '{family}';"
            f"src: url('{src}') format('truetype');"
            f"font-weight: {weight};"
            "font-style: normal;"
            "font-display: swap;"
            "}"
        )
    return "".join(rules)


def font_faces_css() -> str:
    return _font_faces_css_for_paths(
        draw_module.font_regular_path,
        draw_module.font_light_path,
        draw_module.font_bold_path,
    )


def escape_text(text: str) -> str:
    return html.escape(text, quote=False)


def build_sections(data: list[FriendStatusData]) -> list[SerializedSection]:
    sorted_data = sorted(data, key=lambda item: item["personastate"])

    gaming_data = [
        item
        for item in sorted_data
        if item.get("game_name") is not None
    ]
    gaming_data.sort(key=lambda item: item.get("game_name") or item["status"])

    online_data = [
        item
        for item in sorted_data
        if item["personastate"] != 0 and item.get("game_name") is None
    ]
    offline_data = [item for item in sorted_data if item["personastate"] == 0]

    sections: list[SerializedSection] = []
    if gaming_data:
        sections.append(_serialize_section("游戏中", gaming_data))
    if online_data:
        sections.append(_serialize_section("在线好友", online_data, f"({len(online_data)})"))
    if offline_data:
        sections.append(_serialize_section("离线", offline_data, f"({len(offline_data)})"))

    # 设置分割线颜色（统一灰色，和 PIL 一致）
    for i, section in enumerate(sections):
        if i < len(sections) - 1:
            section["divider_color"] = SECTION_DIVIDER_COLOR
            section["divider_height"] = 1
            section["height"] += 1
        else:
            section["divider_color"] = None
            section["divider_height"] = 0

    return sections


def friends_status_height(sections: list[SerializedSection]) -> int:
    return PARENT_STATUS_HEIGHT + FRIENDS_SEARCH_HEIGHT + sum(
        section["height"] for section in sections
    )


def load_image_from_bytes(data: bytes) -> Image.Image:
    image = Image.open(BytesIO(data))
    image.load()
    return image.convert("RGB")


def friends_status_template_context(
    parent_avatar: Image.Image,
    parent_name: str,
    sections: list[SerializedSection],
) -> dict[str, object]:
    return {
        "width": WIDTH,
        "parent_name": escape_text(parent_name),
        "parent_name_sprite": _text_sprite(
            parent_name,
            draw_module.font_bold(20),
            (109, 207, 246),
        ),
        "parent_online_sprite": _text_sprite(
            "在线",
            draw_module.font_light(18),
            (76, 145, 172),
        ),
        "parent_avatar_src": image_to_data_uri(
            parent_avatar,
            size=(PARENT_AVATAR_SIZE, PARENT_AVATAR_SIZE),
        ),
        "parent_background_src": static_file_to_data_uri(str(parent_status_path)),
        "friends_search_src": static_file_to_data_uri(str(friends_search_path)),
        "friends_search_title_sprite": _text_sprite(
            "好友",
            draw_module.font_regular(20),
            (183, 204, 213),
        ),
        "sections": sections,
        "card_background": CARD_BACKGROUND,
        "font_faces_css": font_faces_css(),
    }


def start_gaming_template_context(
    avatar: Image.Image,
    friend_name: str,
    game_name: str,
    nickname: str | None,
) -> dict[str, object]:
    display_name = _format_friend_display_name(friend_name, nickname)
    return {
        "background_src": static_file_to_data_uri(str(gaming_path)),
        "avatar_src": image_to_data_uri(avatar, size=(66, 66)),
        "display_name": escape_text(display_name),
        "display_name_sprite": _text_sprite(
            display_name,
            draw_module.font_regular(19),
            (227, 255, 194),
        ),
        "playing_sprite": _text_sprite(
            "正在玩",
            draw_module.font_regular(17),
            (150, 150, 150),
        ),
        "game_name": escape_text(game_name),
        "game_name_sprite": _text_sprite(
            game_name,
            draw_module.font_bold(14),
            (145, 194, 87),
        ),
        "font_faces_css": font_faces_css(),
    }


def friends_status_htmlkit_template_context(
    parent_avatar: Image.Image,
    parent_name: str,
    sections: list[SerializedSection],
) -> dict[str, object]:
    return friends_status_template_context(parent_avatar, parent_name, sections)


def start_gaming_htmlkit_template_context(
    avatar: Image.Image,
    friend_name: str,
    game_name: str,
    nickname: str | None,
) -> dict[str, object]:
    return start_gaming_template_context(avatar, friend_name, game_name, nickname)


def _serialize_section(
    title: str,
    data: list[FriendStatusData],
    count_text: str | None = None,
) -> SerializedSection:
    rows = [_serialize_row(item) for item in data]
    height = SECTION_TITLE_HEIGHT + sum(row["row_height"] for row in rows) + SECTION_BOTTOM_PADDING
    return {
        "title": title,
        "count_text": count_text,
        "count_left": {"游戏中": 104, "在线好友": 128, "离线": 78}.get(title, 104),
        "rows": rows,
        "height": height,
        "divider_height": 0,
        "title_sprite": _text_sprite(
            title,
            draw_module.font_regular(22),
            (197, 214, 212),
        ),
        "count_sprite": (
            _text_sprite(
                count_text,
                draw_module.font_regular(18),
                (103, 102, 92),
            )
            if count_text is not None
            else None
        ),
        "divider_color": None,
    }


def _serialize_row(data: FriendStatusData) -> SerializedRow:
    gaming_layout = data.get("game_name") is not None and data["status"] not in {
        "在线",
        "离开",
    }
    row_height = GAMING_ROW_HEIGHT if gaming_layout else ONLINE_ROW_HEIGHT
    avatar_slot_left = 60 if gaming_layout else 22
    avatar_slot_top = (row_height - AVATAR_SLOT_SIZE) // 2
    visual_avatar_top = avatar_slot_top + AVATAR_FRAME_PADDING
    text_left = avatar_slot_left + AVATAR_SLOT_SIZE + (14 if gaming_layout else 18)
    fill = _get_friend_status_fill(data["personastate"], data["status"], gaming_layout)
    avatar_frame = data.get("avatar_frame")
    game_icon = data.get("game_icon")

    if data["personastate"] == 2:
        badge_src = static_file_to_data_uri(str(busy_path))
    elif data["personastate"] == 4:
        badge_src = static_file_to_data_uri(
            str(zzz_gaming_path if gaming_layout else zzz_online_path)
        )
    else:
        badge_src = None

    row: SerializedRow = {
        "gaming": gaming_layout,
        "row_height": row_height,
        "avatar_slot_left": avatar_slot_left,
        "avatar_slot_top": avatar_slot_top,
        "avatar_slot_size": AVATAR_SLOT_SIZE,
        "avatar_left": avatar_slot_left + AVATAR_FRAME_PADDING,
        "avatar_top": visual_avatar_top,
        "avatar_size": MEMBER_AVATAR_SIZE,
        "avatar_src": image_to_data_uri(
            data["avatar"],
            size=(MEMBER_AVATAR_SIZE, MEMBER_AVATAR_SIZE),
        ),
        "avatar_frame_src": (
            image_to_data_uri(avatar_frame, size=(AVATAR_SLOT_SIZE, AVATAR_SLOT_SIZE))
            if avatar_frame is not None
            else None
        ),
        "text_left": text_left,
        "text_top": visual_avatar_top,
        "text_height": MEMBER_AVATAR_SIZE,
        "name": escape_text(
            _format_friend_display_name(data["name"], data.get("nickname"))
        ),
        "detail": escape_text(
            data.get("game_name") or data["status"] if gaming_layout else data["status"]
        ),
        "name_color": _rgb_to_css(fill[0]),
        "detail_color": DETAIL_GAMING_COLOR if gaming_layout else _rgb_to_css(fill[1]),
        "name_font_size": 19 if gaming_layout else 20,
        "detail_font_size": 17 if gaming_layout else 18,
        "name_line_height": 22 if gaming_layout else 24,
        "detail_line_height": 20 if gaming_layout else 22,
        "badge_src": badge_src,
        "badge_margin_left": 6 if data["personastate"] == 2 else 8,
        "badge_height": 18 if data["personastate"] == 2 else 13,
        "name_sprite": _name_sprite(
            _format_friend_display_name(data["name"], data.get("nickname")),
            fill[0],
            19 if gaming_layout else 20,
            data["personastate"],
            gaming_layout,
        ),
        "detail_sprite": _text_sprite(
            data.get("game_name") or data["status"] if gaming_layout else data["status"],
            draw_module.font_regular(17 if gaming_layout else 18),
            (142, 190, 86) if gaming_layout else fill[1],
        ),
    }

    if gaming_layout:
        row["game_icon_src"] = (
            image_to_data_uri(game_icon, size=(GAME_ICON_SIZE, GAME_ICON_SIZE))
            if game_icon is not None
            else None
        )
        row["game_icon_left"] = 20
        row["game_icon_top"] = (row_height - GAME_ICON_SIZE) // 2
        row["game_icon_size"] = GAME_ICON_SIZE
        bar_left = avatar_slot_left + AVATAR_SLOT_SIZE
        bar_top = avatar_slot_top + 3
        row["bar_left"] = bar_left
        row["bar_top"] = bar_top
        row["bar_width"] = 3
        row["bar_height"] = AVATAR_SLOT_SIZE - 6
        row["text_left"] = bar_left + 12
        row["bar_color"] = DETAIL_GAMING_COLOR
    elif data["personastate"] != 0:
        bar_left = avatar_slot_left + AVATAR_SLOT_SIZE
        row["bar_left"] = bar_left
        row["bar_top"] = avatar_slot_top + 5
        row["bar_width"] = 3
        row["bar_height"] = AVATAR_SLOT_SIZE - 10
        row["text_left"] = bar_left + 12
        row["bar_color"] = ONLINE_BAR_COLOR

    return row


def _rgb_to_css(color: tuple[int, int, int]) -> str:
    return f"rgb({color[0]}, {color[1]}, {color[2]})"


def _text_sprite(
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> TextSprite:
    bbox = _normalize_bbox(font.getbbox(text or " "))
    width = max(1, ceil(max(_bbox_width(bbox), _measure_textlength(text or " ", font))))
    height = max(1, bbox[3] - bbox[1])
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((-bbox[0], -bbox[1]), text or " ", font=font, fill=fill)
    return {
        "src": image_to_data_uri(image),
        "width": image.width,
        "height": image.height,
    }


def text_sprite(
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int],
) -> TextSprite:
    return _text_sprite(text, font, fill)


def _name_sprite(
    display_name: str,
    fill: tuple[int, int, int],
    font_size: int,
    personastate: int,
    gaming_layout: bool,
) -> TextSprite:
    font = draw_module.font_bold(font_size)
    bbox = _normalize_bbox(font.getbbox(display_name or " "))
    text_width = max(
        1, ceil(max(_bbox_width(bbox), _measure_textlength(display_name or " ", font)))
    )
    text_height = max(1, bbox[3] - bbox[1])
    badge = _load_badge_sprite(personastate, gaming_layout)
    badge_gap = 6 if personastate == 2 else 8
    badge_top = 0 if gaming_layout else 6

    width = text_width
    height = text_height
    if badge is not None:
        width += badge_gap + badge.width
        height = max(height, badge_top + badge.height)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.text((-bbox[0], -bbox[1]), display_name or " ", font=font, fill=fill)
    if badge is not None:
        image.alpha_composite(badge, (text_width + badge_gap, badge_top))

    return {
        "src": image_to_data_uri(image),
        "width": image.width,
        "height": image.height,
    }


def _load_badge_sprite(
    personastate: int,
    gaming_layout: bool,
) -> Image.Image | None:
    if personastate == 2:
        return Image.open(busy_path).convert("RGBA")
    if personastate == 4:
        return Image.open(
            zzz_gaming_path if gaming_layout else zzz_online_path
        ).convert("RGBA")
    return None


def _measure_textlength(text: str, font: ImageFont.FreeTypeFont) -> float:
    probe = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    return draw.textlength(text, font=font)


def _bbox_width(bbox: tuple[int, int, int, int]) -> int:
    return max(1, bbox[2] - bbox[0])


def _normalize_bbox(
    bbox: tuple[float, float, float, float],
) -> tuple[int, int, int, int]:
    return (
        floor(bbox[0]),
        floor(bbox[1]),
        ceil(bbox[2]),
        ceil(bbox[3]),
    )


__all__ = [
    "CARD_BACKGROUND",
    "DETAIL_GAMING_COLOR",
    "FRIENDS_SEARCH_HEIGHT",
    "PARENT_STATUS_HEIGHT",
    "START_GAMING_HEIGHT",
    "START_GAMING_WIDTH",
    "SerializedRow",
    "SerializedSection",
    "build_sections",
    "escape_text",
    "font_faces_css",
    "friends_status_height",
    "friends_status_htmlkit_template_context",
    "friends_status_template_context",
    "image_to_data_uri",
    "load_image_from_bytes",
    "start_gaming_htmlkit_template_context",
    "start_gaming_template_context",
    "static_file_to_data_uri",
    "text_sprite",
]
