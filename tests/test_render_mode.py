from __future__ import annotations

import sys
from types import ModuleType
from typing import TYPE_CHECKING, Any, Literal, cast

import pytest
from PIL import Image

if TYPE_CHECKING:
    from nonebot_plugin_steam_info.core.models import FriendStatusData


def _make_friend_status_data() -> "FriendStatusData":
    return {
        "steamid": "76561198000000000",
        "avatar": Image.new("RGBA", (50, 50), (255, 255, 255, 255)),
        "avatar_frame": None,
        "name": "SteamUser",
        "status": "在线",
        "personastate": 1,
        "nickname": None,
        "game_icon": None,
        "game_name": None,
    }


def _make_gaming_friend_status_data() -> "FriendStatusData":
    return {
        "steamid": "76561198000000001",
        "avatar": Image.new("RGBA", (50, 50), (255, 255, 255, 255)),
        "avatar_frame": Image.new("RGBA", (58, 58), (255, 0, 0, 60)),
        "name": "GamingUser",
        "status": "Slay the Spire 2",
        "personastate": 4,
        "nickname": "群名片",
        "game_icon": Image.new("RGBA", (34, 34), (0, 128, 0, 255)),
        "game_name": "Slay the Spire 2",
    }


def _make_away_friend_status_data() -> "FriendStatusData":
    return {
        "steamid": "76561198000000002",
        "avatar": Image.new("RGBA", (50, 50), (200, 200, 255, 255)),
        "avatar_frame": None,
        "name": "AwayUser",
        "status": "离开",
        "personastate": 3,
        "nickname": None,
        "game_icon": None,
        "game_name": None,
    }


@pytest.mark.parametrize("mode", ["htmlkit", "htmlrender"])
def test_config_accepts_html_render_mode(
    mode: Literal["htmlkit", "htmlrender"],
):
    from nonebot_plugin_steam_info.config import Config

    config = Config(steam_api_key=["test-key"], steam_render_mode=mode)

    assert config.steam_render_mode == mode


