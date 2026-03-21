from __future__ import annotations

from colorsys import hsv_to_rgb, rgb_to_hsv
from io import BytesIO
from pathlib import Path
from typing import cast

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from ..core.models import Achievements, DrawPlayerStatusData, FriendStatusData
from .utils import hex_to_rgb

WIDTH = 400
PARENT_AVATAR_SIZE = 72
MEMBER_AVATAR_SIZE = 50
GAMING_ROW_HEIGHT = 78
GAME_ICON_SIZE = 34
AVATAR_FRAME_PADDING = 4
AVATAR_SLOT_SIZE = MEMBER_AVATAR_SIZE + AVATAR_FRAME_PADDING * 2
RGBColor = tuple[int, int, int]
ColorPair = tuple[RGBColor, RGBColor]

unknown_avatar_path = Path(__file__).parent.parent / "res/unknown_avatar.jpg"
parent_status_path = Path(__file__).parent.parent / "res/parent_status.png"
friends_search_path = Path(__file__).parent.parent / "res/friends_search.png"
busy_path = Path(__file__).parent.parent / "res/busy.png"
zzz_online_path = Path(__file__).parent.parent / "res/zzz_online.png"
zzz_gaming_path = Path(__file__).parent.parent / "res/zzz_gaming.png"
gaming_path = Path(__file__).parent.parent / "res/gaming.png"

font_regular_path: str | None = None
font_light_path: str | None = None
font_bold_path: str | None = None


def set_font_paths(regular_path: str, light_path: str, bold_path: str) -> None:
    global font_regular_path, font_light_path, font_bold_path
    base_dir = Path().cwd()
    font_regular_path = str((base_dir / regular_path).resolve())
    font_light_path = str((base_dir / light_path).resolve())
    font_bold_path = str((base_dir / bold_path).resolve())


def _get_font_path(path: str | None, name: str) -> str:
    if path is None:
        raise RuntimeError(
            f"Font path for {name} not set. Call set_font_paths() first."
        )
    return path


def font_regular(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_get_font_path(font_regular_path, "regular"), size)


def font_light(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_get_font_path(font_light_path, "light"), size)


def font_bold(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_get_font_path(font_bold_path, "bold"), size)


def check_font() -> None:
    rp = _get_font_path(font_regular_path, "regular")
    lp = _get_font_path(font_light_path, "light")
    bp = _get_font_path(font_bold_path, "bold")
    if not Path(rp).exists():
        raise FileNotFoundError(f"Font file {rp} not found.")
    if not Path(lp).exists():
        raise FileNotFoundError(f"Font file {lp} not found.")
    if not Path(bp).exists():
        raise FileNotFoundError(f"Font file {bp} not found.")


personastate_colors: dict[int, ColorPair] = {
    0: (hex_to_rgb("969697"), hex_to_rgb("656565")),
    1: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),
    2: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),
    3: (hex_to_rgb("45778e"), hex_to_rgb("365969")),
    4: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),
    5: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),
    6: (hex_to_rgb("6dcef5"), hex_to_rgb("4c91ac")),
}

GAMING_TEXT_FILL: ColorPair = (hex_to_rgb("e3ffc2"), hex_to_rgb("8ebe56"))


def vertically_concatenate_images(images: list[Image.Image]) -> Image.Image:
    widths, heights = zip(*(i.size for i in images), strict=True)
    total_width = max(widths)
    total_height = sum(heights)

    new_image = Image.new("RGB", (total_width, total_height))

    y_offset = 0
    for image in images:
        new_image.paste(image, (0, y_offset))
        y_offset += image.size[1]

    return new_image


def _format_friend_display_name(friend_name: str, nickname: str | None = None) -> str:
    cleaned_nickname = nickname.strip() if nickname else ""
    return f"{friend_name} ({cleaned_nickname})" if cleaned_nickname else friend_name


