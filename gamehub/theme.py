# -*- coding: utf-8 -*-
"""界面尺寸与配色（渲染层和主程序共用）。"""

# 窗口与卡片布局
W, H = 1200, 560
CARD_X = [48, 330, 612, 894]
CARD_Y, CARD_W, CARD_H = 124, 258, 340
PER_PAGE = len(CARD_X)

# 卡片内部相对坐标
ICON_SIZE = 84
ICON_Y = 28
NAME_Y = 140
SCRIPT_Y = 164
DIVIDER_Y = 186
STATUS_Y = 210
BTN_W, BTN_H = 99, 44
BTN_Y = 236
BTN_GAP = 12
LINK_Y = 308

# 顶部工具栏（x, y, w, h）
ADD_RECT = (536, 32, 104, 30)
CHECK_RECT = (650, 32, 104, 30)
RESCAN_RECT = (764, 32, 112, 30)
CLASH_RECT = (886, 32, 136, 30)

# 翻页箭头
PAGE_LEFT_RECT = (8, 278, 32, 32)
PAGE_RIGHT_RECT = (1160, 278, 32, 32)

# 页脚
FOOT_DIVIDER_Y = 488
FOOT_Y = 520

# 颜色
BG_TOP = (10, 13, 19)
BG_BOTTOM = (16, 22, 34)
CARD_BG = (20, 26, 36)
CARD_BG_HOVER = (27, 35, 48)
CARD_BORDER = (35, 44, 59)
TXT = (234, 240, 248)
TXT2 = (154, 168, 188)
TXT3 = (104, 120, 142)

HEX_BG = "#0a0d13"
HEX_TXT = "#eaf0f8"
HEX_TXT2 = "#9aa8bc"
HEX_TXT3 = "#68788e"
HEX_OK = "#4ade80"
HEX_ERR = "#ff7f7f"
HEX_WAIT = "#ffce6b"

# 预设主题色
ACCENT_PRESETS = [
    ("蔚蓝", "#4fc3ff"),
    ("紫罗兰", "#b98bff"),
    ("青碧", "#5ee7c7"),
    ("明黄", "#ffe066"),
    ("橙红", "#ff8f7a"),
    ("玫红", "#ff8fc7"),
    ("薄荷", "#9ae66e"),
    ("雾蓝", "#8fb8ff"),
]

FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
