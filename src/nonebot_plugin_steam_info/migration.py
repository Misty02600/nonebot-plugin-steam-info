"""旧数据迁移模块 — 启动时自动执行"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nonebot.log import logger

from .core.data_models import BindRecord
from .infra.stores import GroupStore


def _iter_legacy_paths(data_dir: Path, filename: str) -> list[Path]:
    base_path = data_dir / filename
    migrated_path = base_path.with_suffix(".json.migrated")
    return [path for path in (base_path, migrated_path) if path.exists()]


def _mark_path_as_migrated(path: Path) -> bool:
    if path.name.endswith(".json.migrated"):
        return False

    migrated_path = path.with_suffix(".json.migrated")
    if migrated_path.exists():
        return False

    path.rename(migrated_path)
    return True


def _merge_bind_records(
    group_store: GroupStore,
    parent_id: str,
    records: list[dict[str, str | None]],
) -> bool:
    config = group_store._get_or_create(parent_id)
    existing_by_user_id = {record.user_id: record for record in config.binds}
    changed = False

    for record in records:
        user_id = str(record["user_id"])
        steam_id = str(record["steam_id"]).strip()
        nickname = record.get("nickname") or None
        existing = existing_by_user_id.get(user_id)

        if existing is None:
            config.binds.append(
                BindRecord(
                    user_id=user_id,
                    steam_id=steam_id,
                    nickname=nickname,
                )
            )
            existing_by_user_id[user_id] = config.binds[-1]
            changed = True
            continue

        if not existing.nickname and nickname:
            existing.nickname = nickname
            changed = True

    return changed


def migrate_legacy_data(
    data_dir: Path,
    group_store: GroupStore,
) -> None:
    """检测并迁移/恢复旧版 JSON 数据

    旧文件格式：
    - bind_data.json              → dict[str, list[dict[str, str]]]
    - parent_data.json            → dict[str, str]  (parent_id → name)
    - disable_parent_data.json    → list[str]
    - {parent_id}.png             → 群头像（在数据根目录）

    迁移后旧文件重命名为 .json.migrated
    """
    changed = False
    had_legacy_source = False
    existing_parent_ids = set(group_store.get_all_parent_ids())

    # 1. 合并 bind_data.json / bind_data.json.migrated
    for bind_path in _iter_legacy_paths(data_dir, "bind_data.json"):
        had_legacy_source = True
        old_bind: dict[str, list[dict[str, str | None]]] = json.loads(
            bind_path.read_text("utf-8")
        )
        for parent_id, records in old_bind.items():
            changed = _merge_bind_records(group_store, parent_id, records) or changed
        _mark_path_as_migrated(bind_path)

    # 2. 合并 parent_data.json / parent_data.json.migrated
    for parent_path in _iter_legacy_paths(data_dir, "parent_data.json"):
        had_legacy_source = True
        old_parent: dict[str, str] = json.loads(parent_path.read_text("utf-8"))
        avatars_dir = data_dir / "avatars"
        avatars_dir.mkdir(exist_ok=True)
        for parent_id, name in old_parent.items():
            config = group_store._get_or_create(parent_id)
            if not config.name and name:
                config.name = name
                changed = True

            # 迁移头像文件到 avatars/ 子目录
            old_avatar = data_dir / f"{parent_id}.png"
            new_avatar = avatars_dir / f"{parent_id}.png"
            if old_avatar.exists() and not new_avatar.exists():
                shutil.move(str(old_avatar), str(avatars_dir / f"{parent_id}.png"))
        _mark_path_as_migrated(parent_path)

    # 3. 合并 disable_parent_data.json / disable_parent_data.json.migrated
    for disable_path in _iter_legacy_paths(data_dir, "disable_parent_data.json"):
        had_legacy_source = True
        old_disable: list[str] = json.loads(disable_path.read_text("utf-8"))
        for parent_id in old_disable:
            config = group_store._get_or_create(parent_id)
            if parent_id not in existing_parent_ids and not config.disabled:
                config.disabled = True
                changed = True
        _mark_path_as_migrated(disable_path)

    # 4. 保存合并后的数据
    if changed:
        group_store.save()
        logger.info("旧数据迁移/恢复完成")
    elif had_legacy_source:
        logger.info("旧数据已存在，跳过重复迁移")

    # 5. steam_info.json 直接标记 migrated（数据由 API 重新获取）
    steam_info_path = data_dir / "steam_info.json"
    if steam_info_path.exists():
        steam_info_path.rename(steam_info_path.with_suffix(".json.migrated"))
        logger.info("旧版 steam_info.json 已标记为 migrated（数据由 API 重新获取）")
