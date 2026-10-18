# -*- coding: utf-8 -*-
"""GameHub 精简版 —— 界面素材生成脚本。

运行 `python build_assets.py` 会在 ..\\assets 下生成全部 PNG / ICO 素材：
  bg_home.png           默认窗口背景（含所有静态卡片与文字）
  bg_hover_0..3.png     鼠标悬停某张卡片时的窗口背景
  button_<i>_normal.png / _hover.png / _off.png   每个启动按钮的底图
  clash_<state>.png / rescan_<state>.png          右上角两个小按钮
  dot_on.png / dot_off.png                        运行状态圆点
  hub.png / hub.ico                               窗口图标

主程序 hub.pyw 只依赖 tkinter，运行时不需要 Pillow。
"""
import os
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets")
os.makedirs(ASSETS, exist_ok=True)

# ---------------------------------------------------------------- 基础尺寸
W, H = 1200, 560
CARD_W, CARD_H = 258, 342
CARD_X = [48, 330, 612, 894]
CARD_Y = 126
CARD_R = 18

# ---------------------------------------------------------------- 配色
BG_TOP = (10, 13, 19)
BG_BOTTOM = (16, 22, 34)
CARD_BG = (20, 26, 36)
CARD_BG_HOVER = (27, 35, 48)
CARD_BORDER = (35, 44, 59)
TXT = (234, 240, 248)
TXT2 = (154, 168, 188)
TXT3 = (104, 120, 142)

ACCENTS = ["#4FC3FF", "#B98BFF", "#5EE7C7", "#FFE066"]

GAMES = [
    dict(key="maa", game="明日方舟", script="MAA", version="v6.19.0"),
    dict(key="nte", game="异环", script="MaaNTE", version="v1.6.0"),
    dict(key="wuwa", game="鸣潮", script="ok-ww", version="v3.7.4"),
    dict(key="maaend", game="明日方舟终末地", script="MaaEnd", version="v2.33.0"),
]

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)
    return _font_cache[key]


def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def accent(i, a=255):
    r, g, b = hex2rgb(ACCENTS[i])
    return (r, g, b, a)


# ---------------------------------------------------------------- 工具
def rounded_mask(size, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=255)
    return m


