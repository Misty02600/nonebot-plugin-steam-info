from pathlib import Path
from uuid import uuid4

from PIL import Image


def test_remove_group_deletes_group_data_and_avatar():
    from nonebot_plugin_steam_info.core.data_models import BindRecord
    from nonebot_plugin_steam_info.infra.stores import GroupStore

    tmp_path = Path("cache") / f"test_remove_group_{uuid4().hex}"
    store = GroupStore(tmp_path / "groups.json")
    avatar = Image.new("RGB", (8, 8), color="red")

    store.add_bind("1001", BindRecord(user_id="42", steam_id="steam-42"))
    store.update_info("1001", avatar, "Test Group")

    avatar_path = tmp_path / "avatars" / "1001.png"
    assert "1001" in store.get_all_parent_ids()
    assert avatar_path.exists()

    store.remove_group("1001")

    assert "1001" not in store.get_all_parent_ids()
    assert not avatar_path.exists()


def test_sync_current_parents_temporarily_disables_and_restores_groups():
    from nonebot_plugin_steam_info.core.data_models import BindRecord
    from nonebot_plugin_steam_info.infra.stores import GroupStore

    tmp_path = Path("cache") / f"test_sync_current_parents_{uuid4().hex}"
    store = GroupStore(tmp_path / "groups.json")

    store.add_bind("1001", BindRecord(user_id="42", steam_id="steam-42"))
    store.add_bind("1002", BindRecord(user_id="43", steam_id="steam-43"))

    disabled_parent_ids, restored_parent_ids = store.sync_current_parents({"1001"})

    assert disabled_parent_ids == ["1002"]
    assert restored_parent_ids == []
    assert store.data.groups["1002"].sync_disabled is True
    assert store.get_enabled_parent_ids() == ["1001"]
    assert store.is_disabled("1002") is True

    disabled_parent_ids, restored_parent_ids = store.sync_current_parents(
        {"1001", "1002"}
    )

    assert disabled_parent_ids == []
    assert restored_parent_ids == ["1002"]
    assert store.data.groups["1002"].sync_disabled is False
    assert set(store.get_enabled_parent_ids()) == {"1001", "1002"}
    assert store.is_disabled("1002") is False
