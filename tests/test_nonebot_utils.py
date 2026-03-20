from types import SimpleNamespace


def test_get_parent_id_prefers_parent_scene():
    from nonebot_plugin_steam_info.bot.nonebot_utils import get_parent_id

    session = SimpleNamespace(
        scene=SimpleNamespace(
            is_private=False,
            id="channel-1",
            parent=SimpleNamespace(id="guild-1"),
        )
    )

    assert get_parent_id(session) == "guild-1"


def test_is_admin_checks_role_level():
    from nonebot_plugin_steam_info.bot.nonebot_utils import is_admin

    admin_session = SimpleNamespace(
        member=SimpleNamespace(
            roles=[SimpleNamespace(level=1), SimpleNamespace(level=10)]
        )
    )
    member_session = SimpleNamespace(
        member=SimpleNamespace(roles=[SimpleNamespace(level=1)])
    )

    assert is_admin(admin_session) is True
    assert is_admin(member_session) is False