def draw_start_gaming(
    avatar: Image.Image, friend_name: str, game_name: str, nickname: str | None = None
):
    canvas = Image.open(gaming_path)
    canvas.paste(avatar.resize((66, 66), Image.Resampling.BICUBIC), (15, 20))

    # 绘制名称
    draw = ImageDraw.Draw(canvas)
    draw.text(
        (104, 14),
        _format_friend_display_name(friend_name, nickname),
        font=font_regular(19),
        fill=hex_to_rgb("e3ffc2"),
    )

    # 绘制"正在玩"
    draw.text(
        (103, 42),
        "正在玩",
        font=font_regular(17),
        fill=hex_to_rgb("969696"),
    )

    # 绘制游戏名称
    draw.text(
        (104, 66),
        game_name,
        font=font_bold(14),
        fill=hex_to_rgb("91c257"),
    )

    return canvas


def draw_parent_status(parent_avatar: Image.Image, parent_name: str) -> Image.Image:
    parent_avatar = parent_avatar.resize(
        (PARENT_AVATAR_SIZE, PARENT_AVATAR_SIZE), Image.Resampling.BICUBIC
    )

    canvas = Image.open(parent_status_path).resize(
        (WIDTH, 120), Image.Resampling.BICUBIC
    )

    draw = ImageDraw.Draw(canvas)

    # 在左下角 (16, 16) 处绘制头像
    avatar_height = 120 - 16 - PARENT_AVATAR_SIZE
    canvas.paste(parent_avatar, (16, avatar_height))

    # 绘制名称
    draw.text(
        (16 + PARENT_AVATAR_SIZE + 16, avatar_height + 12),
        parent_name,
        font=font_bold(20),
        fill=hex_to_rgb("6dcff6"),
    )

    # 绘制状态
    draw.text(
        (16 + PARENT_AVATAR_SIZE + 16, avatar_height + 20 + 16),
        "在线",
        font=font_light(18),
        fill=hex_to_rgb("4c91ac"),
    )

    return canvas


def draw_friends_search() -> Image.Image:
    canvas = Image.new("RGB", (WIDTH, 50), hex_to_rgb("434953"))

    friends_search = Image.open(friends_search_path)

    canvas.paste(friends_search, (WIDTH - friends_search.width, 0))

    draw = ImageDraw.Draw(canvas)

    draw.text(
        (24, 10),
        "好友",
        hex_to_rgb("b7ccd5"),
        font=font_regular(20),
    )

    return canvas


