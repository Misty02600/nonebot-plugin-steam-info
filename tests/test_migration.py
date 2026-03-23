import json


def test_migrate_legacy_data_restores_missing_groups_from_migrated_files(tmp_path):
    from nonebot_plugin_steam_info.core.data_models import BindRecord
    from nonebot_plugin_steam_info.infra.stores import GroupStore
    from nonebot_plugin_steam_info.migration import migrate_legacy_data

    data_dir = tmp_path
    store = GroupStore(data_dir / "groups.json")
    store.add_bind("1002", BindRecord(user_id="u-current", steam_id="steam-current"))

    (data_dir / "bind_data.json.migrated").write_text(
        json.dumps(
            {
                "1001": [
                    {
                        "user_id": "u-1",
                        "steam_id": "steam-1",
                        "nickname": "legacy",
                    }
                ],
                "1002": [
                    {
                        "user_id": "u-current",
                        "steam_id": "steam-current",
                        "nickname": "filled",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (data_dir / "parent_data.json.migrated").write_text(
        json.dumps({"1001": "Legacy Group", "1002": "Current Group"}),
        encoding="utf-8",
    )
    (data_dir / "disable_parent_data.json.migrated").write_text(
        json.dumps(["1001", "1002"]),
        encoding="utf-8",
    )

    migrate_legacy_data(data_dir, store)
    migrate_legacy_data(data_dir, store)

    restored_group = store.data.groups["1001"]
    current_group = store.data.groups["1002"]

    assert restored_group.name == "Legacy Group"
    assert restored_group.disabled is True
    assert restored_group.sync_disabled is False
    assert [(record.user_id, record.steam_id, record.nickname) for record in restored_group.binds] == [
        ("u-1", "steam-1", "legacy")
    ]

    assert current_group.disabled is False
    assert [(record.user_id, record.steam_id, record.nickname) for record in current_group.binds] == [
        ("u-current", "steam-current", "filled")
    ]
