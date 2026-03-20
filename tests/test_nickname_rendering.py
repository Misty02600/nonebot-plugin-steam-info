from types import SimpleNamespace

from PIL import Image


def test_convert_player_name_to_nickname_omits_blank_nickname():
    from nonebot_plugin_steam_info.infra.utils import convert_player_name_to_nickname

    result = convert_player_name_to_nickname(
        {"steamid": "76561198000000000", "name": "SteamUser"},
        "1001",
        SimpleNamespace(
            get_bind_by_steam_id=lambda _parent_id, _steam_id: SimpleNamespace(
                nickname="   "
            )
        ),
    )

    assert result["nickname"] is None


def test_convert_player_name_to_nickname_keeps_real_nickname():
    from nonebot_plugin_steam_info.infra.utils import convert_player_name_to_nickname

    result = convert_player_name_to_nickname(
        {"steamid": "76561198000000000", "name": "SteamUser"},
        "1001",
        SimpleNamespace(
            get_bind_by_steam_id=lambda _parent_id, _steam_id: SimpleNamespace(
                nickname="Misty"
            )
        ),
    )

    assert result["nickname"] == "Misty"


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
