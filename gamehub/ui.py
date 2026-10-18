# -*- coding: utf-8 -*-
"""主界面与对话框：卡片、工具栏、添加/编辑游戏、启动/下载等交互。"""
import ctypes
import os
import queue
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
from tkinter import filedialog, messagebox

from PIL import ImageTk

from . import VERSION, daily, detector, render, store
from . import theme as T

TITLE = "游戏脚本中心"


def _dark_titlebar(root):
    try:
        user32 = ctypes.windll.user32
        dwm = ctypes.WinDLL("dwmapi")
        hwnd = user32.GetAncestor(root.winfo_id(), 2)
        caption = 0x00140E0B
        for attr, value in ((20, 1), (34, caption), (35, caption), (36, 0x00F9F5F2)):
            v = ctypes.c_int(value)
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v))
    except Exception:
        pass


def _flat_button(parent, text, command, accent=False):
    """深色扁平按钮（主界面各对话框共用）。"""
    bg = "#25445f" if accent else "#1b2432"
    active = "#2d5577" if accent else "#26313f"
    return tk.Button(parent, text=text, command=command, bg=bg, fg="#eaf0f8",
                     activebackground=active, activeforeground="#ffffff",
                     relief="flat", bd=0, padx=14, pady=5,
                     font=("Microsoft YaHei", -11), cursor="hand2")


