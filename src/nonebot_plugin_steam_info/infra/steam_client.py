"""Steam API 客户端"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import anyio
import httpx
from bs4 import BeautifulSoup, Tag
from nonebot.log import logger

from ..core.models import PlayerData, PlayerSummaries


class SteamAPIClient:
    """Steam Web API 客户端"""

    STEAM_ID_OFFSET = 76561197960265728
    STEAM_API_URL = (
        "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
        "?key={key}&steamids={steamids}"
    )
    # 单次请求最多 100 个 steamid（Steam 官方硬限制）
    MAX_BATCH = 100

    def __init__(
        self,
        api_keys: list[str],
        proxy: str | None = None,
        max_retries: int = 3,
        batch_delay: float = 1.5,
        backoff_factor: float = 2.0,
        cache_ttl: int = 86400,
    ) -> None:
        self._api_keys = api_keys
        self._proxy = proxy
        self._max_retries = max_retries
        self._batch_delay = batch_delay
        self._backoff_factor = backoff_factor
        self._cache_ttl = cache_ttl  # 缓存过期时间（秒），默认 24 小时
        # 存储 steamid -> avatar_url 的映射，用于检测头像是否变化
        self._avatar_url_cache: dict[int, str] = {}

    async def get_users_info(self, steam_ids: list[str]) -> PlayerSummaries:
        """获取多个用户信息（自动分批 + 重试 + key 轮换）"""
        if len(steam_ids) == 0:
            return cast(PlayerSummaries, {"response": {"players": []}})

        if len(steam_ids) > self.MAX_BATCH:
            # 分批获取，批次间添加延迟
            result: PlayerSummaries = cast(
                PlayerSummaries, {"response": {"players": []}}
            )
            for i in range(0, len(steam_ids), self.MAX_BATCH):
                if i > 0:
                    logger.debug(f"分批请求间隔 {self._batch_delay}s...")
                    await asyncio.sleep(self._batch_delay)
                batch_result = await self.get_users_info(
                    steam_ids[i : i + self.MAX_BATCH]
                )
                result["response"]["players"].extend(
                    batch_result["response"]["players"]
                )
            return result

        data = await self._request_with_retry(steam_ids)
        if data is not None:
            return data

        logger.error("所有 API Key 均无法获取 Steam 用户信息")
        return cast(PlayerSummaries, {"response": {"players": []}})

    async def get_user_data(
        self, steam_id: int, cache_path: Path | None = None
    ) -> PlayerData:
        """通过爬取个人主页获取详细用户数据"""
        url = f"https://steamcommunity.com/profiles/{steam_id}"
        default_background = (
            Path(__file__).parent.parent / "res/bg_dots.png"
        ).read_bytes()
        default_avatar = (
            Path(__file__).parent.parent / "res/unknown_avatar.jpg"
        ).read_bytes()
        default_achievement_image = (
            Path(__file__).parent.parent / "res/default_achievement_image.png"
        ).read_bytes()
        default_header_image = (
            Path(__file__).parent.parent / "res/default_header_image.jpg"
        ).read_bytes()

        result: dict[str, Any] = {
            "description": "No information given.",
            "background": default_background,
            "avatar": default_avatar,
            "player_name": "Unknown",
            "recent_2_week_play_time": None,
            "game_data": [],
        }

        local_time = datetime.now(timezone.utc).astimezone()
        utc_offset = local_time.utcoffset()
        utc_offset_minutes = int(utc_offset.total_seconds()) if utc_offset else 0
        timezone_cookie_value = f"{utc_offset_minutes},0"

        try:
            async with httpx.AsyncClient(
                proxy=self._proxy,
                headers={
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"
                },
                cookies={"timezoneOffset": timezone_cookie_value},
            ) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    html = response.text
                elif response.status_code == 302:
                    url = response.headers["Location"]
                    response = await client.get(url)
                    if response.status_code == 200:
                        html = response.text
                    else:
                        response.raise_for_status()
                        return cast(PlayerData, result)
                else:
                    response.raise_for_status()
                    return cast(PlayerData, result)
        except httpx.RequestError as exc:
            logger.error(f"Failed to get user data: {exc}")
            return cast(PlayerData, result)

        # player name
        player_name = re.search(r"<title>Steam 社区 :: (.*?)</title>", html)
        if player_name:
            result["player_name"] = player_name.group(1)

        # description
        description = re.search(
            r'<div class="profile_summary">(.*?)</div>', html, re.DOTALL | re.MULTILINE
        )
        if description:
            desc_text = description.group(1)
            desc_text = re.sub(r"<br>", "\n", desc_text)
            desc_text = re.sub(r"\t", "", desc_text)
            result["description"] = desc_text.strip()

        # remove emoji
        result["description"] = re.sub(r"ː.*?ː", "", result["description"])

        # remove xml
        result["description"] = re.sub(r"<.*?>", "", result["description"])

        # background
        background_url = re.search(r"background-image: url\( \'(.*?)\' \)", html)
        if background_url:
            bg_url = background_url.group(1)
            bg_split = bg_url.split("/")
            bg_file = (
                cache_path / f"background_{bg_split[-1].split('_')[0]}.jpg"
                if cache_path
                else None
            )
            result["background"] = await self._fetch(
                bg_url,
                default_background,
                cache_file=bg_file,
                cache_ttl=self._cache_ttl,
            )

        # avatar
        avatar_url = re.search(r'<link rel="image_src" href="(.*?)"', html)
        if avatar_url:
            av_url = avatar_url.group(1)
            av_split = av_url.split("/")
            avatar_file = (
                cache_path / f"avatar_{av_split[-1].split('_')[0]}.jpg"
                if cache_path
                else None
            )
            # 检查头像 URL 是否变化，如果变化则删除旧缓存
            if (
                steam_id in self._avatar_url_cache
                and self._avatar_url_cache[steam_id] != av_url
            ):
                if avatar_file and avatar_file.exists():
                    avatar_file.unlink()
                    logger.debug(f"删除过期的头像缓存: {avatar_file}")
            self._avatar_url_cache[steam_id] = av_url
            result["avatar"] = await self._fetch(
                av_url,
                default_avatar,
                cache_file=avatar_file,
                cache_ttl=self._cache_ttl,
            )

        # recent 2 week play time
        play_time_text = re.search(
            r'<div class="recentgame_quicklinks recentgame_recentplaytime">\s*<div>(.*?)</div>',
            html,
        )
        if play_time_text:
            result["recent_2_week_play_time"] = play_time_text.group(1)

        # game data
        soup = BeautifulSoup(html, "html.parser")
        game_data = []
        recent_games = soup.find_all("div", class_="recent_game")

        for game in recent_games:
            game_info: dict[str, Any] = {}
            game_name_el = game.find("div", class_="game_name")
            game_info["game_name"] = game_name_el.text.strip() if game_name_el else ""
            game_capsule_el = game.find("img", class_="game_capsule")
            game_info["game_image_url"] = (
                str(game_capsule_el["src"]) if isinstance(game_capsule_el, Tag) else ""
            )

            game_info_split = game_info["game_image_url"].split("/")
            game_info["game_image"] = await self._fetch(
                game_info["game_image_url"],
                default_header_image,
                cache_file=cache_path / f"header_{game_info_split[-2]}.jpg"
                if cache_path
                else None,
                cache_ttl=self._cache_ttl,
            )

            game_info_details_el = game.find("div", class_="game_info_details")
            play_time_info = (
                game_info_details_el.text.strip() if game_info_details_el else ""
            )
            play_time = re.search(r"总时数\s*(.*?)\s*小时", play_time_info)
            game_info["play_time"] = play_time.group(1) if play_time else ""

            last_played = re.search(r"最后运行日期：(.*) 日", play_time_info)
            if last_played is not None:
                game_info["last_played"] = (
                    "最后运行日期：" + last_played.group(1) + " 日"
                )
            else:
                game_info["last_played"] = "当前正在游戏"

            achievements = []
            achievement_elements = game.find_all("div", class_="game_info_achievement")
            for achievement in achievement_elements:
                if "plus_more" in achievement["class"]:
                    continue
                achievement_info: dict[str, Any] = {}
                achievement_info["name"] = achievement.get("data-tooltip-text", "")
                achievement_img_el = achievement.find("img")
                achievement_info["image_url"] = (
                    str(achievement_img_el["src"])
                    if isinstance(achievement_img_el, Tag)
                    else ""
                )
                ach_split = achievement_info["image_url"].split("/")
                achievement_info["image"] = await self._fetch(
                    achievement_info["image_url"],
                    default_achievement_image,
                    cache_file=cache_path
                    / f"achievement_{ach_split[-2]}_{ach_split[-1]}"
                    if cache_path
                    else None,
                    cache_ttl=self._cache_ttl,
                )
                achievements.append(achievement_info)
            game_info["achievements"] = achievements

            game_info_achievement_summary = game.find(
                "span", class_="game_info_achievement_summary"
            )
            if game_info_achievement_summary is None:
                game_data.append(game_info)
                continue
            remain_achievement_el = game_info_achievement_summary.find(
                "span", class_="ellipsis"
            )
            if remain_achievement_el is None:
                game_data.append(game_info)
                continue
            remain_achievement_text = remain_achievement_el.text
            game_info["completed_achievement_number"] = int(
                remain_achievement_text.split("/")[0].strip()
            )
            game_info["total_achievement_number"] = int(
                remain_achievement_text.split("/")[1].strip()
            )

            game_data.append(game_info)

        result["game_data"] = game_data

        return cast(PlayerData, result)

    async def _request_with_retry(self, steam_ids: list[str]) -> PlayerSummaries | None:
        """带重试和退避的 Steam API 请求。

        限流策略：
        - 429（Rate Limited）：解析 Retry-After 头，等待后同一个 key 重试
        - 403（Auth Failed）：切换下一个 key
        - 5xx（Server Error）：指数退避后重试
        - 网络错误：指数退避后重试
        """
        steamids_str = ",".join(steam_ids)

        for api_key in self._api_keys:
            key_preview = api_key[:8] + "..." if len(api_key) > 8 else api_key
            retry_count = 0

            while retry_count <= self._max_retries:
                try:
                    async with httpx.AsyncClient(proxy=self._proxy) as client:
                        url = self.STEAM_API_URL.format(
                            key=api_key, steamids=steamids_str
                        )
                        response = await client.get(url)

                        if response.status_code == 200:
                            return response.json()

                        elif response.status_code == 429:
                            retry_after = self._parse_retry_after(response)
                            retry_count += 1
                            if retry_count > self._max_retries:
                                logger.warning(
                                    f"API key {key_preview} 达到最大重试次数 "
                                    f"({self._max_retries})，切换下一个 key"
                                )
                                break
                            logger.warning(
                                f"Steam API 限流 (429)，Retry-After: {retry_after}s，"
                                f"等待后重试 ({retry_count}/{self._max_retries})"
                            )
                            await asyncio.sleep(retry_after)
                            continue

                        elif response.status_code == 403:
                            logger.warning(
                                f"API key {key_preview} 认证失败 (403)，切换下一个 key"
                            )
                            break

                        elif response.status_code >= 500:
                            retry_count += 1
                            if retry_count > self._max_retries:
                                logger.warning(
                                    f"API key {key_preview} 服务端错误 "
                                    f"({response.status_code})，"
                                    f"达到最大重试次数，切换下一个 key"
                                )
                                break
                            wait_time = self._backoff_factor**retry_count
                            logger.warning(
                                f"Steam API 服务端错误 ({response.status_code})，"
                                f"等待 {wait_time:.1f}s 后重试 "
                                f"({retry_count}/{self._max_retries})"
                            )
                            await asyncio.sleep(wait_time)
                            continue

                        else:
                            logger.warning(
                                f"API key {key_preview} 未知响应状态 "
                                f"({response.status_code})，切换下一个 key"
                            )
                            break

                except httpx.RequestError as exc:
                    retry_count += 1
                    if retry_count > self._max_retries:
                        logger.warning(
                            f"API key {key_preview} 网络错误，"
                            f"达到最大重试次数，切换下一个 key: {exc}"
                        )
                        break
                    wait_time = self._backoff_factor**retry_count
                    logger.warning(
                        f"Steam API 网络错误: {exc}，等待 {wait_time:.1f}s 后重试 "
                        f"({retry_count}/{self._max_retries})"
                    )
                    await asyncio.sleep(wait_time)

        return None

    async def _fetch(
        self,
        url: str,
        default: bytes,
        cache_file: Path | None = None,
        cache_ttl: int | None = None,
    ) -> bytes:
        """获取远程资源，支持 TTL 缓存清理。

        Args:
            url: 资源 URL
            default: 获取失败时的默认值
            cache_file: 缓存文件路径
            cache_ttl: 缓存过期时间（秒），为 None 时不检查 TTL
        """
        if cache_file is not None:
            apath = anyio.Path(cache_file)
            if await apath.exists():
                # 检查缓存是否过期
                if cache_ttl is not None:
                    try:
                        stat = await apath.stat()
                        age = time.time() - stat.st_mtime
                        if age < cache_ttl:
                            return await apath.read_bytes()
                        # 缓存已过期，删除它
                        await apath.unlink()
                        logger.debug(f"缓存已过期，删除: {cache_file}")
                    except (OSError, ValueError) as e:
                        logger.warning(f"检查缓存失败: {e}")
                else:
                    # 不检查 TTL，直接返回
                    return await apath.read_bytes()

        try:
            async with httpx.AsyncClient(proxy=self._proxy) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    if cache_file is not None:
                        await anyio.Path(cache_file).write_bytes(response.content)
                    return response.content
                else:
                    response.raise_for_status()
        except Exception as exc:
            logger.error(f"Failed to get image: {exc}")
        return default

    @classmethod
    def get_steam_id(cls, steam_id_or_steam_friends_code: str) -> str | None:
        """将好友码或 Steam ID 转换为 64 位 Steam ID"""
        if not steam_id_or_steam_friends_code.isdigit():
            return None

        id_ = int(steam_id_or_steam_friends_code)

        if id_ < cls.STEAM_ID_OFFSET:
            return str(id_ + cls.STEAM_ID_OFFSET)

        return steam_id_or_steam_friends_code

    async def clear_cache(self, cache_path: Path, steam_id: int | None = None) -> int:
        """清除缓存文件。

        Args:
            cache_path: 缓存目录路径
            steam_id: 清除特定用户的缓存，为 None 时清除所有

        Returns:
            清除的文件数
        """
        apath = anyio.Path(cache_path)
        if not await apath.exists():
            return 0

        count = 0

        try:
            async for entry in apath.iterdir():
                if steam_id is not None:
                    # 只清除特定用户的缓存
                    if entry.name.startswith(
                        f"avatar_{steam_id}"
                    ) or entry.name.startswith(f"background_{steam_id}"):
                        await entry.unlink()
                        count += 1
                        logger.debug(f"删除缓存: {entry.name}")
                else:
                    # 清除所有缓存
                    await entry.unlink()
                    count += 1
                    logger.debug(f"删除缓存: {entry.name}")
        except Exception as exc:
            logger.error(f"清除缓存失败: {exc}")

        return count

    def reset_avatar_cache(self) -> None:
        """重置头像 URL 缓存映射。用于测试或特殊需求。"""
        self._avatar_url_cache.clear()
        logger.debug("重置头像缓存映射")

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        """解析 Retry-After 响应头，返回等待秒数。"""
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return 60.0
        try:
            return max(float(retry_after), 1.0)
        except (ValueError, TypeError):
            return 60.0

    def clear_avatar_cache(self, cache_path: Path, steam_id: int | None = None) -> None:
        """清除头像缓存。

        Args:
            cache_path: 缓存目录路径
            steam_id: 特定用户 ID，为 None 时清除所有头像缓存
        """
        if steam_id is not None:
            # 清除特定用户的头像
            steam_id_str = str(steam_id).split("_")[0]  # 获取 steam_id 哈希
            pattern = f"avatar_{steam_id_str}*.jpg"
            for f in cache_path.glob(pattern):
                try:
                    f.unlink()
                    logger.info(f"删除头像缓存: {f}")
                except OSError as e:
                    logger.warning(f"删除缓存失败 {f}: {e}")
            # 从映射中移除
            if steam_id in self._avatar_url_cache:
                del self._avatar_url_cache[steam_id]
        else:
            # 清除所有头像缓存
            for f in cache_path.glob("avatar_*.jpg"):
                try:
                    f.unlink()
                    logger.info(f"删除头像缓存: {f}")
                except OSError as e:
                    logger.warning(f"删除缓存失败 {f}: {e}")
            self._avatar_url_cache.clear()
            logger.info("已清除所有头像缓存")
