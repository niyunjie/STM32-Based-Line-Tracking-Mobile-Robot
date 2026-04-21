import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
import struct
import math
import datetime
import sys
import random
import pygame
import os # 【新增】用于文件操作

# --- 1. 环境自检 ---
try:
    import serial
    import serial.tools.list_ports
except ImportError:
    import ctypes
    ctypes.windll.user32.MessageBoxW(0, "启动失败：缺少 pyserial 库！\n请打开CMD输入: pip install pyserial", "环境错误", 16)
    sys.exit()

# --- 协议定义 (与 remote.c 严格对应) ---
TX_HEADER = 0xA5; TX_TAIL = 0x5A
RX_HEADER = 0x55; RX_TAIL = 0xAA

# --- [UI 视觉核心：深空幽蓝 V10.0 (全中文特供版)] ---
C_BG_MAIN   = "#020406"   # 更深邃的黑
C_BG_PANEL  = "#0a0f16"   # 极暗蓝灰
C_CYAN      = "#00f2ff"   # 能量青
C_CYAN_DIM  = "#003338"   # 极暗青 (背景流光用)
C_ORANGE    = "#ffaa00"   # 警告橙
C_RED       = "#ff003c"   # 危险红
C_GREEN     = "#00ff41"   # 正常绿
C_TEXT_W    = "#e6edf3"   # 白字
C_TEXT_G    = "#556677"   # 灰字 (降低对比度，突出主体)
# 【新增】高亮文字颜色，用于通信配置面板，确保清晰
C_TEXT_HL   = "#00f2ff"   

# 字体配置 (去除英文字体依赖，使用系统通用)
F_H1 = ("Microsoft YaHei", 14, "bold")
F_H2 = ("Microsoft YaHei", 10, "bold")
F_TXT = ("Microsoft YaHei", 9)
F_NUM = ("Impact", 24) # 数字保持 Impact 以获得仪表感

# =================================================================
# [组件库] 动态渲染引擎
# =================================================================

class CyberButton(tk.Canvas):
    """ [组件] 带有光效交互的战术按钮 """
    def __init__(self, parent, text, command, w=120, h=35, col=C_CYAN):
        super().__init__(parent, width=w, height=h, bg=C_BG_PANEL, highlightthickness=0)
        self.command = command
        self.text = text
        self.col = col
        self.w, self.h = w, h
        
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.bind("<ButtonRelease-1>", self.on_release)
        
        self.draw_state("normal")

    def draw_state(self, state):
        self.delete("all")
        w, h = self.w, self.h
        cut = 8 
        
        fill_c, outline_c, text_c, width_l = C_BG_PANEL, self.col, self.col, 1
        
        if state == "hover":
            fill_c = "#1c2533"
            text_c = "#ffffff"
            width_l = 2
            # 悬停时的科技线条装饰
            self.create_line(0, h, cut, h-cut, fill=text_c, width=1)
            self.create_line(w, 0, w-cut, cut, fill=text_c, width=1)
            
        elif state == "click":
            fill_c = self.col
            text_c = "#000000"
            outline_c = "#ffffff"
        
        pts = [cut,0, w,0, w,h-cut, w-cut,h, 0,h, 0,cut]
        self.create_polygon(pts, fill=fill_c, outline=outline_c, width=width_l)
        self.create_text(w/2, h/2, text=self.text, fill=text_c, font=("Microsoft YaHei", 10, "bold"))

    def on_enter(self, e): self.draw_state("hover")
    def on_leave(self, e): self.draw_state("normal")
    def on_click(self, e): self.draw_state("click")
    def on_release(self, e): 
        self.draw_state("hover")
        if self.command: self.command()
        
    def set_config(self, text=None, col=None):
        if text: self.text = text
        if col: self.col = col
        self.draw_state("normal")

class ActiveTechFrame(tk.Frame):
    """ [组件] 带有流光动效边框的容器 """
    def __init__(self, parent, title, w, h):
        super().__init__(parent, bg=C_BG_MAIN, width=w, height=h)
        self.pack_propagate(False) 
        self.w, self.h = w, h
        
        self.cv = tk.Canvas(self, width=w, height=h, bg=C_BG_MAIN, highlightthickness=0)
        self.cv.place(x=0, y=0)
        
        # 静态边框
        self.cv.create_rectangle(2, 12, w-2, h-2, outline="#0d1926", width=1)
        
        # 装饰角
        len_c = 15
        self.cv.create_line(2, 12, 2, 12+len_c, fill=C_CYAN_DIM, width=2)
        self.cv.create_line(2, 12, 2+len_c, 12, fill=C_CYAN_DIM, width=2)
        self.cv.create_line(w-2, h-2, w-2, h-2-len_c, fill=C_CYAN_DIM, width=2)
        self.cv.create_line(w-2, h-2, w-2-len_c, h-2, fill=C_CYAN_DIM, width=2)
        
        # 标题背景
        title_w = len(title)*20 + 20
        self.cv.create_rectangle(15, 0, 15 + title_w, 20, fill=C_BG_MAIN, outline="")
        self.cv.create_text(20, 10, text=f"▎{title}", fill=C_CYAN, anchor="w", font=F_H2)
        
        # 动态光标
        self.scanner_pos = 0
        self.scanner = self.cv.create_line(0, 0, 0, 0, fill=C_CYAN, width=2)
        
        self.inner = tk.Frame(self, bg=C_BG_PANEL)
        self.inner.place(x=5, y=25, width=w-10, height=h-30)

    def update_anim(self):
        w, h = self.w-4, self.h-14 
        total_len = 2 * (w + h)
        p = self.scanner_pos
        
        head_len = 50 
        
        def get_coord(dist):
            dist = dist % total_len
            if dist < w: return (2 + dist, 12) 
            elif dist < w + h: return (2 + w, 12 + (dist-w)) 
            elif dist < 2*w + h: return (2 + w - (dist-w-h), 12 + h) 
            else: return (2, 12 + h - (dist-2*w-h)) 

        pt1 = get_coord(p)
        pt2 = get_coord(p + head_len)
        
        if (pt1[0]==pt2[0] or pt1[1]==pt2[1]):
            self.cv.coords(self.scanner, pt1[0], pt1[1], pt2[0], pt2[1])
            self.cv.itemconfig(self.scanner, state="normal")
        else:
            self.cv.itemconfig(self.scanner, state="hidden")
            
        self.scanner_pos = (self.scanner_pos + 4) % total_len 

