"""服务实例化

集中管理配置、数据路径和数据实例。
"""

import nonebot
import nonebot_plugin_localstore as store
from nonebot.log import logger

from ..config import Config
from ..infra.draw import check_font, set_font_paths
from ..infra.steam_client import SteamAPIClient
from ..infra.steam_state import SteamInfoState
from ..infra.stores import GroupStore
from ..migration import migrate_legacy_data

# Config
if hasattr(nonebot, "get_plugin_config"):
    config = nonebot.get_plugin_config(Config)
else:
    from nonebot import get_driver

    config = Config.parse_obj(get_driver().config)

set_font_paths(
    config.steam_font_regular_path,
    config.steam_font_light_path,
    config.steam_font_bold_path,
)

# Data paths
data_dir = store.get_data_dir("nonebot_plugin_steam_info")
cache_path = store.get_cache_dir("nonebot_plugin_steam_info")

# Data instances
group_store = GroupStore(data_dir / "groups.json")

# 启动时自动迁移旧数据
migrate_legacy_data(data_dir, group_store)

# 纯内存状态
steam_state = SteamInfoState()

# Steam API Client
client = SteamAPIClient(
    api_keys=config.steam_api_key,
    proxy=config.proxy,
    max_retries=config.steam_api_max_retries,
    batch_delay=config.steam_api_batch_delay,
    backoff_factor=config.steam_api_backoff_factor,
)

# Font check
try:
    check_font()
except FileNotFoundError as e:
    logger.error(
        f"{e}, nonebot_plugin_steam_info 无法使用，请参照 `https://github.com/zhaomaoniu/nonebot-plugin-steam-info` 配置字体文件"
    )
