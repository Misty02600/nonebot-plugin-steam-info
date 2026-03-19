from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_fetch_and_broadcast_steam_info_isolates_group_errors(monkeypatch):
    from nonebot_plugin_steam_info.bot.handlers import scheduled

    monkeypatch.setattr(
        scheduled, "update_steam_info", AsyncMock(return_value={"1001": [], "1002": []})
    )
    monkeypatch.setattr(
        scheduled,
        "group_store",
        SimpleNamespace(
            get_all_parent_ids=lambda: ["1001", "1002"],
            get_all_steam_ids=lambda _parent_id: [],
        ),
    )
    monkeypatch.setattr(
        scheduled, "steam_state", SimpleNamespace(get_players=lambda _steam_ids: [])
    )
    monkeypatch.setattr(
        scheduled,
        "config",
        SimpleNamespace(steam_broadcast_send_delay=0),
    )
    broadcast_mock = AsyncMock(side_effect=[RuntimeError("boom"), True])
    monkeypatch.setattr(scheduled, "broadcast_steam_info", broadcast_mock)
    logger_exception = MagicMock()
    monkeypatch.setattr(scheduled.logger, "exception", logger_exception)

    await scheduled.fetch_and_broadcast_steam_info()

    assert broadcast_mock.await_count == 2
    logger_exception.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_and_broadcast_steam_info_waits_between_groups(monkeypatch):
    from nonebot_plugin_steam_info.bot.handlers import scheduled

    monkeypatch.setattr(
        scheduled,
        "update_steam_info",
        AsyncMock(return_value={"1001": [], "1002": [], "1003": []}),
    )
    monkeypatch.setattr(
        scheduled,
        "group_store",
        SimpleNamespace(
            get_all_parent_ids=lambda: ["1001", "1002", "1003"],
            get_all_steam_ids=lambda _parent_id: [],
        ),
    )
    monkeypatch.setattr(
        scheduled, "steam_state", SimpleNamespace(get_players=lambda _steam_ids: [])
    )
    monkeypatch.setattr(
        scheduled,
        "config",
        SimpleNamespace(steam_broadcast_send_delay=1.25),
    )
    monkeypatch.setattr(
        scheduled,
        "broadcast_steam_info",
        AsyncMock(side_effect=[True, False, True]),
    )
    sleep_mock = AsyncMock()
    monkeypatch.setattr(scheduled.asyncio, "sleep", sleep_mock)

    await scheduled.fetch_and_broadcast_steam_info()

    sleep_mock.assert_awaited_once_with(1.25)
