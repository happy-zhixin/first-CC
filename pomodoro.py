# -*- coding: utf-8 -*-
"""桌面番茄钟 —— 基于 Tkinter 的单文件应用。

用法：
    python pomodoro.py

功能：
    - 专注 / 短休息 / 长休息 三种模式，默认 25 / 5 / 15 分钟
    - 每完成 4 个专注自动进入一次长休息
    - 开始 / 暂停、重置、跳过
    - 可自定义时长并保存到 config.json
    - 时间到播放提示音
"""

# ============================================================================
# 导入模块
# ============================================================================
import json          # 读写配置文件（config.json）
import os            # 拼接配置文件路径
import tkinter as tk # GUI 主库，Python 标准库自带，无需安装

# winsound 是 Windows 专属的提示音模块，非 Windows 系统没有，故用 try 保护
try:
    import winsound  # Windows 专用提示音
except ImportError:
    winsound = None  # 其他系统上为 None，播放提示音时跳过

# ============================================================================
# 全局常量与配置
# ============================================================================

# 默认时长（单位：分钟）。用户修改后会覆盖这些值。
DEFAULT_SETTINGS = {
    "work": 25,               # 专注时长
    "short_break": 5,         # 短休息时长
    "long_break": 15,         # 长休息时长
    "long_break_interval": 4, # 每完成 N 个专注后进入一次长休息
}

# 配置文件路径：与脚本同目录下的 config.json
# __file__ 是当前脚本路径，abspath 转绝对路径，dirname 取所在目录
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 每种模式的显示名称和主题色（用于标签文字和进度环/按钮颜色）
MODE_META = {
    "work":        {"label": "专注时间", "color": "#C75C46"},  # 陶土橙
    "short_break": {"label": "短休息",   "color": "#D9A15B"},  # 暖琥珀
    "long_break":  {"label": "长休息",   "color": "#9A4A3A"},  # 深棕红
}

# 界面配色常量（统一管理，方便整体换肤）
# 暖色系配色：奶油米白背景 + 陶土橙强调，取自参考截图
BG = "#F6F0EB"          # 窗口背景色（奶油米白）
CARD = "#FDF7F4"        # 卡片/弹窗背景色（暖白）
TEXT = "#766C65"        # 主文字颜色（暖灰棕）
SUB_TEXT = "#A9A19B"    # 次要文字颜色（浅暖灰）
RING_BG = "#E5DFD9"     # 进度环底色（浅米灰）