def draw_friend_status(
    friend_avatar: Image.Image,
    friend_name: str,
    status: str,
    personastate: int,
    nickname: str | None = None,
    avatar_frame: Image.Image | None = None,
    game_icon: Image.Image | None = None,
    game_name: str | None = None,
) -> Image.Image:
    display_name = _format_friend_display_name(friend_name, nickname)
    friend_avatar = friend_avatar.resize(
        (MEMBER_AVATAR_SIZE, MEMBER_AVATAR_SIZE), Image.Resampling.BICUBIC
    )
    gaming_layout = game_name is not None and status not in {"在线", "离开"}
    row_height = GAMING_ROW_HEIGHT if gaming_layout else 64

    canvas = Image.new("RGBA", (WIDTH, row_height), (*hex_to_rgb("1e2024"), 255))
    draw = ImageDraw.Draw(canvas)

    fill = _get_friend_status_fill(personastate, status, gaming_layout)

    avatar_image = _compose_avatar_with_frame(friend_avatar, avatar_frame)
    avatar_x = 60 if gaming_layout else 22
    avatar_y = (row_height - avatar_image.height) // 2
    canvas.paste(avatar_image, (avatar_x, avatar_y), avatar_image)
    visual_avatar_y = avatar_y + AVATAR_FRAME_PADDING
    visual_avatar_height = MEMBER_AVATAR_SIZE

    if gaming_layout:
        name_font = font_bold(19)
        game_font = font_regular(17)
        name_bbox = _measure_text_bbox(name_font, display_name)
        game_bbox = _measure_text_bbox(game_font, game_name or status)
        name_y, detail_y = _get_two_line_text_positions(
            visual_avatar_y,
            visual_avatar_height,
            _bbox_height(name_bbox),
            _bbox_height(game_bbox),
        )
        name_draw_y = _get_text_draw_y(name_bbox, name_y)
        detail_draw_y = _get_text_draw_y(game_bbox, detail_y)
        icon_y = (row_height - GAME_ICON_SIZE) // 2
        bar_x = avatar_x + avatar_image.width + 2
        text_x = bar_x + 12
        bar_top = max(8, avatar_y + 3)
        bar_bottom = min(row_height - 8, avatar_y + avatar_image.height - 3)

        if game_icon is not None:
            icon = game_icon.resize(
                (GAME_ICON_SIZE, GAME_ICON_SIZE), Image.Resampling.BICUBIC
            )
            icon = rounded_rectangle(icon.convert("RGBA"), 8)
            canvas.paste(icon, (20, icon_y), icon)

        draw.rectangle((bar_x, bar_top, bar_x + 3, bar_bottom), fill=hex_to_rgb("8ebe56"))
        draw.text(
            (text_x, name_draw_y),
            display_name,
            font=name_font,
            fill=fill[0],
        )
        draw.text(
            (text_x, detail_draw_y),
            game_name or status,
            font=game_font,
            fill=hex_to_rgb("8ebe56"),
        )
        badge_text_x = text_x
        badge_text_y = name_y
        badge_font_size = 19
    else:
        text_x = avatar_x + avatar_image.width + 18
        name_font = font_bold(20)
        status_font = font_regular(18)
        name_bbox = _measure_text_bbox(name_font, display_name)
        status_bbox = _measure_text_bbox(status_font, status)
        name_y, detail_y = _get_two_line_text_positions(
            visual_avatar_y,
            visual_avatar_height,
            _bbox_height(name_bbox),
            _bbox_height(status_bbox),
        )
        name_draw_y = _get_text_draw_y(name_bbox, name_y)
        detail_draw_y = _get_text_draw_y(status_bbox, detail_y)
        draw.text(
            (text_x, name_draw_y),
            display_name,
            font=name_font,
            fill=fill[0],
        )
        draw.text(
            (text_x - 2, detail_draw_y),
            status,
            font=status_font,
            fill=fill[1],
        )
        badge_text_x = text_x
        badge_text_y = name_y
        badge_font_size = 20

    _draw_persona_badge(
        canvas,
        display_name,
        personastate,
        badge_text_x,
        badge_text_y,
        badge_font_size,
        gaming_layout,
    )

    return canvas.convert("RGB")


def _compose_avatar_with_frame(
    avatar: Image.Image, avatar_frame: Image.Image | None
) -> Image.Image:
    composed = Image.new("RGBA", (AVATAR_SLOT_SIZE, AVATAR_SLOT_SIZE), (0, 0, 0, 0))
    composed.paste(
        avatar.convert("RGBA"),
        (AVATAR_FRAME_PADDING, AVATAR_FRAME_PADDING),
    )
    if avatar_frame is None:
        return composed

    frame = avatar_frame.resize((AVATAR_SLOT_SIZE, AVATAR_SLOT_SIZE), Image.Resampling.BICUBIC)
    composed.alpha_composite(frame)
    return composed


def _draw_persona_badge(
    canvas: Image.Image,
    display_name: str,
    personastate: int,
    text_x: int,
    text_y: int,
    font_size: int,
    gaming_layout: bool,
) -> None:
    draw = ImageDraw.Draw(canvas)
    name_width = int(draw.textlength(display_name, font=font_bold(font_size)))
    y = text_y if gaming_layout else text_y + 6

    if personastate == 2:
        badge = Image.open(busy_path).convert("RGBA")
        canvas.paste(badge, (text_x + name_width + 6, y), badge)
    elif personastate == 4:
        badge = Image.open(
            zzz_gaming_path if gaming_layout else zzz_online_path
        ).convert("RGBA")
        canvas.paste(badge, (text_x + name_width + 8, y))


def _get_friend_status_fill(
    personastate: int,
    status: str,
    gaming_layout: bool,
) -> ColorPair:
    if gaming_layout:
        return GAMING_TEXT_FILL
    if status != "在线" and personastate == 1:
        return GAMING_TEXT_FILL
    if status != "离开" and personastate == 3:
        return GAMING_TEXT_FILL
    return personastate_colors[personastate]


