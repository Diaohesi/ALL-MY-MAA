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

from PIL import Image, ImageTk

from . import VERSION, daily, detector, render, store
from . import theme as T

TITLE = "AllMyMaa · 游戏脚本中心"


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
    """v0.8 主界面：左侧导航 + 主页 / 清日常 / 设置三页（真实 Tk 控件）。"""

    def __init__(self, root):
        self.root = root
        self.apps, self.clash_exe, self.search_root, meta = store.load_state_full()
        self.settings = store._clean_settings(meta.get("settings"))
        self.daily_order = list(meta.get("daily_order") or store.DEFAULT_DAILY_ORDER)
        # 设置页的「默认超时/完成后关闭脚本」作用于尚未单独保存过 daily 的卡片
        for app in self.apps:
            if app.get("daily_explicit"):
                continue
            key = app.get("key", "")
            current = app.get("daily") or store._clean_daily(None, key)
            current["timeout_min"] = int(
                self.settings.get("daily_default_timeout") or 120)
            current["close_after"] = bool(
                self.settings.get("daily_close_after", True))
            app["daily"] = current
        self.page = "home"
        self.versions = {}
        self.latest = {}
        self.starting = {}
        self.running = {}
        self.game_states = {}
        self.adb_enabled = bool(self.settings.get("adb_enabled"))
        self.daily_manager = daily.DailyManager(self.apps,
                                                on_event=self._daily_manager_event)
        self.daily_events = queue.Queue()
        self.daily_log = []
        self.daily_selected = None
        self._photos = {}
        self._home_rows = {}
        self._daily_rows = {}
        self._daily_vars = {}
        self._daily_status = {}
        self._daily_start_btn = {}
        self._daily_stop_btn = {}
        self._daily_hint = {}
        self._daily_settings = {}
        self._daily_summary = {}
        self._nav_buttons = {}
        self._accent_buttons = []
        self.checking = False
        self.manual_check = False
        self.update_queue = queue.Queue()
        self._toast_after = None
        self._poll_after = None
        self._closing = False
        self.config_saved = store.save_state(
            self.apps, self.clash_exe, self.search_root,
            self.daily_order, self.settings)
        self._setup_fonts()
        self._build_ui()
        try:
            detector.set_adb_enabled(self.adb_enabled)
        except Exception:
            pass
        self._update_versions()
        self._apply_accent_theme()
        self._rebuild_home()
        self._rebuild_daily()
        self.show_page("home")
        self._refresh()
        self._schedule_poll()
        if self.settings.get("check_update_on_start", True):
            self.root.after(900, self._start_update_check)
        if not self.config_saved:
            self.root.after(300, self._warn_save_failed)
        self._toast("就绪")

    # ---------------------------------------------------------- 初始化
    def _save_config(self):
        saved = store.save_state(self.apps, self.clash_exe, self.search_root,
                                 self.daily_order, self.settings)
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
        self.f_title = tkfont.Font(family=fam, size=-20, weight="bold")
        self.f_page = tkfont.Font(family=fam, size=-15, weight="bold")
        self.f_name = tkfont.Font(family=fam, size=-13, weight="bold")
        self.f_body = tkfont.Font(family=fam, size=-11)
        self.f_small = tkfont.Font(family=fam, size=-10)
        self.f_tiny = tkfont.Font(family=fam, size=-9)
        self.f_btn = tkfont.Font(family=fam, size=-11, weight="bold")

    def _app_by_key(self, key):
        for app in self.apps:
            if app.get("key") == key:
                return app
        return None

    def _key_index(self, key):
        for index, app in enumerate(self.apps):
            if app.get("key") == key:
                return index
        return -1

    def _icon_photo(self, path, size):
        key = (path, size)
        if key in self._photos:
            return self._photos[key]
        try:
            img = render.load_icon(path, 256)
            width, height = img.size
            scale = min(size / width, size / height)
            img = img.resize((max(1, int(width * scale)),
                              max(1, int(height * scale))), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img, master=self.root)
        except Exception:
            photo = None
        self._photos[key] = photo
        return photo

    # ---------------------------------------------------------- 控件
    def _button(self, parent, text, command, kind="normal", width=None,
                font=None, state=None):
        styles = {
            "normal": ("#1b2432", "#26313f", "#eaf0f8", "#ffffff"),
            "primary": ("#25445f", "#2d5577", "#eaf0f8", "#ffffff"),
            "ghost": ("#101620", "#1b2432", "#9aa8bc", "#ffffff"),
            "danger": ("#3a2430", "#4a2c3a", "#ffb3b3", "#ffffff"),
        }
        bg, active, fg, active_fg = styles.get(kind, styles["normal"])
        if kind == "primary":
            accent = self.settings.get("accent") or "#4fc3ff"
            bg, active, fg, active_fg = accent, accent, "#071018", "#071018"
        kwargs = dict(text=text, command=command, bg=bg, fg=fg,
                      activebackground=active, activeforeground=active_fg,
                      relief="flat", bd=0, padx=10, pady=4,
                      font=font or self.f_btn, cursor="hand2")
        if width:
            kwargs["width"] = width
        if state:
            kwargs["state"] = state
        button = tk.Button(parent, **kwargs)
        if kind == "primary":
            self._accent_buttons.append(button)
        return button

    def _entry(self, parent, value="", width=18):
        entry = tk.Entry(parent, bg="#0c111a", fg="#eaf0f8",
                         insertbackground="#eaf0f8", relief="flat",
                         highlightthickness=1,
                         highlightbackground="#243044",
                         highlightcolor=self.settings.get("accent", "#4fc3ff"),
                         font=self.f_body, width=width)
        entry.insert(0, str(value or ""))
        return entry

    def _label(self, parent, text="", color="#9aa8bc", font=None, **kwargs):
        return tk.Label(parent, text=text, bg=kwargs.pop("bg", "#0f141d"),
                        fg=color, font=font or self.f_body, **kwargs)

    def _scroll_area(self, parent):
        outer = tk.Frame(parent, bg="#0f141d")
        canvas = tk.Canvas(outer, bg="#0f141d", highlightthickness=0)
        scroll = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                              width=10, bg="#1b2432", troughcolor="#101620",
                              activebackground="#26313f", relief="flat",
                              bd=0, highlightthickness=0)
        inner = tk.Frame(canvas, bg="#0f141d")
        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda event: canvas.configure(
                       scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda event: canvas.itemconfigure(window,
                                                      width=event.width))
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return outer, inner

    # ---------------------------------------------------------- 主布局
    def _build_ui(self):
        self.root.title(TITLE)
        self.root.configure(bg=T.HEX_BG)
        self.root.resizable(True, True)
        self.root.minsize(T.MIN_W, T.MIN_H)
        width, height = T.WIN_W, T.WIN_H
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(
            f"{width}x{height}+{max(0, (sw - width) // 2)}"
            f"+{max(0, (sh - height) // 2 - 20)}")
        try:
            self.root.iconphoto(
                True, tk.PhotoImage(file=os.path.join(store.ASSETS, "hub.png")))
        except Exception:
            pass
        _dark_titlebar(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        self._build_sidebar()
        self.content = tk.Frame(self.root, bg=T.HEX_BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        self.pages = {}
        for name in ("home", "daily", "settings"):
            frame = tk.Frame(self.content, bg=T.HEX_BG)
            frame.grid(row=0, column=0, sticky="nsew")
            self.pages[name] = frame
        self._build_home_page()
        self._build_daily_page()
        self._build_settings_page()
        self._apply_accent_theme()
        self.toast_var = tk.StringVar(value="")
        self.toast_label = tk.Label(self.content, textvariable=self.toast_var,
                                    bg="#0a0d13", fg="#9aa8bc",
                                    anchor="w", font=self.f_small,
                                    padx=14, pady=6)
        self.toast_label.grid(row=1, column=0, sticky="we")

    def _build_sidebar(self):
        sidebar = tk.Frame(self.root, bg="#101620", width=T.SIDEBAR_W)
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(6, weight=1)
        self.sidebar = sidebar

        head = tk.Frame(sidebar, bg="#101620")
        head.grid(row=0, column=0, sticky="we", padx=16, pady=(18, 12))
        logo = self._icon_photo(os.path.join(store.ASSETS, "hub.png"), 38)
        if logo is not None:
            tk.Label(head, image=logo, bg="#101620").pack(side="left")
            self._logo_photo = logo
        text = tk.Frame(head, bg="#101620")
        text.pack(side="left", padx=(10, 0))
        self._label(text, "AllMyMaa", color="#eaf0f8", font=self.f_page,
                    bg="#101620").pack(anchor="w")
        self._label(text, "游戏脚本中心", color="#68788e",
                    font=self.f_tiny, bg="#101620").pack(anchor="w")

        tk.Frame(sidebar, bg="#243044", height=1).grid(
            row=1, column=0, sticky="we", padx=14, pady=(0, 10))

        nav = tk.Frame(sidebar, bg="#101620")
        nav.grid(row=2, column=0, sticky="we", padx=10)
        nav.columnconfigure(0, weight=1)
        items = (("home", "主页"), ("daily", "清日常"), ("settings", "设置"))
        for index, (name, label) in enumerate(items):
            button = tk.Button(
                nav, text=label, command=lambda page=name: self.show_page(page),
                bg="#101620", fg="#9aa8bc", activebackground="#1b2432",
                activeforeground="#ffffff", relief="flat", bd=0,
                anchor="w", padx=16, pady=9, font=self.f_btn, cursor="hand2")
            button.grid(row=index, column=0, sticky="we", pady=2)
            self._nav_buttons[name] = button

        tk.Frame(sidebar, bg="#243044", height=1).grid(
            row=3, column=0, sticky="we", padx=14, pady=(10, 10))

        self.clash_button = self._button(
            sidebar, "打开 Clash Verge", self.open_clash, kind="normal")
        self.clash_button.grid(row=4, column=0, sticky="we", padx=14, pady=2)

        bottom = tk.Frame(sidebar, bg="#101620")
        bottom.grid(row=7, column=0, sticky="we", padx=16, pady=(6, 16))
        self.sidebar_hub_var = tk.StringVar(value="就绪")
        self.sidebar_count_var = tk.StringVar(value="")
        self._label(bottom, "Hub 状态", color="#4d5c74",
                    font=self.f_tiny, bg="#101620").pack(anchor="w")
        tk.Label(bottom, textvariable=self.sidebar_hub_var, bg="#101620",
                 fg="#4ade80", font=self.f_small,
                 anchor="w").pack(anchor="w", pady=(0, 6))
        tk.Label(bottom, textvariable=self.sidebar_count_var, bg="#101620",
                 fg="#68788e", font=self.f_tiny,
                 anchor="w").pack(anchor="w", pady=(0, 8))
        self._label(bottom, f"AllMyMaa v{VERSION} · 单实例", color="#4d5c74",
                    font=self.f_tiny, bg="#101620").pack(anchor="w")

    def _apply_accent_theme(self):
        """把 settings.accent 应用到导航高亮与主按钮（强调色）。"""
        accent = self.settings.get("accent") or "#4fc3ff"
        for button in self._accent_buttons:
            try:
                button.configure(bg=accent, fg="#071018",
                                 activebackground=accent,
                                 activeforeground="#071018")
            except Exception:
                pass
        for page_name, button in self._nav_buttons.items():
            selected = page_name == self.page
            try:
                button.configure(fg=accent if selected else "#9aa8bc",
                                 bg="#1b2a3c" if selected else "#101620")
            except Exception:
                pass

    def show_page(self, name):
        if name not in self.pages:
            return
        self.page = name
        for page_name, frame in self.pages.items():
            if page_name == name:
                frame.tkraise()
            else:
                frame.lower()
        accent = self.settings.get("accent") or "#4fc3ff"
        for page_name, button in self._nav_buttons.items():
            if page_name == name:
                button.configure(bg="#1b2a3c", fg=accent,
                                 activebackground="#243a52")
            else:
                button.configure(bg="#101620", fg="#9aa8bc",
                                 activebackground="#1b2432")
        if name == "home":
            self._refresh_home_states()
        elif name == "daily":
            self._refresh_daily_states()
        elif name == "settings":
            self._refresh_settings_view()

    # ---------------------------------------------------------- 主页
    def _build_home_page(self):
        page = self.pages["home"]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        header = tk.Frame(page, bg=T.HEX_BG)
        header.grid(row=0, column=0, sticky="we", padx=24, pady=(20, 8))
        header.columnconfigure(1, weight=1)
        self._label(header, "主页", color="#eaf0f8", font=self.f_title,
                    bg=T.HEX_BG).grid(row=0, column=0, sticky="w")
        self._label(header, "选择游戏行或「打开脚本」：未运行则启动，运行中则唤到前台",
                    color="#68788e", font=self.f_small,
                    bg=T.HEX_BG).grid(row=1, column=0, sticky="w", pady=(2, 0))
        actions = tk.Frame(header, bg=T.HEX_BG)
        actions.grid(row=0, column=2, rowspan=2, sticky="e")
        self._button(actions, "添加游戏", self.add_app,
                     kind="primary").pack(side="left", padx=(0, 7))
        self._button(actions, "检查更新", self._on_refresh).pack(
            side="left", padx=(0, 7))
        self._button(actions, "重新识别路径", self.rescan_paths).pack(side="left")
        area, self.home_inner = self._scroll_area(page)
        area.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 12))

    def _rebuild_home(self):
        if not hasattr(self, "home_inner"):
            return
        for child in self.home_inner.winfo_children():
            child.destroy()
        self._home_rows = {}
        for index, app in enumerate(self.apps):
            self._build_home_row(index, app)
        if not self.apps:
            self._label(self.home_inner, "还没有游戏，点右上角「添加游戏」开始。",
                        color="#68788e").pack(padx=10, pady=20)
        self._refresh_home_states()

    def _build_home_row(self, index, app):
        key = app["key"]
        row = tk.Frame(self.home_inner, bg="#101620",
                       highlightthickness=1, highlightbackground="#243044")
        row.pack(fill="x", pady=6)
        row.columnconfigure(2, weight=1)
        icon = self._icon_photo(app.get("icon_path"), 58)
        icon_label = tk.Label(row, image=icon, bg="#101620")
        if icon is not None:
            icon_label.image = icon
        icon_label.grid(row=0, column=0, rowspan=2, padx=(16, 14), pady=14)

        name = tk.Label(row, text=app.get("game", ""), bg="#101620",
                        fg="#eaf0f8", font=self.f_name, anchor="w")
        name.grid(row=0, column=1, sticky="sw", pady=(14, 0))
        version = tk.Label(row, text="", bg="#101620", fg="#68788e",
                           font=self.f_small, anchor="w")
        version.grid(row=1, column=1, sticky="nw")

        status_box = tk.Frame(row, bg="#101620")
        status_box.grid(row=2, column=0, columnspan=2, sticky="w",
                        padx=(16, 0), pady=(0, 14))
        script_status = tk.StringVar(value="脚本 未启动")
        game_status = tk.StringVar(value="游戏 未运行")
        script_status_label = tk.Label(status_box, textvariable=script_status,
                                       bg="#101620", fg="#9aa8bc",
                                       font=self.f_small)
        script_status_label.pack(side="left", padx=(0, 16))
        game_status_label = tk.Label(status_box, textvariable=game_status,
                                     bg="#101620", fg="#68788e",
                                     font=self.f_small)
        game_status_label.pack(side="left")

        buttons = tk.Frame(row, bg="#101620")
        buttons.grid(row=0, column=3, rowspan=2, sticky="e",
                     padx=(10, 16), pady=14)
        main_btn = self._button(buttons, "打开脚本",
                                lambda k=key: self.open_script(k),
                                kind="primary", width=11)
        main_btn.pack(side="left", padx=(0, 7))
        game_btn = self._button(buttons, "启动游戏",
                                lambda k=key: self.launch_game(k),
                                width=9)
        game_btn.pack(side="left", padx=(0, 7))
        daily_btn = self._button(buttons, "清日常",
                                 lambda k=key: self.run_daily_single(k),
                                 width=9)
        daily_btn.pack(side="left", padx=(0, 7))
        more_btn = self._button(buttons, "更多 ▾",
                                lambda k=key, w=None: None, width=8)
        more_btn.configure(command=lambda k=key, w=more_btn: self._show_more(k, w))
        more_btn.pack(side="left")

        for widget in (row, icon_label, name, version):
            widget.bind("<Button-1>",
                        lambda event, k=key: self.open_script(k))

        self._home_rows[key] = {
            "row": row, "name": name, "version": version,
            "script_status": script_status, "game_status": game_status,
            "script_status_label": script_status_label,
            "game_status_label": game_status_label,
            "main_btn": main_btn, "game_btn": game_btn,
            "daily_btn": daily_btn,
        }

    def _refresh_home_states(self):
        accent = self.settings.get("accent") or "#4fc3ff"
        by_key = {app["key"]: app for app in self.apps}
        daily_snapshot = self.daily_manager.snapshot()
        daily_busy = daily_snapshot.get("busy")
        daily_active = daily_snapshot.get("active")
        for key, row in self._home_rows.items():
            app = by_key.get(key)
            if app is None:
                continue
            version = self.versions.get(key) or ""
            text = app.get("script", "")
            if version:
                text += " · " + version
            if self._has_update(app):
                text += "  →  " + str(self.latest.get(key))
                row["version"].configure(fg=accent)
            else:
                row["version"].configure(fg="#68788e")
            row["version"].configure(text=text)

            script_state = self._app_state(app)
            script_labels = {"on": ("脚本 运行中", "#4ade80"),
                             "starting": ("脚本 启动中…", "#ffce6b"),
                             "missing": ("脚本 路径缺失", "#ff7f7f"),
                             "off": ("脚本 未启动", "#9aa8bc")}
            label, color = script_labels.get(script_state,
                                            script_labels["off"])
            row["script_status"].set(label)
            row["script_status_label"].configure(fg=color)
            game_state = self._game_state(app)
            if not game_state.get("configured"):
                game_text, game_color = "游戏 未配置", "#68788e"
            elif game_state.get("running"):
                game_text = "游戏 " + (game_state.get("label") or "运行中")
                game_color = "#4ade80"
            elif game_state.get("reason") == "launcher":
                game_text, game_color = "游戏 启动器已开", "#ffce6b"
            elif game_state.get("reason") == "cloud":
                game_text, game_color = "游戏 云游戏运行中", "#4ade80"
            else:
                game_text, game_color = "游戏 未运行", "#68788e"
            row["game_status"].set(game_text)
            row["game_status_label"].configure(fg=game_color)

            running = bool(self.running.get(key, {}).get("script"))
            row["main_btn"].configure(
                text="唤到前台" if running else "打开脚本",
                state="normal")
            if daily_active == key:
                row["daily_btn"].configure(text="清日常中", state="disabled")
            elif daily_busy:
                row["daily_btn"].configure(text="清日常", state="disabled")
            else:
                row["daily_btn"].configure(text="清日常", state="normal")
        self._refresh_sidebar()

    def _refresh_sidebar(self):
        running = sum(1 for app in self.apps
                      if self.running.get(app["key"], {}).get("script"))
        self.sidebar_hub_var.set("运行中" if running else "就绪")
        self.sidebar_count_var.set(f"{running} 个脚本运行中 · 共 {len(self.apps)} 个卡片")

    def _show_more(self, key, widget):
        app = self._app_by_key(key)
        if app is None:
            return
        menu = tk.Menu(self.root, tearoff=0, bg="#151b26", fg="#eaf0f8",
                       activebackground="#2a3547", activeforeground="#ffffff",
                       bd=0, font=self.f_small)
        menu.add_command(label="编辑卡片",
                         command=lambda: self.edit_app(self._key_index(key)))
        menu.add_command(label="检查更新",
                         command=lambda: self.update_app(key))
        menu.add_separator()
        menu.add_command(label="脚本官网",
                         command=lambda: self._open_url(app.get("site"),
                                                        "脚本官网"))
        menu.add_command(label="GitHub",
                         command=lambda: self._open_url(app.get("github"),
                                                        "GitHub"))
        menu.add_command(label="游戏下载页",
                         command=lambda: self.download_game(key))
        menu.add_separator()
        menu.add_command(label="打开脚本文件夹",
                         command=lambda: self.open_folder(key))
        menu.add_command(label="更新启动器",
                         command=lambda: self._launch_updater(app))
        if not app.get("builtin"):
            menu.add_separator()
            menu.add_command(label="删除此卡片",
                             command=lambda: self.delete_app(
                                 self._key_index(key)))
        try:
            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height()
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ---------------------------------------------------------- 清日常页
    def _build_daily_page(self):
        page = self.pages["daily"]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(3, weight=1)
        header = tk.Frame(page, bg=T.HEX_BG)
        header.grid(row=0, column=0, sticky="we", padx=24, pady=(20, 4))
        header.columnconfigure(0, weight=1)
        self._label(header, "清日常", color="#eaf0f8", font=self.f_title,
                    bg=T.HEX_BG).grid(row=0, column=0, sticky="w")
        self._label(header, "使用脚本自身已配置的任务；勾选决定队列，顺序可调；同一时刻只运行一项。",
                    color="#68788e", font=self.f_small,
                    bg=T.HEX_BG).grid(row=1, column=0, sticky="w", pady=(2, 0))
        toolbar = tk.Frame(page, bg=T.HEX_BG)
        toolbar.grid(row=1, column=0, sticky="we", padx=24, pady=(6, 6))
        self._button(toolbar, "全选", lambda: self._daily_check_all(True),
                     width=6).pack(side="left", padx=(0, 6))
        self._button(toolbar, "取消全选", lambda: self._daily_check_all(False),
                     width=8).pack(side="left", padx=(0, 12))
        self._button(toolbar, "↑ 上移", lambda: self._daily_move(-1),
                     width=7).pack(side="left", padx=(0, 6))
        self._button(toolbar, "↓ 下移", lambda: self._daily_move(1),
                     width=7).pack(side="left", padx=(0, 12))
        self._button(toolbar, "开始选中项", self._daily_start_checked,
                     kind="primary", width=11).pack(side="left", padx=(0, 6))
        self._button(toolbar, "停止", self._daily_stop_all,
                     kind="danger", width=6).pack(side="left", padx=(0, 12))
        self._button(toolbar, "查看命令(dry-run)", self._daily_preview,
                     width=16).pack(side="left")
        self._label(page, "⚠ 自动化可能违反游戏条款、存在账号风险；执行期间脚本会抢占鼠标键盘，请确认后使用。",
                    color="#ffce6b", font=self.f_tiny,
                    bg=T.HEX_BG).grid(row=2, column=0, sticky="w",
                                      padx=24)
        self._daily_area, self.daily_inner = self._scroll_area(page)
        self._daily_area.grid(row=3, column=0, sticky="nsew", padx=24,
                              pady=(4, 8))
        log_frame = tk.Frame(page, bg="#101620", highlightthickness=1,
                             highlightbackground="#243044")
        log_frame.grid(row=4, column=0, sticky="we", padx=24, pady=(0, 14))
        self.daily_log_text = tk.Text(
            log_frame, height=7, bg="#101620", fg="#cdd8e6",
            insertbackground="#cdd8e6", relief="flat", bd=0,
            highlightthickness=0, font=self.f_tiny, wrap="word")
        self.daily_log_text.pack(side="left", fill="both", expand=True,
                                 padx=8, pady=6)
        self.daily_log_text.configure(state="disabled")

    def _daily_settings_for(self, app):
        key = app.get("key", "")
        settings = store._clean_daily(app.get("daily"), key)
        if not app.get("daily_explicit"):
            settings["timeout_min"] = int(
                self.settings.get("daily_default_timeout")
                or settings.get("timeout_min") or 120)
            settings["close_after"] = bool(
                self.settings.get("daily_close_after"))
        # MXU 实例为空时展示自动推断的实例名，方便用户确认/保存
        if key in ("nte", "maaend") and not settings.get("instance"):
            try:
                settings = daily.effective_settings(app)
            except Exception:
                pass
        return settings

    def _rebuild_daily(self):
        if not hasattr(self, "daily_inner"):
            return
        for child in self.daily_inner.winfo_children():
            child.destroy()
        self._daily_rows = {}
        self._daily_vars = {}
        self._daily_status = {}
        self._daily_start_btn = {}
        self._daily_stop_btn = {}
        self._daily_hint = {}
        self._daily_settings = {}
        by_key = {app["key"]: app for app in self.apps}
        order = [key for key in self.daily_order if key in by_key]
        for index, key in enumerate(order):
            self._build_daily_row(index, by_key[key])
        if not self.daily_selected and order:
            self._daily_select(order[0])
        self._render_daily_log()
        self._refresh_daily_states()

    def _build_daily_row(self, index, app):
        key = app["key"]
        settings = self._daily_settings_for(app)
        row = tk.Frame(self.daily_inner, bg="#101620",
                       highlightthickness=1, highlightbackground="#243044")
        row.pack(fill="x", pady=5)
        row.columnconfigure(2, weight=1)
        line1 = tk.Frame(row, bg="#101620")
        line1.grid(row=0, column=0, columnspan=4, sticky="we",
                   padx=(12, 12), pady=(8, 2))
        line1.columnconfigure(2, weight=1)
        var = tk.BooleanVar(value=bool(settings.get("enabled", True)))
        check = tk.Checkbutton(
            line1, variable=var, bg="#101620", activebackground="#101620",
            selectcolor="#25445f", fg="#eaf0f8", bd=0, highlightthickness=0,
            command=lambda k=key: self._daily_on_check(k))
        check.grid(row=0, column=0, padx=(0, 4))
        self._daily_vars[key] = var
        icon = self._icon_photo(app.get("icon_path"), 30)
        icon_label = tk.Label(line1, image=icon, bg="#101620")
        if icon is not None:
            icon_label.image = icon
        icon_label.grid(row=0, column=1, padx=(0, 8))
        name = tk.Label(line1, text=app.get("game", ""), bg="#101620",
                        fg="#eaf0f8", font=self.f_name, anchor="w")
        name.grid(row=0, column=2, sticky="w")
        status = tk.StringVar(value="空闲")
        tk.Label(line1, textvariable=status, bg="#101620", fg="#9aa8bc",
                 font=self.f_small, width=18,
                 anchor="e").grid(row=0, column=3, padx=(8, 10))
        self._daily_status[key] = status
        start_btn = self._button(line1, "开始清日常",
                                 lambda k=key: self._daily_start_row(k),
                                 kind="primary", width=10)
        start_btn.grid(row=0, column=4, padx=(0, 6))
        stop_btn = self._button(line1, "停止",
                                lambda k=key: self._daily_stop_row(k),
                                kind="danger", width=6, state="disabled")
        stop_btn.grid(row=0, column=5)
        self._daily_start_btn[key] = start_btn
        self._daily_stop_btn[key] = stop_btn

        line2 = tk.Frame(row, bg="#101620")
        line2.grid(row=1, column=0, columnspan=4, sticky="we",
                   padx=(30, 12), pady=(0, 8))
        fields = [("instance", "实例", 12), ("task", "任务", 10),
                  ("config", "MAA配置", 10), ("timeout_min", "超时", 5),
                  ("extra_args", "额外参数", 14)]
        entries = {}
        for column, (field, label, width) in enumerate(fields):
            tk.Label(line2, text=label, bg="#101620", fg="#68788e",
                     font=self.f_tiny).grid(row=0, column=column * 2,
                                            padx=(0, 3), sticky="e")
            entry = self._entry(line2, self._daily_field_value(settings, field),
                                width=width)
            entry.grid(row=0, column=column * 2 + 1, padx=(0, 8), sticky="w")
            entries[field] = entry
        save_btn = self._button(line2, "保存设置",
                                lambda k=key: self._daily_save_row(k),
                                width=8)
        save_btn.grid(row=0, column=len(fields) * 2, padx=(4, 0))
        hint = self._label(line2, "", color="#68788e", font=self.f_tiny,
                           bg="#101620")
        hint.grid(row=0, column=len(fields) * 2 + 1, padx=(8, 0), sticky="w")
        self._daily_hint[key] = hint
        self._daily_settings[key] = entries

        for widget in (row, name, icon_label):
            widget.bind("<Button-1>", lambda event, k=key: self._daily_select(k))
        self._daily_rows[key] = row

    @staticmethod
    def _daily_field_value(settings, field):
        if field == "extra_args":
            return " ".join(str(item) for item in
                            (settings.get("extra_args") or []))
        return settings.get(field) or ""

    def _daily_select(self, key):
        self.daily_selected = key
        for row_key, row in self._daily_rows.items():
            row.configure(highlightbackground=(
                self.settings.get("accent") if row_key == key else "#243044"))

    def _daily_on_check(self, key):
        app = self._app_by_key(key)
        var = self._daily_vars.get(key)
        if app is None or var is None:
            return
        settings = store._clean_daily(app.get("daily"), key)
        settings["enabled"] = bool(var.get())
        app["daily"] = settings
        app["daily_explicit"] = True
        self._save_config()
        self._refresh_daily_states()

    def _daily_check_all(self, enabled):
        for key, var in self._daily_vars.items():
            var.set(bool(enabled))
            app = self._app_by_key(key)
            if app is None:
                continue
            settings = store._clean_daily(app.get("daily"), key)
            settings["enabled"] = bool(enabled)
            app["daily"] = settings
            app["daily_explicit"] = True
        self._save_config()
        self._refresh_daily_states()

    def _daily_move(self, delta):
        key = self.daily_selected
        if not key:
            self._toast("请先点选一行，再调整顺序")
            return
        if self.move_daily(key, delta):
            self._rebuild_daily()
            self._daily_select(key)
            self._toast("已调整清日常顺序")

    def _daily_save_row(self, key):
        app = self._app_by_key(key)
        entries = self._daily_settings.get(key) or {}
        if app is None:
            return
        try:
            timeout = max(1, min(600, int(
                entries["timeout_min"].get().strip() or "120")))
        except ValueError:
            self._toast("超时必须是 1–600 的整数分钟")
            return
        import shlex
        raw_extra = entries["extra_args"].get().strip()
        try:
            extra = shlex.split(raw_extra, posix=True) if raw_extra else []
        except Exception:
            extra = raw_extra.split()
        settings = store._clean_daily(app.get("daily"), key)
        settings.update({
            "instance": entries["instance"].get().strip(),
            "task": entries["task"].get().strip(),
            "config": entries["config"].get().strip(),
            "timeout_min": timeout,
            "extra_args": extra,
            "enabled": bool(self._daily_vars[key].get()),
        })
        app["daily"] = settings
        app["daily_explicit"] = True
        if self._save_config():
            self._toast(f"已保存「{app.get('game')}」的清日常设置")
        self._refresh_daily_states()

    def _daily_start_row(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        ok, reason = self.daily_manager.start_single(key)
        if not ok:
            self._toast(reason or "无法开始清日常")
            return
        self._append_daily_log(f"▶ 开始：{app.get('game')}")
        self._refresh_daily_states()
        self._refresh_home_states()

    def _daily_stop_row(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self.daily_manager.state_of(key).get("state") not in (
                daily.STARTING, daily.RUNNING):
            return
        if not messagebox.askyesno(
                "停止清日常",
                f"停止「{app.get('game')}」的清日常吗？\n"
                "会结束由 Hub 启动的脚本进程（不会动你自己打开的程序）。",
                parent=self.root):
            return
        self.daily_manager.stop_single(key)
        self._append_daily_log("用户请求停止…")
        self._refresh_daily_states()

    def _daily_start_checked(self):
        keys = daily.enabled_daily_keys(self.apps, self.daily_order)
        if not keys:
            self._toast("请先勾选要执行清日常的游戏")
            return
        plans = [daily.plan_for(self._app_by_key(key)) for key in keys]
        errors = [error for plan in plans for error in plan.get("errors") or []]
        if errors or self.settings.get("daily_show_preview", True):
            if not self._confirm_preview("清日常命令预览（dry-run）", plans):
                return
        elif not messagebox.askyesno(
                "开始一键清日常",
                "将按勾选顺序自动执行清日常。\n"
                "⚠ 自动化存在账号风险；执行期间脚本可能抢占鼠标键盘。\n\n"
                "确定开始吗？", parent=self.root):
            return
        ok, reason = self.daily_manager.start_queue(keys)
        if not ok:
            self._toast(reason)
            return
        self._append_daily_log("准备执行：" + "、".join(
            str(self._app_by_key(key).get("game")) for key in keys))
        self._refresh_daily_states()
        self._refresh_home_states()

    def _daily_stop_all(self):
        if not self.daily_manager.busy:
            self._toast("当前没有正在运行的清日常")
            return
        if not messagebox.askyesno(
                "停止清日常",
                "确定停止当前清日常/队列吗？\n"
                "会结束由 Hub 启动的脚本进程（不会动你自己打开的程序）。",
                parent=self.root):
            return
        self.daily_manager.stop_all()
        self._append_daily_log("用户请求停止…")
        self._refresh_daily_states()

    def _confirm_preview(self, title, plans, confirm=True):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg="#0f141d")
        dialog.transient(self.root)
        dialog.geometry("760x460")
        result = {"ok": False}
        text = tk.Text(dialog, bg="#101620", fg="#cdd8e6", relief="flat",
                       wrap="word", font=self.f_small)
        text.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        text.insert("1.0", "\n\n".join(daily.describe_plan(plan)
                                       for plan in plans))
        text.configure(state="disabled")
        footer = tk.Frame(dialog, bg="#0f141d")
        footer.pack(fill="x", padx=14, pady=(0, 12))

        def start():
            result["ok"] = True
            dialog.destroy()

        if confirm:
            self._button(footer, "开始执行", start,
                         kind="primary").pack(side="right")
        self._button(footer, "取消" if confirm else "关闭",
                     dialog.destroy).pack(side="right",
                                          padx=(0, 8) if confirm else (0, 0))
        dialog.grab_set()
        self.root.wait_window(dialog)
        return result["ok"]

    def _daily_preview(self):
        keys = daily.enabled_daily_keys(self.apps, self.daily_order)
        if not keys:
            keys = [key for key in self.daily_order if self._app_by_key(key)]
        plans = [daily.plan_for(self._app_by_key(key)) for key in keys]
        if not plans:
            self._toast("没有可预览的清日常项")
            return
        self._confirm_preview("清日常命令预览（dry-run，不启动）", plans,
                              confirm=False)

    def _daily_manager_event(self, event):
        self.daily_events.put(event)

    def _append_daily_log(self, line):
        self.daily_log.append(time.strftime("%H:%M:%S ") + line)
        self.daily_log = self.daily_log[-300:]
        self._render_daily_log()

    def _render_daily_log(self):
        if not hasattr(self, "daily_log_text"):
            return
        text = "\n".join(self.daily_log[-200:]) or "（尚未开始）"
        self.daily_log_text.configure(state="normal")
        self.daily_log_text.delete("1.0", "end")
        self.daily_log_text.insert("1.0", text)
        self.daily_log_text.see("end")
        self.daily_log_text.configure(state="disabled")

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
                changed = True
            elif kind == "item":
                result = event.get("result") or {}
                self._append_daily_log(
                    f"■ {result.get('game') or event.get('key')}："
                    f"{result.get('state_label') or result.get('state')}"
                    + (f"（{result.get('reason')}）"
                       if result.get("reason") else ""))
                changed = True
            elif kind == "done":
                result = event.get("result") or {}
                self._append_daily_log(
                    f"■ {result.get('game') or event.get('key')}："
                    f"{result.get('state_label') or result.get('state')}")
                summary = self._daily_summary_text()
                self._append_daily_log("── " + summary)
                self._toast(summary)
                changed = True
            elif kind == "queue":
                if event.get("state") in (daily.FINISHED, daily.STOPPED,
                                          daily.FAILED):
                    summary = self._daily_summary_text()
                    self._append_daily_log("── " + summary)
                    self._toast(summary)
                    changed = True
        if changed:
            self._refresh_daily_states()
            self._refresh_home_states()
            self._render_daily_log()

    def _daily_summary_text(self):
        snapshot = self.daily_manager.snapshot()
        results = snapshot.get("queue", {}).get("results") or []
        if not results:
            return "清日常结束"
        finished = [item for item in results
                    if item.get("state") == daily.FINISHED]
        failed = [item for item in results
                  if item.get("state") in (daily.FAILED, daily.TIMEOUT)]
        skipped = [item for item in results
                   if item.get("state") in (daily.STOPPED, daily.SKIPPED)]
        parts = [f"完成 {len(finished)}/{len(results)}"]
        if failed:
            parts.append("失败：" + "、".join(str(item.get("game"))
                                            for item in failed))
        if skipped:
            parts.append("停止/跳过：" + "、".join(str(item.get("game"))
                                              for item in skipped))
        return "清日常结束（" + "，".join(parts) + "）"

    def _refresh_daily_states(self):
        if not self._daily_rows:
            return
        snapshot = self.daily_manager.snapshot()
        apps = snapshot.get("apps") or {}
        busy = snapshot.get("busy")
        active = snapshot.get("active")
        for key, status in self._daily_status.items():
            state = apps.get(key) or {}
            label = state.get("state_label") or "空闲"
            status.set(label)
            start_btn = self._daily_start_btn.get(key)
            stop_btn = self._daily_stop_btn.get(key)
            hint = self._daily_hint.get(key)
            reason = self.daily_manager.busy_reason(key)
            if start_btn is not None:
                can_start = not busy or active == key
                start_btn.configure(state="normal" if can_start else "disabled")
                start_btn.configure(text="开始清日常"
                                    if not (active == key) else "执行中…")
            if stop_btn is not None:
                stop_btn.configure(state="normal" if active == key
                                   else "disabled")
            if hint is not None:
                hint.configure(text=reason, fg="#ffce6b" if reason else "#68788e")

    # ---------------------------------------------------------- 设置页
    def _build_settings_page(self):
        page = self.pages["settings"]
        page.columnconfigure(0, weight=1)
        page.rowconfigure(1, weight=1)
        header = tk.Frame(page, bg=T.HEX_BG)
        header.grid(row=0, column=0, sticky="we", padx=24, pady=(20, 8))
        header.columnconfigure(0, weight=1)
        self._label(header, "设置", color="#eaf0f8", font=self.f_title,
                    bg=T.HEX_BG).grid(row=0, column=0, sticky="w")
        self._label(header, "配置会立即持久化到 config.json（保存失败会提示）",
                    color="#68788e", font=self.f_small,
                    bg=T.HEX_BG).grid(row=1, column=0, sticky="w", pady=(2, 0))
        self._button(header, "保存设置", self._apply_settings,
                     kind="primary").grid(row=0, column=1, rowspan=2,
                                          sticky="e")
        area, body = self._scroll_area(page)
        area.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 14))
        self.settings_body = body
        columns = tk.Frame(body, bg="#0f141d")
        columns.pack(fill="both", expand=True)
        left_col = tk.Frame(columns, bg="#0f141d")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 8))
        right_col = tk.Frame(columns, bg="#0f141d")
        right_col.pack(side="left", fill="both", expand=True, padx=(8, 0))

        def section(title, parent):
            frame = tk.Frame(parent, bg="#101620", highlightthickness=1,
                             highlightbackground="#243044")
            frame.pack(fill="x", pady=4)
            self._label(frame, title, color="#eaf0f8", font=self.f_name,
                        bg="#101620").pack(anchor="w", padx=14, pady=(8, 3))
            content = tk.Frame(frame, bg="#101620")
            content.pack(fill="x", padx=14, pady=(0, 10))
            return content

        # 外观
        appearance = section("外观", left_col)
        self._label(appearance, "强调色", color="#9aa8bc",
                    font=self.f_small, bg="#101620").pack(side="left",
                                                          padx=(0, 10))
        self._accent_var = self.settings.get("accent") or "#4fc3ff"
        self._accent_chips = {}
        for color in store.ACCENT_PRESETS:
            chip = tk.Button(appearance, bg=color, width=3, relief="flat",
                             bd=0, cursor="hand2",
                             command=lambda c=color: self._pick_accent(c))
            chip.pack(side="left", padx=3)
            self._accent_chips[color] = chip
        self._refresh_accent_chips()

        # 启动器
        launcher = section("启动器", left_col)
        self.check_update_var = tk.BooleanVar(
            value=bool(self.settings.get("check_update_on_start", True)))
        tk.Checkbutton(launcher, text="启动时检查更新", variable=self.check_update_var,
                       bg="#101620", fg="#9aa8bc", selectcolor="#101620",
                       activebackground="#101620", activeforeground="#eaf0f8",
                       font=self.f_small).pack(anchor="w", pady=2)
        row = tk.Frame(launcher, bg="#101620")
        row.pack(anchor="w", pady=2)
        self._label(row, "状态刷新间隔：", color="#9aa8bc",
                    font=self.f_small, bg="#101620").pack(side="left")
        self.refresh_var = tk.StringVar(
            value=str(self.settings.get("refresh_interval", 1.5)))
        refresh_menu = tk.OptionMenu(row, self.refresh_var, "1.0", "1.5", "2.0")
        refresh_menu.configure(bg="#1b2432", fg="#eaf0f8",
                               activebackground="#26313f", relief="flat",
                               bd=0, highlightthickness=0, font=self.f_small)
        refresh_menu.pack(side="left")
        self._label(row, " 秒", color="#68788e", font=self.f_tiny,
                    bg="#101620").pack(side="left")
        row2 = tk.Frame(launcher, bg="#101620")
        row2.pack(anchor="w", pady=2)
        self._label(row2, "关闭窗口：", color="#9aa8bc", font=self.f_small,
                    bg="#101620").pack(side="left")
        self.close_action_var = tk.StringVar(
            value=self.settings.get("close_action", "exit"))
        for value, label in (("exit", "退出程序"), ("minimize", "最小化到任务栏")):
            tk.Radiobutton(row2, text=label, value=value,
                           variable=self.close_action_var, bg="#101620",
                           fg="#9aa8bc", selectcolor="#101620",
                           activebackground="#101620",
                           activeforeground="#eaf0f8",
                           font=self.f_small).pack(side="left", padx=(0, 12))

        # 路径
        paths = section("路径", left_col)
        row = tk.Frame(paths, bg="#101620")
        row.pack(fill="x", pady=2)
        self._label(row, "脚本根目录：", color="#9aa8bc",
                    font=self.f_small, bg="#101620").pack(side="left")
        self.settings_root_var = tk.StringVar(value=self.search_root)
        tk.Label(row, textvariable=self.settings_root_var, bg="#101620",
                 fg="#68788e", font=self.f_tiny,
                 anchor="w").pack(side="left", fill="x", expand=True)
        self._button(row, "重新识别", self.rescan_paths, width=8).pack(
            side="right")
        row = tk.Frame(paths, bg="#101620")
        row.pack(fill="x", pady=2)
        self._label(row, "Clash Verge：", color="#9aa8bc",
                    font=self.f_small, bg="#101620").pack(side="left")
        self.clash_var = tk.StringVar(value=self.clash_exe or "")
        tk.Entry(row, textvariable=self.clash_var, bg="#0c111a",
                 fg="#eaf0f8", insertbackground="#eaf0f8", relief="flat",
                 highlightthickness=1, highlightbackground="#243044",
                 font=self.f_tiny).pack(side="left", fill="x", expand=True,
                                         padx=(0, 6))
        self._button(row, "浏览", self._browse_clash, width=6).pack(
            side="left", padx=(0, 6))
        self._button(row, "自动查找", self._auto_find_clash, width=8).pack(
            side="left")

        # 清日常
        daily_frame = section("清日常", right_col)
        row = tk.Frame(daily_frame, bg="#101620")
        row.pack(fill="x", pady=2)
        self._label(row, "默认超时（分钟）：", color="#9aa8bc",
                    font=self.f_small, bg="#101620").pack(side="left")
        self.daily_timeout_var = tk.StringVar(
            value=str(self.settings.get("daily_default_timeout", 120)))
        tk.Entry(row, textvariable=self.daily_timeout_var, width=6,
                 bg="#0c111a", fg="#eaf0f8", insertbackground="#eaf0f8",
                 relief="flat", highlightthickness=1,
                 highlightbackground="#243044",
                 font=self.f_small).pack(side="left", padx=(0, 16))
        self._label(row, "（仅用于未单独设置超时的条目）", color="#4d5c74",
                    font=self.f_tiny, bg="#101620").pack(side="left")
        self.preview_var = tk.BooleanVar(
            value=bool(self.settings.get("daily_show_preview", True)))
        self.adb_var = tk.BooleanVar(
            value=bool(self.settings.get("adb_enabled", False)))
        self.daily_close_var = tk.BooleanVar(
            value=bool(self.settings.get("daily_close_after", True)))
        for var, text in ((self.preview_var, "执行前显示命令预览"),
                          (self.adb_var, "启用 ADB 检测（模拟器内游戏）"),
                          (self.daily_close_var, "完成后结束脚本（默认值）")):
            tk.Checkbutton(daily_frame, text=text, variable=var,
                           bg="#101620", fg="#9aa8bc", selectcolor="#101620",
                           activebackground="#101620",
                           activeforeground="#eaf0f8",
                           font=self.f_small).pack(anchor="w", pady=1)

        # 关于
        about = section("关于", right_col)
        self._label(about, f"AllMyMaa v{VERSION}", color="#eaf0f8",
                    font=self.f_small, bg="#101620").pack(anchor="w", pady=1)
        self._label(about, "游戏脚本中心 · 一体化启动器",
                    color="#68788e", font=self.f_tiny,
                    bg="#101620").pack(anchor="w", pady=(0, 4))
        links = tk.Frame(about, bg="#101620")
        links.pack(anchor="w", pady=(2, 0))
        about_links = (
            ("项目主页", lambda: self._open_url(
                "https://diaohesi.github.io/AllMyMaa/", "项目主页")),
            ("GitHub", lambda: self._open_url(
                "https://github.com/Diaohesi/AllMyMaa", "GitHub")),
            ("Release", lambda: self._open_url(
                "https://github.com/Diaohesi/AllMyMaa/releases/latest",
                "Release")),
            ("更新日志", self._open_changelog),
            ("QA 报告", lambda: self._open_doc("qa-report.md")),
            ("调研报告", lambda: self._open_doc("daily-automation-research.md")),
            ("检查更新", self._on_refresh),
        )
        for index, (label, command) in enumerate(about_links):
            self._button(links, label, command, kind="ghost",
                         width=8, font=self.f_tiny).grid(
                row=index // 4, column=index % 4, padx=(0, 5), pady=2,
                sticky="w")

    # ---------------------------------------------------------- 更新日志
    def _open_changelog(self):
        path = _find_changelog()
        if not path:
            self._toast("未找到更新日志 CHANGELOG.md（打包版需随 exe 附带）")
            return
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:
                text = fh.read()
        except Exception as exc:
            self._toast(f"读取更新日志失败：{exc}")
            return
        sections = _parse_changelog(text)
        if not sections:
            content = text.strip() or "（更新日志为空）"
        else:
            blocks = []
            for section in sections:
                title = section["version"]
                if section["date"]:
                    title += f"  ({section['date']})"
                blocks.append(f"## {title}\n\n{section['body']}".strip())
            content = "\n\n".join(blocks)
        self._show_text_window("更新日志 · AllMyMaa", content)

    def _show_text_window(self, title, content):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg="#0f141d")
        dialog.transient(self.root)
        dialog.geometry("780x580")
        text = tk.Text(dialog, bg="#101620", fg="#cdd8e6", relief="flat",
                       wrap="word", font=self.f_small)
        scroll = tk.Scrollbar(dialog, command=text.yview, width=10,
                              bg="#1b2432", troughcolor="#101620",
                              relief="flat", bd=0, highlightthickness=0)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(fill="both", expand=True, padx=(14, 0), pady=14)
        text.insert("1.0", content)
        text.configure(state="disabled")
        footer = tk.Frame(dialog, bg="#0f141d")
        footer.pack(fill="x", padx=14, pady=(0, 12))
        self._button(footer, "关闭", dialog.destroy).pack(side="right")
        dialog.grab_set()
        self.root.wait_window(dialog)

    def _open_doc(self, filename):
        path = os.path.join(store.APP_DIR, "docs", filename)
        if store.open_path(path):
            self._toast(f"已打开 {filename}")
        else:
            self._toast(f"文档不存在：{path}")

    def _pick_accent(self, color):
        self._accent_var = color
        self._refresh_accent_chips()

    def _refresh_accent_chips(self):
        for color, chip in getattr(self, "_accent_chips", {}).items():
            chip.configure(relief="sunken" if color == self._accent_var
                           else "flat", bd=2 if color == self._accent_var else 0)

    def _refresh_settings_view(self):
        if not hasattr(self, "settings_root_var"):
            return
        self.settings_root_var.set(self.search_root)
        self.clash_var.set(self.clash_exe or "")
        self._refresh_accent_chips()

    def _browse_clash(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="选择 Clash Verge 程序",
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if path:
            self.clash_var.set(os.path.normpath(path))

    def _auto_find_clash(self):
        candidates = list(getattr(store, "CLASH_CANDIDATES", []))
        found = next((p for p in candidates if p and os.path.isfile(p)), "")
        if not found:
            for base in (os.environ.get("ProgramFiles", ""),
                         os.environ.get("ProgramFiles(x86)", ""),
                         os.path.join(os.environ.get("LOCALAPPDATA", ""),
                                      "Programs")):
                if not base or not os.path.isdir(base):
                    continue
                for name in ("Clash Verge", "clash-verge", "Clash Verge Rev"):
                    path = os.path.join(base, name, "clash-verge.exe")
                    if os.path.isfile(path):
                        found = path
                        break
                if found:
                    break
        if found:
            self.clash_var.set(found)
            self._toast("已找到 Clash Verge")
        else:
            self._toast("没有自动找到 Clash Verge，请手动浏览选择")

    def _apply_settings(self):
        try:
            timeout = max(1, min(600, int(
                self.daily_timeout_var.get().strip() or "120")))
        except ValueError:
            self._toast("默认超时必须是 1–600 的整数分钟")
            return
        values = dict(self.settings)
        values.update({
            "accent": self._accent_var,
            "check_update_on_start": bool(self.check_update_var.get()),
            "refresh_interval": float(self.refresh_var.get() or 1.5),
            "close_action": self.close_action_var.get() or "exit",
            "clash_exe": self.clash_var.get().strip(),
            "daily_default_timeout": timeout,
            "daily_show_preview": bool(self.preview_var.get()),
            "adb_enabled": bool(self.adb_var.get()),
            "daily_close_after": bool(self.daily_close_var.get()),
        })
        self.settings = store._clean_settings(values)
        self.clash_exe = self.settings.get("clash_exe") or self.clash_exe
        if self.clash_exe and not os.path.isfile(self.clash_exe):
            self.clash_exe = ""
            self.settings["clash_exe"] = ""
        self.adb_enabled = bool(self.settings.get("adb_enabled"))
        try:
            detector.set_adb_enabled(self.adb_enabled)
        except Exception:
            pass
        saved = self._save_config()
        self._accent_var = self.settings.get("accent") or self._accent_var
        self._apply_accent_theme()
        self.show_page(self.page)
        self._schedule_poll()
        self._refresh_settings_view()
        self._refresh_home_states()
        self._refresh_daily_states()
        if saved:
            self._toast("设置已保存")

    def _schedule_poll(self):
        if self._poll_after:
            try:
                self.root.after_cancel(self._poll_after)
            except Exception:
                pass
        delay = _refresh_delay_ms(self.settings)
        self._poll_after = self.root.after(delay, self._poll)

    # ---------------------------------------------------------- 通用状态
    def _app_state(self, app):
        exe = app.get("script_exe", "")
        key = app.get("key", "")
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
        state = self.game_states.get(app.get("key"))
        if state is None:
            try:
                state = detector.detect_game_state(
                    app, adb_enabled=self.adb_enabled)
            except Exception:
                state = {"running": False, "reason": "", "label": "未运行",
                         "hwnd": None, "configured": False, "source": "none",
                         "rules": {}}
            self.game_states[app["key"]] = state
        return state

    def _has_update(self, app):
        latest = self.latest.get(app["key"])
        current = self.versions.get(app["key"])
        return bool(latest and current and store.is_newer(latest, current))

    def _update_versions(self):
        for app in self.apps:
            self.versions[app["key"]] = store.read_version(app)

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
        if self.page == "home":
            self._refresh_home_states()
        elif self.page == "daily":
            self._refresh_daily_states()
        self._refresh_sidebar()

    # ---------------------------------------------------------- 启动/更新
    def open_script(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self.running.get(key, {}).get("script"):
            focused = False
            if isinstance(app.get("launch"), dict):
                focused = store.focus_launch_spec(app)
            if not focused:
                focused = store.bring_to_front(app.get("script_procs") or [])
            self._toast(f"已切换到 {app.get('game')}" if focused
                        else f"{app.get('game')} 正在运行中（窗口未找到）")
            return
        self.launch_script(key)

    def launch_script(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self._app_state(app) == "missing":
            self._choose_script_path(key)
            return
        try:
            ok, error, mode = store.launch_app(app)
        except Exception as exc:
            ok, error, mode = False, str(exc), "none"
        if not ok:
            self._toast(f"启动 {app.get('game')} 失败：{error}")
            return
        if mode == "launcher":
            self._toast(f"未找到正式脚本，已回退启动 {app.get('script')} 启动器（可在启动器里更新）")
            return
        self.starting[key] = time.time()
        self._toast(f"正在启动 {app.get('game')} · {app.get('script')}")
        self._refresh_home_states()

    def _launch_updater(self, app):
        spec = app.get("launch") if isinstance(app.get("launch"), dict) else {}
        if not spec.get("launcher_exe"):
            return False
        ok, error = store.launch_updater(app)
        self._toast(f"正在打开 {app.get('script')} 更新器…" if ok
                    else f"打开更新器失败：{error}")
        return True

    def launch_game(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        try:
            state = detector.detect_game_state(app, adb_enabled=self.adb_enabled)
        except Exception:
            state = {"running": False, "reason": "", "label": "未运行",
                     "hwnd": None}
        self.game_states[key] = state
        if state.get("running"):
            hwnd = state.get("hwnd")
            if hwnd and detector.focus_window(hwnd):
                self._toast(f"已切换到 {app.get('game')}")
            elif store.bring_to_front(app.get("game_procs") or []):
                self._toast(f"已切换到 {app.get('game')}")
            else:
                self._toast(f"{app.get('game')} {state.get('label') or '运行中'}"
                            "（窗口未找到）")
            return
        exe = app.get("game_exe", "")
        saved = True
        if not exe or not os.path.isfile(exe):
            self._toast(f"正在自动检测「{app.get('game')}」的启动程序…")
            try:
                candidates = store.find_game_candidates(app)
            except Exception:
                candidates = []
            if candidates:
                dialog = GameCandidateDialog(
                    self.root, candidates,
                    title=f"选择「{app.get('game')}」的游戏启动程序")
                self.root.wait_window(dialog)
                if not dialog.result:
                    self._toast("已取消启动游戏")
                    return
                exe = os.path.normpath(dialog.result)
            else:
                path = filedialog.askopenfilename(
                    parent=self.root,
                    title=f"选择「{app.get('game')}」的启动程序",
                    filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
                if not path:
                    return
                exe = os.path.normpath(path)
            app["game_exe"] = exe
            app["game_procs"] = store.proc_names_for_exe(exe)
            saved = self._save_config()
            self._rebuild_home()
        ok, error = store.launch_exe(exe)
        if ok:
            note = "" if saved else "（路径未能保存）"
            self._toast(f"正在启动游戏：{app.get('game')}{note}")
        else:
            self._toast(f"启动游戏失败：{error}")

    def download_game(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        url = app.get("download") or app.get("site")
        if not url:
            self._toast(f"{app.get('game')} 还没有配置下载页，可在「编辑此卡片」里填写")
            return
        self._open_url(url, f"{app.get('game')} 下载页")

    def update_app(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        if self._app_state(app) == "missing":
            self._choose_script_path(key)
            return
        if self.running.get(key, {}).get("script"):
            self._toast(f"{app.get('game')} 正在运行，请关闭后重新打开以检查更新")
            return
        if self.checking and key not in self.latest:
            self._toast("正在检查最新版本，请稍候再点一次")
            return
        if self._has_update(app):
            if not self._launch_updater(app):
                self.launch_script(key)
        elif key in self.latest and not self._has_update(app):
            self._toast(f"{app.get('script')} 已是最新版本 "
                        f"{self.versions.get(key, '')}")
        else:
            self._toast(f"无法获取最新版本，打开 {app.get('game')} 自行检查更新")
            if not self._launch_updater(app):
                self.launch_script(key)

    def open_folder(self, key):
        app = self._app_by_key(key)
        folder = os.path.dirname(app.get("script_exe", "")) if app else ""
        if store.open_path(folder):
            self._toast(f"已打开 {app.get('script')} 所在文件夹")
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

    def _choose_script_path(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        path = filedialog.askopenfilename(
            parent=self.root, title=f"选择「{app.get('game')}」的脚本启动程序",
            initialdir=os.path.dirname(app.get("script_exe", ""))
            or self.search_root,
            filetypes=[("可执行程序", "*.exe"), ("所有文件", "*.*")])
        if not path:
            return
        app["script_exe"] = os.path.normpath(path)
        app["script_procs"] = store.proc_names_for_exe(path)
        store.refresh_launch_spec(app)
        saved = self._save_config()
        self._rebuild_home()
        if saved:
            self._toast(f"已更新 {app.get('script')} 的路径")

    def _store_icon(self, key, path):
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
                detect_procs=values["detect_procs"],
                adb_pkg=values["adb_pkg"], base=current)
            app["detect_custom"] = True
        except Exception:
            pass

    # ---------------------------------------------------------- 添加/编辑/删除
    def add_app(self):
        def on_save(data):
            key = self._next_key()
            icon = self._store_icon(key, data["icon"]) if data["icon"] else ""
            app = dict(
                key=key, game=data["game"], script=data["script"], builtin=False,
                script_exe=data["script_exe"],
                script_procs=store._clean_procs(data["script_procs"],
                                                data["script_exe"]),
                game_exe=data["game_exe"],
                game_procs=store._clean_procs(data["game_procs"],
                                              data["game_exe"]),
                accent=data["accent"], fallback_version="",
                site=data["site"], github=data["github"],
                release=data["release"], download=data["download"],
                icon_path=icon or store.custom_icon_path(key),
                daily=store._clean_daily({"enabled": False}, key),
                daily_explicit=False,
            )
            self._apply_detect_fields(app, data)
            self.apps.append(app)
            if key not in self.daily_order:
                self.daily_order.append(key)
            saved = self._save_config()
            self._rebuild_all()
            if saved:
                self._toast(f"已添加 {app.get('game')} · {app.get('script')}")
            self._start_update_check()
        AppDialog(self.root, None, on_save=on_save)

    def edit_app(self, index):
        if index < 0 or index >= len(self.apps):
            return
        app = self.apps[index]

        def on_save(data):
            app["game"] = data["game"]
            app["script"] = data["script"]
            app["script_exe"] = data["script_exe"]
            app["script_procs"] = store._clean_procs(data["script_procs"],
                                                     data["script_exe"])
            app["game_exe"] = data["game_exe"]
            app["game_procs"] = store._clean_procs(data["game_procs"],
                                                   data["game_exe"])
            app["accent"] = data["accent"]
            app["site"] = data["site"]
            app["github"] = data["github"]
            app["release"] = data["release"]
            app["download"] = data["download"]
            if data["icon"] and os.path.isfile(data["icon"]):
                app["icon_path"] = self._store_icon(app["key"], data["icon"])
            self._apply_detect_fields(app, data)
            store.refresh_launch_spec(app)
            self.game_states.pop(app.get("key"), None)
            saved = self._save_config()
            self._rebuild_all()
            if saved:
                self._toast(f"已保存 {app.get('game')} 的配置")

        def on_delete():
            self.delete_app(index)

        AppDialog(self.root, app, on_save=on_save, on_delete=on_delete)

    def delete_app(self, index):
        if index < 0 or index >= len(self.apps):
            return
        app = self.apps[index]
        if app.get("builtin"):
            messagebox.showinfo("无法删除", "内置脚本卡片不能删除，可以修改或隐藏。",
                                parent=self.root)
            return
        if not messagebox.askyesno(
                "删除卡片",
                f"确定删除「{app.get('game')}」这张卡片吗？\n（不会删除任何文件）",
                parent=self.root):
            return
        key = app["key"]
        self.apps = [item for item in self.apps if item.get("key") != key]
        self.daily_order = [item for item in self.daily_order if item != key]
        self.game_states.pop(key, None)
        self.daily_manager = daily.DailyManager(
            self.apps, on_event=self._daily_manager_event)
        saved = self._save_config()
        self._rebuild_all()
        if saved:
            self._toast(f"已删除 {app.get('game')} 的卡片")

    def _next_key(self):
        index = 1
        existing = {app.get("key") for app in self.apps}
        while f"custom_{index}" in existing:
            index += 1
        return f"custom_{index}"

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
        self._rebuild_all()
        total = sum(1 for app in self.apps
                    if os.path.isfile(app.get("script_exe", "")))
        self._toast("路径识别完成：" + f"{total}/{len(self.apps)} 个脚本可用"
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
            self._toast("正在打开 Clash Verge" if ok
                        else f"打开 Clash Verge 失败：{error}")
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="选择 Clash Verge 程序",
            filetypes=[("可执行程序", "*.exe")])
        if path:
            self.clash_exe = os.path.normpath(path)
            self.settings["clash_exe"] = self.clash_exe
            saved = self._save_config()
            if saved:
                self._toast("已记录 Clash Verge 路径，再点一次即可打开")
                self._refresh_settings_view()

    # ---------------------------------------------------------- 清日常（主页入口）
    def run_daily_single(self, key):
        app = self._app_by_key(key)
        if app is None:
            return
        state = self.daily_manager.state_of(key).get("state")
        if state in (daily.STARTING, daily.RUNNING):
            self._daily_stop_row(key)
            return
        if self.daily_manager.busy:
            self._toast(self.daily_manager.busy_reason(key)
                        or "已有清日常任务在运行")
            return
        plans = [daily.plan_for(app)]
        if self.settings.get("daily_show_preview", True):
            if not self._confirm_preview("清日常命令预览（dry-run）", plans):
                return
        ok, reason = self.daily_manager.start_single(key)
        if not ok:
            self._toast(reason)
            return
        self._append_daily_log(f"▶ 开始：{app.get('game')}")
        self._refresh_daily_states()
        self._refresh_home_states()

    def set_daily_enabled(self, key, enabled):
        app = self._app_by_key(key)
        if app is None:
            return
        settings = store._clean_daily(app.get("daily"), key)
        settings["enabled"] = bool(enabled)
        app["daily"] = settings
        app["daily_explicit"] = True
        self._save_config()

    def move_daily(self, key, delta):
        order = [item for item in self.daily_order if self._app_by_key(item)]
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

    def daily_dry_run_text(self, keys=None):
        if keys is None:
            keys = daily.enabled_daily_keys(self.apps, self.daily_order)
            if not keys:
                keys = [key for key in self.daily_order if self._app_by_key(key)]
        plans = [daily.plan_for(self._app_by_key(key)) for key in keys]
        return "\n\n".join(daily.describe_plan(plan) for plan in plans)

    # ---------------------------------------------------------- 更新检查
    def _start_update_check(self, manual=False):
        if getattr(self, "checking", False):
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
            self._update_versions()
            self._refresh_home_states()

    def _update_summary(self):
        updates = [app for app in self.apps if self._has_update(app)]
        if updates:
            return "发现更新：" + "、".join(
                f"{app.get('game')} → {self.latest.get(app.get('key'))}"
                for app in updates)
        return "检查完成：没有发现新版本"

    def _on_refresh(self):
        self._start_update_check(manual=True)

    # ---------------------------------------------------------- 其他
    def _toast(self, text):
        if not hasattr(self, "toast_var"):
            return
        self.toast_var.set(str(text or ""))
        if self._toast_after:
            try:
                self.root.after_cancel(self._toast_after)
            except Exception:
                pass
        self._toast_after = self.root.after(6000, lambda: self.toast_var.set(""))

    def _on_close(self):
        if self.settings.get("close_action") == "minimize":
            self.root.iconify()
            return
        self._closing = True
        try:
            self.root.destroy()
        except Exception:
            pass

    def _poll(self):
        try:
            self._drain_queue()
            self._drain_daily_events()
            self._refresh()
        except Exception:
            pass
        if not self._closing:
            self._schedule_poll()

    def _rebuild_all(self):
        self._update_versions()
        self.daily_manager = daily.DailyManager(
            self.apps, on_event=self._daily_manager_event)
        self._rebuild_home()
        self._rebuild_daily()
        self._refresh()


def _find_changelog():
    """定位 CHANGELOG.md：源码运行用仓库根目录，打包版用 exe 同目录/_MEIPASS。"""
    import sys
    candidates = []
    bundle = getattr(sys, "_MEIPASS", "")
    if bundle:
        candidates.append(os.path.join(bundle, "CHANGELOG.md"))
    candidates.append(os.path.join(store.APP_DIR, "CHANGELOG.md"))
    candidates.append(os.path.join(os.getcwd(), "CHANGELOG.md"))
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return ""


def _parse_changelog(text):
    """解析 `## vX.Y.Z (日期)` 分节，按版本号从新到旧排序（最新在最上面）。"""
    import re
    sections = []
    current = None
    heading = re.compile(
        r"^##\s+(?:\[)?(v?\d+(?:\.\d+)*)(?:\])?\s*(?:[（(]([^）)]*)[）)])?\s*$")
    for line in (text or "").splitlines():
        match = heading.match(line.strip())
        if match:
            if current is not None:
                sections.append(current)
            current = {"version": match.group(1),
                       "date": (match.group(2) or "").strip(),
                       "body": []}
        elif current is not None:
            current["body"].append(line)
    if current is not None:
        sections.append(current)
    for section in sections:
        section["body"] = "\n".join(section["body"]).strip("\n")
    sections.sort(key=lambda item: store.version_key(item["version"]),
                  reverse=True)
    return sections


def _refresh_delay_ms(settings):
    """把 settings.refresh_interval 转成 after() 毫秒（非法值回落 1.5s）。"""
    try:
        interval = float((settings or {}).get("refresh_interval", 1.5))
    except (TypeError, ValueError):
        interval = 1.5
    if interval not in [float(item) for item in store.REFRESH_INTERVALS]:
        interval = 1.5
    return int(interval * 1000)


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
