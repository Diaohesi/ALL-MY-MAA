# -*- coding: utf-8 -*-
"""运行时界面渲染：背景、卡片、按钮、圆点等都用 Pillow 动态绘制。

这样新增/删除游戏后无需重新生成素材，卡片数量可以随意变化。
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import theme as T

_icon_cache = {}
_font_cache = {}


def font(size, bold=False):
    key = (size, bold)
    if key not in _font_cache:
        path = T.FONT_BOLD if bold else T.FONT_REG
        if not os.path.exists(path):
            path = "arial.ttf"
        _font_cache[key] = ImageFont.truetype(path, size)
    return _font_cache[key]


def hex2rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def accent_rgba(accent, alpha=255):
    r, g, b = hex2rgb(accent)
    return (r, g, b, alpha)


def load_icon(path, size=256):
    """加载 256px 图标并缓存。"""
    if path in _icon_cache:
        return _icon_cache[path]
    try:
        img = Image.open(path).convert("RGBA")
    except Exception:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    _icon_cache[path] = img
    return img


def fit_icon(img, size):
    w, h = img.size
    scale = min(size / w, size / h)
    return img.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)


def vertical_gradient(size, top, bottom):
    w, h = size
    grad = Image.new("RGB", (1, h))
    px = grad.load()
    for y in range(h):
        t = y / max(1, h - 1)
        px[0, y] = tuple(round(top[c] + (bottom[c] - top[c]) * t) for c in range(3))
    return grad.resize((w, h), Image.NEAREST)


def radial_glow(img, center, radius, color, blur=60):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    x, y = center
    ImageDraw.Draw(layer).ellipse(
        [x - radius, y - radius, x + radius, y + radius], fill=color)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


def _divider(draw, y, x0, x1, color=(30, 39, 53, 255)):
    draw.line([x0, y, x1, y], fill=color, width=1)


def _draw_header(img, total, accents):
    d = ImageDraw.Draw(img)
    lx, ly, ls = 48, 30, 32
    d.rounded_rectangle([lx, ly, lx + ls, ly + ls], 9,
                        fill=(24, 31, 44, 255), outline=(47, 58, 78, 255), width=1)
    dots = [(lx + 10, ly + 11), (lx + 22, ly + 11), (lx + 10, ly + 23), (lx + 22, ly + 23)]
    for i, (dx, dy) in enumerate(dots):
        color = accent_rgba(accents[i % len(accents)] if accents else "#4fc3ff")
        d.ellipse([dx - 3, dy - 3, dx + 3, dy + 3], fill=color)

    d.text((lx + ls + 14, ly - 2), "游戏脚本中心", font=font(22, True),
           fill=(*T.TXT, 255), anchor="la")
    d.text((lx + ls + 14, ly + 32), f"一个窗口，管理 {total} 个游戏脚本",
           font=font(11), fill=(*T.TXT3, 255), anchor="la")

    # 版本徽标
    bw, bh = 118, 26
    bx, by = T.W - 48 - bw, 34
    d.rounded_rectangle([bx, by, bx + bw, by + bh], 13,
                        fill=(21, 27, 38, 255), outline=(42, 53, 71, 255), width=1)
    from . import VERSION
    d.text((bx + bw / 2, by + bh / 2), f"v{VERSION}", font=font(10),
           fill=(*T.TXT2, 255), anchor="mm")


def _draw_card(img, x, y, app, hovered, icon_img):
    d = ImageDraw.Draw(img)
    w, h = T.CARD_W, T.CARD_H
    accent = app.get("accent", "#4fc3ff")

    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [x + 2, y + 8, x + w - 2, y + h + 8], 18, fill=(0, 0, 0, 80))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)))

    if hovered:
        radial_glow(img, (x + w // 2, y + 40), 150, accent_rgba(accent, 22), blur=70)

    fill = T.CARD_BG_HOVER if hovered else T.CARD_BG
    border = accent_rgba(accent, 120) if hovered else (*T.CARD_BORDER, 255)
    d.rounded_rectangle([x, y, x + w, y + h], 18, fill=(*fill, 255),
                        outline=border, width=1)
    d.line([x + 26, y + 1, x + w - 26, y + 1],
           fill=accent_rgba(accent, 220 if hovered else 110), width=2)

    cx = x + w // 2
    radial_glow(img, (cx, y + T.ICON_Y + T.ICON_SIZE // 2),
                66, accent_rgba(accent, 26 if hovered else 16), blur=44)
    icon = fit_icon(icon_img, T.ICON_SIZE)
    img.alpha_composite(icon, (cx - icon.width // 2,
                               y + T.ICON_Y + (T.ICON_SIZE - icon.height) // 2))

    name, name_size = _fit_name(d, app["game"], w - 32)
    d.text((cx, y + T.NAME_Y), name, font=font(name_size, True),
           fill=(255, 255, 255, 255) if hovered else (*T.TXT, 255), anchor="mm")
    _divider(d, y + T.DIVIDER_Y, x + 24, x + w - 24)


def _fit_name(draw, text, max_width):
    """名字太长时缩小字号，仍然放不下就截断加省略号。返回 (文本, 字号)。"""
    for size in (19, 17, 15):
        if draw.textlength(text, font=font(size, True)) <= max_width:
            return text, size
    while text and draw.textlength(text + "…", font=font(15, True)) > max_width:
        text = text[:-1]
    return text + "…", 15


def render_window(apps, hover_index, icons, total):
    """渲染整窗背景（apps 为当前页的卡片数据）。"""
    img = vertical_gradient((T.W, T.H), T.BG_TOP, T.BG_BOTTOM).convert("RGBA")
    radial_glow(img, (150, 330), 420, (79, 195, 255, 15), blur=120)
    radial_glow(img, (860, 210), 380, (185, 139, 255, 13), blur=120)
    radial_glow(img, (610, 560), 420, (255, 206, 107, 9), blur=130)

    dots = Image.new("RGBA", (T.W, T.H), (0, 0, 0, 0))
    dd = ImageDraw.Draw(dots)
    for gy in range(0, T.H, 32):
        for gx in range(0, T.W, 32):
            dd.ellipse([gx, gy, gx + 1, gy + 1], fill=(255, 255, 255, 7))
    img.alpha_composite(dots)

    accents = [a.get("accent", "#4fc3ff") for a in apps]
    _draw_header(img, total, accents)

    for i, app in enumerate(apps):
        icon = load_icon(app.get("icon_path", ""))
        _draw_card(img, T.CARD_X[i], T.CARD_Y, app, i == hover_index, icon)

    _divider(ImageDraw.Draw(img), T.FOOT_DIVIDER_Y, 48, T.W - 48)
    d = ImageDraw.Draw(img)
    d.text((T.W - 48, T.FOOT_Y), "右键卡片打开菜单 · F5 检查更新 · Esc 退出",
           font=font(10), fill=(*T.TXT3, 255), anchor="ra")
    return img.convert("RGB")


# ---------------------------------------------------------------- 小部件
def _supersampled(w, h, painter, scale=4):
    img = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    painter(ImageDraw.Draw(img), scale)
    return img.resize((w, h), Image.LANCZOS)


def render_pill(w, h, state, border=None, radius=None):
    """工具栏 / 翻页用的小按钮底图。"""
    def paint(d, s):
        r = (radius if radius is not None else h // 2) * s
        if state == "hover":
            fill, outline = (24, 34, 48, 255), (*border, 200)
        else:
            fill, outline = (20, 26, 37, 255), (40, 52, 70, 255)
        d.rounded_rectangle([0, 0, w * s - 1, h * s - 1], r, fill=fill,
                            outline=outline, width=s)
    return _supersampled(w, h, paint)


def render_script_button(accent, state):
    def paint(d, s):
        w, h = T.BTN_W * s, T.BTN_H * s
        if state == "off":
            d.rounded_rectangle([0, 0, w - 1, h - 1], 12 * s,
                                fill=(19, 25, 35, 255), outline=(36, 46, 61, 255), width=s)
            return
        alpha = 44 if state == "hover" else 22
        edge = 190 if state == "hover" else 95
        d.rounded_rectangle([0, 0, w - 1, h - 1], 12 * s,
                            fill=accent_rgba(accent, alpha),
                            outline=accent_rgba(accent, edge), width=s)
    return _supersampled(T.BTN_W, T.BTN_H, paint)


def render_game_button(state):
    def paint(d, s):
        w, h = T.BTN_W * s, T.BTN_H * s
        if state == "hover":
            fill, outline = (27, 36, 49, 255), (78, 98, 126, 255)
        else:
            fill, outline = (19, 25, 35, 255), (42, 53, 71, 255)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 12 * s, fill=fill,
                            outline=outline, width=s)
    return _supersampled(T.BTN_W, T.BTN_H, paint)


def render_dot(on=True, color=None, size=5):
    color = color or ((74, 222, 128) if on else (70, 83, 106))
    pad = 6
    def paint(d, s):
        cx = cy = (size + pad) * s
        if on:
            d.ellipse([cx - size * s, cy - size * s, cx + size * s, cy + size * s],
                      fill=(*color[:3], 90))
        d.ellipse([cx - size * s / 2, cy - size * s / 2,
                   cx + size * s / 2, cy + size * s / 2], fill=(*color[:3], 255))
    img = _supersampled((size + pad) * 2, (size + pad) * 2, paint)
    return img


def render_page_arrow(direction, hovered):
    size = 32
    def paint(d, s):
        fill = (24, 34, 48, 255) if hovered else (18, 24, 34, 255)
        outline = (90, 160, 230, 220) if hovered else (40, 52, 70, 255)
        d.ellipse([0, 0, size * s - 1, size * s - 1], fill=fill,
                  outline=outline, width=s)
        c = (size // 2) * s
        off = 4 * s
        color = (234, 240, 248, 255) if hovered else (154, 168, 188, 255)
        if direction == "left":
            d.line([c + off // 2, c - off, c - off // 2, c], fill=color, width=2 * s)
            d.line([c - off // 2, c, c + off // 2, c + off], fill=color, width=2 * s)
        else:
            d.line([c - off // 2, c - off, c + off // 2, c], fill=color, width=2 * s)
            d.line([c + off // 2, c, c - off // 2, c + off], fill=color, width=2 * s)
    return _supersampled(size, size, paint)


def render_hub_icon():
    """窗口 / 快捷方式图标（2x2 彩点）。"""
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([8, 8, 248, 248], 60, fill=(15, 20, 30, 255),
                        outline=(40, 51, 69, 255), width=4)
    for i, (dx, dy) in enumerate([(88, 96), (168, 96), (88, 176), (168, 176)]):
        color = hex2rgb(T.ACCENT_PRESETS[i][1])
        d.ellipse([dx - 20, dy - 20, dx + 20, dy + 20], fill=(*color, 255))
    return img