def _get_two_line_text_positions(
    container_y: int,
    container_height: int,
    primary_height: int,
    secondary_height: int,
    inset: int = 0,
    min_gap: int = 4,
) -> tuple[int, int]:
    primary_y = container_y + inset
    secondary_y = container_y + container_height - secondary_height - inset
    secondary_y = max(secondary_y, primary_y + primary_height + min_gap)
    return primary_y, secondary_y


def _measure_text_height(font: ImageFont.FreeTypeFont, text: str) -> int:
    return _bbox_height(_measure_text_bbox(font, text))


def _measure_text_bbox(
    font: ImageFont.FreeTypeFont, text: str
) -> tuple[int, int, int, int]:
    return cast(tuple[int, int, int, int], font.getbbox(text or "A"))


def _bbox_height(bbox: tuple[int, int, int, int]) -> int:
    return max(1, bbox[3] - bbox[1])


def _get_text_draw_y(
    bbox: tuple[int, int, int, int],
    visual_top_y: int,
) -> int:
    return visual_top_y - bbox[1]


def _draw_status_section(
    title: str,
    data: list[FriendStatusData],
    count_text: str | None = None,
) -> Image.Image:
    rows = [
        draw_friend_status(
            d["avatar"],
            d["name"],
            d["status"],
            d["personastate"],
            d.get("nickname"),
            d.get("avatar_frame"),
            d.get("game_icon"),
            d.get("game_name"),
        )
        for d in data
    ]
    height = 64 + sum(row.height for row in rows) + 16
    canvas = Image.new("RGB", (WIDTH, height), hex_to_rgb("1e2024"))
    draw = ImageDraw.Draw(canvas)

    draw.text(
        (22, 22),
        title,
        hex_to_rgb("c5d6d4"),
        font=font_regular(22),
    )
    if count_text is not None:
        draw.text(
            (22 + int(draw.textlength(title, font=font_regular(22))) + 8, 25),
            count_text,
            hex_to_rgb("67665c"),
            font=font_regular(18),
        )

    y = 64
    for row in rows:
        canvas.paste(row, (0, y))
        y += row.height

    return canvas


def draw_gaming_friends_status(data: list[FriendStatusData]) -> Image.Image:
    # 排序数据，按照游戏名称字母表顺序排序
    data.sort(key=lambda x: x.get("game_name") or x["status"])
    return _draw_status_section("游戏中", data)


def draw_online_friends_status(data: list[FriendStatusData]) -> Image.Image:
    return _draw_status_section("在线好友", data, f"({len(data)})")


def draw_offline_friends_status(data: list[FriendStatusData]) -> Image.Image:
    return _draw_status_section("离线", data, f"({len(data)})")


def draw_friends_status(
    parent_avatar: Image.Image, parent_name: str, data: list[FriendStatusData]
):
    data.sort(key=lambda x: x["personastate"])

    parent_status = draw_parent_status(parent_avatar, parent_name)
    friends_search = draw_friends_search()

    status_images: list[Image.Image] = []
    height = parent_status.height + friends_search.height

    gaming_data = [
        d
        for d in data
        if (d["personastate"] == 1 and d["status"] != "在线")
        or (d["personastate"] == 3 and d["status"] != "离开")
        or (d["personastate"] == 4 and d["status"] != "在线")
    ]

    if gaming_data:
        status_images.append(draw_gaming_friends_status(gaming_data))
        height += status_images[-1].height

    online_data = [
        d
        for d in data
        if (d["personastate"] == 1 and d["status"] == "在线")
        or (d["personastate"] == 3 and d["status"] == "离开")
        or (d["personastate"] == 4 and d["status"] == "在线")
        or (d["personastate"] in [2, 5, 6])
    ]
    # 按 1, 2, 4, 5, 6, 3 的顺序排序
    online_data.sort(key=lambda x: 7 if x["personastate"] == 3 else x["personastate"])

    if online_data:
        status_images.append(draw_online_friends_status(online_data))
        height += status_images[-1].height

    offline_data = [d for d in data if d["personastate"] == 0]
    if offline_data:
        status_images.append(draw_offline_friends_status(offline_data))
        height += status_images[-1].height

    # 拼合图片
    canvas = Image.new("RGB", (WIDTH, height), hex_to_rgb("1e2024"))
    draw = ImageDraw.Draw(canvas)

    canvas.paste(parent_status, (0, 0))
    canvas.paste(friends_search, (0, parent_status.height))

    y = parent_status.height + friends_search.height

    for i, status_image in enumerate(status_images):
        canvas.paste(status_image, (0, y))
        y += status_image.height

        # 绘制分割线
        if i != len(status_images) - 1:
            draw.rectangle([0, y - 1, WIDTH, y], fill=hex_to_rgb("333439"))

    return canvas


