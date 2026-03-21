from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from nonebot_plugin_steam_info.core.models import FriendStatusData


@dataclass
class BindEntryStub:
    nickname: str | None


class GroupStoreStub:
    def __init__(self, nickname: str | None) -> None:
        self._nickname = nickname

    def get_bind_by_steam_id(
        self, parent_id: str, steam_id: str
    ) -> BindEntryStub | None:
        del parent_id, steam_id
        return BindEntryStub(self._nickname)


def make_friend_status_data() -> "FriendStatusData":
    return {
        "steamid": "76561198000000000",
        "avatar": Image.new("RGBA", (50, 50), (255, 255, 255, 255)),
        "avatar_frame": None,
        "name": "SteamUser",
        "status": "在线",
        "personastate": 1,
        "game_icon": None,
    }


def test_convert_player_name_to_nickname_omits_blank_nickname():
    from nonebot_plugin_steam_info.infra.utils import convert_player_name_to_nickname

    result = convert_player_name_to_nickname(
        make_friend_status_data(),
        "1001",
        GroupStoreStub("   "),
    )

    assert result.get("nickname") is None


def test_convert_player_name_to_nickname_keeps_real_nickname():
    from nonebot_plugin_steam_info.infra.utils import convert_player_name_to_nickname

    result = convert_player_name_to_nickname(
        make_friend_status_data(),
        "1001",
        GroupStoreStub("Misty"),
    )

    assert result.get("nickname") == "Misty"


def test_format_friend_display_name_hides_empty_parentheses():
    from nonebot_plugin_steam_info.infra.draw import _format_friend_display_name

    assert _format_friend_display_name("SteamUser") == "SteamUser"
    assert _format_friend_display_name("SteamUser", "") == "SteamUser"
    assert _format_friend_display_name("SteamUser", "   ") == "SteamUser"
    assert _format_friend_display_name("SteamUser", "Misty") == "SteamUser (Misty)"


def test_draw_friend_status_supports_sleeping_gaming_badge():
    from nonebot_plugin_steam_info.infra.draw import WIDTH, draw_friend_status

    image = draw_friend_status(
        Image.new("RGBA", (50, 50), (255, 255, 255, 255)),
        "SteamUser",
        "Slay the Spire 2",
        4,
        game_name="Slay the Spire 2",
    )

    assert image.size == (WIDTH, 78)


def test_gaming_friend_status_fill_stays_green_for_sleeping_user():
    from nonebot_plugin_steam_info.infra.draw import (
        GAMING_TEXT_FILL,
        _get_friend_status_fill,
    )

    assert (
        _get_friend_status_fill(4, "Slay the Spire 2", True) == GAMING_TEXT_FILL
    )


def test_compose_avatar_with_frame_uses_fixed_slot_size():
    from nonebot_plugin_steam_info.infra.draw import (
        AVATAR_SLOT_SIZE,
        _compose_avatar_with_frame,
    )

    avatar = Image.new("RGBA", (50, 50), (255, 255, 255, 255))

    without_frame = _compose_avatar_with_frame(avatar, None)
    with_frame = _compose_avatar_with_frame(
        avatar,
        Image.new("RGBA", (64, 64), (0, 255, 0, 128)),
    )

    assert without_frame.size == (AVATAR_SLOT_SIZE, AVATAR_SLOT_SIZE)
    assert with_frame.size == (AVATAR_SLOT_SIZE, AVATAR_SLOT_SIZE)


def test_two_line_text_positions_align_to_avatar_slot_edges():
    from nonebot_plugin_steam_info.infra.draw import _get_two_line_text_positions

    primary_y, secondary_y = _get_two_line_text_positions(10, 58, 18, 16)

    assert primary_y == 10
    assert secondary_y == 52


def test_text_draw_y_offsets_font_top_bbox():
    from nonebot_plugin_steam_info.infra.draw import (
        _get_text_draw_y,
        _measure_text_bbox,
        font_bold,
    )

    bbox = _measure_text_bbox(font_bold(19), "Misty")

    assert _get_text_draw_y(bbox, 10) == 10 - bbox[1]
