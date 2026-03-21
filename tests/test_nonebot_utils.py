from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from nonebot_plugin_uninfo import Session
else:
    Session = Any


def test_get_parent_id_prefers_parent_scene():
    from nonebot_plugin_steam_info.bot.nonebot_utils import get_parent_id

    session = cast(
        Session,
        SimpleNamespace(
            scene=SimpleNamespace(
                is_private=False,
                id="channel-1",
                parent=SimpleNamespace(id="guild-1"),
            )
        ),
    )

    assert get_parent_id(session) == "guild-1"


def test_is_admin_checks_role_level():
    from nonebot_plugin_steam_info.bot.nonebot_utils import is_admin

    admin_session = cast(
        Session,
        SimpleNamespace(
            member=SimpleNamespace(
                roles=[SimpleNamespace(level=1), SimpleNamespace(level=10)]
            )
        ),
    )
    member_session = cast(
        Session,
        SimpleNamespace(member=SimpleNamespace(roles=[SimpleNamespace(level=1)])),
    )

    assert is_admin(admin_session) is True
    assert is_admin(member_session) is False
