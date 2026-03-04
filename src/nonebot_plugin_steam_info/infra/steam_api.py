from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import anyio
import httpx
from bs4 import BeautifulSoup, Tag
from nonebot.log import logger

from ..core.models import PlayerData, PlayerSummaries

STEAM_ID_OFFSET = 76561197960265728

STEAM_API_URL = (
    "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    "?key={key}&steamids={steamids}"
)


def get_steam_id(steam_id_or_steam_friends_code: str) -> str | None:
    if not steam_id_or_steam_friends_code.isdigit():
        return None

    id_ = int(steam_id_or_steam_friends_code)

    if id_ < STEAM_ID_OFFSET:
        return str(id_ + STEAM_ID_OFFSET)

    return steam_id_or_steam_friends_code


async def _request_with_retry(
    steam_ids: list[str],
    api_keys: list[str],
    proxy: str | None = None,
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> PlayerSummaries | None:
    """带重试和退避的 Steam API 请求。

    限流策略：
    - 429（Rate Limited）：解析 Retry-After 头，等待后同一个 key 重试
    - 403（Auth Failed）：切换下一个 key
    - 5xx（Server Error）：指数退避后重试
    - 网络错误：指数退避后重试
    """
    steamids_str = ",".join(steam_ids)

    for api_key in api_keys:
        key_preview = api_key[:8] + "..." if len(api_key) > 8 else api_key
        retry_count = 0

        while retry_count <= max_retries:
            try:
                async with httpx.AsyncClient(proxy=proxy) as client:
                    url = STEAM_API_URL.format(key=api_key, steamids=steamids_str)
                    response = await client.get(url)

                    if response.status_code == 200:
                        return response.json()

                    elif response.status_code == 429:
                        # 限流：解析 Retry-After 头，同一个 key 等待后重试
                        retry_after = _parse_retry_after(response)
                        retry_count += 1
                        if retry_count > max_retries:
                            logger.warning(
                                f"API key {key_preview} 达到最大重试次数 "
                                f"({max_retries})，切换下一个 key"
                            )
                            break
                        logger.warning(
                            f"Steam API 限流 (429)，Retry-After: {retry_after}s，"
                            f"等待后重试 ({retry_count}/{max_retries})"
                        )
                        await asyncio.sleep(retry_after)
                        continue

                    elif response.status_code == 403:
                        # 认证失败：切换 key
                        logger.warning(
                            f"API key {key_preview} 认证失败 (403)，切换下一个 key"
                        )
                        break

                    elif response.status_code >= 500:
                        # 服务端错误：指数退避后重试
                        retry_count += 1
                        if retry_count > max_retries:
                            logger.warning(
                                f"API key {key_preview} 服务端错误 "
                                f"({response.status_code})，"
                                f"达到最大重试次数，切换下一个 key"
                            )
                            break
                        wait_time = backoff_factor**retry_count
                        logger.warning(
                            f"Steam API 服务端错误 ({response.status_code})，"
                            f"等待 {wait_time:.1f}s 后重试 "
                            f"({retry_count}/{max_retries})"
                        )
                        await asyncio.sleep(wait_time)
                        continue

                    else:
                        # 其他未知状态码
                        logger.warning(
                            f"API key {key_preview} 未知响应状态 "
                            f"({response.status_code})，切换下一个 key"
                        )
                        break

            except httpx.RequestError as exc:
                retry_count += 1
                if retry_count > max_retries:
                    logger.warning(
                        f"API key {key_preview} 网络错误，"
                        f"达到最大重试次数，切换下一个 key: {exc}"
                    )
                    break
                wait_time = backoff_factor**retry_count
                logger.warning(
                    f"Steam API 网络错误: {exc}，等待 {wait_time:.1f}s 后重试 "
                    f"({retry_count}/{max_retries})"
                )
                await asyncio.sleep(wait_time)

    return None


def _parse_retry_after(response: httpx.Response) -> float:
    """解析 Retry-After 响应头，返回等待秒数。

    Steam 通常返回 60-120 秒。如果头不存在或无法解析，默认 60 秒。
    """
    retry_after = response.headers.get("Retry-After")
    if retry_after is None:
        return 60.0
    try:
        return max(float(retry_after), 1.0)
    except (ValueError, TypeError):
        return 60.0


async def get_steam_users_info(
    steam_ids: list[str],
    steam_api_key: list[str],
    proxy: str | None = None,
    max_retries: int = 3,
    batch_delay: float = 1.5,
    backoff_factor: float = 2.0,
) -> PlayerSummaries:
    if len(steam_ids) == 0:
        return cast(PlayerSummaries, {"response": {"players": []}})

    if len(steam_ids) > 100:
        # 分批获取，批次间添加延迟
        result: PlayerSummaries = cast(PlayerSummaries, {"response": {"players": []}})
        for i in range(0, len(steam_ids), 100):
            if i > 0:
                logger.debug(f"分批请求间隔 {batch_delay}s...")
                await asyncio.sleep(batch_delay)
            batch_result = await get_steam_users_info(
                steam_ids[i : i + 100],
                steam_api_key,
                proxy,
                max_retries=max_retries,
                batch_delay=batch_delay,
                backoff_factor=backoff_factor,
            )
            result["response"]["players"].extend(batch_result["response"]["players"])
        return result

    data = await _request_with_retry(
        steam_ids, steam_api_key, proxy, max_retries, backoff_factor
    )

    if data is not None:
        return data

    logger.error("所有 API Key 均无法获取 Steam 用户信息")
    return cast(PlayerSummaries, {"response": {"players": []}})


async def _fetch(
    url: str, default: bytes, cache_file: Path | None = None, proxy: str | None = None
) -> bytes:
    if cache_file is not None:
        apath = anyio.Path(cache_file)
        if await apath.exists():
            return await apath.read_bytes()
    try:
        async with httpx.AsyncClient(proxy=proxy) as client:
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


async def get_user_data(
    steam_id: int, cache_path: Path | None = None, proxy: str | None = None
) -> PlayerData:
    url = f"https://steamcommunity.com/profiles/{steam_id}"
    default_background = (Path(__file__).parent.parent / "res/bg_dots.png").read_bytes()
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
            proxy=proxy,
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
    except httpx.RequestError as exc:
        logger.error(f"Failed to get user data: {exc}")
        return cast(PlayerData, result)

    # player name
    player_name = re.search(r"<title>Steam 社区 :: (.*?)</title>", html)
    if player_name:
        result["player_name"] = player_name.group(1)

    # description t<div class="profile_summary">\r\n\t\t\t\t\t\t\t\t風が雨が激しくても<br>思いだすんだ 僕らを照らす光があるよ<br>今日もいっぱい<br>明日もいっぱい 力を出しきってみるよ\t\t\t\t\t\t\t</div>
    description = re.search(
        r'<div class="profile_summary">(.*?)</div>', html, re.DOTALL | re.MULTILINE
    )
    if description:
        description = description.group(1)
        description = re.sub(r"<br>", "\n", description)
        description = re.sub(r"\t", "", description)
        result["description"] = description.strip()

    # remove emoji
    result["description"] = re.sub(r"ː.*?ː", "", result["description"])

    # remove xml
    result["description"] = re.sub(r"<.*?>", "", result["description"])

    # background
    background_url = re.search(r"background-image: url\( \'(.*?)\' \)", html)
    if background_url:
        background_url = background_url.group(1)
        result["background"] = await _fetch(
            background_url, default_background, proxy=proxy
        )

    # avatar
    # \t<link rel="image_src" href="https://avatars.akamai.steamstatic.com/3ade30f61c3d2cc0b8c80aaf567b573cd022c405_full.jpg">
    avatar_url = re.search(r'<link rel="image_src" href="(.*?)"', html)
    if avatar_url:
        avatar_url = avatar_url.group(1)
        avatar_url_split = avatar_url.split("/")
        avatar_file = (
            cache_path / f"avatar_{avatar_url_split[-1].split('_')[0]}.jpg"
            if cache_path
            else None
        )
        result["avatar"] = await _fetch(
            avatar_url, default_avatar, cache_file=avatar_file, proxy=proxy
        )

    # recent 2 week play time
    # \t<div class="recentgame_quicklinks recentgame_recentplaytime">\r\n\t\t\t\t\t\t\t\t\t<div>15.5 小时（过去 2 周）</div>
    play_time_text = re.search(
        r'<div class="recentgame_quicklinks recentgame_recentplaytime">\s*<div>(.*?)</div>',
        html,
    )
    if play_time_text:
        play_time_text = play_time_text.group(1)
        result["recent_2_week_play_time"] = play_time_text

    # game data
    soup = BeautifulSoup(html, "html.parser")
    game_data = []
    recent_games = soup.find_all("div", class_="recent_game")

    for game in recent_games:
        game_info = {}
        game_name_el = game.find("div", class_="game_name")
        game_info["game_name"] = game_name_el.text.strip() if game_name_el else ""
        game_capsule_el = game.find("img", class_="game_capsule")
        game_info["game_image_url"] = (
            str(game_capsule_el["src"]) if isinstance(game_capsule_el, Tag) else ""
        )
        # https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/1144400/capsule_184x69_schinese.jpg?t=1724440433

        game_info_split = game_info["game_image_url"].split("/")
        game_info["game_image"] = await _fetch(
            game_info["game_image_url"],
            default_header_image,
            cache_file=cache_path / f"header_{game_info_split[-2]}.jpg"
            if cache_path
            else None,
            proxy=proxy,
        )

        game_info_details_el = game.find("div", class_="game_info_details")
        play_time_text = (
            game_info_details_el.text.strip() if game_info_details_el else ""
        )
        play_time = re.search(r"总时数\s*(.*?)\s*小时", play_time_text)
        if play_time is None:
            game_info["play_time"] = ""
        else:
            game_info["play_time"] = play_time.group(1)

        last_played = re.search(r"最后运行日期：(.*) 日", play_time_text)
        if last_played is not None:
            game_info["last_played"] = "最后运行日期：" + last_played.group(1) + " 日"
        else:
            game_info["last_played"] = "当前正在游戏"
        achievements = []
        achievement_elements = game.find_all("div", class_="game_info_achievement")
        for achievement in achievement_elements:
            if "plus_more" in achievement["class"]:
                continue
            achievement_info = {}
            achievement_info["name"] = achievement.get("data-tooltip-text", "")
            achievement_img_el = achievement.find("img")
            achievement_info["image_url"] = (
                str(achievement_img_el["src"])
                if isinstance(achievement_img_el, Tag)
                else ""
            )
            achievement_info_split = achievement_info["image_url"].split("/")

            achievement_info["image"] = await _fetch(
                achievement_info["image_url"],
                default_achievement_image,
                cache_file=cache_path
                / f"achievement_{achievement_info_split[-2]}_{achievement_info_split[-1]}"
                if cache_path
                else None,
                proxy=proxy,
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


if __name__ == "__main__":
    import asyncio

    from nonebot.log import logger

    data = asyncio.run(get_user_data(76561199135038179, None))

    with open("bg.jpg", "wb") as f:
        f.write(data["background"])
    logger.info(data["description"])