def radial_glow(img, center, radius, color, blur=60):
    """在 img 上叠加一团柔光。"""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x, y = center
    d.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def vertical_gradient(size, top, bottom):
    w, h = size
    grad = Image.new("RGB", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(round(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
    return grad.resize((w, h), Image.NEAREST)


def draw_text(d, xy, text, size, color, bold=False, anchor="mm"):
    d.text(xy, text, font=font(size, bold), fill=color, anchor=anchor)


# ---------------------------------------------------------------- 基础背景
def base_canvas():
    img = vertical_gradient((W, H), BG_TOP, BG_BOTTOM).convert("RGBA")
    radial_glow(img, (150, 330), 420, (79, 195, 255, 15), blur=120)
    radial_glow(img, (860, 210), 380, (185, 139, 255, 13), blur=120)
    radial_glow(img, (610, 560), 420, (255, 206, 107, 9), blur=130)
    # 极细的装饰网格点
    dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for gy in range(0, H, 32):
        for gx in range(0, W, 32):
            dd.ellipse([gx, gy, gx + 1, gy + 1], fill=(255, 255, 255, 7))
    img.alpha_composite(dots)
    return img


def draw_header(img):
    d = ImageDraw.Draw(img)
    # logo: 圆角方块 + 三个彩色圆点
    lx, ly, ls = 48, 30, 32
    d.rounded_rectangle([lx, ly, lx + ls, ly + ls], 9, fill=(24, 31, 44, 255),
                        outline=(47, 58, 78, 255), width=1)
    dot_xy = [(lx + 10, ly + 11), (lx + 21, ly + 11), (lx + 10, ly + 22)]
    for i, (dx, dy) in enumerate(dot_xy):
        c = accent(i)
        d.ellipse([dx - 3, dy - 3, dx + 3, dy + 3], fill=c)
    d.ellipse([lx + 18, ly + 19, lx + 24, ly + 25], fill=accent(2))

    draw_text(d, (lx + ls + 14, ly - 2), "游戏脚本中心", 22, TXT, bold=True, anchor="la")
    draw_text(d, (lx + ls + 14, ly + 32), "一个窗口，启动你的四个自动化脚本",
              11, TXT3, anchor="la")

    # 右上角版本徽标
    bw, bh = 118, 26
    bx, by = W - 48 - bw, 36
    d.rounded_rectangle([bx, by, bx + bw, by + bh], 13, fill=(21, 27, 38, 255),
                        outline=(42, 53, 71, 255), width=1)
    draw_text(d, (bx + bw / 2, by + bh / 2 - 1), "精简版 v0.3", 10, TXT2)


def draw_divider(img, y, x0, x1, color=(30, 39, 53, 255)):
    d = ImageDraw.Draw(img)
    d.line([x0, y, x1, y], fill=color, width=1)


def load_icon(key, size):
    src = os.path.join(ASSETS, f"{key}.png")  # 256x256 高清源图
    if not os.path.exists(src):
        src = os.path.join(ROOT, "assets", f"{key}.png")
    img = Image.open(src).convert("RGBA")
    # 图标四周留一点白边裁掉，避免贴边
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    scale = size / max(w, h)
    img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
    return img


def draw_card(img, i, hovered):
    x, y = CARD_X[i], CARD_Y
    d = ImageDraw.Draw(img)

    # 卡片下方的柔光阴影
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([x + 2, y + 8, x + CARD_W - 2, y + CARD_H + 8],
                         CARD_R, fill=(0, 0, 0, 80))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))

    if hovered:
        radial_glow(img, (x + CARD_W // 2, y + 40), 150, accent(i, 22), blur=70)

    fill = CARD_BG_HOVER if hovered else CARD_BG
    border = accent(i, 120) if hovered else (*CARD_BORDER, 255)
    d.rounded_rectangle([x, y, x + CARD_W, y + CARD_H], CARD_R, fill=(*fill, 255),
                        outline=border, width=1)

    # 顶部强调线
    ax0, ax1 = x + 26, x + CARD_W - 26
    d.line([ax0, y + 1, ax1, y + 1], fill=accent(i, 220 if hovered else 110), width=2)

    cx = x + CARD_W // 2

    # 图标光晕 + 图标
    radial_glow(img, (cx, y + 73), 66, accent(i, 26 if hovered else 16), blur=44)
    icon = load_icon(GAMES[i]["key"], 86)
    img.alpha_composite(icon, (cx - icon.width // 2, y + 30 + (86 - icon.height) // 2))

    draw_text(d, (cx, y + 142), GAMES[i]["game"], 19,
              TXT if not hovered else (255, 255, 255), bold=True)
    # 脚本名与版本号由主程序动态绘制（方便脚本升级后自动显示新版本）

    draw_divider(img, y + 188, x + 24, x + CARD_W - 24, (30, 39, 53, 255))

    # 状态胶囊底（文字与圆点由主程序绘制）
    px0, px1 = cx - 48, cx + 48
    d.rounded_rectangle([px0, y + 204, px1, y + 228], 12, fill=(13, 18, 26, 255),
                        outline=(33, 42, 56, 255), width=1)

    # 按钮底图、底部操作链接由主程序绘制


def render_bg(hover_index=None):
    img = base_canvas()
    draw_header(img)
    for i in range(len(GAMES)):
        draw_card(img, i, i == hover_index)
    draw_divider(img, 492, 48, W - 48)
    draw_text(ImageDraw.Draw(img), (W - 48, 520),
              "点击卡片启动 · F5 检查更新 · Esc 退出", 10, TXT3, anchor="ra")
    return img.convert("RGB")


# ---------------------------------------------------------------- 按钮 / 圆点
BTN_W, BTN_H, BTN_R = CARD_W - 48, 44, 12


def render_button(i, state):
    """state: normal / hover / off"""
    img = Image.new("RGBA", (BTN_W, BTN_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if state == "normal":
        d.rounded_rectangle([0, 0, BTN_W - 1, BTN_H - 1], BTN_R,
                            fill=accent(i, 22), outline=accent(i, 95), width=1)
    elif state == "hover":
        d.rounded_rectangle([0, 0, BTN_W - 1, BTN_H - 1], BTN_R,
                            fill=accent(i, 44), outline=accent(i, 190), width=1)
    else:  # off
        d.rounded_rectangle([0, 0, BTN_W - 1, BTN_H - 1], BTN_R,
                            fill=(19, 25, 35, 255), outline=(36, 46, 61, 255), width=1)
    return img


def render_dot(size=10, on=True):
    img = Image.new("RGBA", (size * 4, size * 4), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = (74, 222, 128) if on else (70, 83, 106)
    cx = cy = size * 2
    if on:
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([cx - size, cy - size, cx + size, cy + size], fill=(*c, 90))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(5)))
    d.ellipse([cx - size / 2, cy - size / 2, cx + size / 2, cy + size / 2], fill=(*c, 255))
    return img


CLASH_W, CLASH_H, CLASH_R = 136, 28, 14
RESCAN_W, RESCAN_H = 112, 28


def _pill_button(w, h, state):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if state == "normal":
        d.rounded_rectangle([0, 0, w - 1, h - 1], h // 2,
                            fill=(20, 26, 37, 255), outline=(40, 52, 70, 255), width=1)
    else:
        d.rounded_rectangle([0, 0, w - 1, h - 1], h // 2,
                            fill=(24, 34, 48, 255), outline=(90, 160, 230, 200), width=1)
    return img


def render_clash_button(state):
    """右上角「打开 Clash Verge」按钮底图。"""
    return _pill_button(CLASH_W, CLASH_H, state)


def render_rescan_button(state):
    """右上角「重新识别路径」按钮底图。"""
    return _pill_button(RESCAN_W, RESCAN_H, state)


# ---------------------------------------------------------------- 主流程
def main():
    # 1. 应用图标（若缺失，先运行 extract_icons.py 生成 256 源图）
    missing = [g["key"] for g in GAMES if not os.path.exists(os.path.join(ASSETS, g["key"] + ".png"))]
    if missing:
        print(f"[提示] 缺少图标源文件 {missing}，先运行 extract_icons.py")

    # 2. 背景
    render_bg(None).save(os.path.join(ASSETS, "bg_home.png"))
    for i in range(len(GAMES)):
        render_bg(i).save(os.path.join(ASSETS, f"bg_hover_{i}.png"))

    # 3. 按钮
    for i in range(len(GAMES)):
        for state in ("normal", "hover", "off"):
            render_button(i, state).save(os.path.join(ASSETS, f"button_{i}_{state}.png"))

    # 4. 圆点
    render_dot(5, True).save(os.path.join(ASSETS, "dot_on.png"))
    render_dot(5, False).save(os.path.join(ASSETS, "dot_off.png"))

    # 5. 右上角两个小按钮
    for state in ("normal", "hover"):
        render_clash_button(state).save(os.path.join(ASSETS, f"clash_{state}.png"))
        render_rescan_button(state).save(os.path.join(ASSETS, f"rescan_{state}.png"))

    # 6. Hub 图标（2x2 彩点，对应四个脚本）
    hub = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(hub)
    d.rounded_rectangle([8, 8, 248, 248], 60, fill=(15, 20, 30, 255),
                        outline=(40, 51, 69, 255), width=4)
    for i, (dx, dy) in enumerate([(88, 96), (168, 96), (88, 176), (168, 176)]):
        d.ellipse([dx - 20, dy - 20, dx + 20, dy + 20], fill=accent(i))
    hub.save(os.path.join(ASSETS, "hub.png"))
    hub.save(os.path.join(ASSETS, "hub.ico"),
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("[完成] 素材已生成到", ASSETS)


if __name__ == "__main__":
    main()
