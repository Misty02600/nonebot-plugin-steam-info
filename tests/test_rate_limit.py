"""Steam API 限流逻辑单元测试。

测试 SteamAPIClient._request_with_retry() 和 get_users_info() 的重试、退避、分批延迟行为。
使用 nonebug App fixture 确保 NoneBot 环境正确初始化。

注意：SteamAPIClient 的 import 放在 fixture 中延迟执行，
避免 collection 阶段触发 __init__.py 的 require() 链。
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from nonebug import App

if TYPE_CHECKING:
    from nonebot_plugin_steam_info.infra.steam_client import SteamAPIClient


@pytest.fixture
def client_cls(app: App):
    """延迟 import SteamAPIClient，确保 NoneBot 已初始化。"""
    from nonebot_plugin_steam_info.infra.steam_client import SteamAPIClient

    return SteamAPIClient


def _make_client(
    client_cls: type[SteamAPIClient],
    api_keys: list[str] | None = None,
    max_retries: int = 3,
    batch_delay: float = 1.5,
    backoff_factor: float = 0.01,
) -> SteamAPIClient:
    return client_cls(
        api_keys=api_keys or ["test_api_key_1"],
        max_retries=max_retries,
        batch_delay=batch_delay,
        backoff_factor=backoff_factor,
    )


# ============================================================
# _parse_retry_after 测试
# ============================================================


class TestParseRetryAfter:
    """测试 Retry-After 头解析。"""

    def test_valid_integer(self, client_cls: type[SteamAPIClient]):
        response = MagicMock()
        response.headers = {"Retry-After": "120"}
        assert client_cls._parse_retry_after(response) == 120.0

    def test_valid_float(self, client_cls: type[SteamAPIClient]):
        response = MagicMock()
        response.headers = {"Retry-After": "30.5"}
        assert client_cls._parse_retry_after(response) == 30.5

    def test_missing_header(self, client_cls: type[SteamAPIClient]):
        response = MagicMock()
        response.headers = {}
        assert client_cls._parse_retry_after(response) == 60.0

    def test_invalid_value(self, client_cls: type[SteamAPIClient]):
        response = MagicMock()
        response.headers = {"Retry-After": "invalid"}
        assert client_cls._parse_retry_after(response) == 60.0

    def test_zero_value_clamps_to_one(self, client_cls: type[SteamAPIClient]):
        response = MagicMock()
        response.headers = {"Retry-After": "0"}
        assert client_cls._parse_retry_after(response) == 1.0

    def test_negative_value_clamps_to_one(self, client_cls: type[SteamAPIClient]):
        response = MagicMock()
        response.headers = {"Retry-After": "-5"}
        assert client_cls._parse_retry_after(response) == 1.0


# ============================================================
# get_steam_id 测试
# ============================================================


class TestGetSteamId:
    """测试 Steam ID / 好友码转换。"""

    def test_valid_steam64_id(self, client_cls: type[SteamAPIClient]):
        steam_id = "76561198000000001"
        assert client_cls.get_steam_id(steam_id) == steam_id

    def test_friend_code_to_steam64(self, client_cls: type[SteamAPIClient]):
        # 76561197960265729 - 76561197960265728 = 1
        result = client_cls.get_steam_id("1")
        assert result == "76561197960265729"

    def test_non_digit_returns_none(self, client_cls: type[SteamAPIClient]):
        assert client_cls.get_steam_id("STEAM_0:1:xxxx") is None

    def test_empty_string_returns_none(self, client_cls: type[SteamAPIClient]):
        assert client_cls.get_steam_id("abc") is None


# ============================================================
# Helper
# ============================================================


def _make_response(status_code: int, json_data=None, headers=None):
    """构造模拟的 httpx.Response。"""
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data or {}
    response.headers = headers or {}
    return response


STEAM_IDS = ["76561198000000001"]
GOOD_RESPONSE = {"response": {"players": [{"steamid": "76561198000000001"}]}}


# ============================================================
# _request_with_retry 测试
# ============================================================


class TestRequestWithRetry:
    """测试 _request_with_retry() 的重试逻辑。"""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, client_cls: type[SteamAPIClient]):
        """200 成功响应应直接返回。"""
        client = _make_client(client_cls)
        mock_response = _make_response(200, GOOD_RESPONSE)

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result == GOOD_RESPONSE
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_429_retry_then_success(self, client_cls: type[SteamAPIClient]):
        """429 限流后应等待并重试，最终成功。"""
        client = _make_client(client_cls)
        rate_limited = _make_response(429, headers={"Retry-After": "0.01"})
        success = _make_response(200, GOOD_RESPONSE)

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [rate_limited, success]
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result == GOOD_RESPONSE
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_429_exhausts_retries(self, client_cls: type[SteamAPIClient]):
        """429 限流超过最大重试次数应返回 None。"""
        client = _make_client(client_cls, max_retries=2)
        rate_limited = _make_response(429, headers={"Retry-After": "0.01"})

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = rate_limited
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result is None
        assert mock_client.get.call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_403_switches_key(self, client_cls: type[SteamAPIClient]):
        """403 认证失败应切换到下一个 key。"""
        client = _make_client(client_cls, api_keys=["bad_key", "good_key"])
        auth_failed = _make_response(403)
        success = _make_response(200, GOOD_RESPONSE)

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [auth_failed, success]
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result == GOOD_RESPONSE
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_5xx_retries_with_backoff(self, client_cls: type[SteamAPIClient]):
        """5xx 服务端错误应指数退避后重试。"""
        client = _make_client(client_cls)
        server_error = _make_response(503)
        success = _make_response(200, GOOD_RESPONSE)

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [server_error, success]
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result == GOOD_RESPONSE
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_network_error_retries(self, client_cls: type[SteamAPIClient]):
        """网络错误应指数退避后重试。"""
        client = _make_client(client_cls)
        success = _make_response(200, GOOD_RESPONSE)

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [
                httpx.ConnectError("Connection refused"),
                success,
            ]
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result == GOOD_RESPONSE
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_all_keys_fail_returns_none(self, client_cls: type[SteamAPIClient]):
        """所有 key 都失败应返回 None。"""
        client = _make_client(client_cls, api_keys=["key1", "key2", "key3"])
        auth_failed = _make_response(403)

        with patch(
            "nonebot_plugin_steam_info.infra.steam_client.httpx.AsyncClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = auth_failed
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await client._request_with_retry(STEAM_IDS)

        assert result is None
        assert mock_client.get.call_count == 3  # 一个 key 一次


# ============================================================
# get_users_info 测试
# ============================================================


class TestGetUsersInfo:
    """测试 get_users_info() 的整体行为。"""

    @pytest.mark.asyncio
    async def test_empty_steam_ids(self, client_cls: type[SteamAPIClient]):
        """空 Steam ID 列表应直接返回空。"""
        client = _make_client(client_cls)
        result = await client.get_users_info([])
        assert result == {"response": {"players": []}}

    @pytest.mark.asyncio
    async def test_all_keys_fail_returns_empty(self, client_cls: type[SteamAPIClient]):
        """所有 key 失败时应返回空玩家列表（不抛异常）。"""
        client = _make_client(client_cls)

        with patch.object(client, "_request_with_retry", return_value=None):
            result = await client.get_users_info(["76561198000000001"])

        assert result == {"response": {"players": []}}

    @pytest.mark.asyncio
    async def test_batch_splitting(self, client_cls: type[SteamAPIClient]):
        """超过 100 个 Steam ID 应分批请求。"""
        client = _make_client(client_cls, batch_delay=0.001)
        steam_ids = [f"7656119800000{i:04d}" for i in range(250)]

        batch_results = [
            {"response": {"players": [{"steamid": sid} for sid in steam_ids[:100]]}},
            {"response": {"players": [{"steamid": sid} for sid in steam_ids[100:200]]}},
            {"response": {"players": [{"steamid": sid} for sid in steam_ids[200:]]}},
        ]

        with patch.object(client, "_request_with_retry", side_effect=batch_results):
            result = await client.get_users_info(steam_ids)

        assert len(result["response"]["players"]) == 250