def get_average_color(image: Image.Image) -> tuple[int, int, int]:
    """获取图片的平均颜色"""
    image_np = np.array(image)
    average_color = image_np.mean(axis=(0, 1)).astype(int)
    r, g, b = int(average_color[0]), int(average_color[1]), int(average_color[2])
    return (r, g, b)


def split_image(
    image: Image.Image, rows: int, cols: int
) -> tuple[list[Image.Image], int, int]:
    """将图片分割为rows * cols份"""
    width, height = image.size
    piece_width = width // cols
    piece_height = height // rows
    pieces = []

    for r in range(rows):
        for c in range(cols):
            box = (
                c * piece_width,
                r * piece_height,
                (c + 1) * piece_width,
                (r + 1) * piece_height,
            )
            piece = image.crop(box)
            pieces.append(piece)

    return pieces, piece_width, piece_height


def recolor_image(image: Image.Image, rows: int, cols: int) -> Image.Image:
    """分片图片，提取平均颜色后拼接"""
    total_average_color = get_average_color(image)  # 获取整体平均颜色
    pieces, piece_width, piece_height = split_image(image, rows, cols)

    diameter = min(pieces[0].size)  # 以最小边为直径
    radius = diameter // 2
    new_image = Image.new("RGB", image.size, total_average_color)

    for i, piece in enumerate(pieces):
        average_color = get_average_color(piece)  # 获取每片的平均颜色

        # 计算放置的位置
        row, col = divmod(i, cols)
        x = col * piece_width + piece_width // 2
        y = row * piece_height + piece_height // 2

        # 画圆
        circle = Image.new("RGBA", (piece_width, piece_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(circle)
        draw.ellipse((0, 0, piece_width, piece_height), fill=average_color)

        # 将圆形图片粘贴到新图片上
        new_image.paste(circle, (x - radius, y - radius), circle)

    new_image = new_image.filter(ImageFilter.SMOOTH)
    new_image = new_image.filter(ImageFilter.GaussianBlur(50))

    return new_image


def create_gradient_image(
    size: tuple[int, int],
    color1: tuple[int, ...],
    color2: tuple[int, ...],
) -> Image.Image:
    """创建渐变图片"""
    # 确保颜色值在 0-255 范围内
    c1 = tuple(max(0, min(255, c)) for c in color1)
    c2 = tuple(max(0, min(255, c)) for c in color2)
    # 创建一个渐变的线性空间
    gradient_array = np.linspace(c1, c2, size[0])

    # 将渐变数组的形状调整为 (height, width, 3)
    gradient_image = np.tile(gradient_array, (size[1], 1, 1)).astype(np.uint8)

    return Image.fromarray(gradient_image, "RGBA")


def create_vertical_gradient_rect(width, height, start_color, end_color):
    """
    创建一个在竖直方向上渐变的矩形图像.

    Args:
        width (int): 矩形的宽度 (以像素为单位).
        height (int): 矩形的高度 (以像素为单位).
        start_color (tuple): 起始颜色，格式为 (R, G, B)，每个值范围为 0-255.
        end_color (tuple): 结束颜色，格式为 (R, G, B)，每个值范围为 0-255.

    Returns:
        Image: PIL Image 对象，表示生成的渐变矩形.
    """
    if width <= 0 or height <= 0:
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    # 确保颜色不超过 0-255 的范围
    start_color = tuple(max(0, min(255, c)) for c in start_color)
    end_color = tuple(max(0, min(255, c)) for c in end_color)

    # 使用 NumPy 创建一个线性渐变数组
    gradient_array = np.linspace(start_color, end_color, num=height, dtype=np.uint8)
    gradient_array = np.tile(gradient_array[:, np.newaxis, :], (1, width, 1))

    # 使用 Pillow 创建图像并填充颜色
    image = Image.fromarray(gradient_array)
    return image


def random_color_offset(color: tuple[int, ...], offset: int) -> tuple[int, ...]:
    return tuple(
        min(255, max(0, c + np.random.randint(-offset, offset + 1))) for c in color
    )


def get_brightest_and_darkest_color(
    image: Image.Image,
    saturation_threshold: int = 100,
    hue_difference_threshold: int = 30,
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """获取图片最亮和最暗的颜色"""
    # 将RGB图像转换为HSV
    img_hsv = np.array(image.convert("HSV"))

    # 设定一个阈值来定义"鲜艳的颜色"，例如饱和度大于150
    vivid_mask = img_hsv[..., 1] > saturation_threshold

    # 获取饱和度较高（鲜艳）的像素索引
    vivid_pixels = img_hsv[vivid_mask]

    if len(vivid_pixels) < 10:
        return get_brightest_and_darkest_color(image, saturation_threshold - 10)

    # 在鲜艳的像素中，根据亮度（V通道）找到最亮和最暗的颜色
    brightest_pixel = vivid_pixels[np.argmax(vivid_pixels[..., 2])]
    darkest_pixel = vivid_pixels[np.argmin(vivid_pixels[..., 2])]

    # 获取最亮和最暗的颜色的色相差异
    hue_difference = abs(int(brightest_pixel[0]) - int(darkest_pixel[0]))

    # 如果色相差异过小，则尝试寻找新的最暗颜色，直到色相差异大于设定阈值
    if hue_difference < hue_difference_threshold:
        possible_dark_pixels = vivid_pixels[vivid_pixels[..., 0] != brightest_pixel[0]]
        if len(possible_dark_pixels) > 0:
            darkest_pixel = possible_dark_pixels[
                np.argmin(possible_dark_pixels[..., 2])
            ]

    # 将最亮和最暗的像素从HSV转回RGB
    brightest_color = (
        Image.fromarray(np.uint8([[brightest_pixel]]), "HSV")  # type: ignore[arg-type]
        .convert("RGB")
        .getpixel((0, 0))
    )
    darkest_color = (
        Image.fromarray(np.uint8([[darkest_pixel]]), "HSV")  # type: ignore[arg-type]
        .convert("RGB")
        .getpixel((0, 0))
    )

    return cast(
        tuple[tuple[int, int, int], tuple[int, int, int]],
        (brightest_color, darkest_color),
    )


def draw_game_info(
    header: Image.Image,
    game_name: str,
    game_time: str,
    last_play_time: str,
    achievements: list[Achievements],
    completed_achievement_number: int,
    total_achievement_number: int,
    achievement_color: tuple[int, int, int],
) -> Image.Image:
    bg = Image.new("RGBA", (880, 110 + 64 + 10), (0, 0, 0, 110))
    header = header.resize((229, 86), Image.Resampling.BICUBIC)
    bg.paste(header, (10, 110 // 2 - header.height // 2))

    draw = ImageDraw.Draw(bg)

    # 画游戏名
    draw.text(
        (260, 10),
        game_name,
        font=font_regular(26),
        fill=(255, 255, 255),
    )

    # 画最后游玩时间
    font = font_light(22)
    display_text = last_play_time
    draw.text(
        (int(bg.width - font.getlength(display_text)) - 10, 75),
        display_text,
        font=font,
        fill=(150, 150, 150),
    )

    # 画游戏时间
    font = font_light(22)
    display_text = f"总时数 {game_time}"
    draw.text(
        (int(bg.width - font.getlength(display_text)) - 10, 50),
        display_text,
        font=font,
        fill=(150, 150, 150),
    )

    if completed_achievement_number is None or total_achievement_number is None:
        return bg.crop((0, 0, bg.width, 110))

    # 画成就  + 64 + 10
    achievement_bg = Image.new("RGBA", (860, 64), achievement_color)
    draw_achievement = ImageDraw.Draw(achievement_bg)

    # 画成就进度
    font = font_light(18)
    x = 14
    draw_achievement.text(
        (x, 20),
        "成就进度",
        font=font,
        fill=(255, 255, 255, 255),
    )
    x += font.getlength("成就进度") + 10
    draw_achievement.text(
        (int(x), 20),
        f"{completed_achievement_number} / {total_achievement_number}",
        font=font,
        fill=(130, 130, 130),
    )
    x += (
        font.getlength(f"{completed_achievement_number} / {total_achievement_number}")
        + 10
    )
    progress_bar = create_progress_bar(
        completed_achievement_number / total_achievement_number, achievement_color
    )
    achievement_bg.paste(progress_bar, (int(x), 24), progress_bar)

    # 画成就图标
    x = 860 - 48 * 6 - 10 * 6
    for achievement in achievements:
        achievement_image = Image.open(BytesIO(achievement["image"])).resize((48, 48))
        achievement_bg.paste(achievement_image, (x, 8))
        x += 48 + 10

    if completed_achievement_number > 6:
        font = font_regular(22)
        display_text = f"+{completed_achievement_number - 5}"
        draw_achievement.rectangle((x, 8, x + 48, 56), fill=(34, 34, 34))
        draw_achievement.text(
            (x + 24 - font.getlength(display_text) // 2, 18),
            display_text,
            font=font,
            fill=(255, 255, 255),
        )

    bg.paste(achievement_bg, (10, 110), achievement_bg)
    return bg


def draw_player_status(
    player_bg: Image.Image,
    player_avatar: Image.Image,
    player_name: str,
    player_id: str,
    player_description: str,
    player_last_two_weeks_time: str,  # e.g. 10.2 小时
    player_games: list[DrawPlayerStatusData],
):
    if isinstance(player_bg, bytes):
        player_bg = Image.open(BytesIO(player_bg))
    if isinstance(player_avatar, bytes):
        player_avatar = Image.open(BytesIO(player_avatar))

    bg = recolor_image(
        player_bg.crop(
            (
                (player_bg.width - 960) // 2,
                0,
                (player_bg.width + 960) // 2,
                player_bg.height,
            )
        ),
        10,
        10,
    )
    # 调暗背景
    enhancer = ImageEnhance.Brightness(bg)
    bg = enhancer.enhance(0.7)
    # bg.size = (960, 1020)
    player_avatar = player_avatar.resize((200, 200))
    bg.paste(player_avatar, (40, 40))

    draw = ImageDraw.Draw(bg)

    # 画头像外框
    draw.rectangle((40, 40, 240, 240), outline=(83, 164, 196), width=3)

    # 画昵称
    draw.text(
        (280, 48),
        player_name,
        font=font_light(40),
        fill=(255, 255, 255),
    )

    # 画ID
    draw.text(
        (280, 100),
        f"好友代码: {player_id}",
        font=font_regular(19),
        fill=(191, 191, 191),
    )

    # 画简介
    line_width = 0
    offset = 0
    line = ""
    for idx, char in enumerate(player_description):
        line += char
        line_width += font_light(22).getlength(char)
        if line_width > 640 or idx == len(player_description) - 1 or char == "\n":
            draw.text(
                (280, 132 + offset),
                line,
                font=font_light(22),
                fill=(255, 255, 255),
            )
            line = ""
            offset += 25
            line_width = 0
        if offset >= 25 * 4:
            break

    # 画游戏

    bright_rgb, dark_rgb = get_brightest_and_darkest_color(player_bg)
    bright_adj = tuple(x - 30 if x >= 30 else 0 for x in bright_rgb)
    dark_adj = tuple(x + 30 if x <= 255 - 30 else 255 for x in dark_rgb)
    brightest_color = random_color_offset((*bright_adj, 128), 20)
    darkest_color = random_color_offset((*dark_adj, 128), 20)

    # 画游戏信息
    hsv_achievement_color = rgb_to_hsv(*brightest_color[:3])
    ach_r, ach_g, ach_b = hsv_to_rgb(
        hsv_achievement_color[0],
        hsv_achievement_color[1] * 0.85,
        hsv_achievement_color[2] * 0.6,
    )
    achievement_color: tuple[int, int, int] = (int(ach_r), int(ach_g), int(ach_b))
    game_images: list[Image.Image] = []
    for _idx, game in enumerate(player_games):
        game_image = Image.open(BytesIO(game["game_header"]))
        game_info = draw_game_info(
            game_image,
            game["game_name"],
            game["game_time"],
            game["last_play_time"],
            game["achievements"],
            game["completed_achievement_number"],
            game["total_achievement_number"],
            achievement_color,
        )
        game_images.append(game_info)

    # 画半透明黑色背景
    bg_game = Image.new(
        "RGBA", (920, 106 + sum([game_image.height + 26 for game_image in game_images]))
    )
    draw_game = ImageDraw.Draw(bg_game)
    draw_game.rectangle(
        (
            0,
            0,
            920,
            bg_game.height,
        ),
        fill=(0, 0, 0, 120),
    )
    bg.paste(bg_game, (20, 272), bg_game)

    # 画渐变条
    gradient = create_gradient_image((920, 50), brightest_color, darkest_color)
    bg.paste(gradient, (20, 272), gradient)

    # 画渐变条的文字：最新动态，最近游戏
    draw.text(
        (34, 279),
        "最新动态",
        font=font_light(26),
        fill=(255, 255, 255),
    )
    if player_last_two_weeks_time is not None:
        width = font_light(26).getlength(player_last_two_weeks_time)
        draw.text(
            (960 - width - 34, 279),
            player_last_two_weeks_time,
            font=font_light(26),
            fill=(255, 255, 255),
        )

    y = 350
    for _idx, game_image in enumerate(game_images):
        bg.paste(
            game_image,
            ((920 - game_image.width) // 2 + 20, y),
            game_image.convert("RGBA"),
        )
        y += game_image.height + 26

    player_bg.paste(bg, ((player_bg.width - 960) // 2, 0), bg.convert("RGBA"))

    return player_bg


def rounded_rectangle(
    image: Image.Image,
    radius: int,
    border=False,
    border_width=0,
    border_color=(0, 0, 0),
):
    """
    将给定的Image.Image对象切割为圆角矩形。

    Args:
        image: 一个PIL Image对象。
        radius: 圆角半径，单位为像素。
        border: 是否需要边框，默认为False。
        border_width: 边框宽度，单位为像素，默认为0。
        border_color: 边框颜色，RGB元组，默认为黑色(0, 0, 0)。

    Returns:
        一个PIL Image对象，表示切割后的圆角矩形图像。
    """

    image_rgba = image.convert("RGBA")
    width, height = image_rgba.size

    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)

    result = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    result.paste(image_rgba, (0, 0), mask)

    if border and border_width > 0:
        border_layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border_layer)
        inset = max(0, border_width // 2)
        border_draw.rounded_rectangle(
            (inset, inset, width - 1 - inset, height - 1 - inset),
            radius=max(0, radius - inset),
            outline=border_color,
            width=border_width,
        )
        result.alpha_composite(border_layer)

    return result


def create_progress_bar(
    progress: float, color: tuple[int, int, int], width=186, height=16
):
    color_hsv = rgb_to_hsv(*color)

    # 外条
    bar_color = tuple(
        map(int, hsv_to_rgb(color_hsv[0], color_hsv[1], color_hsv[2] * 0.8))
    )
    border_color = tuple(max(x - 20, 0) for x in color)
    border_image = rounded_rectangle(
        Image.new("RGBA", (width, height), bar_color),
        8,
        border=True,
        border_width=1,
        border_color=border_color,
    )

    # 内条
    bar_color_top = tuple(
        map(int, hsv_to_rgb(color_hsv[0], color_hsv[1] / 2, color_hsv[2] * 5 / 2))
    )
    bar_color_bottem = tuple(
        map(int, hsv_to_rgb(color_hsv[0], color_hsv[1] / 2, color_hsv[2]))
    )

    bar_image = create_vertical_gradient_rect(
        int(width * progress) - 6, height - 4, bar_color_top, bar_color_bottem
    )
    bar_image = rounded_rectangle(bar_image, 6)

    # 合并
    border_image.paste(bar_image, (3, 2), bar_image)

    return border_image
