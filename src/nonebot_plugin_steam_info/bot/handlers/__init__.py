"""命令模块

所有 NoneBot 命令处理器的统一入口。
通过导入此模块来注册所有命令。
"""

from . import (
    bind,
    broadcast,
    cache,
    check,
    help,
    info,
    nickname,
    parent,
    scheduled,
)

__all__ = [
    "bind",
    "broadcast",
    "cache",
    "check",
    "help",
    "info",
    "nickname",
    "parent",
    "scheduled",
]