@pytest.mark.asyncio
async def test_render_friends_status_uses_htmlkit_when_enabled(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (12, 12), (0, 255, 0))
    fake_module = cast(Any, ModuleType("nonebot_plugin_steam_info.infra.html_render"))

    async def fake_render(*args, **kwargs):
        del args, kwargs
        return sentinel

    fake_module.render_friends_status_html = fake_render
    monkeypatch.setitem(
        sys.modules, "nonebot_plugin_steam_info.infra.html_render", fake_module
    )

    image = await render.render_friends_status(
        Image.new("RGBA", (72, 72), (255, 255, 255, 255)),
        "Misty",
        [_make_friend_status_data()],
        "htmlkit",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_friends_status_falls_back_to_pil(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (20, 20), (255, 0, 0))
    fake_module = cast(Any, ModuleType("nonebot_plugin_steam_info.infra.html_render"))

    async def fake_render(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    fake_module.render_friends_status_html = fake_render
    monkeypatch.setitem(
        sys.modules, "nonebot_plugin_steam_info.infra.html_render", fake_module
    )
    monkeypatch.setattr(render, "draw_friends_status", lambda *args, **kwargs: sentinel)

    image = await render.render_friends_status(
        Image.new("RGBA", (72, 72), (255, 255, 255, 255)),
        "Misty",
        [_make_friend_status_data()],
        "htmlkit",
    )

    assert image is sentinel


@pytest.mark.parametrize(
    ("mode", "expected_plugin"),
    [
        ("pil", None),
        ("htmlkit", "nonebot_plugin_htmlkit"),
        ("htmlrender", "nonebot_plugin_htmlrender"),
    ],
)
def test_preload_render_plugin(
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["pil", "htmlkit", "htmlrender"],
    expected_plugin: str | None,
):
    from nonebot_plugin_steam_info.infra import render

    called: list[str] = []
    monkeypatch.setattr(render, "require", called.append)

    render.preload_render_plugin(mode)

    assert called == ([] if expected_plugin is None else [expected_plugin])


def test_html_template_context_embeds_static_assets_and_fonts():
    from nonebot_plugin_steam_info.infra.html_render_common import (
        build_sections,
        friends_status_template_context,
        start_gaming_template_context,
    )

    sections = build_sections([_make_gaming_friend_status_data()])
    friends_context = friends_status_template_context(
        Image.new("RGBA", (72, 72), (0, 0, 255, 255)),
        "ParentUser",
        sections,
    )
    start_context = start_gaming_template_context(
        Image.new("RGBA", (66, 66), (255, 255, 0, 255)),
        "GamingUser",
        "Slay the Spire 2",
        "群名片",
    )
    parent_background_src = cast(str, friends_context["parent_background_src"])
    friends_search_src = cast(str, friends_context["friends_search_src"])
    start_background_src = cast(str, start_context["background_src"])

    assert parent_background_src.startswith("data:")
    assert friends_search_src.startswith("data:")
    assert start_background_src.startswith("data:")
    assert "SteamInfoRegular" in str(friends_context["font_faces_css"])
    parent_name_sprite = cast(dict[str, object], friends_context["parent_name_sprite"])
    friends_search_title_sprite = cast(
        dict[str, object], friends_context["friends_search_title_sprite"]
    )
    display_name_sprite = cast(dict[str, object], start_context["display_name_sprite"])
    playing_sprite = cast(dict[str, object], start_context["playing_sprite"])
    assert cast(str, parent_name_sprite["src"]).startswith("data:")
    assert cast(str, friends_search_title_sprite["src"]).startswith("data:")
    assert cast(str, display_name_sprite["src"]).startswith("data:")
    assert cast(str, playing_sprite["src"]).startswith("data:")

    row = sections[0]["rows"][0]
    name_sprite = cast(dict[str, object], row.get("name_sprite"))
    detail_sprite = cast(dict[str, object], row.get("detail_sprite"))
    assert (row["badge_src"] or "").startswith("data:")
    assert cast(str, name_sprite["src"]).startswith("data:")
    assert cast(str, detail_sprite["src"]).startswith("data:")
    assert sections[0]["title_sprite"]["src"].startswith("data:")


def test_build_sections_places_away_friend_in_online_section():
    from nonebot_plugin_steam_info.infra.html_render_common import build_sections

    sections = build_sections(
        [_make_gaming_friend_status_data(), _make_away_friend_status_data()]
    )

    assert [section["title"] for section in sections] == ["游戏中", "在线好友"]
    assert [row["name"] for row in sections[1]["rows"]] == ["AwayUser"]


@pytest.mark.asyncio
async def test_render_friends_status_uses_htmlrender_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (14, 14), (0, 255, 255))
    fake_module = cast(
        Any,
        ModuleType("nonebot_plugin_steam_info.infra.htmlrender_render"),
    )

    async def fake_render(*args, **kwargs):
        del args, kwargs
        return sentinel

    fake_module.render_friends_status_htmlrender = fake_render
    monkeypatch.setitem(
        sys.modules,
        "nonebot_plugin_steam_info.infra.htmlrender_render",
        fake_module,
    )

    image = await render.render_friends_status(
        Image.new("RGBA", (72, 72), (255, 255, 255, 255)),
        "Misty",
        [_make_friend_status_data()],
        "htmlrender",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_friends_status_falls_back_from_htmlrender(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (22, 22), (255, 0, 255))
    fake_module = cast(
        Any,
        ModuleType("nonebot_plugin_steam_info.infra.htmlrender_render"),
    )

    async def fake_render(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    fake_module.render_friends_status_htmlrender = fake_render
    monkeypatch.setitem(
        sys.modules,
        "nonebot_plugin_steam_info.infra.htmlrender_render",
        fake_module,
    )
    monkeypatch.setattr(render, "draw_friends_status", lambda *args, **kwargs: sentinel)

    image = await render.render_friends_status(
        Image.new("RGBA", (72, 72), (255, 255, 255, 255)),
        "Misty",
        [_make_friend_status_data()],
        "htmlrender",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_start_gaming_uses_htmlkit_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (30, 30), (0, 0, 255))
    fake_module = cast(Any, ModuleType("nonebot_plugin_steam_info.infra.html_render"))

    async def fake_render(*args, **kwargs):
        del args, kwargs
        return sentinel

    fake_module.render_start_gaming_html = fake_render
    monkeypatch.setitem(
        sys.modules, "nonebot_plugin_steam_info.infra.html_render", fake_module
    )

    image = await render.render_start_gaming(
        Image.new("RGBA", (66, 66), (255, 255, 255, 255)),
        "Misty",
        "Slay the Spire 2",
        None,
        "htmlkit",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_start_gaming_falls_back_to_pil(monkeypatch: pytest.MonkeyPatch):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (40, 40), (255, 255, 0))
    fake_module = cast(Any, ModuleType("nonebot_plugin_steam_info.infra.html_render"))

    async def fake_render(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    fake_module.render_start_gaming_html = fake_render
    monkeypatch.setitem(
        sys.modules, "nonebot_plugin_steam_info.infra.html_render", fake_module
    )
    monkeypatch.setattr(render, "draw_start_gaming", lambda *args, **kwargs: sentinel)

    image = await render.render_start_gaming(
        Image.new("RGBA", (66, 66), (255, 255, 255, 255)),
        "Misty",
        "Slay the Spire 2",
        None,
        "htmlkit",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_start_gaming_uses_htmlrender_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (32, 32), (125, 125, 255))
    fake_module = cast(
        Any,
        ModuleType("nonebot_plugin_steam_info.infra.htmlrender_render"),
    )

    async def fake_render(*args, **kwargs):
        del args, kwargs
        return sentinel

    fake_module.render_start_gaming_htmlrender = fake_render
    monkeypatch.setitem(
        sys.modules,
        "nonebot_plugin_steam_info.infra.htmlrender_render",
        fake_module,
    )

    image = await render.render_start_gaming(
        Image.new("RGBA", (66, 66), (255, 255, 255, 255)),
        "Misty",
        "Slay the Spire 2",
        None,
        "htmlrender",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_start_gaming_falls_back_from_htmlrender(
    monkeypatch: pytest.MonkeyPatch,
):
    from nonebot_plugin_steam_info.infra import render

    sentinel = Image.new("RGB", (42, 42), (255, 125, 125))
    fake_module = cast(
        Any,
        ModuleType("nonebot_plugin_steam_info.infra.htmlrender_render"),
    )

    async def fake_render(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    fake_module.render_start_gaming_htmlrender = fake_render
    monkeypatch.setitem(
        sys.modules,
        "nonebot_plugin_steam_info.infra.htmlrender_render",
        fake_module,
    )
    monkeypatch.setattr(render, "draw_start_gaming", lambda *args, **kwargs: sentinel)

    image = await render.render_start_gaming(
        Image.new("RGBA", (66, 66), (255, 255, 255, 255)),
        "Misty",
        "Slay the Spire 2",
        None,
        "htmlrender",
    )

    assert image is sentinel


@pytest.mark.asyncio
async def test_render_friends_status_html_smoke():
    from nonebot_plugin_steam_info.infra.html_render import render_friends_status_html

    image = await render_friends_status_html(
        Image.new("RGBA", (72, 72), (0, 0, 255, 255)),
        "Misty",
        [_make_gaming_friend_status_data()],
    )

    assert image.size[0] == 400
    assert image.size[1] > 120
    assert image.getpixel((350, 15)) != (255, 255, 255)


@pytest.mark.asyncio
async def test_render_start_gaming_html_smoke():
    from nonebot_plugin_steam_info.infra.html_render import render_start_gaming_html

    image = await render_start_gaming_html(
        Image.new("RGBA", (66, 66), (255, 255, 0, 255)),
        "Misty",
        "Slay the Spire 2",
        "群名片",
    )

    assert image.size == (424, 105)
    assert image.getpixel((320, 20)) != (255, 255, 255)
