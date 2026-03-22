from __future__ import annotations

import json
from collections import deque
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IMAGE = ROOT / "origin.png"
OUTPUT_DIR = ROOT / "cache" / "layout_measure"
TARGET_WIDTH = 400

FRIENDS_BAR_COLOR = np.array([67, 73, 83], dtype=np.float32)
FRIENDS_TITLE_COLOR = np.array([183, 204, 213], dtype=np.float32)
TITLE_COLOR = np.array([197, 214, 212], dtype=np.float32)
MAIN_BG_COLOR = np.array([29, 31, 36], dtype=np.float32)


@dataclass
class Box:
    x: int
    y: int
    width: int
    height: int

    @property
    def x2(self) -> int:
        return self.x + self.width

    @property
    def y2(self) -> int:
        return self.y + self.height

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image = Image.open(DEFAULT_IMAGE).convert("RGB")
    scaled = scale_to_width(image, TARGET_WIDTH)
    scaled_array = np.asarray(scaled, dtype=np.uint8)

    friends_bar = detect_friends_bar(scaled_array)
    top_panel = Box(0, 0, scaled.width, friends_bar.y)
    parent_avatar = detect_parent_avatar(scaled_array, top_panel)
    friends_title = detect_friends_title(scaled_array, friends_bar)
    square_components = detect_square_components(scaled_array, friends_bar)
    section_titles = detect_section_titles(scaled_array, friends_bar, square_components)
    layout_hints = derive_layout_hints(
        scaled_array,
        friends_bar=friends_bar,
        parent_avatar=parent_avatar,
        friends_title=friends_title,
        square_components=square_components,
    )

    measurements = {
        "source_image": str(DEFAULT_IMAGE),
        "scaled_image": {
            "width": scaled.width,
            "height": scaled.height,
        },
        "top_panel": asdict(top_panel),
        "friends_bar": asdict(friends_bar),
        "parent_avatar": asdict(parent_avatar) if parent_avatar else None,
        "friends_title": asdict(friends_title) if friends_title else None,
        "section_titles": [asdict(box) for box in section_titles],
        "square_components": [asdict(box) for box in square_components],
        "layout_hints": layout_hints,
    }

    annotated = scaled.copy()
    draw_annotations(
        annotated,
        top_panel=top_panel,
        friends_bar=friends_bar,
        parent_avatar=parent_avatar,
        friends_title=friends_title,
        section_titles=section_titles,
        square_components=square_components,
    )

    scaled_path = OUTPUT_DIR / "origin_scaled_400.png"
    annotated_path = OUTPUT_DIR / "origin_annotated.png"
    json_path = OUTPUT_DIR / "measurements.json"

    scaled.save(scaled_path)
    annotated.save(annotated_path)
    json_path.write_text(
        json.dumps(measurements, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"scaled: {scaled_path}")
    print(f"annotated: {annotated_path}")
    print(f"json: {json_path}")
    print(json.dumps(measurements, ensure_ascii=False, indent=2))


def scale_to_width(image: Image.Image, width: int) -> Image.Image:
    height = round(image.height * width / image.width)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def detect_friends_bar(image: np.ndarray) -> Box:
    scores: list[tuple[float, int]] = []
    for y in range(70, min(image.shape[0] - 1, 260)):
        row = image[y, :320].astype(np.float32)
        row_color = np.median(row, axis=0)
        deviation = float(np.linalg.norm(row_color - FRIENDS_BAR_COLOR))
        brightness = float(row_color.mean())
        if 55 <= brightness <= 95:
            scores.append((deviation, y))

    if not scores:
        raise RuntimeError("Failed to detect friends bar seed.")

    _, seed = min(scores, key=lambda item: item[0])

    start = seed
    while start > 0 and _row_matches_friends_bar(image, start - 1):
        start -= 1

    end = seed + 1
    while end < image.shape[0] and _row_matches_friends_bar(image, end):
        end += 1

    return Box(0, start, image.shape[1], end - start)


def detect_parent_avatar(image: np.ndarray, top_panel: Box) -> Box | None:
    crop = image[top_panel.y : top_panel.y2, :140]
    bg_color = crop[:20, 120:].reshape(-1, 3).mean(axis=0)
    mask = color_distance(crop, bg_color) > 35
    components = connected_components(mask)
    boxes = [
        component_to_box(component)
        for component in components
        if len(component) >= 900
    ]
    boxes = [
        box for box in boxes if box.width >= 40 and box.height >= 40 and box.x < 80
    ]
    if not boxes:
        return None
    best = max(boxes, key=lambda box: box.width * box.height)
    return Box(best.x, best.y + top_panel.y, best.width, best.height)


def detect_friends_title(image: np.ndarray, friends_bar: Box) -> Box | None:
    crop = image[friends_bar.y : friends_bar.y2, :140]
    mask = color_distance(crop, FRIENDS_TITLE_COLOR) < 55
    ys, xs = np.where(mask)
    if len(xs) == 0 or len(ys) == 0:
        return None
    x0 = int(xs.min())
    x1 = int(xs.max())
    y0 = int(ys.min())
    y1 = int(ys.max())
    return Box(x0, y0 + friends_bar.y, x1 - x0 + 1, y1 - y0 + 1)


def detect_section_titles(
    image: np.ndarray,
    friends_bar: Box,
    square_components: list[Box],
) -> list[Box]:
    gaming_avatars = [
        box for box in square_components if box.x >= 45 and box.width >= 40 and box.y < 430
    ]
    regular_avatars = [
        box for box in square_components if box.x <= 30 and box.width >= 40 and box.y >= 430
    ]
    candidate_bands: list[tuple[int, int]] = []
    if gaming_avatars:
        candidate_bands.append((friends_bar.y2, max(friends_bar.y2, gaming_avatars[0].y - 8)))
    if gaming_avatars and regular_avatars:
        gaming_bottom = max(box.y2 for box in gaming_avatars)
        candidate_bands.append((gaming_bottom + 8, max(gaming_bottom + 8, regular_avatars[0].y - 8)))

    boxes: list[Box] = []
    for band_top, band_bottom in candidate_bands:
        if band_bottom - band_top < 18:
            continue
        crop = image[band_top:band_bottom, :180]
        mask = color_distance(crop, TITLE_COLOR) < 65
        ys, xs = np.where(mask)
        if len(xs) == 0 or len(ys) == 0:
            continue
        boxes.append(
            Box(
                int(xs.min()),
                int(band_top + ys.min()),
                int(xs.max() - xs.min() + 1),
                int(ys.max() - ys.min() + 1),
            )
        )
    boxes.sort(key=lambda box: box.y)
    return boxes


def detect_square_components(image: np.ndarray, friends_bar: Box) -> list[Box]:
    crop = image[friends_bar.y2 :, :]
    mask = color_distance(crop, MAIN_BG_COLOR) > 24
    components = connected_components(mask)
    boxes = [
        component_to_box(component)
        for component in components
        if len(component) >= 250
    ]
    filtered: list[Box] = []
    for box in boxes:
        if box.width < 18 or box.height < 18:
            continue
        if box.width > 90 or box.height > 90:
            continue
        ratio = box.width / max(box.height, 1)
        if not 0.65 <= ratio <= 1.35:
            continue
        filtered.append(Box(box.x, box.y + friends_bar.y2, box.width, box.height))

    filtered.sort(key=lambda box: (box.y, box.x))
    return filtered[:24]


def draw_annotations(
    image: Image.Image,
    *,
    top_panel: Box,
    friends_bar: Box,
    parent_avatar: Box | None,
    friends_title: Box | None,
    section_titles: list[Box],
    square_components: list[Box],
) -> None:
    draw = ImageDraw.Draw(image)
    draw.rectangle(
        (top_panel.x, top_panel.y, top_panel.x2 - 1, top_panel.y2 - 1),
        outline=(255, 128, 64),
        width=2,
    )
    draw.rectangle(
        (friends_bar.x, friends_bar.y, friends_bar.x2 - 1, friends_bar.y2 - 1),
        outline=(64, 220, 255),
        width=2,
    )
    if parent_avatar is not None:
        draw.rectangle(
            (parent_avatar.x, parent_avatar.y, parent_avatar.x2 - 1, parent_avatar.y2 - 1),
            outline=(255, 64, 180),
            width=2,
        )
    if friends_title is not None:
        draw.rectangle(
            (friends_title.x, friends_title.y, friends_title.x2 - 1, friends_title.y2 - 1),
            outline=(255, 255, 128),
            width=2,
        )
    for box in section_titles:
        draw.rectangle((box.x, box.y, box.x2 - 1, box.y2 - 1), outline=(80, 255, 180), width=2)
    for box in square_components:
        draw.rectangle((box.x, box.y, box.x2 - 1, box.y2 - 1), outline=(255, 80, 80), width=1)


def derive_layout_hints(
    image: np.ndarray,
    *,
    friends_bar: Box,
    parent_avatar: Box | None,
    friends_title: Box | None,
    square_components: list[Box],
) -> dict[str, object]:
    gaming_avatars = [
        box for box in square_components if box.x >= 45 and box.width >= 40 and box.y < 430
    ]
    regular_avatars = [
        box for box in square_components if box.x <= 30 and box.width >= 40 and box.y >= 430
    ]
    game_icons = [
        box for box in square_components if box.x <= 30 and box.width <= 35 and box.y < 430
    ]

    hints: dict[str, object] = {
        "parent_avatar": asdict(parent_avatar) if parent_avatar else None,
        "friends_bar_height": friends_bar.height,
        "friends_title": asdict(friends_title) if friends_title else None,
        "gaming_avatar_boxes": [asdict(box) for box in gaming_avatars],
        "regular_avatar_boxes": [asdict(box) for box in regular_avatars],
        "game_icon_boxes": [asdict(box) for box in game_icons],
    }

    if parent_avatar is not None:
        hints["parent_name_left"] = detect_text_start_x(
            image,
            row_top=max(0, parent_avatar.y - 4),
            row_bottom=min(image.shape[0], parent_avatar.y2 + 8),
            search_left=parent_avatar.x2,
            search_right=min(image.shape[1], parent_avatar.x2 + 220),
            background_color=image[max(0, parent_avatar.y - 5), min(image.shape[1] - 1, parent_avatar.x2 + 30)],
        )

    if gaming_avatars:
        first_gaming = gaming_avatars[0]
        hints["gaming_avatar_left"] = first_gaming.x
        hints["gaming_avatar_size"] = int(round((first_gaming.width + first_gaming.height) / 2))
        hints["gaming_text_left"] = detect_text_start_x(
            image,
            row_top=max(0, first_gaming.y - 4),
            row_bottom=min(image.shape[0], first_gaming.y2 + 6),
            search_left=first_gaming.x2,
            search_right=min(image.shape[1], first_gaming.x2 + 200),
            background_color=MAIN_BG_COLOR.astype(np.uint8),
        )

    if game_icons:
        first_icon = game_icons[0]
        hints["gaming_icon_left"] = first_icon.x
        hints["gaming_icon_size"] = int(round((first_icon.width + first_icon.height) / 2))

    if regular_avatars:
        first_regular = regular_avatars[0]
        hints["regular_avatar_left"] = first_regular.x
        hints["regular_avatar_size"] = int(round((first_regular.width + first_regular.height) / 2))
        hints["regular_text_left"] = detect_text_start_x(
            image,
            row_top=max(0, first_regular.y - 4),
            row_bottom=min(image.shape[0], first_regular.y2 + 6),
            search_left=first_regular.x2,
            search_right=min(image.shape[1], first_regular.x2 + 220),
            background_color=MAIN_BG_COLOR.astype(np.uint8),
        )
        if len(regular_avatars) >= 2:
            gaps = [
                regular_avatars[idx + 1].y - regular_avatars[idx].y
                for idx in range(len(regular_avatars) - 1)
            ]
            hints["regular_row_gap_samples"] = gaps

    return hints


def color_distance(image: np.ndarray, color: np.ndarray) -> np.ndarray:
    diff = image.astype(np.float32) - color.astype(np.float32)
    return np.sqrt(np.sum(diff * diff, axis=-1))


def detect_text_start_x(
    image: np.ndarray,
    *,
    row_top: int,
    row_bottom: int,
    search_left: int,
    search_right: int,
    background_color: np.ndarray,
) -> int | None:
    crop = image[row_top:row_bottom, search_left:search_right]
    if crop.size == 0:
        return None
    mask = color_distance(crop, background_color.astype(np.float32)) > 28
    counts = mask.sum(axis=0)
    candidates = np.where(counts >= 3)[0]
    if len(candidates) == 0:
        return None
    return int(search_left + candidates[0])


def connected_components(mask: np.ndarray) -> list[list[tuple[int, int]]]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            queue = deque([(x, y)])
            visited[y, x] = True
            component: list[tuple[int, int]] = []
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in (
                    (cx + 1, cy),
                    (cx - 1, cy),
                    (cx, cy + 1),
                    (cx, cy - 1),
                ):
                    if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        queue.append((nx, ny))
            components.append(component)
    return components


def component_to_box(component: list[tuple[int, int]]) -> Box:
    xs = [point[0] for point in component]
    ys = [point[1] for point in component]
    x0 = min(xs)
    x1 = max(xs)
    y0 = min(ys)
    y1 = max(ys)
    return Box(x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def merge_ranges(ranges: list[tuple[int, int]], gap: int) -> list[tuple[int, int]]:
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged: list[tuple[int, int]] = [ranges[0]]
    for start, end in ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + gap:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def merge_boxes(boxes: list[Box]) -> Box:
    x0 = min(box.x for box in boxes)
    y0 = min(box.y for box in boxes)
    x1 = max(box.x2 for box in boxes)
    y1 = max(box.y2 for box in boxes)
    return Box(x0, y0, x1 - x0, y1 - y0)


def _row_matches_friends_bar(image: np.ndarray, y: int) -> bool:
    row = image[y, :320].astype(np.float32)
    row_color = np.median(row, axis=0)
    deviation = float(np.linalg.norm(row_color - FRIENDS_BAR_COLOR))
    brightness = float(row_color.mean())
    return deviation < 22 and 55 <= brightness <= 95


if __name__ == "__main__":
    main()