class RingGauge(tk.Canvas):
    """ [组件] 动态涡轮仪表盘 """
    def __init__(self, parent, w, h, title, unit, max_val=100, color=C_CYAN):
        super().__init__(parent, width=w, height=h, bg=C_BG_PANEL, highlightthickness=0)
        self.w, self.h = w, h
        self.title = title; self.unit = unit
        self.max_val = max_val; self.color = color
        self.rot_angle = 0 
        self.draw_base()

    def draw_base(self):
        cx, cy = self.w/2, self.h/2
        r = min(cx, cy) - 10
        self.create_arc(cx-r, cy-r, cx+r, cy+r, start=-45, extent=270, style="arc", outline="#161b22", width=8)
        
        # 动态外圈
        r_out = r + 5
        self.id_spin = self.create_arc(cx-r_out, cy-r_out, cx+r_out, cy+r_out, start=0, extent=60, style="arc", outline=C_CYAN_DIM, width=2)
        
        self.create_text(cx, cy+25, text=self.title, fill=C_TEXT_G, font=("Microsoft YaHei", 8))
        self.id_val = self.create_text(cx, cy-5, text="0", fill=C_TEXT_W, font=F_NUM)
        self.create_text(cx, cy-32, text=self.unit, fill=C_TEXT_G, font=("Arial", 9))
        
        self.id_arc = self.create_arc(cx-r, cy-r, cx+r, cy+r, start=225, extent=0, style="arc", outline=self.color, width=8)

    def set_value(self, val):
        disp_val = max(0, min(val, self.max_val))
        extent = -(disp_val / self.max_val) * 270 
        self.itemconfig(self.id_arc, extent=extent)
        self.itemconfig(self.id_val, text=str(int(val)))
        
        col = self.color
        # 距离报警变色逻辑
        if "距离" in self.title:
            if val < 20: col = C_RED
            elif val < 40: col = C_ORANGE
            else: col = C_CYAN
        self.itemconfig(self.id_arc, outline=col)
        
    def animate_spin(self):
        self.rot_angle = (self.rot_angle - 5) % 360
        self.itemconfig(self.id_spin, start=self.rot_angle)

