"""缓存管理命令处理器"""

from nonebot import on_command
from nonebot.adapters import Message
from nonebot.log import logger
from nonebot.params import CommandArg, Depends
from nonebot_plugin_alconna import Target

from ..nonebot_utils import get_target
from ..service import cache_path, client

# 清除缓存命令（仅管理员可用）
clear_cache = on_command(
    "steamcache",
    aliases={"清除steam缓存", "清steam缓存"},
    priority=10,
    block=True,
)


@clear_cache.handle()
async def clear_cache_handle(
    target: Target = Depends(get_target), arg: Message = CommandArg()
):
    """清除所有 Steam 缓存或特定用户缓存

    使用方法：
    - steamcache all / 清除steam缓存 all    # 清除所有缓存
    - steamcache [steamid]                  # 清除指定用户缓存
    """
    # 检查权限（仅管理员）
    if not getattr(target, "is_admin", False):
        await clear_cache.finish("❌ 仅管理员可以使用此命令")
        return

    arg_text = arg.extract_plain_text().strip()

    if arg_text.lower() in ("all", "全部", ""):
        # 清除所有缓存
        count = await client.clear_cache(cache_path)
        await clear_cache.finish(f"✅ 已清除所有 Steam 缓存，共 {count} 个文件")
    else:
        try:
            steam_id = int(arg_text)
            count = await client.clear_cache(cache_path, steam_id=steam_id)
            if count > 0:
                await clear_cache.finish(
                    f"✅ 已清除用户 {steam_id} 的缓存，共 {count} 个文件"
                )
            else:
                await clear_cache.finish(f"ℹ️ 用户 {steam_id} 没有缓存文件")
        except ValueError:
            await clear_cache.finish(f"❌ 无效的 Steam ID: {arg_text}")
        except Exception as exc:
            logger.error(f"清除缓存出错: {exc}")
            await clear_cache.finish(f"❌ 清除缓存失败: {exc}")
