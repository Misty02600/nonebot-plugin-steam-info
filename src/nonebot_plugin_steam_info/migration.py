"""旧数据迁移模块 — 启动时自动执行"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from nonebot.log import logger

from .core.data_models import BindRecord
from .infra.stores import GroupStore


def migrate_legacy_data(
    data_dir: Path,
    group_store: GroupStore,
) -> None:
    """检测并迁移旧版 JSON 数据

    旧文件格式：
    - bind_data.json              → dict[str, list[dict[str, str]]]
    - parent_data.json            → dict[str, str]  (parent_id → name)
    - disable_parent_data.json    → list[str]
    - {parent_id}.png             → 群头像（在数据根目录）

    迁移后旧文件重命名为 .json.migrated
    """
    migrated = False

    # 1. 迁移 bind_data.json
    bind_path = data_dir / "bind_data.json"
    if bind_path.exists():
        logger.info("检测到旧版 bind_data.json，开始迁移...")
        old_bind: dict[str, list[dict[str, str]]] = json.loads(
            bind_path.read_text("utf-8")
        )
        for parent_id, records in old_bind.items():
            config = group_store._get_or_create(parent_id)
            for record in records:
                config.binds.append(
                    BindRecord(
                        user_id=record["user_id"],
                        steam_id=record["steam_id"],
                        nickname=record.get("nickname", ""),
                    )
                )
        bind_path.rename(bind_path.with_suffix(".json.migrated"))
        migrated = True

    # 2. 迁移 parent_data.json
    parent_path = data_dir / "parent_data.json"
    if parent_path.exists():
        logger.info("检测到旧版 parent_data.json，开始迁移...")
        old_parent: dict[str, str] = json.loads(parent_path.read_text("utf-8"))
        avatars_dir = data_dir / "avatars"
        avatars_dir.mkdir(exist_ok=True)
        for parent_id, name in old_parent.items():
            config = group_store._get_or_create(parent_id)
            config.name = name
            # 迁移头像文件到 avatars/ 子目录
            old_avatar = data_dir / f"{parent_id}.png"
            if old_avatar.exists():
                shutil.move(str(old_avatar), str(avatars_dir / f"{parent_id}.png"))
        parent_path.rename(parent_path.with_suffix(".json.migrated"))
        migrated = True

    # 3. 迁移 disable_parent_data.json
    disable_path = data_dir / "disable_parent_data.json"
    if disable_path.exists():
        logger.info("检测到旧版 disable_parent_data.json，开始迁移...")
        old_disable: list[str] = json.loads(disable_path.read_text("utf-8"))
        for parent_id in old_disable:
            group_store._get_or_create(parent_id).disabled = True
        disable_path.rename(disable_path.with_suffix(".json.migrated"))
        migrated = True

    # 4. 保存合并后的数据
    if migrated:
        group_store.save()
        logger.info("旧数据迁移完成")

    # 5. steam_info.json 直接标记 migrated（数据由 API 重新获取）
    steam_info_path = data_dir / "steam_info.json"
    if steam_info_path.exists():
        steam_info_path.rename(steam_info_path.with_suffix(".json.migrated"))
        logger.info("旧版 steam_info.json 已标记为 migrated（数据由 API 重新获取）")