# =================================================================
# 主程序逻辑
# =================================================================
class FinalSystem:
    def __init__(self, root):
        self.root = root
        self.root.title("STM32 循迹小车 张智棋 倪蕴杰 周佑城")
        
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w1, h1 = 1100, 750 
        w2, h2 = 650, 500
        
        self.root.geometry(f"{w1}x{h1}+{int(sw/2 - w1/2 - 30)}+{int(sh/2 - h1/2)}")
        self.root.configure(bg=C_BG_MAIN)
        self.root.resizable(False, False)
        
        # 核心变量
        self.ser = None; self.conn = False; self.run = True
        self.mode = 0; self.joy_x = 0; self.joy_y = 0

        # --- [手柄] Xbox/通用手柄支持：左摇杆接管虚拟摇杆（仅手动模式生效） ---
        self.gamepad = None
        self._gamepad_init_msg = None   # 先存消息，不立刻 log

        try:
            pygame.init()
            pygame.joystick.init()
            if pygame.joystick.get_count() > 0:
                self.gamepad = pygame.joystick.Joystick(0)
                self.gamepad.init()
                self._gamepad_init_msg = f"检测到手柄: {self.gamepad.get_name()}"
            else:
                self._gamepad_init_msg = "未检测到手柄：如需手柄控制，请连接 Xbox 手柄后重启程序"
        except Exception as e:
            self.gamepad = None
            self._gamepad_init_msg = f"手柄初始化失败: {e}"

        # 【核心修改点 1】初始化站点记录变量，防止重复记录同一站
        self.last_log_sta = -1
        
        # 动画变量
        self.radar_angle = 0; self.radar_dir = 2 
        self.dist_history = [0]*100 # 增加历史记录长度以获得更平滑的波形
        self.anim_frames = [] 
        self.current_distance = 0
        
        # --- [背景视觉对象] ---
        self.bg_stars = []    
        self.bg_rain = []    

        # 样式配置
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TCombobox', fieldbackground=C_BG_PANEL, background=C_BG_PANEL, 
                        foreground=C_CYAN, arrowcolor=C_CYAN, bordercolor=C_CYAN_DIM)
        self.root.option_add('*TCombobox*Listbox.background', C_BG_PANEL)
        self.root.option_add('*TCombobox*Listbox.foreground', 'white')

        # === 构建 UI ===
        self.cv_bg = tk.Canvas(self.root, width=w1, height=h1, bg=C_BG_MAIN, highlightthickness=0)
        self.cv_bg.place(x=0, y=0)
        self.init_bg_visuals(w1, h1)

        self.setup_main_ui()
        # UI 已就绪，现在可以安全写日志
        if self._gamepad_init_msg:
            self.log_sys(self._gamepad_init_msg)

        # === 构建雷达副屏 ===
        self.radar_win = tk.Toplevel(self.root)
        self.radar_win.title("超声波雷达监测视图")
        self.radar_win.geometry(f"{w2}x{h2}+{int(sw/2 + w1/2 - 40)}+{int(sh/2 - h2/2)}")
        self.radar_win.configure(bg="black")
        self.radar_win.resizable(False, False)
        self.radar_win.protocol("WM_DELETE_WINDOW", lambda: None)
        self.setup_radar_ui(w2, h2)
        
        # 启动
        self.animate_visuals() 
        self.t = threading.Thread(target=self.loop, daemon=True)
        self.t.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.log_sys("系统内核加载完成...")
        self.log_sys("超声波已就绪")
        self.log_sys("等待数据链路连接...")

    def init_bg_visuals(self, w, h):
        # 1. 静态星尘
        for _ in range(80):
            x = random.randint(0, w)
            y = random.randint(0, h)
            sz = random.randint(1, 2)
            col = random.choice(["#112233", "#0d1a26", "#002233"])
            star = self.cv_bg.create_oval(x, y, x+sz, y+sz, fill=col, outline="")
            self.bg_stars.append(star)

        # 2. 动态数据流
        for _ in range(15):
            x = random.randint(0, w)
            y = random.randint(-200, h)
            length = random.randint(50, 150)
            spd = random.uniform(2, 6)
            line = self.cv_bg.create_line(x, y, x, y+length, fill="#001a1a", width=1)
            self.bg_rain.append([line, spd, length])

    # =================================================================
    # 主界面布局
    # =================================================================
    def setup_main_ui(self):
        # 顶部栏
        top = tk.Frame(self.root, bg=C_BG_PANEL, height=50)
        top.place(x=20, y=10, width=1060, height=50)
        # 标题完全中文化
        tk.Label(top, text="STM32 智能车载监控终端", font=("Microsoft YaHei", 18, "bold"), fg=C_CYAN, bg=C_BG_PANEL).pack(side=tk.LEFT, padx=20)
        self.lbl_status = tk.Label(top, text="链路状态：断开", font=F_H2, fg=C_TEXT_G, bg=C_BG_PANEL)
        self.lbl_status.pack(side=tk.RIGHT, padx=20)
        # 装饰线
        tk.Canvas(self.root, width=1060, height=2, bg=C_CYAN_DIM, highlightthickness=0).place(x=20, y=60)

        # --- 左列 ---
        
        # [修改] 增加高级串口配置的 ActiveTechFrame，内部布局调整为更紧凑
        self.f_comm = ActiveTechFrame(self.root, "通信参数配置", 320, 220); self.f_comm.place(x=20, y=80)
        self.anim_frames.append(self.f_comm)
        
        # 【修改点 A】: 将通信参数配置面板的标签改为 C_TEXT_HL (青色高亮)，确保清晰可见
        
        # 1. 端口 (Port)
        self.mk_label(self.f_comm.inner, "端口 (PORT)", 10, 5, col=C_TEXT_HL)
        self.cb_port = ttk.Combobox(self.f_comm.inner, values=["正在扫描..."], state="readonly")
        self.cb_port.place(x=10, y=25, width=290)
        
        # 2. 第一行：波特率 & 数据位
        self.mk_label(self.f_comm.inner, "速率 (BAUD)", 10, 55, col=C_TEXT_HL)
        self.cb_baud = ttk.Combobox(self.f_comm.inner, values=["9600", "115200"], state="readonly")
        self.cb_baud.current(0)
        self.cb_baud.place(x=10, y=75, width=140)

        self.mk_label(self.f_comm.inner, "数据位 (DATA)", 160, 55, col=C_TEXT_HL)
        self.cb_data = ttk.Combobox(self.f_comm.inner, values=["8", "7", "6", "5"], state="readonly")
        self.cb_data.current(0) # 默认 8
        self.cb_data.place(x=160, y=75, width=140)

        # 3. 第二行：校验位 & 停止位
        self.mk_label(self.f_comm.inner, "校验位 (PARITY)", 10, 105, col=C_TEXT_HL)
        self.cb_parity = ttk.Combobox(self.f_comm.inner, values=["无 (None)", "奇 (Odd)", "偶 (Even)", "Mark", "Space"], state="readonly")
        self.cb_parity.current(0) # 默认 None
        self.cb_parity.place(x=10, y=125, width=140)

        self.mk_label(self.f_comm.inner, "停止位 (STOP)", 160, 105, col=C_TEXT_HL)
        self.cb_stop = ttk.Combobox(self.f_comm.inner, values=["1", "1.5", "2"], state="readonly")
        self.cb_stop.current(0) # 默认 1
        self.cb_stop.place(x=160, y=125, width=140)

        # 4. 按钮区
        CyberButton(self.f_comm.inner, "刷新列表", self.refresh, w=100).place(x=10, y=165)
        self.btn_cn = CyberButton(self.f_comm.inner, "连接设备", self.toggle, w=160, col=C_CYAN)
        self.btn_cn.place(x=130, y=165)
        # --- 左列结束 ---

        self.f_conf = ActiveTechFrame(self.root, "车载参数设定", 320, 180); self.f_conf.place(x=20, y=320)
        self.anim_frames.append(self.f_conf)
        self.mk_label(self.f_conf.inner, "巡航速度 (%)", 10, 10)
        self.sc_spd = tk.Scale(self.f_conf.inner, from_=0, to=100, orient=tk.HORIZONTAL, bg=C_BG_PANEL, fg=C_CYAN, 
                                highlightthickness=0, activebackground=C_CYAN, troughcolor="#000", length=280)
        self.sc_spd.set(60); self.sc_spd.place(x=10, y=35)
        self.mk_label(self.f_conf.inner, "站点停留时长 (秒)", 10, 75)
        self.ent_tim = tk.Entry(self.f_conf.inner, bg="#000", fg="white", insertbackground="white", relief="flat", font=("Consolas", 12))
        self.ent_tim.insert(0, "10"); self.ent_tim.place(x=10, y=100, width=60)
        CyberButton(self.f_conf.inner, "同步参数至车辆", self.send_settings, w=180, col=C_GREEN).place(x=110, y=95)

        self.f_log = ActiveTechFrame(self.root, "黑匣子日志", 320, 220); self.f_log.place(x=20, y=520)
        self.anim_frames.append(self.f_log)
        self.txt_log = scrolledtext.ScrolledText(self.f_log.inner, bg="#000", fg=C_GREEN, font=("Consolas", 9), relief="flat")
        self.txt_log.place(x=0, y=0, width=310, height=180)

        # --- 中列 ---
        self.f_dash = ActiveTechFrame(self.root, "实时遥测数据", 340, 660); self.f_dash.place(x=360, y=80)
        self.anim_frames.append(self.f_dash)
        self.gauge_spd = RingGauge(self.f_dash.inner, 140, 140, "设定功率", "%", 100, C_CYAN)
        self.gauge_spd.place(x=15, y=10); self.anim_frames.append(self.gauge_spd)
        
        # 距离表量程调整为 250cm
        self.gauge_dist = RingGauge(self.f_dash.inner, 140, 140, "前方障距", "cm", 250, C_ORANGE)
        self.gauge_dist.place(x=170, y=10); self.anim_frames.append(self.gauge_dist)
        
        self.mk_card(self.f_dash.inner, 15, 160, "当前模式", "待机", "val_st")
        # 【修改点 B】: 显示运动状态和速度 (快/慢/静止)
        self.mk_card(self.f_dash.inner, 170, 160, "运动姿态", "--", "val_dr")
        self.mk_card(self.f_dash.inner, 15, 250, "已停站点", "0", "val_ct")
        
        self.f_dash.inner.update()
        cv = tk.Canvas(self.f_dash.inner, bg="#080c10", height=200, width=300, highlightthickness=1, highlightbackground="#161b22")
        cv.place(x=15, y=360)
        cv.create_text(10, 10, text="距离传感器时域波形(cm)", fill=C_TEXT_G, anchor="nw", font=F_TXT)
        self.cv_wave = cv
        # 波形图网格
        for i in range(0, 300, 20): cv.create_line(i, 0, i, 200, fill="#0a0e14")
        for i in range(0, 200, 20): cv.create_line(0, i, 300, i, fill="#0a0e14")
        
            # ===== 纵坐标：距离刻度 (cm) =====
        max_graph_dist = 250
        h_graph = 200
        num_ticks = 5

        for i in range(num_ticks + 1):
            # 距离值
            dist = int(max_graph_dist * (1 - i / num_ticks))
            # y 坐标
            y = int(h_graph * i / num_ticks)

            # 刻度短线
            cv.create_line(0, y, 6, y, fill=C_TEXT_G)

            # 距离文字
            cv.create_text(8, y,
                        text=f"{dist}",
                        fill=C_TEXT_G,
                        anchor="w",
                        font=("Consolas", 8))

        self.scan_bar = self.cv_wave.create_line(0, 0, 0, 200, fill=C_CYAN_DIM, width=2)
        self.wave_line = self.cv_wave.create_line(0,0,0,0, fill=C_CYAN, width=2)

        # --- 右列 ---
        self.f_ctrl = ActiveTechFrame(self.root, "手动遥控", 340, 660); self.f_ctrl.place(x=720, y=80)
        self.anim_frames.append(self.f_ctrl)
        self.btn_mode = CyberButton(self.f_ctrl.inner, "切换模式：自动巡航", self.sw_mode, w=260, h=50, col=C_GREEN)
        self.btn_mode.place(x=30, y=30)
        
        # 摇杆绘制
        self.cv_joy = tk.Canvas(self.f_ctrl.inner, width=260, height=260, bg=C_BG_PANEL, highlightthickness=0)
        self.cv_joy.place(x=30, y=120)
        cx, cy = 130, 130
        self.cv_joy.create_oval(10, 10, 250, 250, outline="#161b22", width=1)
        self.cv_joy.create_oval(30, 30, 230, 230, outline="#161b22", width=1, dash=(2,4))
        self.cv_joy.create_line(130, 10, 130, 250, fill="#111")
        self.cv_joy.create_line(10, 130, 250, 130, fill="#111")
        for i in range(0, 360, 30):
            rad = math.radians(i)
            x1 = cx + 115 * math.cos(rad); y1 = cy + 115 * math.sin(rad)
            x2 = cx + 125 * math.cos(rad); y2 = cy + 125 * math.sin(rad)
            self.cv_joy.create_line(x1, y1, x2, y2, fill=C_CYAN_DIM, width=2)

        self.cv_joy.create_text(130, 20, text="前进", fill=C_TEXT_G, font=("Microsoft YaHei", 8))
        self.cv_joy.create_text(130, 240, text="后退", fill=C_TEXT_G, font=("Microsoft YaHei", 8))
        self.cv_joy.create_text(20, 130, text="左转", fill=C_TEXT_G, font=("Microsoft YaHei", 8))
        self.cv_joy.create_text(240, 130, text="右转", fill=C_TEXT_G, font=("Microsoft YaHei", 8))
        
        self.joy_arrow_n = self.cv_joy.create_polygon(cx, 35, cx-5, 45, cx+5, 45, fill="#333")
        self.joy_arrow_s = self.cv_joy.create_polygon(cx, 225, cx-5, 215, cx+5, 215, fill="#333")
        self.joy_arrow_w = self.cv_joy.create_polygon(35, cy, 45, cy-5, 45, cy+5, fill="#333")
        self.joy_arrow_e = self.cv_joy.create_polygon(225, cy, 215, cy-5, 215, cy+5, fill="#333")

        self.joy_shaft = self.cv_joy.create_line(cx, cy, cx, cy, fill=C_CYAN, width=4)
        self.kn_shadow = self.cv_joy.create_oval(100, 100, 160, 160, outline=C_CYAN, width=1, state="hidden")
        self.knob_outer = self.cv_joy.create_oval(95, 95, 165, 165, fill="", outline=C_CYAN, width=2)
        self.knob = self.cv_joy.create_oval(105, 105, 155, 155, fill="#1c2533", outline=C_TEXT_W, width=2)
        self.knob_in = self.cv_joy.create_line(120, 130, 140, 130, fill="white")
        self.knob_in2 = self.cv_joy.create_line(130, 120, 130, 140, fill="white")
        self.kn_dot = self.cv_joy.create_oval(125, 125, 135, 135, fill=C_CYAN, outline="")
        self.kn_txt = self.cv_joy.create_text(130, 145, text="就绪", fill=C_TEXT_G, font=("Microsoft YaHei", 7))
        self.joy_txt_xy = self.cv_joy.create_text(130, 280, text="横向: 000  纵向: 000", fill=C_CYAN, font=("Consolas", 10))
        
        self.cv_joy.bind("<B1-Motion>", self.joy_move)
        self.cv_joy.bind("<ButtonRelease-1>", self.joy_reset)
        self.cv_joy.bind("<Button-1>", self.joy_move)
        tk.Label(self.f_ctrl.inner, text="提示：仅在手动模式下可用", fg=C_TEXT_G, bg=C_BG_PANEL, font=F_TXT).place(x=80, y=400)

    # --- 雷达副屏 ---
    def setup_radar_ui(self, w, h):
        tk.Frame(self.radar_win, bg="#111", height=40).pack(fill=tk.X)
        tk.Label(self.radar_win, text="超声波避障监测系统", font=("Microsoft YaHei", 16, "bold"), fg=C_GREEN, bg="#111").place(x=20, y=5)
        self.rcv = tk.Canvas(self.radar_win, width=w, height=h-40, bg="black", highlightthickness=0)
        self.rcv.pack()
        cx, cy = 325, 350
        
        # 定义圆弧 (由内向外：arc1=近, arc2=中, arc3=远)
        # 修正圆弧大小以符合视觉逻辑
        self.arc_3 = self.rcv.create_arc(cx-300, cy-300, cx+300, cy+300, start=0, extent=180, style="arc", outline="#0f1f0f", width=5) # 远
        self.arc_2 = self.rcv.create_arc(cx-200, cy-200, cx+200, cy+200, start=0, extent=180, style="arc", outline="#0f1f0f", width=5) # 中
        self.arc_1 = self.rcv.create_arc(cx-100, cy-100, cx+100, cy+100, start=0, extent=180, style="arc", outline="#0f1f0f", width=5) # 近

        # 网格线
        self.rcv.create_line(cx, cy, cx-300, cy, fill="#0f1f0f", dash=(4,4))
        self.rcv.create_line(cx, cy, cx+300, cy, fill="#0f1f0f", dash=(4,4))
        self.rcv.create_line(cx, cy, cx, cy-300, fill="#0f1f0f", dash=(4,4))
        
        self.radar_sectors = []
        for _ in range(5): 
            s = self.rcv.create_arc(cx-300, cy-300, cx+300, cy+300, start=90, extent=15, fill="", outline="", style="pieslice")
            self.radar_sectors.append(s)
            
        self.scan_line = self.rcv.create_line(cx, cy, cx, cy-300, fill=C_CYAN, width=3)
        self.lbl_r_dist = self.rcv.create_text(60, 350, text="---", fill="#333", anchor="w", font=("Impact", 50))
        self.rcv.create_text(60, 400, text="实时距离 (CM)", fill="#555", anchor="w", font=F_TXT)
        self.lbl_r_txt = self.rcv.create_text(w-50, 380, text="无信号", fill="#333", anchor="e", font=("Microsoft YaHei", 18, "bold"))
        self.rcv.create_text(w-50, 410, text="环境感知状态", fill="#555", anchor="e", font=F_TXT)
        
        self.radar_ping = self.rcv.create_oval(cx, cy, cx, cy, outline=C_GREEN, width=2, state="hidden")
        self.radar_pulse_r = 0

    # 【修改】mk_label 增加可选颜色参数，默认为 C_TEXT_G
    def mk_label(self, p, t, x, y, col=C_TEXT_G): 
        tk.Label(p, text=t, fg=col, bg=C_BG_PANEL, font=F_TXT).place(x=x, y=y)
        
    def mk_card(self, p, x, y, title, val, tag_name):
        f = tk.Frame(p, bg="#111", padx=10, pady=5)
        f.place(x=x, y=y, width=140, height=80)
        tk.Label(f, text=title, fg=C_TEXT_G, bg="#111", font=("Microsoft YaHei", 9)).pack(anchor="w")
        # 调小一点字号以容纳更多中文
        l = tk.Label(f, text=val, fg="white", bg="#111", font=("Impact", 18))
        l.pack(anchor="e")
        setattr(self, tag_name, l)

    # --- 核心动画循环 ---
    def animate_visuals(self):
        if not self.run: return
        
        # 1. 更新数据流雨 (Cyber Rain)
        h_max = 750
        for drop in self.bg_rain:
            self.cv_bg.move(drop[0], 0, drop[1])
            pos = self.cv_bg.coords(drop[0])
            if pos[3] > h_max:
                new_x = random.randint(0, 1100)
                new_len = random.randint(50, 150)
                new_spd = random.uniform(2, 6)
                self.cv_bg.coords(drop[0], new_x, -new_len, new_x, 0)
                drop[1] = new_spd

        # 2. 更新背景星尘
        if random.random() < 0.1:
            star_id = random.choice(self.bg_stars)
            cur_col = self.cv_bg.itemcget(star_id, "fill")
            new_col = "#004455" if cur_col == "#0d1a26" else "#0d1a26"
            self.cv_bg.itemconfig(star_id, fill=new_col)
        
        # 3. 组件流光
        for f in self.anim_frames:
            if hasattr(f, 'update_anim'): f.update_anim()
            if hasattr(f, 'animate_spin'): f.animate_spin()

        # 4. 雷达扫描动画
        step = 3
        self.radar_angle += step * self.radar_dir
        if self.radar_angle >= 180: self.radar_angle = 180; self.radar_dir = -1
        elif self.radar_angle <= 0: self.radar_angle = 0; self.radar_dir = 1

        if self.radar_win.winfo_exists():
            cx, cy = 325, 350
            angle = 180 - self.radar_angle
            cols = [C_CYAN, "#00a0a0", "#007070", "#004040", "#002020"]
            for i, sec in enumerate(self.radar_sectors):
                lag = i * 2 * self.radar_dir 
                start_ang = angle + lag
                self.rcv.itemconfigure(sec, start=start_ang, extent=3, fill=cols[i])
                
            rad = math.radians(angle)
            self.rcv.coords(self.scan_line, cx, cy, cx+300*math.cos(rad), cy-300*math.sin(rad))
            
            # 雷达波扩散特效
            self.radar_pulse_r += 8
            if self.radar_pulse_r > 300: self.radar_pulse_r = 0
            self.rcv.coords(self.radar_ping, cx-self.radar_pulse_r, cy-self.radar_pulse_r, 
                            cx+self.radar_pulse_r, cy+self.radar_pulse_r)
            
            # 只有当距离有效且较近时显示扩散波
            if self.current_distance < 60 and self.current_distance > 0:
                 self.rcv.itemconfig(self.radar_ping, state="normal")
            else:
                 self.rcv.itemconfig(self.radar_ping, state="hidden")

        # 5. 波形图光栅
        self.cv_wave.move(self.scan_bar, 5, 0)
        if self.cv_wave.coords(self.scan_bar)[0] > 300:
            self.cv_wave.move(self.scan_bar, -300, 0)
        
        # 6. 波形多边形绘制 (修复爆表问题)
        w_graph, h_graph = 300, 200
        max_graph_dist = 250 # 对应 HC-SR04 量程
        
        pts = [0, h_graph]
        step_x = w_graph / len(self.dist_history)
        
        for i, d in enumerate(self.dist_history):
            # [关键修复] 限制数据在量程内，防止绘制到负坐标区
            clamped_d = min(max(d, 0), max_graph_dist) 
            
            # 计算Y坐标 (d=0 -> y=200, d=250 -> y=0)
            y = h_graph - (clamped_d / max_graph_dist * h_graph)
            pts.extend([i*step_x, y])
            
        pts.extend([w_graph, h_graph])
        if len(pts) > 4:
            self.cv_wave.coords(self.wave_line, *pts[2:-2])
            
        if self.conn:
            pulse = int(155 + 100 * math.sin(time.time() * 3))
            hex_c = f"#00{pulse:02x}00"
            self.lbl_status.config(fg=hex_c)

        self.root.after(30, self.animate_visuals)

    # --- 逻辑控制 ---
    def refresh(self):
        try: self.cb_port['values'] = sorted([p.device for p in serial.tools.list_ports.comports()])
        except: pass

    def toggle(self):
        if not self.conn:
            try:
                p = self.cb_port.get()
                if not p: return
                b = int(self.cb_baud.get())
                
                # --- [新增] 读取高级串口参数 ---
                # 1. 停止位
                s_map = {"1": serial.STOPBITS_ONE, "1.5": serial.STOPBITS_ONE_POINT_FIVE, "2": serial.STOPBITS_TWO}
                s_bit = s_map.get(self.cb_stop.get(), serial.STOPBITS_ONE)
                
                # 2. 数据位
                d_bit = int(self.cb_data.get())
                
                # 3. 校验位
                p_str = self.cb_parity.get()
                if "Odd" in p_str: p_bit = serial.PARITY_ODD
                elif "Even" in p_str: p_bit = serial.PARITY_EVEN
                elif "Mark" in p_str: p_bit = serial.PARITY_MARK
                elif "Space" in p_str: p_bit = serial.PARITY_SPACE
                else: p_bit = serial.PARITY_NONE
                
                # 初始化串口
                self.ser = serial.Serial(
                    port=p, 
                    baudrate=b, 
                    bytesize=d_bit, 
                    parity=p_bit, 
                    stopbits=s_bit, 
                    timeout=0.05
                )
                
                self.conn = True
                self.btn_cn.set_config("断开连接", C_RED)
                self.lbl_status.config(text="链路状态：已连接", fg=C_GREEN)
                self.log_sys(f"链路建立: {b}bps, {d_bit}数据位, {p_str.split(' ')[0]}校验")
            except Exception as e: messagebox.showerror("错误", str(e))
        else:
            self.conn = False; self.ser.close()
            self.btn_cn.set_config("连接设备", C_CYAN)
            self.lbl_status.config(text="链路状态：断开", fg=C_TEXT_G)
            self.log_sys("串口通信链路已断开")

    def sw_mode(self):
        self.mode = 1 - self.mode
        if self.mode:
            self.btn_mode.set_config("当前模式：手动控制 (点击切换)", C_ORANGE)
            self.log_sys("指令：切换至手动遥控模式")
            self.cv_joy.itemconfig(self.kn_shadow, state="normal")
        else:
            self.btn_mode.set_config("当前模式：自动巡航 (点击切换)", C_GREEN)
            self.log_sys("指令：切换至自动巡航模式")
            self.cv_joy.itemconfig(self.kn_shadow, state="hidden")
        self.joy_reset(None)

    def send_settings(self):
        if not self.conn: return
        try:
            s = int(self.sc_spd.get()); t = int(self.ent_tim.get())
            # 协议：0xB5, Spd, Tim, 0, Sum, 0x5B
            chk = (s + t + 0) & 0xFF
            self.ser.write(struct.pack('BBBBBB', 0xB5, s, t, 0, chk, 0x5B))
            self.log_sys(f"参数下发: 巡航速度{s}% 驻留时间{t}s")
        except: pass

    def joy_move(self, e):
        if not self.mode: return
        cx, cy = 130, 130
        dx, dy = e.x-cx, e.y-cy
        d = math.sqrt(dx*dx + dy*dy)
        if d > 90: k=90/d; dx*=k; dy*=k
        
        self.cv_joy.coords(self.knob, 105+dx, 105+dy, 155+dx, 155+dy)
        self.cv_joy.coords(self.knob_outer, 95+dx, 95+dy, 165+dx, 165+dy)
        self.cv_joy.coords(self.knob_in, 120+dx, 130+dy, 140+dx, 130+dy)
        self.cv_joy.coords(self.knob_in2, 130+dx, 120+dy, 130+dx, 140+dy)
        self.cv_joy.coords(self.kn_dot, 125+dx, 125+dy, 135+dx, 135+dy)
        self.cv_joy.coords(self.kn_shadow, 100+dx, 100+dy, 160+dx, 160+dy)
        self.cv_joy.coords(self.joy_shaft, cx, cy, cx+dx, cy+dy)
        
        self.cv_joy.coords(self.kn_txt, 130+dx, 145+dy)
        self.cv_joy.itemconfig(self.kn_txt, text="输出中", fill=C_ORANGE)

        self.cv_joy.itemconfig(self.joy_arrow_n, fill=C_CYAN if dy < -20 else "#333")
        self.cv_joy.itemconfig(self.joy_arrow_s, fill=C_CYAN if dy > 20 else "#333")
        self.cv_joy.itemconfig(self.joy_arrow_w, fill=C_CYAN if dx < -20 else "#333")
        self.cv_joy.itemconfig(self.joy_arrow_e, fill=C_CYAN if dx > 20 else "#333")

        val_x = int(dx * 1.4); val_y = int(-dy * 1.4)
        self.cv_joy.itemconfig(self.joy_txt_xy, text=f"横向: {val_x:+04d}  纵向: {val_y:+04d}")
        self.joy_x, self.joy_y = val_x, val_y

    def joy_reset(self, e):
        cx, cy = 130, 130
        self.cv_joy.coords(self.knob, 105, 105, 155, 155)
        self.cv_joy.coords(self.knob_outer, 95, 95, 165, 165)
        self.cv_joy.coords(self.knob_in, 120, 130, 140, 130)
        self.cv_joy.coords(self.knob_in2, 130, 120, 130, 140)
        self.cv_joy.coords(self.kn_dot, 125, 125, 135, 135)
        self.cv_joy.coords(self.kn_shadow, 100, 100, 160, 160)
        self.cv_joy.coords(self.joy_shaft, cx, cy, cx, cy)
        self.cv_joy.coords(self.kn_txt, 130, 145)
        self.cv_joy.itemconfig(self.kn_txt, text="就绪", fill=C_TEXT_G)
        self.cv_joy.itemconfig(self.joy_txt_xy, text="横向: +000  纵向: +000")
        for a in [self.joy_arrow_n, self.joy_arrow_s, self.joy_arrow_w, self.joy_arrow_e]:
            self.cv_joy.itemconfig(a, fill="#333")
        self.joy_x, self.joy_y = 0, 0

    # --- [手柄] 轮询 Xbox 左摇杆，映射到 joy_x/joy_y，并驱动 UI 虚拟摇杆 ---
    def poll_gamepad(self):
        # 仅手动模式读取
        if not getattr(self, "gamepad", None):
            return
        if not self.mode:
            return
        try:
            # 刷新事件队列，避免数值不更新
            pygame.event.pump()

            # Xbox 左摇杆：axis 0 (X), axis 1 (Y)
            lx = float(self.gamepad.get_axis(0))
            ly = float(self.gamepad.get_axis(1))

            # 死区（防抖）
            dead = 0.10
            if abs(lx) < dead: lx = 0.0
            if abs(ly) < dead: ly = 0.0

            # 映射到你现有协议的范围（与你鼠标摇杆一致：大约 ±126）
            val_x = int(lx * 127)
            val_y = int(-ly * 127)

            # 限幅到 int8
            val_x = max(-127, min(127, val_x))
            val_y = max(-127, min(127, val_y))

            self.joy_x, self.joy_y = val_x, val_y

            # Tk UI 必须在主线程更新：用 after 投递
            try:
                self.root.after(0, self.update_joy_ui_from_value, val_x, val_y)
            except Exception:
                pass
        except Exception:
            # 读手柄失败时静默（不影响主系统）
            pass

    # --- [手柄] 用数值直接更新 UI 虚拟摇杆（与 joy_move 同一套显示逻辑） ---
    def update_joy_ui_from_value(self, val_x, val_y):
        # 这里复用你原来的映射关系：dx*1.4 -> val_x，所以 dx = val_x/1.4
        cx, cy = 130, 130
        dx = val_x / 1.4
        dy = -val_y / 1.4

        d = math.sqrt(dx*dx + dy*dy)
        if d > 90:
            k = 90 / d
            dx *= k
            dy *= k

        self.cv_joy.coords(self.knob, 105+dx, 105+dy, 155+dx, 155+dy)
        self.cv_joy.coords(self.knob_outer, 95+dx, 95+dy, 165+dx, 165+dy)
        self.cv_joy.coords(self.knob_in, 120+dx, 130+dy, 140+dx, 130+dy)
        self.cv_joy.coords(self.knob_in2, 130+dx, 120+dy, 130+dx, 140+dy)
        self.cv_joy.coords(self.kn_dot, 125+dx, 125+dy, 135+dx, 135+dy)
        self.cv_joy.coords(self.kn_shadow, 100+dx, 100+dy, 160+dx, 160+dy)
        self.cv_joy.coords(self.joy_shaft, cx, cy, cx+dx, cy+dy)

        # 文本与指示
        self.cv_joy.coords(self.kn_txt, 130+dx, 145+dy)
        self.cv_joy.itemconfig(self.kn_txt, text="输出中", fill=C_ORANGE)

        self.cv_joy.itemconfig(self.joy_arrow_n, fill=C_CYAN if dy < -20 else "#333")
        self.cv_joy.itemconfig(self.joy_arrow_s, fill=C_CYAN if dy > 20 else "#333")
        self.cv_joy.itemconfig(self.joy_arrow_w, fill=C_CYAN if dx < -20 else "#333")
        self.cv_joy.itemconfig(self.joy_arrow_e, fill=C_CYAN if dx > 20 else "#333")

        self.cv_joy.itemconfig(self.joy_txt_xy, text=f"横向: {val_x:+04d}  纵向: {val_y:+04d}")

    def log_sys(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{ts}] {msg}\n")
        self.txt_log.see(tk.END)
        
        # 【核心修改点 2】如果是站点相关的日志，同步写入到 station_log.txt 文件
        if "站点" in msg:
            try:
                # [修复] 获取当前脚本的绝对路径，确保文件生成在脚本旁边
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(current_dir, "station_log.txt")
                
                with open(file_path, "a", encoding="utf-8") as f:
                    f.write(f"[{ts}] {msg}\n")
                    f.flush()            # 强制刷新内存缓冲
                    os.fsync(f.fileno()) # 强制让操作系统写盘
                
                # print(f"[成功] 已写入文档: {file_path}") # 调试打印(可选)
            except Exception as e:
                # print(f"[失败] 文件写入错误: {e}")
                pass

    def on_close(self):
        self.run = False
        if self.ser: self.ser.close()
        self.root.destroy()
        sys.exit()

    def loop(self):
        buf = b''
        while self.run:
            self.poll_gamepad()
            if self.conn and self.ser:
                try:
                    # 发送控制指令 (每100ms或操作时)
                    if self.mode or time.time()%0.1 < 0.02:
                        chk = (self.joy_x & 0xFF) + (self.joy_y & 0xFF) + (self.mode & 0xFF)
                        self.ser.write(struct.pack('BbbBBB', TX_HEADER, self.joy_x, self.joy_y, self.mode, chk & 0xFF, TX_TAIL))
                    
                    if self.ser.in_waiting: buf += self.ser.read(self.ser.in_waiting)
                    
                    # 协议解析: 55 [State] [Dir] [Spd] [Sta] [Data] [Sum] AA
                    while len(buf) >= 8:
                        if buf[0]!=0x55 or buf[7]!=0xAA: 
                            buf=buf[1:]
                            continue
                            
                        st, dr, sp, sta, dat, chk = struct.unpack('BBBBBB', buf[1:7])
                        
                        # 校验和检查
                        if (st+dr+sp+sta+dat)&0xFF == chk:
                            self.root.after(0, self.update_ui, st, dr, sp, sta, dat)
                            
                            # 【核心修改点 3】记录站点日志 (状态3且站点号变更时触发)
                            # st=3 对应 remote.c 中的 STATE_STATION
                            # sta 是当前站点计数
                            if st == 3 and sta != self.last_log_sta:
                                # 通过 after 调用 log_sys 确保线程安全
                                self.root.after(0, self.log_sys, f"抵达站点: 第{sta}站 | 执行停靠程序")
                                self.last_log_sta = sta
                                
                            buf = buf[8:]
                        else: 
                            buf=buf[1:]
                except: pass
            time.sleep(0.05)

    # --- UI 数据刷新 (核心修复部分) ---
    def update_ui(self, st, dr, sp, sta, dat):
        # 1. 速度表显示
        pwr = self.sc_spd.get() if st in [1,2] else 0
        self.gauge_spd.set_value(pwr)
        
        # 2. 距离/倒计时处理 (匹配 remote.c 逻辑)
        real_dist = 0
        is_countdown = False
        
        if st == 3: # 状态3：站点停靠
            # 此时 dat 是倒计时秒数
            self.val_st.config(text=f"停靠中 {dat}s", fg=C_ORANGE)
            is_countdown = True
            # 停靠时，不更新波形图的历史距离，避免出现方波干扰
            if len(self.dist_history) > 0:
                real_dist = self.dist_history[-1] 
        else:
            # 其他状态：dat 是距离 (cm)
            real_dist = float(dat)
            self.current_distance = real_dist
            self.dist_history.append(real_dist)
            if len(self.dist_history) > 100: self.dist_history.pop(0)
            
            # 更新距离表
            self.gauge_dist.set_value(real_dist)

        # 3. 状态文字颜色
        st_txt_map = {0:"系统待机", 1:"正在巡航", 2:"紧急避障", 3:"站点停靠"}
        st_txt = st_txt_map.get(st, "未知状态")
        
        col_st = C_TEXT_W
        if st == 1: col_st = C_GREEN
        elif st == 2: 
            st_txt = "主动刹车(AEB)" # 对应 remote.c 的 logic
            col_st = C_RED
        elif st == 3: col_st = C_ORANGE
        
        if not is_countdown: self.val_st.config(text=st_txt, fg=col_st)

        dr_map = {0:"停止", 1:"全速前进", 2:"正在倒车", 3:"左旋机动", 4:"右旋机动"}
        dr_text = dr_map.get(dr, "--")
        
        # 【修改点 C】：显示速度状态 (快/慢/静止)
        # 根据协议，sp=1 为高速，sp=0 为低速
        sp_text = ""
        if dr == 0 or st in [0, 3]: # 停止或停靠状态
            sp_text = " (静止)"
        else:
            sp_text = " (快)" if sp == 1 else " (慢)"
            
        self.val_dr.config(text=f"{dr_text}{sp_text}") # 拼接字符串，例如 "全速前进 (快)"
        self.val_ct.config(text=str(sta))

        # 4. 雷达副屏逻辑 (修复颜色和圆弧)
        if self.radar_win.winfo_exists():
            c1, c2, c3 = "#0f1f0f", "#0f1f0f", "#0f1f0f" # 默认暗色
            txt = "航路安全"; col_txt = C_GREEN
            
            # 仅在非停靠模式下更新雷达警告
            if not is_countdown:
                # 对应 remote.c 中的 g_Distance
                if real_dist > 0:
                    # 距离 < 60: 外圈绿灯亮
                    if real_dist < 60: 
                        c3 = "#1b5e20" # 暗绿
                        txt = "注意观察"; col_txt = C_GREEN
                        
                    # 距离 < 40: 中圈橙灯亮
                    if real_dist < 40: 
                        c2 = "#f57f17" # 暗橙
                        txt = "接近障碍"; col_txt = C_ORANGE
                        
                    # 距离 < 20: 内圈红灯亮
                    if real_dist < 20: 
                        c1 = "#b71c1c" # 暗红
                        txt = "碰撞警告"; col_txt = C_RED
                
                # 如果处于 AEB 触发状态 (st=2)
                if st == 2:
                    txt = "主动刹车介入"; col_txt = C_RED
                    if int(time.time()*6)%2: # 快速闪烁
                        c1=c2=c3 = C_RED
            else:
                txt = "站点作业中"; col_txt = C_ORANGE

            self.rcv.itemconfig(self.lbl_r_dist, text=str(int(real_dist)), fill=col_txt)
            self.rcv.itemconfig(self.lbl_r_txt, text=txt, fill=col_txt)
            
            # 更新圆弧颜色 (内、中、外)
            self.rcv.itemconfig(self.arc_1, outline=c1)
            self.rcv.itemconfig(self.arc_2, outline=c2)
            self.rcv.itemconfig(self.arc_3, outline=c3)

if __name__ == "__main__":
    root = tk.Tk()
    app = FinalSystem(root)
    root.mainloop()