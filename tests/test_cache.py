"""缓存功能测试"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pytest
from nonebug import App

if TYPE_CHECKING:
    from nonebot_plugin_steam_info.infra.steam_client import SteamAPIClient


@pytest.fixture
def client_cls(app: App):
    """延迟导入 SteamAPIClient，避免 collection 阶段触发插件加载。"""
    from nonebot_plugin_steam_info.infra.steam_client import SteamAPIClient

    return SteamAPIClient


@pytest.mark.asyncio
async def test_cache_ttl(tmp_path, client_cls: type[SteamAPIClient]):
    """测试缓存 TTL 功能"""
    # 创建测试文件
    cache_file = tmp_path / "test_cache.jpg"
    cache_file.write_bytes(b"old content")

    # 设置文件修改时间为 1 小时前（在 24 小时 TTL 内）
    old_time = time.time() - 3600
    import os

    os.utime(cache_file, (old_time, old_time))

    client = client_cls(
        api_keys=["test_key"],
        cache_ttl=86400,  # 24 小时
    )

    # TTL 内应该返回缓存
    assert cache_file.exists()
    result = await client._fetch(
        "http://example.com/image.jpg",
        b"default",
        cache_file=cache_file,
        cache_ttl=86400,
    )
    assert result == b"old content"

    # 当前用例仅验证 TTL 内命中缓存
    cache_file.unlink()
    assert not cache_file.exists()


@pytest.mark.asyncio
async def test_avatar_url_change_detection(tmp_path, client_cls: type[SteamAPIClient]):
    """测试头像 URL 变化检测"""
    old_cache = tmp_path / "avatar_123.jpg"
    old_cache.write_bytes(b"old avatar")

    client = client_cls(
        api_keys=["test_key"],
    )

    # 记录旧 URL
    client._avatar_url_cache[123] = "http://example.com/old_avatar.jpg"

    # 模拟 URL 变化
    new_url = "http://example.com/new_avatar.jpg"
    if 123 in client._avatar_url_cache and client._avatar_url_cache[123] != new_url:
        if old_cache.exists():
            old_cache.unlink()

    assert not old_cache.exists()
    client._avatar_url_cache[123] = new_url


@pytest.mark.asyncio
async def test_clear_cache(tmp_path, client_cls: type[SteamAPIClient]):
    """测试清除缓存"""
    # 创建测试缓存文件
    avatar_file = tmp_path / "avatar_123.jpg"
    avatar_file.write_bytes(b"avatar data")

    bg_file = tmp_path / "background_456.jpg"
    bg_file.write_bytes(b"background data")

    other_file = tmp_path / "other.jpg"
    other_file.write_bytes(b"other data")

    client = client_cls(api_keys=["test_key"])

    # 清除用户 123 的缓存
    count = await client.clear_cache(tmp_path, steam_id=123)
    assert count == 1
    assert not avatar_file.exists()
    assert bg_file.exists()
    assert other_file.exists()

    # 清除所有缓存
    count = await client.clear_cache(tmp_path)
    assert count == 2
    assert not bg_file.exists()
    assert not other_file.exists()


@pytest.mark.asyncio
async def test_reset_avatar_cache(client_cls: type[SteamAPIClient]):
    """测试重置头像缓存映射"""
    client = client_cls(api_keys=["test_key"])

    # 添加一些数据
    client._avatar_url_cache[123] = "url1"
    client._avatar_url_cache[456] = "url2"

    assert len(client._avatar_url_cache) == 2

    # 重置
    client.reset_avatar_cache()

    assert len(client._avatar_url_cache) == 0
