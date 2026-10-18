# -*- coding: utf-8 -*-
"""界面尺寸与配色（渲染层和主程序共用）。"""

# 窗口与卡片布局
W, H = 1200, 560
# v0.8/v0.9 主窗口（侧边栏 + 三页）；W/H 保留给旧版 Pillow 背景渲染（回归测试）
WIN_W, WIN_H = 1180, 760
MIN_W, MIN_H = 1000, 640
SIDEBAR_W = 232

# ---------------------------------------------------------------- v0.9 设计令牌
# 字体：统一 Microsoft YaHei UI；最小辅助字号 10，不使用更小字号
UI_FONT = "Microsoft YaHei UI"
UI_FONT_SIZES = {
    "title": 21,      # 页面标题 20-22
    "page": 16,       # 页面/侧边栏标题
    "name": 13,       # 卡片/游戏名
    "body": 11,       # 正文
    "aux": 10,        # 辅助信息（最小 10）
}
# 圆角与间距（8/12/16/20 体系）
RADIUS = 12
RADIUS_SM = 8
SPACE_XS = 8
SPACE_SM = 12
SPACE_MD = 16
SPACE_LG = 20
SPACE_XL = 24
# 色板：深色 surface 分层 + 柔和描边
UI_BG = "#0b0f16"
UI_SIDEBAR = "#0f1520"
UI_PANEL = "#141b26"
UI_PANEL_2 = "#1a2331"
UI_PANEL_3 = "#223043"
UI_BORDER = "#263244"
UI_BORDER_SOFT = "#1d2735"
UI_TEXT = "#e9eef7"
UI_TEXT_2 = "#a7b4c8"
UI_TEXT_3 = "#7d8ba1"
UI_ACCENT = "#4fc3ff"
UI_ACCENT_SOFT = "#1f3a4f"
UI_SUCCESS = "#4ade80"
UI_WARNING = "#ffce6b"
UI_DANGER = "#ff7f7f"
UI_DANGER_SOFT = "#3a2430"
# 兼容旧 UI 常量名（v0.8 及渲染代码仍引用）
HEX_BG = UI_BG
HEX_TXT = UI_TEXT
HEX_TXT2 = UI_TEXT_2
HEX_TXT3 = UI_TEXT_3
HEX_OK = UI_SUCCESS
HEX_ERR = UI_DANGER
HEX_WAIT = UI_WARNING
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

# 顶部工具栏（x, y, w, h）；v0.7 增加「一键清日常」并压缩原有按钮
ADD_RECT = (452, 32, 94, 30)
CHECK_RECT = (554, 32, 98, 30)
RESCAN_RECT = (660, 32, 116, 30)
DAILY_RECT = (784, 32, 116, 30)
CLASH_RECT = (908, 32, 114, 30)

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