# ============================================================================
# 主应用类
# ============================================================================
class PomodoroApp:
    """番茄钟应用。持有所有界面控件和计时状态。"""

    def __init__(self, root):
        """初始化：读配置 → 建界面 → 进入默认的专注模式。

        参数 root 是 tk.Tk() 创建的主窗口对象。
        """
        self.root = root
        self.settings = self.load_settings()   # 从 config.json 读取（缺失则用默认）
        self.remaining = 0                     # 当前阶段剩余秒数
        self.total = 0                         # 当前阶段总秒数（用于算进度比例）
        self.running = False                   # 是否正在计时
        self.mode = "work"                     # 当前阶段：work / short_break / long_break
        self.work_count = 0                    # 已完成的专注次数（判断何时进长休息）
        self._after_id = None                  # 记录 after() 定时回调的编号，用于暂停时取消

        # ---- 主窗口基础设置 ----
        self.root.title("番茄钟")                    # 窗口标题
        self.root.configure(bg=BG)                  # 背景色
        self.root.resizable(False, False)           # 禁止拉伸窗口（布局固定）
        self.root.geometry("360x560")               # 初始尺寸 360×560 像素

        # ---- 构建界面并进入初始状态 ----
        self.build_ui()                             # 创建所有控件
        self.set_mode("work", reset=True)           # 初始化为专注模式并重置
        self.root.bind("<space>", lambda e: self.toggle())  # 空格键 = 开始/暂停
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)  # 点关闭按钮时做清理

    # ------------------------------------------------------------------------
    # 配置读写
    # ------------------------------------------------------------------------
    def load_settings(self):
        """从 config.json 读取配置。

        返回一个完整配置字典。逻辑：
        1. 若配置文件存在，读出 JSON 并只取默认配置里有的键，覆盖到默认值上；
        2. 任何读取/解析异常（文件损坏、非数字等）都静默忽略，退回默认值。
        """
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 以默认配置为底，用文件里的合法键覆盖
                merged = dict(DEFAULT_SETTINGS)
                merged.update({k: int(v) for k, v in data.items()
                               if k in DEFAULT_SETTINGS})
                return merged
            except (ValueError, OSError, json.JSONDecodeError):
                pass  # 配置文件有问题就放弃，用默认值
        return dict(DEFAULT_SETTINGS)

    def save_settings(self):
        """把当前配置写入 config.json（失败则静默忽略，不影响使用）。"""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                # ensure_ascii=False 让中文按原样保存；indent=2 便于人工阅读
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    # ------------------------------------------------------------------------
    # 界面构建
    # ------------------------------------------------------------------------
    def build_ui(self):
        """创建所有界面控件。从上到下依次是：
        设置按钮 → 模式标签 → 圆形进度环 → 完成度圆点 → 按钮区 → 底部提示。
        """
        # 右上角设置按钮，用 place 精确放到角落
        self.settings_btn = tk.Button(
            self.root, text="⚙", font=("Segoe UI", 14), bg=BG,
            fg=SUB_TEXT, bd=0, activebackground=BG, activeforeground=TEXT,
            cursor="hand2", command=self.open_settings)
        self.settings_btn.place(x=320, y=10, width=30, height=30)

        # 顶部模式标签（"专注时间"/"短休息"/"长休息"），文字颜色随模式变化
        self.mode_label = tk.Label(
            self.root, text="", font=("Microsoft YaHei UI", 16, "bold"),
            bg=BG, fg=TEXT)
        self.mode_label.pack(pady=(36, 0))

        # ---- 圆形进度环 + 中央时间文字 ----
        # Canvas 是画布，可画圆形、弧线、文字等
        self.canvas = tk.Canvas(self.root, width=260, height=260,
                                bg=BG, highlightthickness=0)
        self.canvas.pack(pady=16)

        # 灰色底环：一个完整的圆，作为进度环的"轨道"
        self.ring_bg = self.canvas.create_oval(
            20, 20, 240, 240, outline=RING_BG, width=16)

        # 彩色进度弧：style="arc" 表示只画弧线（不填充）。
        # start=90 让弧线起点在正上方，extent 是弧线角度，初始 0（无进度）
        self.ring_progress = self.canvas.create_arc(
            20, 20, 240, 240, start=90, extent=0, style="arc",
            outline=MODE_META["work"]["color"], width=16)

        # 中央倒计时文字（初始 25:00，随后由 update_display 刷新）
        self.time_text = self.canvas.create_text(
            130, 130, text="25:00", font=("Consolas", 52, "bold"), fill=TEXT)

        # 完成度圆点：显示当前长休息周期内已完成几个专注（● 实心 / ○ 空心）
        self.dots_label = tk.Label(
            self.root, text="", font=("Segoe UI", 14), bg=BG, fg=SUB_TEXT)
        self.dots_label.pack()

        # ---- 按钮区：开始/暂停、重置、跳过 ----
        btn_frame = tk.Frame(self.root, bg=BG)
        btn_frame.pack(pady=24)

        # 开始/暂停按钮（同一个按钮切换文字和功能）
        self.start_btn = tk.Button(
            btn_frame, text="开始", font=("Microsoft YaHei UI", 13, "bold"),
            width=7, height=1, bg="#C75C46", fg="#ffffff", bd=0,
            activebackground="#A34B39", activeforeground="#ffffff",
            cursor="hand2", command=self.toggle)
        self.start_btn.pack(side="left", padx=6)

        # 重置按钮：把当前阶段剩余时间恢复为满
        self.reset_btn = tk.Button(
            btn_frame, text="重置", font=("Microsoft YaHei UI", 13),
            width=7, bg="#E5DFD9", fg=TEXT, bd=0,
            activebackground="#D8CFCA", cursor="hand2",
            command=lambda: self.set_mode(self.mode, reset=True))
        self.reset_btn.pack(side="left", padx=6)

        # 跳过按钮：直接进入下一阶段
        self.skip_btn = tk.Button(
            btn_frame, text="跳过", font=("Microsoft YaHei UI", 13),
            width=7, bg="#E5DFD9", fg=TEXT, bd=0,
            activebackground="#D8CFCA", cursor="hand2",
            command=self.skip)
        self.skip_btn.pack(side="left", padx=6)

        # 底部快捷键提示
        self.hint_label = tk.Label(
            self.root, text="空格键 开始/暂停", font=("Microsoft YaHei UI", 9),
            bg=BG, fg=SUB_TEXT)
        self.hint_label.pack(side="bottom", pady=12)

    # ------------------------------------------------------------------------
    # 模式与状态切换
    # ------------------------------------------------------------------------
    def set_mode(self, mode, reset=False):
        """切换到指定模式并刷新界面。

        参数：
            mode  ：目标模式（"work"/"short_break"/"long_break"）
            reset ：True 时会先停止计时再重置（首次进入/跳过时用）
        """
        self.mode = mode
        meta = MODE_META[mode]
        # 该模式总时长 = 分钟数 × 60 得到秒数，剩余时间先填满
        self.total = self.settings[mode] * 60
        self.remaining = self.total
        # 更新模式标签文字与颜色、开始按钮颜色（用 _darken 生成"按下时"的深色）
        self.mode_label.config(text=meta["label"], fg=meta["color"])
        self.start_btn.config(bg=meta["color"],
                              activebackground=self._darken(meta["color"]))
        self.update_dots()          # 刷新完成度圆点
        if reset:
            self.stop()             # 停止计时并让按钮回到"开始"状态
        self.update_display()       # 刷新倒计时文字和进度环

    def next_mode(self):
        """根据当前模式计算并返回下一个模式。

        规则：
        - 专注结束：work_count 加 1；若达到长休息间隔的整数倍 → 长休息，
          否则 → 短休息。
        - 休息结束：回到专注。
        """
        if self.mode == "work":
            self.work_count += 1
            if self.work_count % self.settings["long_break_interval"] == 0:
                return "long_break"
            return "short_break"
        return "work"  # 休息结束回到专注

    def toggle(self):
        """开始/暂停的切换入口（开始按钮和空格键都调用它）。"""
        if self.running:
            self.stop()   # 正在计时 → 暂停
        else:
            self.running = True
            self.start_btn.config(text="暂停")
            self._tick()  # 立即触发第一次计时

    def stop(self):
        """停止计时：取消定时回调，按钮文字恢复为"开始"。"""
        self.running = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)  # 取消尚未执行的定时回调
            self._after_id = None
        self.start_btn.config(text="开始")

    def reset(self):
        """重置当前阶段（停止并回到满时间）。"""
        self.stop()
        self.set_mode(self.mode, reset=False)

    def skip(self):
        """跳过当前阶段，直接进入下一阶段并重置计时。"""
        self.set_mode(self.next_mode(), reset=True)

    # ------------------------------------------------------------------------
    # 计时核心
    # ------------------------------------------------------------------------
    def _tick(self):
        """每秒执行一次的核心计时函数（由 after 定时触发）。"""
        if not self.running:
            return                          # 已暂停则直接退出
        if self.remaining <= 0:
            self.on_complete()              # 时间到，进入完成处理
            return
        self.remaining -= 1                 # 剩余秒数减 1
        self.update_display()               # 刷新界面
        # 预约 1 秒后再次调用自己，形成循环；保存编号以便暂停时取消
        self._after_id = self.root.after(1000, self._tick)

    def on_complete(self):
        """一个阶段结束时的处理：提示音 → 自动切到下一阶段。"""
        self.notify()                        # 播放提示音
        self.set_mode(self.next_mode(), reset=False)  # 切到下一阶段并刷新

    def notify(self):
        """播放提示音：先响系统铃声，再响两段 Beep 音。"""
        self.root.bell()                     # Tkinter 自带铃声（跨平台）
        if winsound:                         # Windows 上再追加两段不同音高的 Beep
            try:
                winsound.Beep(880, 400)      # 880Hz 响 400ms
                winsound.Beep(1175, 500)     # 1175Hz 响 500ms
            except RuntimeError:
                pass                         # 无声卡等情况下静默失败

    # ------------------------------------------------------------------------
    # 界面刷新
    # ------------------------------------------------------------------------
    def update_display(self):
        """根据 remaining 刷新倒计时文字和进度环。"""
        # divmod 把总秒数拆成 分:秒，max(0, ...) 防止显示负数
        minutes, seconds = divmod(max(0, self.remaining), 60)
        self.canvas.itemconfig(self.time_text, text=f"{minutes:02d}:{seconds:02d}")

        # 进度环颜色跟随当前模式
        color = MODE_META[self.mode]["color"]
        self.canvas.itemconfig(self.ring_progress, outline=color)

        # 计算剩余比例，换算成弧线角度。
        # 用负角度让弧线从正上方（start=90）顺时针缩短，形成倒计时效果
        fraction = self.remaining / self.total if self.total else 0
        extent = -360 * fraction
        self.canvas.itemconfig(self.ring_progress, extent=extent)

    def update_dots(self):
        """刷新完成度圆点，显示当前长休息周期内的完成情况。"""
        interval = self.settings["long_break_interval"]
        done = self.work_count % interval  # 当前周期内已完成的专注数
        # 长休息阶段（一个周期刚结束、done 归零时），把圆点显示为满，
        # 让用户看到"这一轮 4 个都完成了"
        if self.mode != "work" and self.work_count > 0 and done == 0:
            done = interval
        filled = "●" * done               # 实心圆点
        empty = "○" * (interval - done)   # 空心圆点
        self.dots_label.config(text=filled + empty)

    # ------------------------------------------------------------------------
    # 设置弹窗
    # ------------------------------------------------------------------------
    def open_settings(self):
        """打开设置弹窗，可修改时长并保存。"""
        win = tk.Toplevel(self.root)      # 新建一个顶层窗口（弹窗）
        win.title("设置")
        win.geometry("300x300")
        win.resizable(False, False)
        win.transient(self.root)          # 设为主窗口的子窗口
        win.grab_set()                    # 模态：弹出期间主窗口不可操作
        win.configure(bg=CARD)

        # 内部辅助函数：生成一行"标签 + 数值输入框（Spinbox）"
        def row(parent, text, var, r):
            tk.Label(parent, text=text, font=("Microsoft YaHei UI", 11),
                     bg=CARD, fg=TEXT).grid(row=r, column=0, sticky="w",
                                            padx=16, pady=8)
            # Spinbox 是带上下箭头的数值输入框，范围 1~180 分钟
            tk.Spinbox(parent, from_=1, to=180, textvariable=var, width=6,
                       font=("Consolas", 12), justify="center").grid(
                row=r, column=1, sticky="e", padx=16, pady=8)

        # 用 IntVar 绑定当前值，供 Spinbox 读写
        work_var = tk.IntVar(value=self.settings["work"])
        short_var = tk.IntVar(value=self.settings["short_break"])
        long_var = tk.IntVar(value=self.settings["long_break"])
        interval_var = tk.IntVar(value=self.settings["long_break_interval"])

        body = tk.Frame(win, bg=CARD)
        body.pack(pady=16)
        row(body, "专注时长（分钟）", work_var, 0)
        row(body, "短休息（分钟）", short_var, 1)
        row(body, "长休息（分钟）", long_var, 2)
        row(body, "长休息间隔（个）", interval_var, 3)

        def save():
            """保存设置：更新配置 → 写文件 → 重置并回到专注模式。"""
            self.settings.update({
                "work": int(work_var.get()),
                "short_break": int(short_var.get()),
                "long_break": int(long_var.get()),
                "long_break_interval": int(interval_var.get()),
            })
            self.save_settings()
            self.work_count = 0                 # 计数清零，重新开始一个周期
            self.set_mode("work", reset=True)
            win.destroy()

        btn = tk.Frame(win, bg=CARD)
        btn.pack(pady=8)
        tk.Button(btn, text="保存", width=8, bg="#C75C46", fg="#ffffff", bd=0,
                  activebackground="#A34B39", activeforeground="#ffffff",
                  cursor="hand2", command=save).pack(side="left", padx=8)
        tk.Button(btn, text="取消", width=8, bg="#E5DFD9", fg=TEXT, bd=0,
                  activebackground="#D8CFCA", cursor="hand2",
                  command=win.destroy).pack(side="left", padx=8)

        # 让弹窗居中显示在主窗口上：先刷新得到真实尺寸，再计算坐标
        win.update_idletasks()
        x = self.root.winfo_x() + (360 - win.winfo_width()) // 2
        y = self.root.winfo_y() + (560 - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------------
    # 关闭与工具
    # ------------------------------------------------------------------------
    def on_close(self):
        """关闭窗口时先停止计时（取消定时器），再销毁窗口，避免程序残留。"""
        self.stop()
        self.root.destroy()

    @staticmethod
    def _darken(hex_color, factor=0.82):
        """把十六进制颜色调暗，用于按钮"按下时"的颜色。

        例如 "#C75C46" 乘以 0.82 后得到更深的陶土橙，作为 activebackground。
        """
        c = hex_color.lstrip("#")
        r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4))  # 拆出 RGB 三通道
        r, g, b = (int(x * factor) for x in (r, g, b))      # 各通道按比例变暗
        return f"#{r:02x}{g:02x}{b:02x}"


# ============================================================================
# 程序入口
# ============================================================================
if __name__ == "__main__":
    # 只有直接运行本文件时才执行下面的代码（被 import 时不会执行）
    root = tk.Tk()            # 创建主窗口
    app = PomodoroApp(root)   # 初始化应用（建界面、进默认模式）
    root.mainloop()           # 进入 Tkinter 事件循环，程序在此持续运行直到关闭窗口
