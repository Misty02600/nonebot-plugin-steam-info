from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Config(BaseModel):
    steam_api_key: list[str] = Field(description="Steam Web API Key，支持单个或多个")
    proxy: str | None = Field(default=None, description="HTTP 代理地址")
    steam_request_interval: int = Field(
        default=300, description="Steam 状态轮询间隔（秒）"
    )
    steam_broadcast_type: str = Field(
        default="part", description="播报类型：all / part / none"
    )
    steam_disable_broadcast_on_startup: bool = Field(
        default=False, description="是否禁用启动时的首次播报"
    )
    steam_font_regular_path: str = Field(
        default="fonts/MiSans-Regular.ttf", description="Regular 字体路径"
    )
    steam_font_light_path: str = Field(
        default="fonts/MiSans-Light.ttf", description="Light 字体路径"
    )
    steam_font_bold_path: str = Field(
        default="fonts/MiSans-Bold.ttf", description="Bold 字体路径"
    )

    # 限流相关配置
    steam_api_max_retries: int = Field(
        default=3, description="单个 API Key 最大重试次数"
    )
    steam_api_batch_delay: float = Field(default=1.5, description="分批请求间隔（秒）")
    steam_api_backoff_factor: float = Field(default=2.0, description="指数退避因子")

    # 缓存相关配置
    steam_cache_ttl: int = Field(
        default=86400, description="图片缓存过期时间（秒），默认 24 小时"
    )

    @field_validator("steam_api_key", mode="before")
    @classmethod
    def ensure_list(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [v]
        return v