class AppDialog(tk.Toplevel):
    """添加 / 编辑一个游戏脚本卡片。"""

    FIELDS = [
        ("game", "游戏名称 *", "例如：明日方舟"),
        ("script", "脚本名称 *", "例如：MAA"),
        ("script_exe", "脚本启动程序 *", ""),
        ("script_procs", "脚本进程名", "可选，多个用逗号分隔"),
        ("game_exe", "游戏启动程序", "可选，用于「启动游戏」"),
        ("game_procs", "游戏进程名", "可选，用于显示游戏运行状态"),
        ("site", "脚本官网", "可选"),
        ("github", "GitHub 地址", "可选"),
        ("release", "更新检查地址", "可选，GitHub releases/latest"),
        ("download", "游戏下载页", "可选，点「下载游戏」时打开"),
        ("icon", "自定义图标", "可选，png / ico"),
    ]

    # 检测规则（用于判断「游戏运行中」；留空则用脚本自动规则）
    DETECT_FIELDS = [
        ("win_class", "检测：窗口类", "正则，如 ^UnrealWindow$"),
        ("win_title", "检测：窗口标题", "正则，如 异环"),
        ("detect_procs", "检测：进程名", "多个用逗号分隔"),
        ("adb_pkg", "检测：ADB 包名", "可选，多个用逗号分隔"),
    ]

    def __init__(self, master, app=None, on_save=None, on_delete=None):
        super().__init__(master)
        self.title("编辑游戏卡片" if app else "添加游戏")
        self.configure(bg="#0f141d")
        self.resizable(False, False)
        self.transient(master)
        self.on_save = on_save
        self.on_delete = on_delete
        self.editing = app is not None
        self.app = app or {}
        self.values = {}
        self.accent = self.app.get("accent") or T.ACCENT_PRESETS[0][1]
        self._chip_refs = []
        try:
            self.detect_initial = detector.rules_to_fields(
                detector.read_game_rules(self.app))
        except Exception:
            self.detect_initial = {}
        self._build()
        self.minsize(640, 0)
        self.grab_set()
        self._center()

    # ---------------------------------------------------------- 界面
    def _entry(self, parent, value=""):
        entry = tk.Entry(parent, bg="#101620", fg="#eaf0f8", insertbackground="#eaf0f8",
                         relief="flat", highlightthickness=1,
                         highlightbackground="#2a3547", highlightcolor="#4fc3ff",
                         font=("Microsoft YaHei", -11), width=34)
        entry.insert(0, value or "")
        return entry

    def _button(self, parent, text, command, accent=False):
        return _flat_button(parent, text, command, accent=accent)

    def _build(self):
        pad = 18
        body = tk.Frame(self, bg="#0f141d")
        body.pack(fill="both", expand=True, padx=pad, pady=(pad, 6))
        body.columnconfigure(1, weight=1)

        tk.Label(body, text="填写后保存即可，路径会自动记录成相对路径",
                 bg="#0f141d", fg="#68788e",
                 font=("Microsoft YaHei", -10)).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 10))

        row = 1
        for field, label, hint in self.FIELDS:
            tk.Label(body, text=label, bg="#0f141d", fg="#9aa8bc",
                     font=("Microsoft YaHei", -11), anchor="e", width=14).grid(
                row=row, column=0, sticky="e", pady=4)
            entry = self._entry(body, self.app.get(field, ""))
            entry.grid(row=row, column=1, sticky="we", pady=4)
            self.values[field] = entry
            if field == "game_exe":
                box = tk.Frame(body, bg="#0f141d")
                box.grid(row=row, column=2, sticky="w", padx=(8, 0), pady=4)
                self._button(box, "浏览", lambda: self._browse("game_exe")).pack(
                    side="left")
                self._button(box, "自动检测", self._auto_detect_game).pack(
                    side="left", padx=(6, 0))
            elif field in ("script_exe", "icon"):
                self._button(body, "浏览", lambda f=field: self._browse(f)).grid(
                    row=row, column=2, padx=(8, 0), pady=4)
            elif hint:
                tk.Label(body, text=hint, bg="#0f141d", fg="#4d5c74",
                         font=("Microsoft YaHei", -9), anchor="w").grid(
                    row=row, column=2, sticky="w", padx=(8, 0))
            row += 1

        # 检测规则（可选）
        tk.Frame(body, bg="#243044", height=1).grid(
            row=row, column=0, columnspan=3, sticky="we", pady=(10, 2))
        row += 1
        tk.Label(body, text="检测规则（可选，用于准确判断「游戏运行中」）",
                 bg="#0f141d", fg="#68788e",
                 font=("Microsoft YaHei", -10)).grid(
            row=row, column=0, columnspan=3, sticky="w", pady=(2, 4))
        row += 1
        for field, label, hint in self.DETECT_FIELDS:
            tk.Label(body, text=label, bg="#0f141d", fg="#9aa8bc",
                     font=("Microsoft YaHei", -11), anchor="e", width=14).grid(
                row=row, column=0, sticky="e", pady=4)
            entry = self._entry(body, self.detect_initial.get(field, ""))
            entry.grid(row=row, column=1, sticky="we", pady=4)
            self.values[field] = entry
            if hint:
                tk.Label(body, text=hint, bg="#0f141d", fg="#4d5c74",
                         font=("Microsoft YaHei", -9), anchor="w").grid(
                    row=row, column=2, sticky="w", padx=(8, 0))
            row += 1

        # 主题色
        tk.Label(body, text="主题色", bg="#0f141d", fg="#9aa8bc",
                 font=("Microsoft YaHei", -11), anchor="e", width=14).grid(
            row=row, column=0, sticky="e", pady=6)
        colors = tk.Frame(body, bg="#0f141d")
        colors.grid(row=row, column=1, columnspan=2, sticky="w", pady=6)
        for name, color in T.ACCENT_PRESETS:
            chip = tk.Frame(colors, bg=color, width=26, height=26,
                            highlightthickness=3,
                            highlightbackground="#0f141d", cursor="hand2")
            chip.pack(side="left", padx=2)
            chip.bind("<Button-1>", lambda e, c=color, f=chip: self._pick_accent(c, f))
            self._chip_refs.append((color, chip))
        self._refresh_chips()

        # 底部按钮
        footer = tk.Frame(self, bg="#0f141d")
        footer.pack(fill="x", padx=pad, pady=(4, 14))
        self._button(footer, "保存", self._save, accent=True).pack(side="right")
        self._button(footer, "取消", self.destroy).pack(side="right", padx=(0, 8))
        if self.editing and self.on_delete and not self.app.get("builtin"):
            self._button(footer, "删除此卡片", self._delete).pack(side="left")

    def _refresh_chips(self):
        for color, chip in self._chip_refs:
            chip.configure(highlightbackground="#eaf0f8" if color == self.accent
                           else "#0f141d")

    def _pick_accent(self, color, chip):
        self.accent = color
        self._refresh_chips()

    def _browse(self, field):
        if field == "icon":
            path = filedialog.askopenfilename(
                parent=self, title="选择图标",
                filetypes=[("图片", "*.png;*.ico;*.jpg;*.jpeg"), ("所有文件", "*.*")])
        else:
            path = filedialog.askopenfilename(
                parent=self, title="选择可执行程序",
                filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.values[field].delete(0, "end")
            self.values[field].insert(0, os.path.normpath(path))

    def _detect_target(self):
        """自动检测用的 app 信息：优先编辑中的游戏，其次看用户刚输入的名称。"""
        game = ""
        if "game" in self.values:
            game = self.values["game"].get().strip()
        return {"key": self.app.get("key", ""), "game": game or self.app.get("game", "")}

    def _auto_detect_game(self):
        info = self._detect_target()
        self.config(cursor="watch")
        try:
            self.update_idletasks()
            candidates = store.find_game_candidates(info)
        except Exception:
            candidates = []
        finally:
            self.config(cursor="")
        if not candidates:
            messagebox.showinfo(
                "未检测到游戏启动程序",
                f"没有自动找到「{info['game'] or '该游戏'}」的启动程序。\n"
                "可以点「浏览」手动选择。",
                parent=self)
            return
        dialog = GameCandidateDialog(self, candidates)
        self.wait_window(dialog)
        try:
            self.grab_set()       # 候选框关掉后恢复编辑框的模态
        except Exception:
            pass
        if dialog.result:
            path = os.path.normpath(dialog.result)
            entry = self.values["game_exe"]
            entry.delete(0, "end")
            entry.insert(0, path)
            self._fill_detect_suggestion(path)

    def _fill_detect_suggestion(self, exe_path):
        """自动检测选中启动程序后，把脚本自带的检测规则填进空着的输入框。"""
        script_entry = self.values.get("script_exe")
        script_exe = script_entry.get().strip() if script_entry is not None else ""
        try:
            rules = detector.read_auto_rules({
                "key": self.app.get("key", ""),
                "game": self.app.get("game", ""),
                "script_exe": script_exe,
            })
            suggestion = detector.rules_to_fields(rules)
        except Exception:
            suggestion = {}
        if not suggestion.get("detect_procs"):
            suggestion["detect_procs"] = os.path.basename(exe_path)
        for field in ("win_class", "win_title", "detect_procs", "adb_pkg"):
            entry = self.values.get(field)
            if entry is None or entry.get().strip():
                continue
            value = suggestion.get(field, "")
            if value:
                entry.insert(0, value)

    def _center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        master = self.master
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + (master.winfo_height() - h) // 2
        self.geometry(f"+{max(0, x)}+{max(0, y)}")

    # ---------------------------------------------------------- 动作
    def _collect(self):
        data = {}
        for field in self.values:
            data[field] = self.values[field].get().strip()
        data["accent"] = self.accent
        if not data["game"] or not data["script"]:
            messagebox.showwarning("请填写完整", "游戏名称和脚本名称不能为空。", parent=self)
            return None
        if not data["script_exe"] or not os.path.isfile(data["script_exe"]):
            messagebox.showwarning("路径无效", "请选择正确的脚本启动程序（.exe）。", parent=self)
            return None
        if data["game_exe"] and not os.path.isfile(data["game_exe"]):
            messagebox.showwarning("路径无效", "游戏启动程序路径不存在。", parent=self)
            return None
        return data

    def _save(self):
        data = self._collect()
        if data and self.on_save:
            self.on_save(data)
        self.destroy()

    def _delete(self):
        if self.on_delete and messagebox.askyesno(
                "删除卡片", "确定要删除这个游戏卡片吗？\n（只删除 Hub 里的卡片，不会删除文件）",
                parent=self):
            self.on_delete()
            self.destroy()


class GameCandidateDialog(tk.Toplevel):
    """游戏启动程序候选选择框（深色）：双击候选或选中后点「确定」返回路径。"""

    def __init__(self, master, candidates, title="选择游戏启动程序"):
        super().__init__(master)
        self.title(title)
        self.configure(bg="#0f141d")
        self.resizable(False, False)
        self.transient(master)
        self.result = None
        self.candidates = list(candidates or [])
        self._path_var = tk.StringVar(value="")
        self._build()
        self.grab_set()
        self._center(master)

    def _build(self):
        pad = 16
        tk.Label(self, text=f"找到 {len(self.candidates)} 个候选，双击或选中后点「确定」",
                 bg="#0f141d", fg="#9aa8bc",
                 font=("Microsoft YaHei", -11)).pack(anchor="w", padx=pad, pady=(14, 8))
        body = tk.Frame(self, bg="#101620", highlightthickness=1,
                        highlightbackground="#2a3547")
        body.pack(fill="both", expand=True, padx=pad)
        self.listbox = tk.Listbox(
            body, bg="#101620", fg="#eaf0f8", selectbackground="#25445f",
            selectforeground="#ffffff", relief="flat", bd=0, highlightthickness=0,
            activestyle="none", font=("Microsoft YaHei", -11),
            width=96, height=min(9, max(3, len(self.candidates))))
        scroll = tk.Scrollbar(body, command=self.listbox.yview, width=10,
                              bg="#1b2432", troughcolor="#0f141d",
                              activebackground="#26313f", relief="flat", bd=0,
                              highlightthickness=0)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.listbox.pack(side="left", fill="both", expand=True)
        for candidate in self.candidates:
            name = candidate.get("name") or os.path.basename(candidate.get("path", ""))
            source = candidate.get("source") or ""
            path = self._short_path(candidate.get("path", ""))
            self.listbox.insert("end", f"{name}    〔{source}〕  {path}")
        if self.candidates:
            self.listbox.selection_set(0)
            self.listbox.activate(0)
            self._show_path(0)
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", lambda event: self._confirm())
        tk.Label(self, textvariable=self._path_var, bg="#0f141d", fg="#68788e",
                 font=("Microsoft YaHei", -9), anchor="w", justify="left",
                 wraplength=720).pack(fill="x", padx=pad, pady=(8, 0))
        footer = tk.Frame(self, bg="#0f141d")
        footer.pack(fill="x", padx=pad, pady=(12, 14))
        _flat_button(footer, "确定", self._confirm, accent=True).pack(side="right")
        _flat_button(footer, "取消", self._cancel).pack(side="right", padx=(0, 8))
        _flat_button(footer, "浏览…", self._browse).pack(side="left")
        self.bind("<Return>", lambda event: self._confirm())
        self.bind("<Escape>", lambda event: self._cancel())
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    @staticmethod
    def _short_path(path, limit=44):
        """列表里用中间省略的路径，完整路径在下方单独显示。"""
        path = str(path or "")
        if len(path) <= limit:
            return path
        head = limit // 2 - 2
        tail = limit - head - 3
        return f"{path[:head]}…{path[-tail:]}"

    def _on_select(self, _event=None):
        selection = self.listbox.curselection()
        if selection:
            self._show_path(selection[0])

    def _show_path(self, index):
        if 0 <= index < len(self.candidates):
            self._path_var.set(self.candidates[index]["path"])

    def _confirm(self):
        selection = self.listbox.curselection()
        if not selection:
            if not self.candidates:
                return
            selection = (0,)
        self.result = self.candidates[selection[0]]["path"]
        self.destroy()

    def _browse(self):
        path = filedialog.askopenfilename(
            parent=self, title="手动选择游戏启动程序",
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.result = os.path.normpath(path)
            self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    def _center(self, master):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - w) // 2
            y = master.winfo_rooty() + (master.winfo_height() - h) // 2
        except Exception:
            x = y = 100
        x = min(max(0, x), max(0, self.winfo_screenwidth() - w))
        y = min(max(0, y), max(0, self.winfo_screenheight() - h))
        self.geometry(f"+{x}+{y}")


class GameHub:
    def __init__(self, root):
        self.root = root
        self.apps, self.clash_exe, self.search_root, meta = store.load_state_full()
        self.daily_order = list(meta.get("daily_order")
                                or store.DEFAULT_DAILY_ORDER)
        self.config_saved = store.save_state(self.apps, self.clash_exe,
                                             self.search_root, self.daily_order)
        self.page = 0
        self.versions = {}
        self.latest = {}
        self.starting = {}
        self.running = {}
        self.game_states = {}
        self.adb_enabled = detector.ADB_ENABLED
        self.daily_queue = None
        self.daily_events = queue.Queue()
        self.daily_log = []
        self.daily_dialog = None
        self.hover = ("none",)
        self.toast_msg = "就绪 · 等待启动"
        self.toast_after = None
        self.checking = False
        self.manual_check = False
        self.update_queue = queue.Queue()
        self.photo = {}
        self.bg_photos = {}
        self.cards = []
        self._page_apps = []
        self.pages = 1
        self._setup_fonts()
        self._build_ui()
        self._rebuild()
        if not self.config_saved:
            self.root.after(300, self._warn_save_failed)
        self.root.after(120, self._poll)
        self.root.after(900, self._start_update_check)
        self._toast(self.toast_msg)

    # ---------------------------------------------------------- 基础
    def _save_config(self):
        """保存配置；失败时用 toast 提示，返回是否成功。"""
        saved = store.save_state(self.apps, self.clash_exe, self.search_root,
                                 self.daily_order)
        if not saved:
            self._toast("配置文件无法写入，本次修改无法保存")
        return saved

    def _warn_save_failed(self):
        messagebox.showwarning(
            "配置文件无法写入",
            "配置文件 config.json 无法写入，之后的修改将无法保存。\n"
            "请检查 Hub 所在目录是否有写入权限，或 config.json 是否被占用、设为只读。",
            parent=self.root)
    def _setup_fonts(self):
        fam = "Microsoft YaHei"
        self.f_script = tkfont.Font(family=fam, size=-11)
        self.f_status = tkfont.Font(family=fam, size=-10)
        self.f_btn = tkfont.Font(family=fam, size=-12, weight="bold")
        self.f_link = tkfont.Font(family=fam, size=-10)
        self.f_foot = tkfont.Font(family=fam, size=-10)

    def _build_ui(self):
        self.root.title(TITLE)
        self.root.configure(bg=T.HEX_BG)
        self.root.resizable(False, False)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{T.W}x{T.H}+{max(0, (sw - T.W) // 2)}+{max(0, (sh - T.H) // 2 - 20)}")
        try:
            self.icon = tk.PhotoImage(file=os.path.join(store.ASSETS, "hub.png"))
            self.root.iconphoto(True, self.icon)
        except Exception:
            pass
        _dark_titlebar(self.root)
        self.canvas = tk.Canvas(self.root, width=T.W, height=T.H, bg=T.HEX_BG,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Motion>", self._on_motion)
        self.canvas.bind("<Leave>", lambda e: self._set_hover(("none",)))
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<F5>", lambda e: self._on_refresh())
        for idx in range(T.PER_PAGE):
            self.root.bind(str(idx + 1), lambda e, i=idx: self.launch_script(i))
        self.root.focus_force()

    # ---------------------------------------------------------- 渲染
    def _toolbar_photo(self, name, rect, state, border=None):
        key = ("pill", name, state, border)
        if key not in self.photo:
            img = render.render_pill(rect[2], rect[3], state, border=border)
            self.photo[key] = ImageTk.PhotoImage(img, master=self.root)
        return self.photo[key]

    def _page_photo(self, direction, hovered):
        key = ("page", direction, hovered)
        if key not in self.photo:
            self.photo[key] = ImageTk.PhotoImage(
                render.render_page_arrow(direction, hovered), master=self.root)
        return self.photo[key]

    def _btn_photo(self, accent, state):
        key = ("scriptbtn", accent, state)
        if key not in self.photo:
            self.photo[key] = ImageTk.PhotoImage(
                render.render_script_button(accent, state), master=self.root)
        return self.photo[key]

    def _game_btn_photo(self, state):
        key = ("gamebtn", state)
        if key not in self.photo:
            self.photo[key] = ImageTk.PhotoImage(
                render.render_game_button(state), master=self.root)
        return self.photo[key]

    def _dot_photo(self, color, on):
        key = ("dot", color, on)
        if key not in self.photo:
            self.photo[key] = ImageTk.PhotoImage(
                render.render_dot(on, render.hex2rgb(color) if color else None),
                master=self.root)
        return self.photo[key]

    def _rebuild(self):
        self.pages = max(1, (len(self.apps) + T.PER_PAGE - 1) // T.PER_PAGE)
        self.page = max(0, min(self.page, self.pages - 1))
        self._page_apps = self.apps[self.page * T.PER_PAGE:(self.page + 1) * T.PER_PAGE]
        self.hover = ("none",)
        self.canvas.configure(cursor="")

        icons = {}
        for app in self._page_apps:
            icons[app["key"]] = None
        self.bg_photos = {}
        for hover_index in range(-1, len(self._page_apps)):
            img = render.render_window(self._page_apps, hover_index, icons, len(self.apps))
            self.bg_photos[hover_index] = ImageTk.PhotoImage(img, master=self.root)

        self.canvas.delete("all")
        self._bg_item = self.canvas.create_image(0, 0, anchor="nw",
                                                 image=self.bg_photos[-1])

        # 顶部工具栏
        self.toolbar = [
            ("add", "添加游戏", T.ADD_RECT, "#4fc3ff"),
            ("check", "检查更新", T.CHECK_RECT, "#b98bff"),
            ("rescan", "重新识别路径", T.RESCAN_RECT, "#5ee7c7"),
            ("daily", "一键清日常", T.DAILY_RECT, "#ffce6b"),
            ("clash", "打开 Clash Verge", T.CLASH_RECT, "#ffce6b"),
        ]
        self.toolbar_items = {}
        for name, label, rect, border in self.toolbar:
            x, y, w, h = rect
            image_item = self.canvas.create_image(
                x, y, anchor="nw", image=self._toolbar_photo(name, rect, "normal", border))
            text_item = self.canvas.create_text(
                x + w // 2, y + h // 2, text=label, font=self.f_link,
                fill=T.HEX_TXT2)
            self.toolbar_items[name] = (image_item, text_item, rect, border)

        # 翻页箭头 + 页码
        left = T.PAGE_LEFT_RECT
        right = T.PAGE_RIGHT_RECT
        self.page_items = {}
        if self.pages > 1:
            self.page_items["left"] = self.canvas.create_image(
                left[0], left[1], anchor="nw", image=self._page_photo("left", False))
            self.page_items["right"] = self.canvas.create_image(
                right[0], right[1], anchor="nw", image=self._page_photo("right", False))
            self.page_text = self.canvas.create_text(
                T.W // 2, T.FOOT_Y, text=f"{self.page + 1} / {self.pages}",
                font=self.f_foot, fill=T.HEX_TXT3)
        else:
            self.page_text = None

        # 卡片动态元素
        self.cards = []
        for i, app in enumerate(self._page_apps):
            x = T.CARD_X[i]
            cx = x + T.CARD_W // 2
            card = {}
            card["script_text"] = self.canvas.create_text(
                cx, T.CARD_Y + T.SCRIPT_Y, text="", font=self.f_script,
                fill=T.HEX_TXT3)

            card["script_dot"] = self.canvas.create_image(
                0, T.CARD_Y + T.STATUS_Y, anchor="w", image=self._dot_photo(None, False))
            card["script_status"] = self.canvas.create_text(
                0, T.CARD_Y + T.STATUS_Y, anchor="w", text="", font=self.f_status)
            card["game_dot"] = self.canvas.create_image(
                0, T.CARD_Y + T.STATUS_Y, anchor="w", image=self._dot_photo(None, False))
            card["game_status"] = self.canvas.create_text(
                0, T.CARD_Y + T.STATUS_Y, anchor="w", text="", font=self.f_status)

            btn_x = x + 24
            card["script_btn"] = self.canvas.create_image(
                btn_x, T.CARD_Y + T.BTN_Y, anchor="nw",
                image=self._btn_photo(app["accent"], "normal"))
            card["script_btn_label"] = self.canvas.create_text(
                btn_x + T.BTN_W // 2, T.CARD_Y + T.BTN_Y + T.BTN_H // 2,
                text="启动脚本", font=self.f_btn, fill=app["accent"])
            game_x = btn_x + T.BTN_W + T.BTN_GAP
            card["game_btn"] = self.canvas.create_image(
                game_x, T.CARD_Y + T.BTN_Y, anchor="nw",
                image=self._game_btn_photo("normal"))
            card["game_btn_label"] = self.canvas.create_text(
                game_x + T.BTN_W // 2, T.CARD_Y + T.BTN_Y + T.BTN_H // 2,
                text="启动游戏", font=self.f_btn, fill=T.HEX_TXT)

            card["links"] = []
            link_labels = [("清日常", "daily"), ("更新", "update"),
                           ("下载", "download"), ("官网", "site"),
                           ("GitHub", "github"), ("更多", "more")]
            widths = [self.f_link.measure(t) for t, _ in link_labels]
            # 运行中会显示「清日常中」，预留宽度避免与下一项重叠
            widths[0] = max(widths[0], self.f_link.measure("清日常中"))
            gap = 14
            total = sum(widths) + gap * (len(link_labels) - 1)
            lx = cx - total / 2
            for (text, zone), w in zip(link_labels, widths):
                item = self.canvas.create_text(
                    lx, T.CARD_Y + T.LINK_Y, text=text, anchor="w",
                    font=self.f_link, fill=T.HEX_TXT3)
                card["links"].append((item, zone, (lx - 2, T.CARD_Y + T.LINK_Y - 8,
                                                   lx + w + 2, T.CARD_Y + T.LINK_Y + 8)))
                lx += w + gap
            self.cards.append(card)

        self.toast_item = self.canvas.create_text(
            48, T.FOOT_Y, anchor="w", text=self.toast_msg, font=self.f_foot,
            fill=T.HEX_TXT3)

        self._update_versions()
        self._refresh()

    # ---------------------------------------------------------- 状态
    def _app_state(self, app):
        exe = app.get("script_exe", "")
        key = app["key"]
        launch = app.get("launch") if isinstance(app.get("launch"), dict) else {}
        if not exe or not os.path.isfile(exe):
            if not launch.get("exe") or not os.path.isfile(launch.get("exe")):
                return "missing"
        if key in self.starting:
            if time.time() - self.starting[key] < 12:
                return "starting"
            self.starting.pop(key, None)
        return "on" if self.running.get(key, {}).get("script") else "off"

    def _game_state(self, app):
        """返回缓存的检测状态 dict（running/reason/label/hwnd/source…）。"""
        state = self.game_states.get(app["key"])
        if state is None:
            try:
                state = detector.detect_game_state(app, adb_enabled=self.adb_enabled)
            except Exception:
                state = {"running": False, "reason": "", "label": "未运行",
                         "hwnd": None, "configured": False, "source": "none",
                         "rules": {}}
            self.game_states[app["key"]] = state
        return state

    def _update_versions(self):
        for app in self.apps:
            self.versions[app["key"]] = store.read_version(app)

    def _has_update(self, app):
        latest = self.latest.get(app["key"])
        current = self.versions.get(app["key"])
        return bool(latest and current and store.is_newer(latest, current))

    def _refresh(self):
        names = store.snapshot_processes()
        windows = detector.snapshot_windows()
        for app in self.apps:
            key = app["key"]
            prev = self.running.get(key, {"script": False, "game": False})
            prev_game = self.game_states.get(key) or {}
            script_on = bool(app.get("script_procs")) and bool(
                names & set(app["script_procs"]))
            launch = app.get("launch")
            if isinstance(launch, dict) and launch.get("exe"):
                # 正式脚本是 bundled pythonw：按 exe 路径判定；
                # 启动器 ok-ww.exe 不算脚本运行中，也不误判用户其它 python。
                try:
                    script_on = store.launch_spec_running(app)
                except Exception:
                    script_on = False
            try:
                game_state = detector.detect_game_state(
                    app, windows=windows, processes=names,
                    adb_enabled=self.adb_enabled)
            except Exception:
                game_state = {"running": False, "reason": "", "label": "未运行",
                              "hwnd": None, "configured": False,
                              "source": "none", "rules": {}}
            self.game_states[key] = game_state
            game_on = bool(game_state.get("running"))
            self.running[key] = {"script": script_on, "game": game_on}
            if prev["script"] != script_on:
                if script_on and key in self.starting:
                    self.starting.pop(key, None)
                    self._toast(f"已启动 {app['game']} · {app['script']}")
                elif not script_on and prev["script"]:
                    self._toast(f"{app['game']} 的脚本已退出")
            if game_on and not prev_game.get("running"):
                self._toast(f"{app['game']} {game_state.get('label') or '已启动'}")
            elif prev_game.get("running") and not game_on:
                self._toast(f"{app['game']} 已退出")
        for i in range(len(self._page_apps)):
            self._repaint_card(i)

    def _repaint_card(self, i):
        if i >= len(self.cards):
            return
        app = self._page_apps[i]
        card = self.cards[i]
        key = app["key"]
        hover = self.hover

        # 版本行
        text = app["script"]
        version = self.versions.get(key) or ""
        if version:
            text += f" · {version}"
        has_update = self._has_update(app)
        if has_update:
            text += f" → {self.latest[key]}"
        self.canvas.itemconfigure(
            card["script_text"], text=text,
            fill=app["accent"] if has_update else T.HEX_TXT3)

        # 脚本状态
        state = self._app_state(app)
        label, color = {
            "on": ("运行中", T.HEX_OK),
            "starting": ("启动中", T.HEX_WAIT),
            "missing": ("缺失", T.HEX_ERR),
            "off": ("未启动", T.HEX_TXT2),
        }[state]
        gstate = self._game_state(app)
        if not gstate.get("configured"):
            game_state = "unset"
        elif gstate.get("running"):
            game_state = "on"
        elif gstate.get("reason") == "launcher":
            game_state = "launcher"
        elif gstate.get("reason") == "cloud":
            game_state = "cloud"
        else:
            game_state = "off"
        game_label = {
            "on": gstate.get("label") or "运行中",
            "launcher": "启动器已开",
            "cloud": "云游戏运行中",
            "off": "未运行",
            "unset": "未配置",
        }[game_state]

        # 两段状态居中排版
        st1 = f"脚本 {label}"
        st2 = f"游戏 {game_label}"
        dot_w = 22
        tw1 = self.f_status.measure(st1)
        tw2 = self.f_status.measure(st2)
        total = dot_w + 3 + tw1 + 14 + dot_w + 3 + tw2
        cx = T.CARD_X[i] + T.CARD_W // 2
        x1 = cx - total / 2
        x2 = x1 + dot_w + 3 + tw1 + 14
        y = T.CARD_Y + T.STATUS_Y
        self.canvas.coords(card["script_dot"], x1, y)
        self.canvas.coords(card["script_status"], x1 + dot_w + 3, y)
        self.canvas.coords(card["game_dot"], x2, y)
        self.canvas.coords(card["game_status"], x2 + dot_w + 3, y)
        self.canvas.itemconfigure(
            card["script_dot"],
            image=self._dot_photo(T.HEX_OK if state in ("on", "starting") else
                                  (T.HEX_ERR if state == "missing" else None),
                                  state in ("on", "starting", "missing")))
        self.canvas.itemconfigure(card["script_status"], text=st1, fill=color)
        if game_state in ("on", "cloud"):
            game_dot_color, game_dot_on, game_color = T.HEX_OK, True, T.HEX_OK
        elif game_state == "launcher":
            game_dot_color, game_dot_on, game_color = T.HEX_WAIT, True, T.HEX_WAIT
        elif game_state == "unset":
            game_dot_color, game_dot_on, game_color = None, False, T.HEX_TXT3
        else:
            game_dot_color, game_dot_on, game_color = None, False, T.HEX_TXT2
        self.canvas.itemconfigure(
            card["game_dot"],
            image=self._dot_photo(game_dot_color, game_dot_on))
        self.canvas.itemconfigure(
            card["game_status"], text=st2, fill=game_color)

        # 按钮
        script_hover = hover[0] == "scriptbtn" and hover[1] == i
        game_hover = hover[0] == "gamebtn" and hover[1] == i
        if state in ("on", "missing"):
            img_state = "off"
        elif script_hover:
            img_state = "hover"
        else:
            img_state = "normal"
        self.canvas.itemconfigure(card["script_btn"],
                                  image=self._btn_photo(app["accent"], img_state))
        btn_text, btn_color = {
            "on": ("已运行", T.HEX_TXT3),
            "missing": ("选择路径", T.HEX_ERR),
            "starting": ("启动中…", T.HEX_WAIT),
            "off": ("启动脚本", app["accent"]),
        }[state]
        self.canvas.itemconfigure(card["script_btn_label"],
                                  text=btn_text, fill=btn_color)

        if game_state == "on":
            game_img_state = "off"
        elif game_hover:
            game_img_state = "hover"
        else:
            game_img_state = "normal"
        self.canvas.itemconfigure(card["game_btn"],
                                  image=self._game_btn_photo(game_img_state))
        if game_state == "on":
            game_text, game_color = "游戏中", T.HEX_TXT3
        elif game_state == "unset":
            game_text, game_color = "选择游戏", T.HEX_TXT2
        else:
            game_text, game_color = "启动游戏", T.HEX_TXT
        self.canvas.itemconfigure(card["game_btn_label"],
                                  text=game_text, fill=game_color)

        # 底部链接
        daily_running = self._daily_state_for(key) in (daily.STARTING,
                                                       daily.RUNNING)
        for item, zone, _rect in card["links"]:
            if zone == "daily":
                self.canvas.itemconfigure(
                    item, text="清日常中" if daily_running else "清日常")
                if hover[0] == "link" and hover[1] == i and hover[2] == zone:
                    fill = T.HEX_TXT
                elif daily_running:
                    fill = T.HEX_WAIT
                else:
                    fill = app["accent"]
                self.canvas.itemconfigure(item, fill=fill)
                continue
            if hover[0] == "link" and hover[1] == i and hover[2] == zone:
                fill = app["accent"]
            elif zone == "update" and has_update:
                fill = app["accent"]
            elif hover[0] == "card" and hover[1] == i:
                fill = T.HEX_TXT2
            else:
                fill = T.HEX_TXT3
            self.canvas.itemconfigure(item, fill=fill)

    # ---------------------------------------------------------- 鼠标
    def _toolbar_hit(self, x, y):
        for name, _label, rect, _border in self.toolbar:
            bx, by, bw, bh = rect
            if bx <= x <= bx + bw and by <= y <= by + bh:
                return name
        return None

    def _hit(self, x, y):
        name = self._toolbar_hit(x, y)
        if name:
            return ("toolbar", name)
        if self.pages > 1:
            for direction, rect in (("left", T.PAGE_LEFT_RECT),
                                    ("right", T.PAGE_RIGHT_RECT)):
                bx, by, bw, bh = rect
                if bx <= x <= bx + bw and by <= y <= by + bh:
                    return ("page", direction)
        for i, app in enumerate(self._page_apps):
            x0 = T.CARD_X[i]
            if not (x0 <= x <= x0 + T.CARD_W and T.CARD_Y <= y <= T.CARD_Y + T.CARD_H):
                continue
            btn_y0 = T.CARD_Y + T.BTN_Y
            if btn_y0 <= y <= btn_y0 + T.BTN_H:
                if x0 + 24 <= x <= x0 + 24 + T.BTN_W:
                    return ("scriptbtn", i)
                if x0 + 24 + T.BTN_W + T.BTN_GAP <= x <= x0 + 24 + 2 * T.BTN_W + T.BTN_GAP:
                    return ("gamebtn", i)
            for item, zone, (ax0, ay0, ax1, ay1) in self.cards[i]["links"]:
                if ax0 <= x <= ax1 and ay0 <= y <= ay1:
                    return ("link", i, zone)
            return ("card", i)
        return ("none",)

    def _set_hover(self, hover):
        if hover == self.hover:
            return
        old = self.hover
        self.hover = hover
        self.canvas.configure(cursor="hand2"
                              if hover[0] in ("card", "scriptbtn", "gamebtn", "link",
                                              "toolbar", "page") else "")

        # 背景悬停
        old_card = old[1] if old[0] in ("card", "scriptbtn", "gamebtn", "link") else -1
        new_card = hover[1] if hover[0] in ("card", "scriptbtn", "gamebtn", "link") else -1
        if old_card != new_card:
            self.canvas.itemconfigure(self._bg_item, image=self.bg_photos[new_card])

        # 工具栏
        for name, label, rect, border in self.toolbar:
            hovered = hover[0] == "toolbar" and hover[1] == name
            image_item, text_item, _rect, _border = self.toolbar_items[name]
            self.canvas.itemconfigure(
                image_item, image=self._toolbar_photo(
                    name, rect, "hover" if hovered else "normal", border))
            self.canvas.itemconfigure(
                text_item, fill=T.HEX_TXT if hovered else T.HEX_TXT2)

        # 翻页
        if self.pages > 1:
            for direction in ("left", "right"):
                hovered = hover[0] == "page" and hover[1] == direction
                self.canvas.itemconfigure(
                    self.page_items[direction],
                    image=self._page_photo(direction, hovered))

        for i in range(len(self._page_apps)):
            self._repaint_card(i)

    def _on_motion(self, event):
        self._set_hover(self._hit(event.x, event.y))

    def _on_click(self, event):
        hit = self._hit(event.x, event.y)
        kind = hit[0]
        if kind == "toolbar":
            self._toolbar_action(hit[1])
        elif kind == "page":
            self._turn_page(-1 if hit[1] == "left" else 1)
        elif kind == "card":
            self.launch_script(hit[1])
        elif kind == "scriptbtn":
            self.launch_script(hit[1])
        elif kind == "gamebtn":
            self.launch_game(hit[1])
        elif kind == "link":
            self._link_action(hit[1], hit[2])

    def _on_right_click(self, event):
        hit = self._hit(event.x, event.y)
        if hit[0] in ("card", "scriptbtn", "gamebtn", "link"):
            self._show_menu(hit[1], event.x_root, event.y_root)

    # ---------------------------------------------------------- 工具栏 / 翻页
    def _toolbar_action(self, name):
        if name == "add":
            self.add_app()
        elif name == "check":
            self._on_refresh()
        elif name == "rescan":
            self.rescan_paths()
        elif name == "daily":
            self.open_daily_dialog()
        elif name == "clash":
            self.open_clash()

    def _turn_page(self, delta):
        new_page = self.page + delta
        if 0 <= new_page < self.pages:
            self.page = new_page
            self._rebuild()
            self._toast(f"第 {self.page + 1} / {self.pages} 页")

    # ---------------------------------------------------------- 链接 / 菜单
    def _link_action(self, i, zone):
        app = self._page_apps[i]
        if zone == "daily":
            self.run_daily_single(i)
        elif zone == "update":
            self.update_app(i)
        elif zone == "download":
            self.download_game(i)
        elif zone == "site":
            self._open_url(app.get("site"), f"{app['script']} 官网")
        elif zone == "github":
            self._open_url(app.get("github"), f"{app['script']} GitHub")
        elif zone == "more":
            self._show_menu(i, self.root.winfo_pointerx(), self.root.winfo_pointery())

    def _show_menu(self, i, x, y):
        app = self._page_apps[i]
        menu = tk.Menu(self.root, tearoff=0, bg="#151b26", fg="#eaf0f8",
                       activebackground="#2a3547", activeforeground="#ffffff",
                       bd=0, font=("Microsoft YaHei", -10))
        menu.add_command(label="启动游戏", command=lambda: self.launch_game(i))
        menu.add_command(label="清日常（当前游戏）",
                         command=lambda: self.run_daily_single(i))
        menu.add_command(label="下载游戏（打开下载页）", command=lambda: self.download_game(i))
        menu.add_separator()
        menu.add_command(label="打开脚本文件夹", command=lambda: self.open_folder(i))
        menu.add_command(label="编辑此卡片", command=lambda: self.edit_app(i))
        if not app.get("builtin"):
            menu.add_command(label="删除此卡片", command=lambda: self.delete_app(i))
        menu.add_separator()
        menu.add_command(label="重新检查更新", command=self._on_refresh)
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ---------------------------------------------------------- 启动 / 下载
    def launch_script(self, i):
        if i >= len(self._page_apps):
            return
        app = self._page_apps[i]
        if self._app_state(app) == "missing":
            self._choose_script_path(i)
            return
        if self.running.get(app["key"], {}).get("script"):
            focused = False
            if isinstance(app.get("launch"), dict):
                focused = store.focus_launch_spec(app)
            if not focused:
                focused = store.bring_to_front(app.get("script_procs", []))
            if focused:
                self._toast(f"已切换到 {app['game']}")
            else:
                self._toast(f"{app['game']} 正在运行中（窗口未找到）")
            return
        try:
            ok, error, mode = store.launch_app(app)
        except Exception as exc:
            ok, error, mode = False, str(exc), "none"
        if not ok:
            self._toast(f"启动 {app['game']} 失败：{error}")
            return
        if mode == "launcher":
            self._toast(f"未找到正式脚本，已回退启动 {app['script']} 启动器（可在启动器里更新）")
            return
        self.starting[app["key"]] = time.time()
        self._repaint_card(i)
        self._toast(f"正在启动 {app['game']} · {app['script']}")

    def _launch_updater(self, app):
        """有独立启动器（ok-ww.exe）时，「更新」走启动器以保留更新能力。"""
        spec = app.get("launch") if isinstance(app.get("launch"), dict) else {}
        if not spec.get("launcher_exe"):
            return False
        ok, error = store.launch_updater(app)
        if ok:
            self._toast(f"正在打开 {app['script']} 更新器…")
        else:
            self._toast(f"打开更新器失败：{error}")
        return True

    def launch_game(self, i):
        app = self._page_apps[i]
        try:
            state = detector.detect_game_state(app, adb_enabled=self.adb_enabled)
        except Exception:
            state = {"running": False, "reason": "", "label": "未运行", "hwnd": None}
        self.game_states[app["key"]] = state
        if state.get("running"):
            hwnd = state.get("hwnd")
            if hwnd and detector.focus_window(hwnd):
                self._toast(f"已切换到 {app['game']}")
            elif store.bring_to_front(app.get("game_procs") or []):
                self._toast(f"已切换到 {app['game']}")
            else:
                self._toast(f"{app['game']} {state.get('label') or '运行中'}"
                            "（窗口未找到）")
            return
        exe = app.get("game_exe", "")
        saved = True
        if not exe or not os.path.isfile(exe):
            self._toast(f"正在自动检测「{app['game']}」的启动程序…")
            try:
                self.root.update_idletasks()
                candidates = store.find_game_candidates(app)
            except Exception:
                candidates = []
            if candidates:
                dialog = GameCandidateDialog(
                    self.root, candidates,
                    title=f"选择「{app['game']}」的游戏启动程序")
                self.root.wait_window(dialog)
                if not dialog.result:
                    self._toast("已取消启动游戏")
                    return
                exe = os.path.normpath(dialog.result)
            else:
                path = filedialog.askopenfilename(
                    parent=self.root, title=f"选择「{app['game']}」的启动程序",
                    filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
                if not path:
                    return
                exe = os.path.normpath(path)
            app["game_exe"] = exe
            app["game_procs"] = store.proc_names_for_exe(exe)
            saved = self._save_config()
            self._rebuild()
        ok, error = store.launch_exe(exe)
        if ok:
            note = "" if saved else "（路径未能保存）"
            self._toast(f"正在启动游戏：{app['game']}{note}")
        else:
            self._toast(f"启动游戏失败：{error}")

    def download_game(self, i):
        app = self._page_apps[i]
        url = app.get("download") or app.get("site")
        if not url:
            self._toast(f"{app['game']} 还没有配置下载页，可在「编辑此卡片」里填写")
            return
        self._open_url(url, f"{app['game']} 下载页")

    def update_app(self, i):
        app = self._page_apps[i]
        if self._app_state(app) == "missing":
            self._choose_script_path(i)
            return
        if self.running.get(app["key"], {}).get("script"):
            self._toast(f"{app['game']} 正在运行，请关闭后重新打开以检查更新")
            return
        if self.checking and app["key"] not in self.latest:
            self._toast("正在检查最新版本，请稍候再点一次")
            return
        if self._has_update(app):
            if not self._launch_updater(app):
                self.launch_script(i)
        elif app["key"] in self.latest and not self._has_update(app):
            self._toast(f"{app['script']} 已是最新版本 {self.versions.get(app['key'], '')}")
        else:
            self._toast(f"无法获取最新版本，打开 {app['game']} 自行检查更新")
            if not self._launch_updater(app):
                self.launch_script(i)

    def open_folder(self, i):
        app = self._page_apps[i]
        folder = os.path.dirname(app.get("script_exe", ""))
        if store.open_path(folder):
            self._toast(f"已打开 {app['script']} 所在文件夹")
        else:
            self._toast("脚本目录不存在")

    def _open_url(self, url, label):
        if not url:
            self._toast(f"还没有配置 {label} 地址")
            return
        try:
            if not webbrowser.open(url):
                os.startfile(url)
            self._toast(f"已打开 {label}")
        except Exception:
            try:
                os.startfile(url)
                self._toast(f"已打开 {label}")
            except Exception:
                self._toast(f"打开失败：{url}")

    def _choose_script_path(self, i):
        app = self._page_apps[i]
        path = filedialog.askopenfilename(
            parent=self.root, title=f"选择「{app['game']}」的脚本启动程序",
            initialdir=os.path.dirname(app.get("script_exe", "")) or self.search_root,
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if not path:
            return
        app["script_exe"] = os.path.normpath(path)
        app["script_procs"] = store.proc_names_for_exe(path)
        store.refresh_launch_spec(app)
        saved = self._save_config()
        self._rebuild()
        if saved:
            self._toast(f"已更新 {app['script']} 的路径")

    # ---------------------------------------------------------- 添加 / 编辑 / 删除
    def _store_icon(self, key, path):
        """把用户选择的图标复制到 user_icons/，方便随 Hub 一起搬走。"""
        if not path or not os.path.isfile(path):
            return ""
        try:
            import shutil
            folder = os.path.join(store.APP_DIR, "user_icons")
            os.makedirs(folder, exist_ok=True)
            ext = os.path.splitext(path)[1].lower() or ".png"
            target = os.path.join(folder, key + ext)
            shutil.copyfile(path, target)
            return target
        except Exception:
            return path

    def _apply_detect_fields(self, app, data):
        """把编辑框里的检测规则写入 app；与原有规则一致则保持自动规则。"""
        fields = ("win_class", "win_title", "detect_procs", "adb_pkg")
        try:
            current = detector.read_game_rules(app)
            initial = detector.rules_to_fields(current)
        except Exception:
            current, initial = {}, {}
        values = {field: (data.get(field) or "").strip() for field in fields}
        if all(values[field] == (initial.get(field) or "").strip()
               for field in fields):
            return
        self.game_states.pop(app.get("key"), None)
        if not any(values.values()):
            app.pop("detect", None)
            app["detect_custom"] = False
            return
        try:
            app["detect"] = detector.rules_from_fields(
                win_class=values["win_class"], win_title=values["win_title"],
                detect_procs=values["detect_procs"], adb_pkg=values["adb_pkg"],
                base=current)
            app["detect_custom"] = True
        except Exception:
            pass

    def add_app(self):
        def on_save(data):
            key = self._next_key()
            icon = self._store_icon(key, data["icon"]) if data["icon"] else ""
            app = dict(
                key=key, game=data["game"], script=data["script"], builtin=False,
                script_exe=data["script_exe"],
                script_procs=store._clean_procs(data["script_procs"], data["script_exe"]),
                game_exe=data["game_exe"],
                game_procs=store._clean_procs(data["game_procs"], data["game_exe"]),
                accent=data["accent"], fallback_version="",
                site=data["site"], github=data["github"],
                release=data["release"], download=data["download"],
                icon_path=icon or store.custom_icon_path(key),
            )
            self._apply_detect_fields(app, data)
            self.apps.append(app)
            saved = self._save_config()
            self.page = (len(self.apps) - 1) // T.PER_PAGE
            self._rebuild()
            if saved:
                self._toast(f"已添加 {app['game']} · {app['script']}")
            self._start_update_check()
        AppDialog(self.root, None, on_save=on_save)

    def edit_app(self, i):
        app = self._page_apps[i]

        def on_save(data):
            app["game"] = data["game"]
            app["script"] = data["script"]
            app["script_exe"] = data["script_exe"]
            app["script_procs"] = store._clean_procs(data["script_procs"], data["script_exe"])
            app["game_exe"] = data["game_exe"]
            app["game_procs"] = store._clean_procs(data["game_procs"], data["game_exe"])
            app["accent"] = data["accent"]
            app["site"] = data["site"]
            app["github"] = data["github"]
            app["release"] = data["release"]
            app["download"] = data["download"]
            if data["icon"] and os.path.isfile(data["icon"]):
                app["icon_path"] = self._store_icon(app["key"], data["icon"])
            self._apply_detect_fields(app, data)
            self.game_states.pop(app["key"], None)
            saved = self._save_config()
            self._rebuild()
            if saved:
                self._toast(f"已保存 {app['game']} 的配置")

        def on_delete():
            self.delete_app(i)

        AppDialog(self.root, app, on_save=on_save, on_delete=on_delete)

    def delete_app(self, i):
        app = self._page_apps[i]
        if app.get("builtin"):
            messagebox.showinfo("无法删除", "内置脚本卡片不能删除，可以修改或隐藏。",
                                parent=self.root)
            return
        if not messagebox.askyesno(
                "删除卡片", f"确定删除「{app['game']}」这张卡片吗？\n（不会删除任何文件）",
                parent=self.root):
            return
        self.apps = [a for a in self.apps if a["key"] != app["key"]]
        self.game_states.pop(app["key"], None)
        saved = self._save_config()
        self.page = min(self.page, max(0, (len(self.apps) - 1) // T.PER_PAGE))
        self._rebuild()
        if saved:
            self._toast(f"已删除 {app['game']} 的卡片")

    def _next_key(self):
        index = 1
        existing = {a["key"] for a in self.apps}
        while f"custom_{index}" in existing:
            index += 1
        return f"custom_{index}"

    # ---------------------------------------------------------- 路径识别
    def rescan_paths(self):
        found = 0
        for app in self.apps:
            exe_name = os.path.basename(app.get("script_exe", "")) or app.get(
                "script_exe_name", "")
            if not exe_name:
                continue
            hits = store.find_app_exe(self.search_root, exe_name)
            best = store.pick_best_exe(hits)
            if best and best != app.get("script_exe"):
                app["script_exe"] = best
                app["script_procs"] = store.proc_names_for_exe(best)
                store.refresh_launch_spec(app)
                found += 1
        saved = self._save_config()
        self._update_versions()
        self._rebuild()
        total = sum(1 for a in self.apps if os.path.isfile(a.get("script_exe", "")))
        if saved:
            self._toast(f"路径识别完成：{total}/{len(self.apps)} 个脚本可用"
                        + (f"，更新了 {found} 个路径" if found else ""))

    def open_clash(self):
        path = self.clash_exe
        if path and os.path.exists(path):
            if store.snapshot_processes() & store.CLASH_PROCS:
                if store.bring_to_front(store.CLASH_PROCS):
                    self._toast("已切换到 Clash Verge")
                else:
                    self._toast("Clash Verge 已在运行（可能最小化在托盘）")
                return
            ok, error = store.launch_exe(path)
            self._toast("正在打开 Clash Verge" if ok else f"打开 Clash Verge 失败：{error}")
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="选择 Clash Verge 程序",
            filetypes=[("可执行程序", "*.exe")])
        if path:
            self.clash_exe = os.path.normpath(path)
            saved = self._save_config()
            if saved:
                self._toast("已记录 Clash Verge 路径，再点一次即可打开")

    # ---------------------------------------------------------- 一键清日常
    def _app_by_key(self, key):
        for app in self.apps:
            if app.get("key") == key:
                return app
        return None

    def _daily_snapshot(self):
        if self.daily_queue is None:
            return {"state": daily.IDLE, "state_label": "空闲", "current": None,
                    "index": -1, "total": 0, "results": [],
                    "order": list(self.daily_order)}
        return self.daily_queue.snapshot()

    def _daily_state_for(self, key):
        snapshot = self._daily_snapshot()
        if snapshot.get("current") == key:
            return daily.RUNNING
        return snapshot.get("state") or daily.IDLE

    def _daily_busy(self):
        return bool(self.daily_queue and self.daily_queue.is_running())

    def _queue_event(self, event):
        """DailyQueue 在工作线程里回调：只入队，由主线程 _poll 消费。"""
        self.daily_events.put(event)

    def _append_daily_log(self, text):
        self.daily_log.append(time.strftime("%H:%M:%S ") + text)
        self.daily_log = self.daily_log[-200:]

    def _daily_summary(self, snapshot):
        results = snapshot.get("results") or []
        if not results:
            return "清日常结束"
        finished = [r for r in results if r.get("state") == daily.FINISHED]
        failed = [r for r in results
                  if r.get("state") in (daily.FAILED, daily.TIMEOUT)]
        stopped = [r for r in results
                   if r.get("state") in (daily.STOPPED, daily.SKIPPED)]
        parts = [f"完成 {len(finished)}/{len(results)}"]
        if failed:
            parts.append("失败：" + "、".join(str(r.get("game")) for r in failed))
        if stopped:
            parts.append("停止/跳过：" + "、".join(str(r.get("game"))
                                                 for r in stopped))
        return "清日常结束（" + "，".join(parts) + "）"

    def _drain_daily_events(self):
        changed = False
        while True:
            try:
                event = self.daily_events.get_nowait()
            except queue.Empty:
                break
            kind = event.get("type")
            if kind == "item_start":
                self._append_daily_log(f"▶ 开始：{event.get('game')}")
                self._toast(f"开始清日常：{event.get('game')}")
                changed = True
            elif kind == "runner":
                sub = event.get("event") or {}
                if sub.get("type") == "state" and sub.get("state") == daily.RUNNING:
                    app = self._app_by_key(sub.get("key"))
                    if app:
                        self._append_daily_log(f"… {app.get('game')} 运行中")
            elif kind == "item":
                result = event.get("result") or {}
                state = result.get("state")
                label = result.get("state_label") or state or ""
                if state == daily.DRY_RUN:
                    self._append_daily_log(f"预演：{result.get('game')}")
                else:
                    reason = result.get("reason") or ""
                    pid = result.get("pid")
                    pid_text = f"，PID {pid}" if pid else ""
                    self._append_daily_log(
                        f"■ {result.get('game') or event.get('key')}：{label}"
                        + pid_text + (f"（{reason}）" if reason else ""))
                    is_single = bool(self.daily_queue and
                                     len(self.daily_queue.order) == 1)
                    if is_single and state in (daily.FAILED, daily.TIMEOUT,
                                               daily.STOPPED):
                        short = reason if len(reason) <= 80 else reason[:80] + "…"
                        self._toast(f"{result.get('game') or '清日常'}：{label}"
                                    + (f"（{short}）" if short else ""))
                changed = True
            elif kind == "queue":
                if event.get("state") in (daily.FINISHED, daily.STOPPED,
                                          daily.FAILED):
                    snapshot = event.get("snapshot") or self._daily_snapshot()
                    summary = self._daily_summary(snapshot)
                    self._append_daily_log("── " + summary)
                    self._toast(summary)
                    changed = True
        if changed:
            for i in range(len(self._page_apps)):
                self._repaint_card(i)
            dialog = self.daily_dialog
            if dialog is not None:
                try:
                    dialog.refresh()
                except Exception:
                    pass

    def run_daily_single(self, i):
        """点击卡片底部「清日常」：单游戏执行；运行中再点则停止。"""
        if i >= len(self._page_apps):
            return
        app = self._page_apps[i]
        key = app["key"]
        if self._daily_state_for(key) in (daily.STARTING, daily.RUNNING):
            self.stop_daily()
            return
        if self._daily_busy():
            self._toast("已有清日常任务在运行，请先等待或点「停止」")
            return
        self._start_daily([key], single=True)

    def start_daily_queue(self, keys=None):
        """开始顺序队列（由队列对话框调用）；默认按 daily_order 的启用项。"""
        if self._daily_busy():
            self._toast("清日常队列已在运行")
            return False
        if keys is None:
            keys = []
            for key in self.daily_order:
                app = self._app_by_key(key)
                if app and (app.get("daily") or {}).get("enabled", True):
                    keys.append(key)
        return self._start_daily(keys, single=False)

    def _start_daily(self, keys, single=False):
        by_key = {app["key"]: app for app in self.apps}
        order = []
        for key in keys:
            if key in by_key and key not in order:
                order.append(key)
        if not order:
            self._toast("没有可执行的清日常项（请勾选启用）")
            return False
        self.daily_log = []
        self.daily_queue = daily.DailyQueue(
            self.apps, order, on_event=self._queue_event)
        started = self.daily_queue.start()
        if not started:
            self._toast("清日常队列启动失败")
            return False
        names = "、".join(str(by_key[key].get("game")) for key in order)
        self._append_daily_log("准备执行：" + names)
        self._toast(("正在清日常：" if single else "一键清日常：") + names)
        for i in range(len(self._page_apps)):
            self._repaint_card(i)
        dialog = self.daily_dialog
        if dialog is not None:
            try:
                dialog.refresh()
            except Exception:
                pass
        return True

    def stop_daily(self):
        if not self._daily_busy():
            self._toast("当前没有正在运行的清日常任务")
            return
        if not messagebox.askyesno(
                "停止清日常",
                "确定停止当前清日常吗？\n"
                "会结束由 Hub 启动的脚本进程（不会动你自己打开的程序）。",
                parent=self.root):
            return
        self.daily_queue.stop()
        self._append_daily_log("用户请求停止…")
        self._toast("正在停止清日常…")

    def open_daily_dialog(self):
        if self.daily_dialog is not None:
            try:
                self.daily_dialog.deiconify()
                self.daily_dialog.lift()
                self.daily_dialog.focus_force()
                self.daily_dialog.refresh()
                return
            except Exception:
                self.daily_dialog = None
        self.daily_dialog = DailyQueueDialog(self.root, self)

    def move_daily(self, key, delta):
        order = [item for item in self.daily_order
                 if self._app_by_key(item) is not None]
        if key not in order:
            order.append(key)
        index = order.index(key)
        target = index + delta
        if 0 <= target < len(order):
            order[index], order[target] = order[target], order[index]
            self.daily_order = order
            self._save_config()
            return True
        return False

    def set_daily_enabled(self, key, enabled):
        app = self._app_by_key(key)
        if app is None:
            return
        settings = store._clean_daily(app.get("daily"), key)
        settings["enabled"] = bool(enabled)
        app["daily"] = settings
        self._save_config()

    def apply_daily_settings(self, key, values):
        app = self._app_by_key(key)
        if app is None:
            return False
        current = store._clean_daily(app.get("daily"), key)
        current.update(values or {})
        app["daily"] = store._clean_daily(current, key)
        saved = self._save_config()
        if saved:
            self._toast(f"已保存「{app.get('game')}」的清日常设置")
        return saved

    def daily_dry_run_text(self, key=None):
        """UI 预览：单个或全部启用项的命令（不启动进程）。"""
        apps = self.apps
        order = [key] if key else list(self.daily_order)
        plans = daily.dry_run(apps, order)
        return "\n\n".join(daily.describe_plan(plan) for plan in plans)

    # ---------------------------------------------------------- 更新检查
    def _start_update_check(self, manual=False):
        if self.checking:
            if manual:
                self._toast("正在检查更新中，请稍候…")
            return
        self.checking = True
        self.manual_check = manual
        if manual:
            self._toast("正在检查更新…")
        threading.Thread(target=self._update_worker, daemon=True).start()

    def _update_worker(self):
        for app in list(self.apps):
            try:
                latest = store.check_latest(app)
            except Exception:
                latest = None
            self.update_queue.put((app["key"], latest))
        self.update_queue.put(("done", None))

    def _drain_queue(self):
        changed = False
        while True:
            try:
                key, value = self.update_queue.get_nowait()
            except queue.Empty:
                break
            if key == "done":
                self.checking = False
                if self.manual_check:
                    self._toast(self._update_summary())
                self.manual_check = False
            else:
                self.latest[key] = value
                changed = True
        if changed:
            for i in range(len(self._page_apps)):
                self._repaint_card(i)

    def _update_summary(self):
        pending = [a for a in self.apps if self._has_update(a)]
        failed = [a for a in self.apps if a["key"] not in self.latest
                  or self.latest[a["key"]] is None]
        if pending:
            names = "、".join(a["script"] for a in pending)
            extra = f"（{len(failed)} 个无法检查）" if failed else ""
            return f"发现可更新：{names}{extra}，点卡片底部「更新」"
        if len(failed) == len(self.apps):
            return "更新检查失败：网络不可用，可先打开 Clash Verge 再按 F5"
        if failed:
            names = "、".join(a["script"] for a in failed)
            return f"其余脚本已是最新（{names} 暂时无法检查）"
        return "全部脚本已是最新版本"

    def _on_refresh(self):
        self._update_versions()
        self._start_update_check(manual=True)
        self._refresh()

    # ---------------------------------------------------------- 提示 / 轮询
    def _toast(self, text):
        self.toast_msg = text
        try:
            self.canvas.itemconfigure(self.toast_item, text=text)
        except Exception:
            pass
        if self.toast_after:
            try:
                self.root.after_cancel(self.toast_after)
            except Exception:
                pass
        self.toast_after = self.root.after(
            6000, lambda: self._set_toast_default())

    def _set_toast_default(self):
        self.toast_msg = "就绪 · 每 1.5 秒刷新状态"
        try:
            self.canvas.itemconfigure(self.toast_item, text=self.toast_msg)
        except Exception:
            pass

    def _poll(self):
        try:
            self._drain_queue()
            self._drain_daily_events()
            self._refresh()
        except Exception:
            pass
        self.root.after(1500, self._poll)


class DailyQueueDialog(tk.Toplevel):
    """「一键清日常」顺序队列对话框：排序、启用、设置、开始/停止、实时进度。"""

    def __init__(self, master, hub):
        super().__init__(master)
        self.hub = hub
        self.title("一键清日常（顺序队列）")
        self.configure(bg="#0f141d")
        self.resizable(False, False)
        self.transient(master)
        self._rows = {}
        self._check_vars = {}
        self._summary_labels = {}
        self._status_labels = {}
        self._entries = {}
        self._settings_title = None
        self._progress = None
        self._poll_after = None
        self._last_progress = ""
        order = [key for key in hub.daily_order if hub._app_by_key(key)]
        self._selected = order[0] if order else None
        self._build()
        self._center(master)
        self.protocol("WM_DELETE_WINDOW", self._close)
        self._poll()

    # ---------------------------------------------------------- 界面
    def _build(self):
        pad = 14
        tk.Label(self, text="按顺序串行执行各游戏的清日常（使用脚本自身已配置的任务）",
                 bg="#0f141d", fg="#9aa8bc",
                 font=("Microsoft YaHei", -11)).pack(anchor="w", padx=pad,
                                                     pady=(12, 2))
        tk.Label(self, text="⚠ 自动化操作可能违反游戏条款、存在账号风险；执行期间脚本会抢占鼠标键盘，请确认后使用。",
                 bg="#0f141d", fg="#ffce6b", justify="left", wraplength=680,
                 font=("Microsoft YaHei", -9)).pack(anchor="w", padx=pad,
                                                    pady=(0, 8))

        self.rows_frame = tk.Frame(self, bg="#101620",
                                   highlightthickness=1,
                                   highlightbackground="#2a3547")
        self.rows_frame.pack(fill="x", padx=pad)
        self._build_rows()

        # 选中项设置
        settings = tk.Frame(self, bg="#0f141d")
        settings.pack(fill="x", padx=pad, pady=(10, 0))
        settings.columnconfigure(1, weight=1)
        self._settings_title = tk.Label(
            settings, text="选中项设置", bg="#0f141d", fg="#68788e",
            font=("Microsoft YaHei", -10), anchor="w")
        self._settings_title.grid(row=0, column=0, columnspan=4, sticky="w",
                                  pady=(0, 4))
        labels = [("instance", "MXU 实例名"), ("task", "ok-ww 任务名"),
                  ("config", "MAA 配置"), ("timeout_min", "超时(分钟)"),
                  ("extra_args", "额外参数")]
        for index, (field, label) in enumerate(labels):
            row = 1 + index // 2
            col = 0 if index % 2 == 0 else 2
            tk.Label(settings, text=label, bg="#0f141d", fg="#9aa8bc",
                     font=("Microsoft YaHei", -10), anchor="e",
                     width=11).grid(row=row, column=col, sticky="e", pady=3)
            entry = tk.Entry(settings, bg="#101620", fg="#eaf0f8",
                             insertbackground="#eaf0f8", relief="flat",
                             highlightthickness=1,
                             highlightbackground="#2a3547",
                             highlightcolor="#4fc3ff",
                             font=("Microsoft YaHei", -10), width=26)
            entry.grid(row=row, column=col + 1, sticky="we", padx=(4, 12),
                       pady=3)
            self._entries[field] = entry
        self._close_var = tk.BooleanVar(value=True)
        tk.Checkbutton(settings, text="完成后结束脚本（ok-ww/MXU 完成判定需要）",
                       variable=self._close_var, bg="#0f141d", fg="#9aa8bc",
                       selectcolor="#101620", activebackground="#0f141d",
                       activeforeground="#eaf0f8",
                       font=("Microsoft YaHei", -9)).grid(
            row=1 + 3, column=0, columnspan=3, sticky="w", pady=3)
        _flat_button(settings, "应用设置", self._apply_settings).grid(
            row=1 + 3, column=3, sticky="e", padx=(4, 12), pady=3)

        # 进度
        tk.Label(self, text="执行进度", bg="#0f141d", fg="#68788e",
                 font=("Microsoft YaHei", -10)).pack(anchor="w", padx=pad,
                                                     pady=(8, 2))
        self._progress = tk.Text(
            self, height=9, width=84, bg="#101620", fg="#cdd8e6",
            insertbackground="#cdd8e6", relief="flat", bd=0,
            highlightthickness=1, highlightbackground="#2a3547",
            font=("Microsoft YaHei", -9), wrap="word")
        self._progress.pack(fill="both", padx=pad)
        self._progress.configure(state="disabled")

        footer = tk.Frame(self, bg="#0f141d")
        footer.pack(fill="x", padx=pad, pady=(10, 12))
        _flat_button(footer, "开始队列", self._start, accent=True).pack(side="left")
        self._stop_button = _flat_button(footer, "停止", self._stop)
        self._stop_button.pack(side="left", padx=(8, 0))
        _flat_button(footer, "关闭", self._close).pack(side="right")
        _flat_button(footer, "查看命令（dry-run）", self._preview).pack(
            side="right", padx=(0, 8))
        self._load_settings(self._selected)

    def _build_rows(self):
        for child in self.rows_frame.winfo_children():
            child.destroy()
        self._toggle_buttons = {}
        self._summary_labels = {}
        self._status_labels = {}
        for index, key in enumerate(self.hub.daily_order):
            app = self.hub._app_by_key(key)
            if app is None:
                continue
            settings = store._clean_daily(app.get("daily"), key)
            row = tk.Frame(self.rows_frame, bg="#101620")
            row.pack(fill="x", padx=6, pady=3)
            enabled = bool(settings.get("enabled", True))
            toggle = tk.Button(
                row, text="启用" if enabled else "停用",
                command=lambda k=key: self._toggle(k),
                bg="#25445f" if enabled else "#1b2432",
                fg="#eaf0f8" if enabled else "#68788e",
                activebackground="#2d5577", activeforeground="#ffffff",
                relief="flat", bd=0, padx=6, pady=1, width=4,
                font=("Microsoft YaHei", -9), cursor="hand2")
            toggle.pack(side="left")
            self._toggle_buttons[key] = toggle
            name = tk.Label(row, text=f"{index + 1}. {app.get('game')}",
                            bg="#101620", fg="#eaf0f8",
                            font=("Microsoft YaHei", -10), cursor="hand2")
            name.pack(side="left", padx=(2, 8))
            summary = tk.Label(row, text=self._summary_text(app, key),
                               bg="#101620", fg="#68788e",
                               font=("Microsoft YaHei", -9), cursor="hand2")
            summary.pack(side="left")
            self._summary_labels[key] = summary
            status = tk.Label(row, text="", bg="#101620", fg="#9aa8bc",
                              font=("Microsoft YaHei", -9), width=14,
                              anchor="e")
            status.pack(side="right", padx=(4, 6))
            self._status_labels[key] = status
            for widget in (row, name, summary):
                widget.bind("<Button-1>", lambda event, k=key: self._select(k))
            buttons = tk.Frame(row, bg="#101620")
            buttons.pack(side="right")
            tk.Button(buttons, text="↑", command=lambda k=key: self._move(k, -1),
                      bg="#1b2432", fg="#9aa8bc", relief="flat", bd=0,
                      width=2, font=("Microsoft YaHei", -9),
                      cursor="hand2").pack(side="left")
            tk.Button(buttons, text="↓", command=lambda k=key: self._move(k, 1),
                      bg="#1b2432", fg="#9aa8bc", relief="flat", bd=0,
                      width=2, font=("Microsoft YaHei", -9),
                      cursor="hand2").pack(side="left", padx=(2, 0))

    @staticmethod
    def _summary_text(app, key):
        settings = store._clean_daily(app.get("daily"), key)
        if key in ("nte", "maaend"):
            instance = settings.get("instance") or "（自动）"
            detail = f"实例：{instance}"
        elif key == "wuwa":
            detail = f"任务：{settings.get('task') or 'DailyTask'}"
        else:
            detail = f"MAA 配置：{settings.get('config') or '当前配置'}"
        return f"{detail} · 超时 {settings.get('timeout_min')}min"

    def _select(self, key):
        self._selected = key
        self._load_settings(key)
        for item_key, label in self._summary_labels.items():
            label.configure(fg="#4fc3ff" if item_key == key else "#68788e")

    def _load_settings(self, key):
        app = self.hub._app_by_key(key) if key else None
        if app is None:
            return
        settings = daily.effective_settings(app)
        self._settings_title.configure(
            text=f"选中项设置：{app.get('game')}（{app.get('script')}）")
        for field in ("instance", "task", "config"):
            entry = self._entries[field]
            entry.delete(0, "end")
            entry.insert(0, str(settings.get(field) or ""))
        entry = self._entries["timeout_min"]
        entry.delete(0, "end")
        entry.insert(0, str(settings.get("timeout_min") or 120))
        entry = self._entries["extra_args"]
        entry.delete(0, "end")
        entry.insert(0, " ".join(str(item) for item in
                                 (settings.get("extra_args") or [])))
        self._close_var.set(bool(settings.get("close_after")))

    def _apply_settings(self):
        key = self._selected
        if not key:
            return
        try:
            timeout = max(1, min(600, int(self._entries["timeout_min"].get()
                                          .strip() or "120")))
        except ValueError:
            messagebox.showwarning("超时无效", "超时必须是 1–600 的整数分钟。",
                                   parent=self)
            return
        raw_extra = self._entries["extra_args"].get().strip()
        try:
            import shlex
            extra = shlex.split(raw_extra, posix=False) if raw_extra else []
        except Exception:
            extra = raw_extra.split()
        values = {
            "instance": self._entries["instance"].get().strip(),
            "task": self._entries["task"].get().strip(),
            "config": self._entries["config"].get().strip(),
            "timeout_min": timeout,
            "extra_args": extra,
            "close_after": bool(self._close_var.get()),
        }
        self.hub.apply_daily_settings(key, values)
        self._refresh_rows()
        self._load_settings(key)

    def _toggle(self, key):
        app = self.hub._app_by_key(key)
        if app is None:
            return
        settings = store._clean_daily(app.get("daily"), key)
        self.hub.set_daily_enabled(key, not settings.get("enabled", True))
        self._refresh_rows()

    def _move(self, key, delta):
        if self.hub.move_daily(key, delta):
            self._build_rows()
            self._select(key)
            self._refresh_rows()

    def _preview(self):
        text = self.hub.daily_dry_run_text(self._selected)
        top = tk.Toplevel(self)
        top.title("清日常命令预览（dry-run，不启动）")
        top.configure(bg="#0f141d")
        top.transient(self)
        box = tk.Text(top, width=96, height=22, bg="#101620", fg="#cdd8e6",
                      relief="flat", font=("Microsoft YaHei", -9), wrap="word")
        box.pack(padx=12, pady=12)
        box.insert("1.0", text or "（没有可预览的命令）")
        box.configure(state="disabled")

    def _start(self):
        if self.hub._daily_busy():
            messagebox.showinfo("正在执行", "清日常队列已在运行。", parent=self)
            return
        keys = []
        for key in self.hub.daily_order:
            app = self.hub._app_by_key(key)
            if app and (app.get("daily") or {}).get("enabled", True):
                keys.append(key)
        if not keys:
            messagebox.showwarning("没有启用的游戏",
                                   "请先在列表里勾选要执行清日常的游戏。",
                                   parent=self)
            return
        if not messagebox.askyesno(
                "开始一键清日常",
                "将按列表顺序自动执行这些游戏的清日常。\n\n"
                "⚠ 自动化存在账号风险；执行期间脚本可能抢占鼠标键盘，请不要操作电脑。\n\n"
                "确定开始吗？", parent=self):
            return
        self.hub.start_daily_queue(keys)
        self._refresh_rows()

    def _stop(self):
        self.hub.stop_daily()

    # ---------------------------------------------------------- 刷新
    def _refresh_rows(self):
        snapshot = self.hub._daily_snapshot()
        results = {item.get("key"): item for item in (snapshot.get("results") or [])}
        current = snapshot.get("current")
        for key, label in self._status_labels.items():
            result = results.get(key)
            if current == key:
                text, color = "清日常中…", "#ffce6b"
            elif result:
                state = result.get("state")
                text = result.get("state_label") or state or ""
                color = {"finished": T.HEX_OK, "failed": "#ff7f7f",
                         "timeout": "#ffce6b", "stopped": "#ff7f7f"}.get(
                             state, T.HEX_TXT3)
            else:
                text, color = "待执行", T.HEX_TXT3
            label.configure(text=text, fg=color)
        for key, button in getattr(self, "_toggle_buttons", {}).items():
            app = self.hub._app_by_key(key)
            if app is None:
                continue
            settings = store._clean_daily(app.get("daily"), key)
            enabled = bool(settings.get("enabled", True))
            try:
                button.configure(
                    text="启用" if enabled else "停用",
                    bg="#25445f" if enabled else "#1b2432",
                    fg="#eaf0f8" if enabled else "#68788e")
            except Exception:
                pass
        busy = self.hub._daily_busy()
        try:
            self._stop_button.configure(state="normal" if busy else "disabled")
        except Exception:
            pass

    def _update_progress(self):
        text = "\n".join(self.hub.daily_log[-120:])
        if text == self._last_progress:
            return
        self._last_progress = text
        try:
            self._progress.configure(state="normal")
            self._progress.delete("1.0", "end")
            self._progress.insert("1.0", text or "（尚未开始）")
            self._progress.see("end")
            self._progress.configure(state="disabled")
        except Exception:
            pass

    def refresh(self):
        self._refresh_rows()
        self._update_progress()

    def _poll(self):
        try:
            self.refresh()
        except Exception:
            pass
        try:
            self._poll_after = self.after(700, self._poll)
        except Exception:
            self._poll_after = None

    def _close(self):
        if self._poll_after:
            try:
                self.after_cancel(self._poll_after)
            except Exception:
                pass
            self._poll_after = None
        self.hub.daily_dialog = None
        self.destroy()

    def _center(self, master):
        self.update_idletasks()
        width, height = self.winfo_width(), self.winfo_height()
        try:
            x = master.winfo_rootx() + (master.winfo_width() - width) // 2
            y = master.winfo_rooty() + (master.winfo_height() - height) // 2
        except Exception:
            x = y = 100
        x = min(max(0, x), max(0, self.winfo_screenwidth() - width))
        y = min(max(0, y), max(0, self.winfo_screenheight() - height))
        self.geometry(f"+{x}+{y}")


def run():
    import ctypes
    mutex = store.kernel32.CreateMutexW(None, False, "Local\\GameHubLite_SingleInstance")
    if mutex and ctypes.get_last_error() == 183:
        store.focus_window(TITLE)
        return
    root = tk.Tk()
    GameHub(root)
    try:
        root.mainloop()
    finally:
        if mutex:
            store.kernel32.CloseHandle(mutex)
