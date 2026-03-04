# Project Brief

## 项目名称
nonebot-plugin-steam-info

## 项目概述
一个基于 NoneBot2 的 Steam 好友状态播报插件。支持绑定 Steam ID、查询群友状态、展示个人 Steam 主页等功能。支持跨平台，画图部分 100% 使用 Pillow 实现，较无头浏览器渲染更加轻量高效。

## 核心功能
1. **绑定 Steam ID** - 用户可以在群内绑定自己的 Steam 账号
2. **群友状态变更播报** - 定时轮询 Steam API，当群友开始/停止/切换游戏时自动播报
3. **群友游戏时间播报** - 播报玩了多长时间
4. **主动查询群友状态** - 生成仿 Steam 好友列表样式的图片
5. **展示个人 Steam 主页** - 抓取 Steam 个人主页数据并渲染为图片

## 项目来源
- 作者: zhaomaoniu
- 仓库: https://github.com/zhaomaoniu/nonebot-plugin-steam-info
- 当前版本: 1.3.5
- 许可证: MIT

## 项目位置
此项目位于 MigutBot 的插件备份目录中：
`e:\Dev\Projects\MigutBot\nonemigut\Migut\plugins\backups\nonebot-plugin-steam-info`

## 核心需求
- 通过 Steam Web API 获取玩家状态信息
- 通过爬虫获取 Steam 个人主页详细数据
- 使用 Pillow 渲染精美的图片（仿 Steam 好友列表风格）
- 定时轮询并自动播报状态变更
- 跨平台支持（通过 nonebot-plugin-alconna）
