from nonebot import require
from nonebot.plugin import PluginMetadata, inherit_supported_adapters

require("nonebot_plugin_alconna")
require("nonebot_plugin_localstore")
require("nonebot_plugin_apscheduler")

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="Steam Info",
    description="播报绑定的 Steam 好友状态",
    usage="""
steamhelp: 查看帮助
steambind [Steam ID 或 Steam 好友代码]: 绑定 Steam ID
steamunbind: 解绑 Steam ID
steaminfo (可选)[@某人 或 Steam ID 或 Steam好友代码]: 查看 Steam 主页
steamcheck: 查看 Steam 好友状态
steamenable: 启用 Steam 播报
steamdisable: 禁用 Steam 播报
steamupdate [名称] [图片]: 更新群信息
steamnickname [昵称]: 设置玩家昵称
""".strip(),
    type="application",
    homepage="https://github.com/zhaomaoniu/nonebot-plugin-steam-info",
    config=Config,
    supported_adapters=inherit_supported_adapters("nonebot_plugin_alconna"),
)

# 导入 handlers 以注册所有命令处理器
from .bot import handlers as handlers

