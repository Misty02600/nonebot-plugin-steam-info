"""Generate preview renderings for comparison (standalone, no NoneBot)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

# Prevent nonebot plugin __init__.py from loading
sys.modules["nonebot_plugin_steam_info"] = type(sys)("nonebot_plugin_steam_info")
sys.modules["nonebot_plugin_steam_info"].__path__ = [str(SRC / "nonebot_plugin_steam_info")]
sys.modules["nonebot_plugin_steam_info"].core = type(sys)("nonebot_plugin_steam_info.core")
sys.modules["nonebot_plugin_steam_info.core"] = sys.modules["nonebot_plugin_steam_info"].core
sys.modules["nonebot_plugin_steam_info.core"].__path__ = [str(SRC / "nonebot_plugin_steam_info" / "core")]

# Add src to path for sub-module imports
sys.path.insert(0, str(SRC))

# Import models directly
import importlib
models_mod = importlib.import_module("nonebot_plugin_steam_info.core.models")
sys.modules["nonebot_plugin_steam_info.core.models"] = models_mod

# Now import the infra modules
infra_pkg = type(sys)("nonebot_plugin_steam_info.infra")
infra_pkg.__path__ = [str(SRC / "nonebot_plugin_steam_info" / "infra")]
sys.modules["nonebot_plugin_steam_info.infra"] = infra_pkg
sys.modules["nonebot_plugin_steam_info"].infra = infra_pkg

utils_mod = importlib.import_module("nonebot_plugin_steam_info.infra.utils")
sys.modules["nonebot_plugin_steam_info.infra.utils"] = utils_mod

draw_mod = importlib.import_module("nonebot_plugin_steam_info.infra.draw")
sys.modules["nonebot_plugin_steam_info.infra.draw"] = draw_mod

from PIL import Image

draw_mod.set_font_paths(
    "fonts/MiSans-Regular.ttf",
    "fonts/MiSans-Light.ttf",
    "fonts/MiSans-Bold.ttf",
)

common_mod = importlib.import_module("nonebot_plugin_steam_info.infra.html_render_common")
sys.modules["nonebot_plugin_steam_info.infra.html_render_common"] = common_mod

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = SRC / "nonebot_plugin_steam_info" / "res" / "templates"
OUTPUT_DIR = ROOT / "cache" / "preview"


def make_test_data():
    friends = []

    # Gaming friends
    friends.append({
        "steamid": "1001",
        "avatar": Image.new("RGBA", (50, 50), (120, 80, 200, 255)),
        "avatar_frame": None,
        "name": "我有玉玉症",
        "status": "NARAKA: BLADEPOINT",
        "personastate": 1,
        "nickname": None,
        "game_icon": Image.new("RGBA", (34, 34), (60, 120, 60, 255)),
        "game_name": "NARAKA: BLADEPOINT",
    })
    friends.append({
        "steamid": "1002",
        "avatar": Image.new("RGBA", (50, 50), (200, 180, 100, 255)),
        "avatar_frame": None,
        "name": "Z总",
        "status": "HELLDIVERS™ 2",
        "personastate": 1,
        "nickname": None,
        "game_icon": Image.new("RGBA", (34, 34), (180, 40, 40, 255)),
        "game_name": "HELLDIVERS™ 2",
    })
    friends.append({
        "steamid": "1003",
        "avatar": Image.new("RGBA", (50, 50), (100, 150, 220, 255)),
        "avatar_frame": None,
        "name": "旭旭",
        "status": "HELLDIVERS™ 2",
        "personastate": 4,
        "nickname": None,
        "game_icon": Image.new("RGBA", (34, 34), (180, 40, 40, 255)),
        "game_name": "HELLDIVERS™ 2",
    })

    # Online friends
    for i, (name, state) in enumerate([
        ("酥松SUNi", 1),
        ("Misty", 1),
        ("只是她的男朋友", 1),
        ("AK47YT", 1),
        ("旭旭_away", 3),
        ("Player_001", 2),
    ]):
        status_map = {1: "在线", 2: "在线", 3: "离开", 4: "在线"}
        friends.append({
            "steamid": f"200{i}",
            "avatar": Image.new("RGBA", (50, 50), (80 + i * 25, 120, 180 - i * 15, 255)),
            "avatar_frame": None,
            "name": name,
            "status": status_map.get(state, "在线"),
            "personastate": state,
            "nickname": None,
            "game_icon": None,
            "game_name": None,
        })

    # Offline friend
    friends.append({
        "steamid": "3001",
        "avatar": Image.new("RGBA", (50, 50), (100, 100, 100, 255)),
        "avatar_frame": None,
        "name": "偷窥喵",
        "status": "上次在线 1 个月前",
        "personastate": 0,
        "nickname": None,
        "game_icon": None,
        "game_name": None,
    })

    return friends


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    parent_avatar = Image.new("RGBA", (72, 72), (100, 160, 220, 255))
    parent_name = "播"
    test_data = make_test_data()

    # --- Generate PIL rendering ---
    pil_image = draw_mod.draw_friends_status(
        parent_avatar.copy(), parent_name, list(test_data)
    )
    pil_path = OUTPUT_DIR / "preview_pil.png"
    pil_image.save(pil_path)
    print(f"PIL: {pil_path}")

    # --- Generate HTML ---
    sections = common_mod.build_sections(test_data)
    context = common_mod.friends_status_template_context(
        parent_avatar, parent_name, sections
    )

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=False)
    template = env.get_template("friends_status.html")
    html_content = template.render(**context)

    html_path = OUTPUT_DIR / "preview_html.html"
    html_path.write_text(html_content, encoding="utf-8")
    print(f"HTML: {html_path}")
    print("Open the HTML file in a browser to see the layout.")


if __name__ == "__main__":
    main()
