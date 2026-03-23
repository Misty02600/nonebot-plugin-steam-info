from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_prune_departed_groups_sync_disables_missing_groups(monkeypatch):
    from nonebot_plugin_steam_info.bot.handlers import scheduled

    sync_current_parents_mock = MagicMock(return_value=(["1002"], []))
    monkeypatch.setattr(
        scheduled,
        "group_store",
        SimpleNamespace(
            sync_current_parents=sync_current_parents_mock,
        ),
    )
    monkeypatch.setattr(
        scheduled.nonebot,
        "get_bot",
        lambda: SimpleNamespace(adapter=SimpleNamespace(get_name=lambda: "OneBot V11")),
    )
    monkeypatch.setattr(
        scheduled,
        "get_interface",
        lambda _bot: SimpleNamespace(
            get_scenes=AsyncMock(
                side_effect=[
                    [SimpleNamespace(id="1001")],
                    [],
                ]
            )
        ),
    )
    logger_warning = MagicMock()
    monkeypatch.setattr(scheduled.logger, "warning", logger_warning)

    await scheduled.prune_departed_groups()

    sync_current_parents_mock.assert_called_once_with({"1001"})
    logger_warning.assert_called_once()


@pytest.mark.asyncio
async def test_prune_departed_groups_restores_returned_groups(monkeypatch):
    from nonebot_plugin_steam_info.bot.handlers import scheduled

    sync_current_parents_mock = MagicMock(return_value=([], ["1001"]))
    monkeypatch.setattr(
        scheduled,
        "group_store",
        SimpleNamespace(
            sync_current_parents=sync_current_parents_mock,
        ),
    )
    monkeypatch.setattr(
        scheduled.nonebot,
        "get_bot",
        lambda: SimpleNamespace(adapter=SimpleNamespace(get_name=lambda: "OneBot V11")),
    )
    monkeypatch.setattr(
        scheduled,
        "get_interface",
        lambda _bot: SimpleNamespace(
            get_scenes=AsyncMock(
                side_effect=[
                    [SimpleNamespace(id="1001")],
                    [],
                ]
            )
        ),
    )
    logger_info = MagicMock()
    monkeypatch.setattr(scheduled.logger, "info", logger_info)

    await scheduled.prune_departed_groups()

    sync_current_parents_mock.assert_called_once_with({"1001"})
    logger_info.assert_called_once()


@pytest.mark.asyncio
async def test_update_steam_info_only_reads_enabled_groups(monkeypatch):
    from nonebot_plugin_steam_info.bot.handlers import scheduled

    client_mock = SimpleNamespace(
        get_users_info=AsyncMock(return_value={"response": {"players": []}})
    )
    steam_state = SimpleNamespace(
        get_players=MagicMock(side_effect=lambda steam_ids: [{"steam_ids": steam_ids}]),
        update_by_players=MagicMock(),
    )
    monkeypatch.setattr(scheduled, "client", client_mock)
    monkeypatch.setattr(
        scheduled,
        "group_store",
        SimpleNamespace(
            get_all_enabled_steam_ids_global=lambda: ["steam-1", "steam-2"],
            get_enabled_parent_ids=lambda: ["1001"],
            get_all_steam_ids=lambda _parent_id: ["steam-1"],
        ),
    )
    monkeypatch.setattr(scheduled, "steam_state", steam_state)

    result = await scheduled.update_steam_info()

    client_mock.get_users_info.assert_awaited_once_with(["steam-1", "steam-2"])
    assert result == {"1001": [{"steam_ids": ["steam-1"]}]}
    steam_state.update_by_players.assert_not_called()


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
            get_enabled_parent_ids=lambda: ["1001", "1002"],
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
            get_enabled_parent_ids=lambda: ["1001", "1002", "1003"],
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
