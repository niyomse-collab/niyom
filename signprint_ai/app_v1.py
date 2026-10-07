from __future__ import annotations

import base64
import io
import math
import os
import queue
import shutil
import tempfile
import threading
import time
from pathlib import Path
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from app.engine.engine_manager import EngineManager

APP_NAME = "นิยมศิลป์ดีไซน์ v1.0"
APP_SUBTITLE = "AI Print Image Enhancer for Signage"
IMAGE_TYPES = [
    ("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"),
    ("All files", "*.*"),
]

UNITS_TO_INCH = {
    "px": None,
    "mm": 1 / 25.4,
    "cm": 1 / 2.54,
    "m": 100 / 2.54,
    "inch": 1,
    "feet": 12,
}

BG = "#081019"
PANEL = "#0E1822"
FIELD = "#162431"
LINE = "#274052"
RED = "#ED1C24"
WHITE = "#F4F7FA"
MUTED = "#9FB0BE"
GREEN = "#55E56A"
BLUE = "#45A7FF"
WARN = "#FFB33B"


def resource_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


class App(tk.Tk):
    """Niyomsil Design UI wrapper around the uploaded ARM V2.2.8 processing core.

    The processing path intentionally uses only:
      - ARM DeviceManager
      - ARM EngineManager
      - ARM RealESRGANEngine
      - the same 2x / 4x / 8x flow and final-size logic used by the uploaded code

    No extra denoise, contrast, sharpen, vector, Real-CUGAN, NCNN or other
    enhancement engine is applied in this build.
    """

    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1680x960")
        self.minsize(1360, 800)
        self.configure(bg=BG)

        self.engine_manager = EngineManager()
        self.files: list[Path] = []
        self.current_index: int | None = None
        self.original_ratio = 1.0
        self._syncing_size = False
        self._cancel = threading.Event()
        self._events: queue.Queue = queue.Queue()
        self._last_result: Path | None = None
        self._brand_logo_photo = None
        self._active_engine = None

        # Preview state copied from the uploaded ARM GUI logic.
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._preview_pils = {"before": None, "after": None}
        self._preview_photos = {}
        self._pan_origin = None

        self._build_style()
        self._build_ui()
        self._enable_drag_drop()
        self.after(80, self._drain_events)
        self._set_status("พร้อมใช้งาน — เลือกภาพเพื่อเริ่ม")

    # ------------------------------------------------------------------
    # UI STYLE / BRAND
    # ------------------------------------------------------------------
    def _pick_ui_font(self) -> str:
        try:
            available = {name.lower(): name for name in tkfont.families(self)}
        except tk.TclError:
            available = {}
        for wanted in ("Leelawadee UI", "Tahoma", "Segoe UI", "Arial"):
            if wanted.lower() in available:
                return available[wanted.lower()]
        return "TkDefaultFont"

    def _load_brand_logo(self, max_size=(112, 90)):
        try:
            p = resource_root() / "assets" / "logo.b64"
            raw = base64.b64decode(p.read_text(encoding="utf-8").strip())
            im = Image.open(io.BytesIO(raw)).convert("RGBA")
            px = im.load()
            for y in range(im.height):
                for x in range(im.width):
                    r, g, b, a = px[x, y]
                    spread = max(r, g, b) - min(r, g, b)
                    if r > 246 and g > 246 and b > 246 and spread < 6:
                        px[x, y] = (255, 255, 255, 0)
            bbox = im.getchannel("A").getbbox()
            if bbox:
                im = im.crop(bbox)
            im.thumbnail(max_size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        family = self._pick_ui_font()
        self.ui_font_family = family
        body = (family, 10)
        small = (family, 9)
        bold = (family, 10, "bold")

        for name, size, weight in (
            ("TkDefaultFont", 10, "normal"),
            ("TkTextFont", 10, "normal"),
            ("TkMenuFont", 10, "normal"),
            ("TkHeadingFont", 10, "bold"),
        ):
            try:
                tkfont.nametofont(name).configure(
                    family=family, size=size, weight=weight, slant="roman"
                )
            except tk.TclError:
                pass

        self.option_add("*Font", body)
        self.option_add("*TCombobox*Listbox.background", FIELD)
        self.option_add("*TCombobox*Listbox.foreground", WHITE)
        self.option_add("*TCombobox*Listbox.selectBackground", RED)

        style.configure(".", background=BG, foreground=WHITE, font=body)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=WHITE)
        style.configure("Panel.TLabel", background=PANEL, foreground=WHITE)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED, font=small)
        style.configure("TCheckbutton", background=PANEL, foreground=WHITE)
        style.map("TCheckbutton", background=[("active", PANEL)])
        style.configure("TEntry", fieldbackground=FIELD, foreground=WHITE, insertcolor=WHITE)
        style.configure(
            "TCombobox",
            fieldbackground=FIELD,
            background=FIELD,
            foreground=WHITE,
            arrowcolor=WHITE,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD)],
            foreground=[("readonly", WHITE)],
        )
        style.configure(
            "TButton",
            background="#182837",
            foreground=WHITE,
            bordercolor=LINE,
            padding=(9, 6),
        )
        style.map("TButton", background=[("active", "#20384B")])
        style.configure(
            "Red.TButton",
            background=RED,
            foreground="white",
            bordercolor=RED,
            padding=(10, 8),
            font=bold,
        )
        style.map("Red.TButton", background=[("active", "#FF3038")])
        style.configure(
            "Dark.TButton",
            background="#0E1822",
            foreground=WHITE,
            bordercolor=LINE,
            padding=(9, 7),
            font=bold,
        )
        style.configure(
            "Small.TButton",
            background="#152431",
            foreground=WHITE,
            bordercolor=LINE,
            padding=(7, 4),
            font=small,
        )
        style.configure(
            "Treeview",
            background="#0B141D",
            fieldbackground="#0B141D",
            foreground=WHITE,
            bordercolor=LINE,
            rowheight=31,
        )
        style.configure(
            "Treeview.Heading",
            background="#132431",
            foreground=WHITE,
            font=bold,
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#263C4D")])
        style.configure(
            "Brand.Horizontal.TProgressbar",
            troughcolor="#14222E",
            background=BLUE,
            bordercolor="#14222E",
        )

    def _panel(self, parent):
        return tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=LINE,
            highlightthickness=1,
            bd=0,
        )

    def _red_title(self, parent, text):
        bar = tk.Frame(parent, bg=RED, height=32)
        bar.pack(fill="x")
        bar.pack_propagate(False)
        tk.Label(
            bar,
            text=text,
            bg=RED,
            fg="white",
            font=(self.ui_font_family, 10, "bold"),
            anchor="w",
            padx=10,
        ).pack(fill="both", expand=True)

    # ------------------------------------------------------------------
    # FIXED LAYOUT
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, minsize=245, weight=0)
        root.grid_columnconfigure(1, weight=1)
        root.grid_columnconfigure(2, minsize=310, weight=0)

        self._build_header(root)
        self._build_left(root)
        self._build_center(root)
        self._build_right(root)
        self._build_footer(root)

    def _build_header(self, root):
        head = tk.Frame(root, bg="#050A0F", height=112)
        head.grid(row=0, column=0, columnspan=3, sticky="ew")
        head.grid_propagate(False)
        head.grid_columnconfigure(1, weight=1)

        brand = tk.Frame(head, bg="#050A0F")
        brand.grid(row=0, column=0, sticky="w", padx=18, pady=8)

        self._brand_logo_photo = self._load_brand_logo()
        if self._brand_logo_photo:
            tk.Label(brand, image=self._brand_logo_photo, bg="#050A0F", bd=0).pack(
                side="left", padx=(0, 12)
            )
            try:
                self.iconphoto(True, self._brand_logo_photo)
            except Exception:
                pass

        titles = tk.Frame(brand, bg="#050A0F")
        titles.pack(side="left")
        line = tk.Frame(titles, bg="#050A0F")
        line.pack(anchor="w")
        tk.Label(
            line,
            text="นิยมศิลป์",
            bg="#050A0F",
            fg=WHITE,
            font=(self.ui_font_family, 23, "bold"),
        ).pack(side="left")
        tk.Label(
            line,
            text="ดีไซน์",
            bg="#050A0F",
            fg=RED,
            font=(self.ui_font_family, 23, "bold"),
        ).pack(side="left")
        tk.Label(
            line,
            text=" v1.0",
            bg="#050A0F",
            fg=WHITE,
            font=(self.ui_font_family, 18, "bold"),
        ).pack(side="left")
        tk.Label(
            titles,
            text=APP_SUBTITLE,
            bg="#050A0F",
            fg=MUTED,
            font=(self.ui_font_family, 10, "bold"),
        ).pack(anchor="w")

        tools = tk.Frame(head, bg="#050A0F")
        tools.grid(row=0, column=1, sticky="e", padx=10, pady=16)
        self._header_button(tools, "เปิดไฟล์", self.choose_files).pack(side="left", padx=3)
        self._header_button(tools, "ประมวลผล", self.start_processing, True).pack(side="left", padx=3)
        self._header_button(tools, "บันทึก", self.save_last_as).pack(side="left", padx=3)
        self._header_button(tools, "โฟลเดอร์", self.open_output_folder).pack(side="left", padx=3)

        default = self.engine_manager.device_manager.get_default_device()
        eng = tk.Frame(head, bg="#0B151E", highlightbackground=LINE, highlightthickness=1)
        eng.grid(row=0, column=2, sticky="e", padx=(4, 16), pady=20)
        tk.Label(
            eng, text="ARM V2.2.8 ENGINE", bg="#0B151E", fg=MUTED,
            font=(self.ui_font_family, 8, "bold"),
        ).pack(anchor="w", padx=10, pady=(7, 0))
        tk.Label(
            eng, text="RealESRGAN_x4plus (PyTorch)", bg="#0B151E", fg=WHITE,
            font=(self.ui_font_family, 9, "bold"),
        ).pack(anchor="w", padx=10)
        self.engine_state_label = tk.Label(
            eng, text=f"AUTO · {default.name}", bg="#0B151E", fg=GREEN,
            font=(self.ui_font_family, 9, "bold"),
        )
        self.engine_state_label.pack(anchor="w", padx=10, pady=(0, 7))

        tk.Frame(root, bg=RED, height=3).grid(
            row=0, column=0, columnspan=3, sticky="sew"
        )

    def _header_button(self, parent, text, command, red=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=RED if red else "#0E1822",
            fg="white",
            activebackground="#FF3038" if red else "#1B3041",
            activeforeground="white",
            relief="flat",
            bd=0,
            width=9,
            height=3,
            font=(self.ui_font_family, 9, "bold"),
            cursor="hand2",
            highlightbackground=RED if red else LINE,
            highlightthickness=1,
        )

    def _build_left(self, root):
        left = tk.Frame(root, bg=BG, width=245)
        left.grid(row=1, column=0, sticky="nsw", padx=(10, 5), pady=8)
        left.grid_propagate(False)

        work = self._panel(left)
        work.pack(fill="x")
        self._red_title(work, "WORKSPACE")
        box = tk.Frame(work, bg=PANEL)
        box.pack(fill="x", padx=9, pady=9)
        ttk.Button(
            box, text="+ Import Image", command=self.choose_files, style="Red.TButton"
        ).pack(fill="x", pady=(0, 5))
        ttk.Button(
            box, text="Before / After", command=self._fit_previews, style="Dark.TButton"
        ).pack(fill="x", pady=2)
        ttk.Button(
            box, text="Print Size", command=lambda: self.width_entry.focus_set(),
            style="Dark.TButton",
        ).pack(fill="x", pady=2)
        ttk.Button(
            box, text="AI Enhancement", command=lambda: self.scale_box.focus_set(),
            style="Dark.TButton",
        ).pack(fill="x", pady=2)

        status = self._panel(left)
        status.pack(fill="x", pady=(8, 0))
        self._red_title(status, "PROCESS STATUS")
        inside = tk.Frame(status, bg=PANEL)
        inside.pack(fill="x", padx=10, pady=8)

        self._stage_labels = []
        for name in (
            "1. Prepare / Analyze",
            "2. ARM Real-ESRGAN",
            "3. AI Pass 2 (8x only)",
            "4. Final Resize",
            "5. Save Output",
        ):
            row = tk.Frame(inside, bg=PANEL, height=23)
            row.pack(fill="x")
            row.pack_propagate(False)
            led = tk.Label(
                row, text="●", bg=PANEL, fg="#647483",
                font=(self.ui_font_family, 11, "bold"),
            )
            led.pack(side="left")
            tk.Label(
                row, text=name, bg=PANEL, fg=WHITE,
                font=(self.ui_font_family, 9),
            ).pack(side="left", padx=(5, 0))
            self._stage_labels.append(led)

        self.stage_text = tk.Label(
            inside, text="พร้อมใช้งาน", bg=PANEL, fg=MUTED,
            font=(self.ui_font_family, 9), anchor="w", width=29,
        )
        self.stage_text.pack(fill="x", pady=(6, 2))
        self.progress = ttk.Progressbar(
            inside, maximum=100, mode="determinate",
            style="Brand.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x")
        ttk.Button(
            inside, text="STOP + CLEAR", command=self.stop_and_clear,
            style="Red.TButton",
        ).pack(fill="x", pady=(7, 0))

        engine = self._panel(left)
        engine.pack(fill="x", pady=(8, 0))
        self._red_title(engine, "ENGINE INFORMATION")
        self.engine_info = tk.Label(
            engine,
            text="ARM V2.2.8 source core\nReal-ESRGAN PyTorch\nNo extra enhancement filters",
            bg=PANEL, fg=GREEN, justify="left", anchor="w",
            font=(self.ui_font_family, 9, "bold"),
            padx=10, pady=8,
        )
        self.engine_info.pack(fill="x")

    def _build_center(self, root):
        center = tk.Frame(root, bg=BG)
        center.grid(row=1, column=1, sticky="nsew", padx=4, pady=8)
        center.grid_rowconfigure(0, weight=3)
        center.grid_rowconfigure(1, weight=2, minsize=230)
        center.grid_columnconfigure(0, weight=1)

        compare = self._panel(center)
        compare.grid(row=0, column=0, sticky="nsew")
        compare.grid_rowconfigure(1, weight=1)
        compare.grid_columnconfigure(0, weight=1)
        compare.grid_columnconfigure(1, weight=1)

        zoombar = tk.Frame(compare, bg=PANEL, height=38)
        zoombar.grid(row=0, column=0, columnspan=2, sticky="ew", padx=7, pady=5)
        zoombar.grid_propagate(False)
        tk.Label(
            zoombar, text="ตัวอย่างภาพ", bg=RED, fg="white",
            font=(self.ui_font_family, 10, "bold"), padx=10, pady=4,
        ).pack(side="left")
        ttk.Button(
            zoombar, text="−", width=4, command=lambda: self._zoom_by(1 / 1.25),
            style="Small.TButton",
        ).pack(side="left", padx=(10, 2))
        ttk.Button(
            zoombar, text="+", width=4, command=lambda: self._zoom_by(1.25),
            style="Small.TButton",
        ).pack(side="left", padx=2)
        ttk.Button(
            zoombar, text="พอดีหน้าต่าง", command=self._fit_previews,
            style="Small.TButton",
        ).pack(side="left", padx=5)
        tk.Label(
            zoombar,
            text="ลากภาพเพื่อเลื่อน • หมุนล้อเมาส์เพื่อซูม Before/After พร้อมกัน",
            bg=PANEL, fg=MUTED, font=(self.ui_font_family, 9),
        ).pack(side="left", padx=10)
        self.zoom_label = tk.Label(
            zoombar, text="100%", bg=PANEL, fg=WHITE,
            font=(self.ui_font_family, 9, "bold"),
        )
        self.zoom_label.pack(side="right", padx=8)

        preview = tk.Frame(compare, bg=PANEL)
        preview.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=5, pady=(0, 6))
        preview.grid_rowconfigure(0, weight=1)
        preview.grid_columnconfigure(0, weight=1)
        preview.grid_columnconfigure(1, weight=1)

        self.before_panel = self._preview_panel(preview, "ภาพต้นฉบับ (BEFORE)", 0)
        self.after_panel = self._preview_panel(preview, "ผลลัพธ์ AI (AFTER)", 1)

        lower = self._panel(center)
        lower.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        lower.grid_rowconfigure(1, weight=1)
        lower.grid_columnconfigure(0, weight=1)

        bar = tk.Frame(lower, bg=PANEL, height=34)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_propagate(False)
        tk.Label(
            bar, text=" LOG / STATUS ", bg=RED, fg="white",
            font=(self.ui_font_family, 9, "bold"), pady=5,
        ).pack(side="left")
        ttk.Button(
            bar, text="เพิ่มไฟล์", command=self.choose_files, style="Small.TButton"
        ).pack(side="right", padx=5, pady=3)
        ttk.Button(
            bar, text="ลบที่เลือก", command=self.remove_selected, style="Small.TButton"
        ).pack(side="right", pady=3)

        lower_body = tk.PanedWindow(
            lower, orient="vertical", sashwidth=4, bg=BG, bd=0,
        )
        lower_body.grid(row=1, column=0, sticky="nsew")

        log_frame = tk.Frame(lower_body, bg="#071019", height=105)
        log_frame.pack_propagate(False)
        queue_frame = tk.Frame(lower_body, bg="#071019")
        lower_body.add(log_frame, minsize=95)
        lower_body.add(queue_frame, minsize=115)

        self.log_text = tk.Text(
            log_frame, bg="#071019", fg="#D8E4EC",
            insertbackground="white", relief="flat", bd=0,
            height=5, wrap="word", font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=6)
        self.log_text.insert("end", "READY · ARM V2.2.8 processing core\n")
        self.log_text.configure(state="disabled")

        cols = ("name", "original", "output", "status")
        self.tree = ttk.Treeview(
            queue_frame, columns=cols, show="headings", selectmode="browse",
        )
        for col, title in zip(
            cols, ("ชื่อไฟล์", "ขนาดต้นฉบับ", "ขนาดปลายทาง", "สถานะ")
        ):
            self.tree.heading(col, text=title)
        self.tree.column("name", width=300)
        self.tree.column("original", width=145, anchor="center")
        self.tree.column("output", width=180, anchor="center")
        self.tree.column("status", width=220)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _preview_panel(self, parent, title, column):
        panel = tk.Frame(
            parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1,
        )
        panel.grid(
            row=0, column=column, sticky="nsew",
            padx=(3 if column else 0, 0 if column else 3),
        )
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        tk.Label(
            panel, text=title,
            bg=RED if column else "#26323C",
            fg="white",
            font=(self.ui_font_family, 10, "bold"),
            anchor="w", padx=10, pady=5,
        ).grid(row=0, column=0, sticky="ew")

        canvas = tk.Canvas(
            panel, background="#292929", highlightthickness=0, cursor="hand2",
        )
        canvas.grid(row=1, column=0, sticky="nsew", padx=6, pady=6)

        if column == 0:
            self.before_image = canvas
            key = "before"
        else:
            self.after_image = canvas
            key = "after"

        caption = tk.Label(
            panel,
            text="ยังไม่ได้เลือกภาพ" if column == 0 else "ผลลัพธ์จะแสดงหลังประมวลผล",
            bg="#0B141D", fg=MUTED, height=1,
            font=(self.ui_font_family, 9),
        )
        caption.grid(row=2, column=0, sticky="ew", pady=(0, 4))

        if column == 0:
            self.before_caption = caption
        else:
            self.after_caption = caption

        # Exact pan/zoom interaction pattern from the uploaded ARM GUI.
        canvas.bind("<Configure>", lambda _event: self._render_previews())
        canvas.bind("<ButtonPress-1>", lambda event, k=key: self._pan_start(event, k))
        canvas.bind("<B1-Motion>", lambda event, k=key: self._pan_move(event, k))
        canvas.bind("<MouseWheel>", self._wheel_zoom)
        canvas.bind("<Button-4>", lambda event: self._zoom_by(1.15, event))
        canvas.bind("<Button-5>", lambda event: self._zoom_by(1 / 1.15, event))
        return panel

    def _build_right(self, root):
        right = tk.Frame(root, bg=BG, width=310)
        right.grid(row=1, column=2, sticky="nse", padx=(5, 10), pady=8)
        right.grid_propagate(False)

        size_panel = self._panel(right)
        size_panel.pack(fill="x")
        self._red_title(size_panel, "PRINT SIZE / REAL OUTPUT")
        p = tk.Frame(size_panel, bg=PANEL)
        p.pack(fill="x", padx=10, pady=8)

        self.output_mode_var = tk.StringVar(value="print")
        self.width_var = tk.StringVar(value="200")
        self.height_var = tk.StringVar(value="80")
        self.dpi_var = tk.StringVar(value="300")
        self.unit_var = tk.StringVar(value="cm")
        self.lock_ratio = tk.BooleanVar(value=True)

        mode = ttk.Combobox(
            p, textvariable=self.output_mode_var,
            values=("print", "upscale"), state="readonly",
        )
        ttk.Label(p, text="Mode", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        mode.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=3)
        mode.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        ttk.Label(p, text="Width", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        self.width_entry = ttk.Entry(p, textvariable=self.width_var, width=10)
        self.width_entry.grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=3)
        self.width_entry.bind("<KeyRelease>", lambda e: self._size_edited("w"))
        unit1 = ttk.Combobox(
            p, textvariable=self.unit_var,
            values=("px", "mm", "cm", "m", "inch", "feet"),
            state="readonly", width=7,
        )
        unit1.grid(row=1, column=2, pady=3)
        unit1.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        ttk.Label(p, text="Height", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=3)
        self.height_entry = ttk.Entry(p, textvariable=self.height_var, width=10)
        self.height_entry.grid(row=2, column=1, sticky="ew", padx=(8, 4), pady=3)
        self.height_entry.bind("<KeyRelease>", lambda e: self._size_edited("h"))
        unit2 = ttk.Combobox(
            p, textvariable=self.unit_var,
            values=("px", "mm", "cm", "m", "inch", "feet"),
            state="readonly", width=7,
        )
        unit2.grid(row=2, column=2, pady=3)
        unit2.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        ttk.Label(p, text="DPI", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=3)
        dpi = ttk.Combobox(
            p, textvariable=self.dpi_var,
            values=("72", "96", "100", "150", "200", "300"),
            width=10,
        )
        dpi.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(8, 0), pady=3)
        dpi.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())
        dpi.bind("<KeyRelease>", lambda e: self._settings_changed())

        ttk.Checkbutton(
            p, text="Lock aspect ratio (คงสัดส่วนภาพ)",
            variable=self.lock_ratio,
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 2))

        self.pixel_info = ttk.Label(p, text="ขนาดพิกเซลปลายทาง: —", style="Muted.TLabel")
        self.pixel_info.grid(row=5, column=0, columnspan=3, sticky="w")
        p.grid_columnconfigure(1, weight=1)

        ai_panel = self._panel(right)
        ai_panel.pack(fill="x", pady=(8, 0))
        self._red_title(ai_panel, "ARM AI ENHANCEMENT")
        a = tk.Frame(ai_panel, bg=PANEL)
        a.pack(fill="x", padx=10, pady=8)

        self.scale_var = tk.StringVar(value="4x")
        ttk.Label(a, text="AI Upscale", style="Panel.TLabel").grid(row=0, column=0, sticky="w", pady=3)
        self.scale_box = ttk.Combobox(
            a, textvariable=self.scale_var,
            values=("2x", "4x", "8x"), state="readonly",
        )
        self.scale_box.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=3)
        self.scale_box.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        devices = self.engine_manager.device_manager.get_devices()
        self.device_display_to_id = {"AUTO": "AUTO"}
        device_values = ["AUTO"]
        for d in devices:
            display = f"{d.backend} · {d.name}"
            if d.memory_mb:
                display += f" ({round(d.memory_mb / 1024, 1)} GB)"
            device_values.append(display)
            self.device_display_to_id[display] = d.device_id

        self.device_var = tk.StringVar(value="AUTO")
        ttk.Label(a, text="Device", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=3)
        device_box = ttk.Combobox(
            a, textvariable=self.device_var,
            values=tuple(device_values), state="readonly",
        )
        device_box.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=3)
        device_box.bind("<<ComboboxSelected>>", self._device_changed)

        tk.Label(
            a,
            text="ประมวลผลด้วยโค้ด ARM V2.2.8 โดยตรง\nไม่มี Denoise / Contrast / Sharpen เพิ่มจากโปรแกรมเรา",
            bg=PANEL, fg=MUTED, justify="left",
            font=(self.ui_font_family, 9),
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 4))

        ttk.Button(
            a, text="AI ENHANCE TO TARGET",
            command=self.start_processing, style="Red.TButton",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        a.grid_columnconfigure(1, weight=1)

        export = self._panel(right)
        export.pack(fill="x", pady=(8, 0))
        self._red_title(export, "EXPORT")
        e = tk.Frame(export, bg=PANEL)
        e.pack(fill="x", padx=10, pady=8)

        tk.Label(
            e, text="PNG · DPI metadata ตามโค้ดต้นฉบับ ARM",
            bg=PANEL, fg=WHITE, font=(self.ui_font_family, 9),
        ).pack(fill="x", pady=(0, 6))
        ttk.Button(
            e, text="Open Print File", command=self.open_last_result,
            style="Dark.TButton",
        ).pack(fill="x", pady=2)
        ttk.Button(
            e, text="Open Output Folder", command=self.open_output_folder,
            style="Dark.TButton",
        ).pack(fill="x", pady=2)

    def _build_footer(self, root):
        foot = tk.Frame(root, bg="#050A0F", height=30)
        foot.grid(row=2, column=0, columnspan=3, sticky="ew")
        foot.grid_propagate(False)
        foot.grid_columnconfigure(1, weight=1)

        self.status_label = tk.Label(
            foot, text="พร้อมใช้งาน", bg="#050A0F", fg=MUTED,
            font=(self.ui_font_family, 9), anchor="w", width=58,
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=12)

        tk.Label(
            foot,
            text="นิยมศิลป์ดีไซน์ v1.0 · ARM V2.2.8 Core",
            bg="#050A0F", fg="#718493",
            font=(self.ui_font_family, 8),
        ).grid(row=0, column=1)

        self.elapsed_label = tk.Label(
            foot, text="00:00:00", bg="#050A0F", fg=GREEN,
            font=(self.ui_font_family, 8, "bold"),
        )
        self.elapsed_label.grid(row=0, column=2, sticky="e", padx=12)

    # ------------------------------------------------------------------
    # FILES / SIZE
    # ------------------------------------------------------------------
    def _enable_drag_drop(self):
        if os.name != "nt":
            return
        try:
            import windnd

            def dropped(items):
                paths = []
                for item in items:
                    if isinstance(item, bytes):
                        try:
                            paths.append(item.decode("utf-8"))
                        except UnicodeDecodeError:
                            paths.append(item.decode("mbcs", errors="replace"))
                    else:
                        paths.append(str(item))
                self.after(0, lambda: self.add_files(paths))

            windnd.hook_dropfiles(self, func=dropped)
        except Exception:
            pass

    def choose_files(self):
        paths = filedialog.askopenfilenames(title="เลือกภาพ", filetypes=IMAGE_TYPES)
        if paths:
            self.add_files(paths)

    def add_files(self, paths):
        added = 0
        for raw in paths:
            p = Path(raw)
            if not p.exists() or p in self.files:
                continue
            try:
                with Image.open(p) as im:
                    size = im.size
            except Exception:
                continue

            self.files.append(p)
            iid = str(len(self.files) - 1)
            self.tree.insert(
                "", "end", iid=iid,
                values=(p.name, f"{size[0]:,} × {size[1]:,}", "—", "พร้อม"),
            )
            added += 1

        if added and self.current_index is None:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self._select_index(0)

        self._set_status(f"เพิ่มภาพแล้ว {added} ไฟล์")
        self._update_tree_output_sizes()

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        self.files.pop(idx)
        self.current_index = None

        for item in self.tree.get_children():
            self.tree.delete(item)

        old = list(self.files)
        self.files = []
        self._preview_pils = {"before": None, "after": None}
        self._render_previews()
        self.add_files(old)

        if not self.files:
            self.before_caption.configure(text="ยังไม่ได้เลือกภาพ")
            self.after_caption.configure(text="ผลลัพธ์จะแสดงหลังประมวลผล")

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self._select_index(int(sel[0]))

    def _select_index(self, idx):
        if idx < 0 or idx >= len(self.files):
            return
        self.current_index = idx
        p = self.files[idx]
        try:
            with Image.open(p) as im:
                w, h = im.size
                preview = ImageOps.contain(im.convert("RGB"), (1800, 1400))
            self.original_ratio = w / max(1, h)
            if self.lock_ratio.get():
                try:
                    width = float(self.width_var.get())
                    self.height_var.set(self._fmt(width / self.original_ratio))
                except ValueError:
                    pass

            self._preview_pils["before"] = preview.copy()
            self._preview_pils["after"] = None
            self.before_caption.configure(text=f"{p.name} · {w:,} × {h:,} px")
            self.after_caption.configure(text="ผลลัพธ์จะแสดงหลังประมวลผล")
            self._fit_previews()
            self._settings_changed()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _fmt(self, value):
        return f"{value:.4f}".rstrip("0").rstrip(".")

    def _size_edited(self, side):
        if self._syncing_size:
            return
        if self.lock_ratio.get() and self.original_ratio > 0:
            self._syncing_size = True
            try:
                if side == "w":
                    v = float(self.width_var.get())
                    self.height_var.set(self._fmt(v / self.original_ratio))
                else:
                    v = float(self.height_var.get())
                    self.width_var.set(self._fmt(v * self.original_ratio))
            except ValueError:
                pass
            finally:
                self._syncing_size = False
        self._settings_changed()

    def _dpi(self):
        try:
            value = int(float(self.dpi_var.get()))
            return value if value > 0 else 72
        except Exception:
            return 72

    def _target_box_size(self):
        width = float(self.width_var.get())
        height = float(self.height_var.get())
        unit = self.unit_var.get()
        dpi = self._dpi()
        if width <= 0 or height <= 0:
            raise ValueError("Width และ Height ต้องมากกว่า 0")
        if unit == "px":
            return max(1, round(width)), max(1, round(height))
        factor = UNITS_TO_INCH[unit]
        return (
            max(1, round(width * factor * dpi)),
            max(1, round(height * factor * dpi)),
        )

    def _output_size_for(self, source_size):
        if self.output_mode_var.get() == "upscale":
            factor = int(self.scale_var.get().rstrip("x"))
            return source_size[0] * factor, source_size[1] * factor
        return self._target_box_size()

    @staticmethod
    def _model_scale_for_dimensions(width, height, target_size):
        # Exact model-scale rule from the uploaded ARM GUI.
        required = max(target_size[0] / width, target_size[1] / height)
        return 2 if required <= 2 else (4 if required <= 4 else 8)

    def _settings_changed(self):
        self._update_pixel_info()
        self._update_tree_output_sizes()

    def _update_pixel_info(self):
        try:
            if self.current_index is not None:
                with Image.open(self.files[self.current_index]) as im:
                    target = self._output_size_for(im.size)
            elif self.output_mode_var.get() == "print":
                target = self._target_box_size()
            else:
                self.pixel_info.configure(text="ขนาดพิกเซลปลายทาง: เลือกภาพก่อน")
                return
            self.pixel_info.configure(
                text=f"ขนาดพิกเซลปลายทาง: {target[0]:,} × {target[1]:,} px"
            )
        except Exception:
            self.pixel_info.configure(text="ขนาดพิกเซลปลายทาง: —")

    def _update_tree_output_sizes(self):
        for i, p in enumerate(self.files):
            iid = str(i)
            if not self.tree.exists(iid):
                continue
            try:
                with Image.open(p) as im:
                    target = self._output_size_for(im.size)
                vals = list(self.tree.item(iid, "values"))
                vals[2] = f"{target[0]:,} × {target[1]:,}"
                self.tree.item(iid, values=vals)
            except Exception:
                pass

    def _device_changed(self, _event=None):
        selected = self.device_display_to_id.get(self.device_var.get(), "AUTO")
        try:
            if selected == "AUTO":
                d = self.engine_manager.device_manager.get_default_device()
            else:
                d = self.engine_manager.device_manager.get_device(selected)
            if d:
                self.engine_state_label.configure(text=f"{d.backend} · {d.name}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # PREVIEW ZOOM / PAN — copied from uploaded ARM GUI behavior
    # ------------------------------------------------------------------
    def _render_previews(self):
        self._clamp_pan()
        for key, canvas in (
            ("before", getattr(self, "before_image", None)),
            ("after", getattr(self, "after_image", None)),
        ):
            image = self._preview_pils.get(key)
            if canvas is None:
                continue
            if image is None:
                canvas.delete("preview")
                self._preview_photos[key] = None
                continue

            cw = max(canvas.winfo_width(), 2)
            ch = max(canvas.winfo_height(), 2)
            factor = min(cw / image.width, ch / image.height) * self.zoom

            left = image.width / 2 - (cw / 2 + self.pan_x * cw) / factor
            top = image.height / 2 - (ch / 2 + self.pan_y * ch) / factor
            box = (
                max(0, int(left)),
                max(0, int(top)),
                min(image.width, int(left + cw / factor) + 1),
                min(image.height, int(top + ch / factor) + 1),
            )

            if box[2] <= box[0] or box[3] <= box[1]:
                canvas.delete("preview")
                continue

            visible = image.crop(box)
            size = (
                max(1, min(cw, int(visible.width * factor))),
                max(1, min(ch, int(visible.height * factor))),
            )
            photo = ImageTk.PhotoImage(
                visible.resize(size, Image.Resampling.LANCZOS)
            )
            self._preview_photos[key] = photo
            canvas.delete("preview")

            x = (
                cw / 2
                + self.pan_x * cw
                - image.width * factor / 2
                + box[0] * factor
            )
            y = (
                ch / 2
                + self.pan_y * ch
                - image.height * factor / 2
                + box[1] * factor
            )
            canvas.create_image(x, y, image=photo, anchor="nw", tags="preview")

        self.zoom_label.configure(text=f"{round(self.zoom * 100)}%")

    def _clamp_pan(self):
        limits_x, limits_y = [], []
        for key, canvas in (
            ("before", getattr(self, "before_image", None)),
            ("after", getattr(self, "after_image", None)),
        ):
            image = self._preview_pils.get(key)
            if canvas is None or image is None:
                continue
            cw = max(canvas.winfo_width(), 2)
            ch = max(canvas.winfo_height(), 2)
            fit = min(cw / image.width, ch / image.height)
            limits_x.append(
                max(0.0, image.width * fit * self.zoom - cw) / (2 * cw)
            )
            limits_y.append(
                max(0.0, image.height * fit * self.zoom - ch) / (2 * ch)
            )
        if limits_x:
            limit = min(limits_x)
            self.pan_x = min(limit, max(-limit, self.pan_x))
        if limits_y:
            limit = min(limits_y)
            self.pan_y = min(limit, max(-limit, self.pan_y))

    def _zoom_by(self, factor, _event=None):
        self.zoom = min(8.0, max(0.25, self.zoom * factor))
        self._render_previews()

    def _wheel_zoom(self, event):
        self._zoom_by(1.15 if event.delta > 0 else 1 / 1.15, event)

    def _fit_previews(self):
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self._render_previews()

    def _pan_start(self, event, key):
        self._pan_origin = (event.x, event.y, key, self.pan_x, self.pan_y)

    def _pan_move(self, event, key):
        if not self._pan_origin:
            return
        x0, y0, _origin_key, px, py = self._pan_origin
        canvas = self.before_image if key == "before" else self.after_image
        self.pan_x = px + (event.x - x0) / max(1, canvas.winfo_width())
        self.pan_y = py + (event.y - y0) / max(1, canvas.winfo_height())
        self._render_previews()

    # ------------------------------------------------------------------
    # ARM V2.2.8 PROCESSING FLOW
    # ------------------------------------------------------------------
    def _selected_device_id(self):
        return self.device_display_to_id.get(self.device_var.get(), "AUTO")

    def _output_filename(self, src, target_size, dpi):
        if self.output_mode_var.get() == "upscale":
            suffix = self.scale_var.get()
        else:
            if self.unit_var.get() == "px":
                width, height = target_size
            else:
                width = self.width_var.get()
                height = self.height_var.get()
            suffix = f"{width}x{height}{self.unit_var.get()}{dpi}DPI"
        safe_suffix = str(suffix).replace(".", "p")
        return src.with_name(f"{src.stem}-{safe_suffix}.png")

    def _tile_progress_callback(self, start, end):
        def callback(value):
            mapped = start + (end - start) * (value / 100.0)
            self._events.put(("progress", int(mapped)))
        return callback

    def start_processing(self):
        if not self.files:
            messagebox.showinfo(APP_NAME, "กรุณาเพิ่มภาพก่อน")
            return

        try:
            jobs = []
            for src in self.files:
                with Image.open(src) as im:
                    source_size = im.size
                target_size = self._output_size_for(source_size)
                if max(target_size) > 30000:
                    raise ValueError(
                        "ขนาดด้านใดด้านหนึ่งเกิน 30,000 px ตามข้อจำกัดของโค้ด ARM V2.2.8"
                    )
                if self.output_mode_var.get() == "upscale":
                    model_scale = int(self.scale_var.get().rstrip("x"))
                else:
                    model_scale = self._model_scale_for_dimensions(
                        source_size[0], source_size[1], target_size
                    )
                jobs.append((src, source_size, target_size, model_scale))
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        self._cancel.clear()
        self.progress["value"] = 0
        self._stage_reset()
        self._set_status("เริ่มประมวลผลด้วย ARM V2.2.8 core")
        started = time.time()

        def worker():
            try:
                selected_device = self._selected_device_id()
                engine = self.engine_manager.create_engine(selected_device)
                self._active_engine = engine
                self._events.put(("engine", engine.device_name()))

                total = len(jobs)
                for index, (src, source_size, target_size, model_scale) in enumerate(jobs):
                    if self._cancel.is_set():
                        raise InterruptedError("Processing stopped by user")

                    self._events.put(("row", index, "กำลังประมวลผล…"))
                    self._events.put(("stage", 0, f"Prepare · {src.name}"))

                    output_file = self._output_filename(src, target_size, self._dpi())
                    temporary_files = []

                    fd, final_temp = tempfile.mkstemp(
                        prefix=f"{src.stem}_ARM_AI_final_",
                        suffix=".png",
                        dir=str(src.parent),
                    )
                    os.close(fd)
                    os.remove(final_temp)
                    temporary_files.append(final_temp)

                    try:
                        if model_scale == 8:
                            fd, temp_stage = tempfile.mkstemp(
                                prefix=f"{src.stem}_ARM_AI_8x_stage_",
                                suffix=".png",
                                dir=str(src.parent),
                            )
                            os.close(fd)
                            os.remove(temp_stage)
                            temporary_files.append(temp_stage)

                            self._events.put(("stage", 1, "ARM Real-ESRGAN · pass 1/2 · 4x"))
                            engine.enhance(
                                src,
                                temp_stage,
                                scale=4,
                                progress_callback=self._tile_progress_callback(12, 48),
                                cancel_check=self._cancel.is_set,
                            )

                            self._events.put(("stage", 2, "ARM Real-ESRGAN · pass 2/2 · 2x"))
                            engine.enhance(
                                temp_stage,
                                final_temp,
                                scale=2,
                                progress_callback=self._tile_progress_callback(48, 82),
                                cancel_check=self._cancel.is_set,
                            )
                        else:
                            self._events.put(
                                ("stage", 1, f"ARM Real-ESRGAN · {model_scale}x")
                            )
                            engine.enhance(
                                src,
                                final_temp,
                                scale=model_scale,
                                progress_callback=self._tile_progress_callback(12, 82),
                                cancel_check=self._cancel.is_set,
                            )

                        if self._cancel.is_set():
                            raise InterruptedError("Processing stopped by user")

                        self._events.put(("stage", 3, "Final Resize · ARM V2.2.8 flow"))
                        with Image.open(final_temp) as image:
                            output = image.convert("RGB")
                            if output.size != target_size:
                                if self.lock_ratio.get():
                                    output = ImageOps.contain(
                                        output,
                                        target_size,
                                        method=Image.Resampling.LANCZOS,
                                    )
                                    canvas = Image.new("RGB", target_size, "white")
                                    canvas.paste(
                                        output,
                                        (
                                            (target_size[0] - output.width) // 2,
                                            (target_size[1] - output.height) // 2,
                                        ),
                                    )
                                    output = canvas
                                else:
                                    output = output.resize(
                                        target_size, Image.Resampling.LANCZOS
                                    )

                            if self._cancel.is_set():
                                raise InterruptedError("Processing stopped by user")

                            self._events.put(("progress", 92))
                            self._events.put(("stage", 4, "Save Output"))
                            output.save(
                                final_temp,
                                format="PNG",
                                dpi=(self._dpi(), self._dpi()),
                            )
                            actual_size = output.size

                        os.replace(final_temp, output_file)
                        temporary_files.remove(final_temp)

                        overall = round((index + 1) / total * 100)
                        self._events.put(("progress", overall))
                        self._events.put(("row", index, "เสร็จแล้ว"))
                        self._events.put(
                            (
                                "result",
                                index,
                                str(output_file),
                                actual_size,
                                engine.device_name(),
                            )
                        )
                    finally:
                        for p in temporary_files:
                            try:
                                if os.path.exists(p):
                                    os.remove(p)
                            except Exception:
                                pass

                self._events.put(("done", time.time() - started))
            except InterruptedError:
                self._events.put(("cancelled", time.time() - started))
            except Exception as exc:
                self._events.put(("error", str(exc), time.time() - started))
            finally:
                self._active_engine = None

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------
    # EVENTS / STABLE STATUS
    # ------------------------------------------------------------------
    def _stage_reset(self):
        for led in self._stage_labels:
            led.configure(fg="#647483")

    def _stage_set(self, index):
        for i, led in enumerate(self._stage_labels):
            led.configure(
                fg=GREEN if i < index else (BLUE if i == index else "#647483")
            )

    def _mark_all_done(self):
        for led in self._stage_labels:
            led.configure(fg=GREEN)

    def _set_status(self, text):
        # Fixed-height labels prevent the UI from reflowing during processing.
        shown = text if len(text) <= 78 else text[:75] + "…"
        self.status_label.configure(text=shown)
        self.stage_text.configure(text=shown)

        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.insert(
                "end", f"[{time.strftime('%H:%M:%S')}]  {text}\n"
            )
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

    def _drain_events(self):
        try:
            while True:
                ev = self._events.get_nowait()
                kind = ev[0]

                if kind == "progress":
                    self.progress["value"] = max(0, min(100, ev[1]))

                elif kind == "stage":
                    self._stage_set(ev[1])
                    self._set_status(ev[2])

                elif kind == "engine":
                    self.engine_state_label.configure(text=ev[1])
                    self._set_status(f"ARM Engine active · {ev[1]}")

                elif kind == "row":
                    idx, status = ev[1], ev[2]
                    iid = str(idx)
                    if self.tree.exists(iid):
                        vals = list(self.tree.item(iid, "values"))
                        vals[3] = status
                        self.tree.item(iid, values=vals)

                elif kind == "result":
                    idx, path, size, device = ev[1], ev[2], ev[3], ev[4]
                    self._last_result = Path(path)

                    iid = str(idx)
                    if self.tree.exists(iid):
                        vals = list(self.tree.item(iid, "values"))
                        vals[2] = f"{size[0]:,} × {size[1]:,}"
                        vals[3] = "เสร็จแล้ว"
                        self.tree.item(iid, values=vals)

                    if idx == self.current_index or self.current_index is None:
                        try:
                            with Image.open(path) as im:
                                self._preview_pils["after"] = ImageOps.contain(
                                    im.convert("RGB"), (1800, 1400)
                                )
                            self.after_caption.configure(
                                text=f"{Path(path).name} · {size[0]:,} × {size[1]:,} px"
                            )
                            self._render_previews()
                        except Exception:
                            pass

                    self._set_status(f"เสร็จ · {Path(path).name} · {device}")

                elif kind == "done":
                    self.progress["value"] = 100
                    self._mark_all_done()
                    self._set_elapsed(ev[1])
                    self._set_status("ประมวลผลครบทุกไฟล์แล้ว")

                elif kind == "cancelled":
                    self._set_elapsed(ev[1])
                    self._set_status("หยุดการประมวลผลแล้ว")

                elif kind == "error":
                    self._set_elapsed(ev[2])
                    self._set_status("ERROR · " + ev[1])
                    messagebox.showerror(APP_NAME, ev[1])

        except queue.Empty:
            pass

        self.after(80, self._drain_events)

    def _set_elapsed(self, seconds):
        seconds = int(max(0, seconds))
        self.elapsed_label.configure(
            text=f"{seconds // 3600:02d}:{(seconds % 3600) // 60:02d}:{seconds % 60:02d}"
        )

    def stop_and_clear(self):
        self._cancel.set()
        self._set_status("กำลังหยุด…")

        def clear_when_safe():
            if self._active_engine is not None:
                self.after(150, clear_when_safe)
                return
            self.files = []
            self.current_index = None
            self._last_result = None
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._preview_pils = {"before": None, "after": None}
            self._fit_previews()
            self.before_caption.configure(text="ยังไม่ได้เลือกภาพ")
            self.after_caption.configure(text="ผลลัพธ์จะแสดงหลังประมวลผล")
            self.progress["value"] = 0
            self._stage_reset()
            self._set_status("พร้อมใช้งาน — เลือกภาพเพื่อเริ่ม")

        self.after(150, clear_when_safe)

    # ------------------------------------------------------------------
    # OUTPUT HELPERS
    # ------------------------------------------------------------------
    def open_output_folder(self):
        if self._last_result:
            p = self._last_result.parent
        elif self.current_index is not None and self.files:
            p = self.files[self.current_index].parent
        elif self.files:
            p = self.files[0].parent
        else:
            return

        try:
            if os.name == "nt":
                os.startfile(p)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{p}"')
            else:
                os.system(f'xdg-open "{p}" >/dev/null 2>&1 &')
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def open_last_result(self):
        if not self._last_result or not self._last_result.exists():
            messagebox.showinfo(APP_NAME, "ยังไม่มีไฟล์ผลลัพธ์")
            return
        try:
            if os.name == "nt":
                os.startfile(self._last_result)  # type: ignore[attr-defined]
            else:
                self.open_output_folder()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def save_last_as(self):
        if not self._last_result or not self._last_result.exists():
            messagebox.showinfo(APP_NAME, "ยังไม่มีผลลัพธ์ให้บันทึก")
            return

        dest = filedialog.asksaveasfilename(
            title="บันทึกผลลัพธ์เป็น…",
            defaultextension=".png",
            initialfile=self._last_result.name,
            filetypes=[("PNG", "*.png"), ("All files", "*.*")],
        )
        if dest:
            shutil.copy2(self._last_result, dest)
            self._set_status(f"บันทึกไฟล์: {dest}")


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
