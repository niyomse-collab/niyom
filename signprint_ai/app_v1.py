from __future__ import annotations

import base64
import io
import os
import shutil
import time
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

from .app import App as CoreApp, resource_root

APP_DISPLAY_NAME = "นิยมศิลป์ดีไซน์ v1.0"
APP_SUBTITLE = "AI Print Image Enhancer for Signage"

BG = "#081019"
PANEL = "#0E1822"
FIELD = "#162431"
LINE = "#274052"
RED = "#ED1C24"
WHITE = "#F4F7FA"
MUTED = "#9FB0BE"
GREEN = "#55E56A"
BLUE = "#45A7FF"


class App(CoreApp):
    """V1 production UI.

    This class changes the interface only. The existing pipeline, aspect-ratio
    logic, export and Real-ESRGAN backend remain untouched.
    """

    def __init__(self):
        self._stage_labels = []
        self._stage_index = 0
        super().__init__()
        self.title(APP_DISPLAY_NAME)
        self.geometry("1680x960")
        self.minsize(1360, 800)
        self.configure(bg=BG)

    def _pick_ui_font(self):
        try:
            available = {name.lower(): name for name in tkfont.families(self)}
        except tk.TclError:
            available = {}
        for wanted in ("Leelawadee UI", "Tahoma", "Segoe UI", "Arial"):
            if wanted.lower() in available:
                return available[wanted.lower()]
        return "TkDefaultFont"

    def _load_brand_logo(self, max_size=(116, 92)):
        try:
            raw = base64.b64decode(
                (resource_root() / "assets" / "logo.b64").read_text(encoding="utf-8").strip()
            )
            im = Image.open(io.BytesIO(raw)).convert("RGBA")
            px = im.load()
            for y in range(im.height):
                for x in range(im.width):
                    r, g, b, a = px[x, y]
                    if r > 246 and g > 246 and b > 246 and max(r, g, b) - min(r, g, b) < 6:
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

    def _build_ui(self):
        root = tk.Frame(self, bg=BG)
        root.pack(fill="both", expand=True)
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(1, weight=1)

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

        self._brand_logo_photo = self._load_brand_logo((112, 90))
        if self._brand_logo_photo:
            tk.Label(
                brand, image=self._brand_logo_photo, bg="#050A0F", bd=0
            ).pack(side="left", padx=(0, 12))
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
        self._header_button(tools, "ตั้งค่า", lambda: self.right_panel.focus_set()).pack(side="left", padx=3)
        self._header_button(tools, "ประมวลผล", self.start_processing, True).pack(side="left", padx=3)
        self._header_button(tools, "บันทึก", self.save_last_as).pack(side="left", padx=3)
        self._header_button(tools, "โฟลเดอร์", self.open_output_folder).pack(side="left", padx=3)
        self._header_button(tools, "ช่วยเหลือ", self.show_help).pack(side="left", padx=3)

        eng = tk.Frame(head, bg="#0B151E", highlightbackground=LINE, highlightthickness=1)
        eng.grid(row=0, column=2, sticky="e", padx=(4, 16), pady=20)
        ready = self.pipeline.ai.available
        tk.Label(
            eng,
            text="AI ENGINE",
            bg="#0B151E",
            fg=MUTED,
            font=(self.ui_font_family, 8, "bold"),
        ).pack(anchor="w", padx=10, pady=(7, 0))
        tk.Label(
            eng,
            text="Real-ESRGAN NCNN/Vulkan",
            bg="#0B151E",
            fg=WHITE,
            font=(self.ui_font_family, 9, "bold"),
        ).pack(anchor="w", padx=10)
        self.ai_state_label = tk.Label(
            eng,
            text="READY" if ready else "MISSING",
            bg="#0B151E",
            fg=GREEN if ready else "#FF6B6B",
            font=(self.ui_font_family, 9, "bold"),
        )
        self.ai_state_label.pack(anchor="w", padx=10, pady=(0, 7))

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
            box,
            text="+ Import Image",
            command=self.choose_files,
            style="Red.TButton",
        ).pack(fill="x", pady=(0, 5))
        ttk.Button(
            box,
            text="Before / After",
            command=self._refresh_preview_images,
            style="Dark.TButton",
        ).pack(fill="x", pady=2)
        ttk.Button(
            box,
            text="Print Size",
            command=lambda: self.print_panel.focus_set(),
            style="Dark.TButton",
        ).pack(fill="x", pady=2)
        ttk.Button(
            box,
            text="AI Enhancement",
            command=lambda: self.ai_panel.focus_set(),
            style="Dark.TButton",
        ).pack(fill="x", pady=2)
        ttk.Button(
            box,
            text="Color & Export",
            command=lambda: self.export_panel.focus_set(),
            style="Dark.TButton",
        ).pack(fill="x", pady=2)

        status = self._panel(left)
        status.pack(fill="x", pady=(8, 0))
        self._red_title(status, "PROCESS STATUS")
        inside = tk.Frame(status, bg=PANEL)
        inside.pack(fill="x", padx=10, pady=8)

        for name in (
            "1. Prepare / Analyze",
            "2. Denoise / Cleanup",
            "3. Color / Contrast",
            "4. Text Edge Recovery",
            "5. Surface / Detail",
            "6. Final Print Master",
        ):
            row = tk.Frame(inside, bg=PANEL)
            row.pack(fill="x", pady=1)
            led = tk.Label(
                row,
                text="●",
                bg=PANEL,
                fg="#647483",
                font=(self.ui_font_family, 11, "bold"),
            )
            led.pack(side="left")
            tk.Label(
                row,
                text=name,
                bg=PANEL,
                fg=WHITE,
                font=(self.ui_font_family, 9),
            ).pack(side="left", padx=(5, 0))
            self._stage_labels.append(led)

        self.stage_text = tk.Label(
            inside,
            text="พร้อมใช้งาน",
            bg=PANEL,
            fg=MUTED,
            font=(self.ui_font_family, 9),
            anchor="w",
        )
        self.stage_text.pack(fill="x", pady=(6, 2))
        self.progress = ttk.Progressbar(
            inside,
            maximum=100,
            mode="determinate",
            style="Brand.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x")
        ttk.Button(
            inside,
            text="STOP + CLEAR",
            command=self.stop_and_clear,
            style="Red.TButton",
        ).pack(fill="x", pady=(7, 0))

        engine = self._panel(left)
        engine.pack(fill="x", pady=(8, 0))
        self._red_title(engine, "ENGINE INFORMATION")
        ei = tk.Frame(engine, bg=PANEL)
        ei.pack(fill="x", padx=10, pady=8)
        tk.Label(
            ei,
            text="● Real-ESRGAN : " + ("ACTIVE" if self.pipeline.ai.available else "MISSING"),
            bg=PANEL,
            fg=GREEN if self.pipeline.ai.available else "#FF6B6B",
            font=(self.ui_font_family, 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            ei,
            text="● Processing Core : V1 Quality",
            bg=PANEL,
            fg=GREEN,
            font=(self.ui_font_family, 9, "bold"),
            anchor="w",
        ).pack(fill="x")
        tk.Label(
            ei,
            text="● Device : Auto",
            bg=PANEL,
            fg=BLUE,
            font=(self.ui_font_family, 9, "bold"),
            anchor="w",
        ).pack(fill="x")

    def _build_center(self, root):
        center = tk.Frame(root, bg=BG)
        center.grid(row=1, column=1, sticky="nsew", padx=4, pady=8)
        center.grid_rowconfigure(0, weight=3)
        center.grid_rowconfigure(1, weight=2)
        center.grid_columnconfigure(0, weight=1)

        compare = self._panel(center)
        compare.grid(row=0, column=0, sticky="nsew")
        compare.grid_rowconfigure(1, weight=1)
        compare.grid_columnconfigure(0, weight=1)
        compare.grid_columnconfigure(1, weight=1)

        top = tk.Frame(compare, bg=PANEL)
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=7, pady=5)
        tk.Label(
            top,
            text="ตัวอย่างภาพ",
            bg=RED,
            fg="white",
            font=(self.ui_font_family, 10, "bold"),
            padx=10,
            pady=4,
        ).pack(side="left")
        ttk.Button(
            top,
            text="Fit",
            command=self._refresh_preview_images,
            style="Small.TButton",
        ).pack(side="left", padx=(10, 3))
        ttk.Button(
            top,
            text="100%",
            command=self._refresh_preview_images,
            style="Small.TButton",
        ).pack(side="left", padx=3)
        self.auto_preview = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            top, text="Auto Preview", variable=self.auto_preview
        ).pack(side="right")

        self.left_image, self.left_caption = self._preview_pane(
            compare, 0, "ภาพต้นฉบับ (BEFORE)", False
        )
        self.right_image, self.right_caption = self._preview_pane(
            compare, 1, "ภาพหลังปรับปรุง (AFTER)", True
        )
        self.left_image.bind("<Configure>", lambda e: self._refresh_preview_images())
        self.right_image.bind("<Configure>", lambda e: self._refresh_preview_images())

        lower = self._panel(center)
        lower.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        lower.grid_rowconfigure(1, weight=1)
        lower.grid_columnconfigure(0, weight=1)

        tab = tk.Frame(lower, bg=PANEL)
        tab.grid(row=0, column=0, sticky="ew")
        tk.Label(
            tab,
            text=" LOG / STATUS ",
            bg=RED,
            fg="white",
            font=(self.ui_font_family, 9, "bold"),
            pady=5,
        ).pack(side="left")
        ttk.Button(
            tab, text="เพิ่มไฟล์", command=self.choose_files, style="Small.TButton"
        ).pack(side="right", padx=5, pady=3)
        ttk.Button(
            tab,
            text="ลบที่เลือก",
            command=self.remove_selected,
            style="Small.TButton",
        ).pack(side="right", pady=3)

        body = tk.PanedWindow(
            lower, orient="vertical", sashwidth=5, bg=BG, bd=0
        )
        body.grid(row=1, column=0, sticky="nsew")
        logframe = tk.Frame(body, bg="#071019")
        qframe = tk.Frame(body, bg="#071019")
        body.add(logframe, minsize=110)
        body.add(qframe, minsize=120)

        self.log_text = tk.Text(
            logframe,
            bg="#071019",
            fg="#D8E4EC",
            insertbackground="white",
            relief="flat",
            bd=0,
            height=6,
            wrap="word",
            font=("Consolas", 9),
        )
        self.log_text.pack(fill="both", expand=True, padx=8, pady=7)
        self.log_text.insert("end", "READY · พร้อมใช้งาน\n")
        self.log_text.configure(state="disabled")

        cols = ("name", "original", "output", "status")
        self.tree = ttk.Treeview(
            qframe, columns=cols, show="headings", selectmode="browse"
        )
        for col, title in zip(
            cols, ("ชื่อไฟล์", "ขนาดต้นฉบับ", "ขนาดปลายทาง", "สถานะ")
        ):
            self.tree.heading(col, text=title)
        self.tree.column("name", width=290)
        self.tree.column("original", width=140, anchor="center")
        self.tree.column("output", width=180, anchor="center")
        self.tree.column("status", width=210)
        self.tree.pack(fill="both", expand=True, padx=6, pady=6)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

    def _preview_pane(self, parent, column, title, after):
        frame = tk.Frame(
            parent, bg=PANEL, highlightbackground=LINE, highlightthickness=1
        )
        frame.grid(
            row=1,
            column=column,
            sticky="nsew",
            padx=(7 if column == 0 else 3, 3 if column == 0 else 7),
            pady=(0, 7),
        )
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)

        tk.Label(
            frame,
            text=title,
            bg=RED if after else "#26323C",
            fg="white",
            font=(self.ui_font_family, 10, "bold"),
            anchor="w",
            padx=10,
            pady=5,
        ).grid(row=0, column=0, sticky="ew")

        image = tk.Label(
            frame,
            bg="#22262B",
            fg=MUTED,
            text="No preview",
            anchor="center",
        )
        image.grid(row=1, column=0, sticky="nsew")

        caption = tk.Label(
            frame,
            bg="#0B141D",
            fg=MUTED,
            text="ยังไม่ได้เลือกภาพ" if not after else "ผลลัพธ์ AI จะแสดงที่นี่",
            font=(self.ui_font_family, 9),
            pady=5,
        )
        caption.grid(row=2, column=0, sticky="ew")
        return image, caption

    def _build_right(self, root):
        self.right_panel = tk.Frame(root, bg=BG, width=305)
        self.right_panel.grid(
            row=1, column=2, sticky="nse", padx=(5, 10), pady=8
        )
        self.right_panel.grid_propagate(False)

        self.print_panel = self._panel(self.right_panel)
        self.print_panel.pack(fill="x")
        self._red_title(self.print_panel, "PRINT SIZE / REAL OUTPUT")
        p = tk.Frame(self.print_panel, bg=PANEL)
        p.pack(fill="x", padx=10, pady=8)

        self.use_print_size = tk.BooleanVar(value=True)
        self.width_var = tk.StringVar(value="200")
        self.height_var = tk.StringVar(value="80")
        self.dpi_var = tk.StringVar(value="300")
        self.unit_var = tk.StringVar(value="cm")
        self.lock_ratio = tk.BooleanVar(value=True)

        self._size_row(p, "Width", self.width_var, 0, "w")
        self._size_row(p, "Height", self.height_var, 1, "h")
        ttk.Label(p, text="DPI", style="Panel.TLabel").grid(
            row=2, column=0, sticky="w", pady=3
        )
        dpi = ttk.Combobox(
            p,
            textvariable=self.dpi_var,
            values=(72, 96, 100, 150, 200, 300, 600),
            width=10,
        )
        dpi.grid(row=2, column=1, sticky="ew", padx=(8, 0))
        dpi.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())
        ttk.Checkbutton(
            p,
            text="Lock aspect ratio (คงสัดส่วนภาพ)",
            variable=self.lock_ratio,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 2))
        self.pixel_info = ttk.Label(
            p, text="ขนาดพิกเซลปลายทาง: —", style="Muted.TLabel"
        )
        self.pixel_info.grid(row=4, column=0, columnspan=3, sticky="w")
        p.grid_columnconfigure(1, weight=1)

        self.ai_panel = self._panel(self.right_panel)
        self.ai_panel.pack(fill="x", pady=(8, 0))
        self._red_title(self.ai_panel, "AI ENHANCEMENT")
        a = tk.Frame(self.ai_panel, bg=PANEL)
        a.pack(fill="x", padx=10, pady=8)

        self.engine_var = tk.StringVar(value="Auto (Real-ESRGAN)")
        self.scale_var = tk.StringVar(value="4x")
        self.mode_var = tk.StringVar(value="V1 Quality Core")
        self.v1_mode = tk.BooleanVar(value=True)

        self._combo_row(
            a, "Engine", self.engine_var, ("Auto (Real-ESRGAN)",), 0
        )
        self._combo_row(a, "AI Scale", self.scale_var, ("2x", "4x", "8x"), 1)
        mode = self._combo_row(
            a,
            "Mode",
            self.mode_var,
            ("V1 Quality Core", "Advanced Detail Preserve"),
            2,
        )
        mode.bind("<<ComboboxSelected>>", self._mode_changed)

        self.denoise_var = tk.DoubleVar(value=48)
        self.flat_var = tk.DoubleVar(value=52)
        self.text_var = tk.DoubleVar(value=58)
        self.contrast_var = tk.DoubleVar(value=20)
        self.sharp_var = tk.DoubleVar(value=46)
        self.sat_var = tk.DoubleVar(value=6)

        self._slider_row(a, "Surface / Detail", self.flat_var, 3)
        self._slider_row(a, "Text / Logo Edge", self.text_var, 4)
        self._slider_row(a, "Final Micro Sharpness", self.sharp_var, 5)

        ttk.Button(
            a,
            text="AI ENHANCE TO TARGET",
            command=self.start_processing,
            style="Red.TButton",
        ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        a.grid_columnconfigure(1, weight=1)

        color = self._panel(self.right_panel)
        color.pack(fill="x", pady=(8, 0))
        self._red_title(color, "COLOR / ICC")
        c = tk.Frame(color, bg=PANEL)
        c.pack(fill="x", padx=10, pady=8)

        self.color_mode_var = tk.StringVar(value="RGB")
        cm = ttk.Combobox(
            c,
            textvariable=self.color_mode_var,
            values=("RGB", "CMYK"),
            state="readonly",
        )
        cm.pack(side="left", fill="x", expand=True)
        cm.bind("<<ComboboxSelected>>", self._color_mode_changed)
        ttk.Button(
            c,
            text="Choose ICC / ICM",
            command=self._choose_icc_profile,
            style="Small.TButton",
        ).pack(side="left", padx=(5, 0))

        self._installed_icc_profiles = self._find_installed_icc_profiles()
        self.icc_profile_name_var = tk.StringVar(value="")
        self.icc_profile_path_var = tk.StringVar(value="")

        self.export_panel = self._panel(self.right_panel)
        self.export_panel.pack(fill="x", pady=(8, 0))
        self._red_title(self.export_panel, "EXPORT")
        e = tk.Frame(self.export_panel, bg=PANEL)
        e.pack(fill="x", padx=10, pady=8)

        self.format_var = tk.StringVar(value="TIFF")
        self._combo_row(
            e, "Format", self.format_var, ("PNG", "TIFF", "PDF", "JPG"), 0
        )
        ttk.Button(
            e,
            text="Save / Export",
            command=self.start_processing,
            style="Red.TButton",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(7, 4))
        ttk.Button(
            e,
            text="Open Print File",
            command=self.open_last_result,
            style="Dark.TButton",
        ).grid(row=2, column=0, sticky="ew", padx=(0, 2))
        ttk.Button(
            e,
            text="Open Output Folder",
            command=self.open_output_folder,
            style="Dark.TButton",
        ).grid(row=2, column=1, sticky="ew", padx=(2, 0))

        self.output_dir_var = tk.StringVar(value="")
        ttk.Button(
            e,
            text="เลือกโฟลเดอร์ปลายทาง…",
            command=self.choose_output_dir,
            style="Small.TButton",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.output_dir_label = ttk.Label(
            e,
            text="ค่าเริ่มต้น: โฟลเดอร์เดียวกับภาพต้นฉบับ",
            style="Muted.TLabel",
            wraplength=270,
        )
        self.output_dir_label.grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(4, 0)
        )
        e.grid_columnconfigure(1, weight=1)
        self.after(80, self._update_pixel_info)

    def _size_row(self, parent, label, var, row, side):
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(
            row=row, column=0, sticky="w", pady=3
        )
        ent = ttk.Entry(parent, textvariable=var, width=10)
        ent.grid(row=row, column=1, sticky="ew", padx=(8, 4), pady=3)
        unit = ttk.Combobox(
            parent,
            textvariable=self.unit_var,
            values=("mm", "cm", "m", "inch"),
            state="readonly",
            width=6,
        )
        unit.grid(row=row, column=2, pady=3)
        ent.bind("<KeyRelease>", lambda e: self._size_edited(side))
        unit.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

    def _combo_row(self, parent, label, variable, values, row):
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(
            row=row, column=0, sticky="w", pady=3
        )
        combo = ttk.Combobox(
            parent,
            textvariable=variable,
            values=values,
            state="readonly",
        )
        combo.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        combo.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())
        return combo

    def _slider_row(self, parent, label, variable, row):
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(
            row=row, column=0, sticky="w", pady=3
        )
        box = tk.Frame(parent, bg=PANEL)
        box.grid(row=row, column=1, sticky="ew", padx=(8, 0))
        value = tk.Label(
            box,
            text=str(round(variable.get())),
            bg=PANEL,
            fg=WHITE,
            width=3,
            font=(self.ui_font_family, 8, "bold"),
        )
        value.pack(side="right")
        slider = ttk.Scale(
            box, from_=0, to=100, variable=variable, orient="horizontal"
        )
        slider.pack(side="left", fill="x", expand=True)

        def changed(_=None):
            value.configure(text=str(round(variable.get())))
            self._settings_changed()

        slider.configure(command=changed)

    def _mode_changed(self, _event=None):
        self.v1_mode.set(self.mode_var.get() == "V1 Quality Core")
        self._settings_changed()

    def _build_footer(self, root):
        foot = tk.Frame(root, bg="#050A0F", height=30)
        foot.grid(row=2, column=0, columnspan=3, sticky="ew")
        foot.grid_propagate(False)
        foot.grid_columnconfigure(1, weight=1)

        self.status_label = tk.Label(
            foot,
            text="พร้อมใช้งาน",
            bg="#050A0F",
            fg=MUTED,
            font=(self.ui_font_family, 9),
            anchor="w",
        )
        self.status_label.grid(row=0, column=0, sticky="w", padx=12)
        tk.Label(
            foot,
            text="นิยมศิลป์ดีไซน์ v1.0  |  AI Print Image Enhancer for Signage",
            bg="#050A0F",
            fg="#718493",
            font=(self.ui_font_family, 8),
        ).grid(row=0, column=1)
        tk.Label(
            foot,
            text="Real-ESRGAN · Auto",
            bg="#050A0F",
            fg=GREEN,
            font=(self.ui_font_family, 8, "bold"),
        ).grid(row=0, column=2, sticky="e", padx=12)

    def _set_status(self, text):
        try:
            self.status_label.configure(text=text)
            self.stage_text.configure(text=text)
        except Exception:
            pass

        self._stage_from_text(text)

        if hasattr(self, "log_text"):
            try:
                self.log_text.configure(state="normal")
                self.log_text.insert(
                    "end", f"[{time.strftime('%H:%M:%S')}]  {text}\n"
                )
                self.log_text.see("end")
                self.log_text.configure(state="disabled")
            except Exception:
                pass

    def _stage_from_text(self, text):
        t = text.lower()
        idx = self._stage_index
        if any(k in t for k in ("โหลด", "วิเคราะห์", "prepare", "analy")):
            idx = max(idx, 0)
        if any(k in t for k in ("noise", "denoise", "cleanup")):
            idx = max(idx, 1)
        if any(k in t for k in ("contrast", "color", "สี")):
            idx = max(idx, 2)
        if any(k in t for k in ("edge", "logo", "graphic", "ขอบ")):
            idx = max(idx, 3)
        if any(
            k in t
            for k in (
                "real-esrgan",
                "upscale",
                "resize",
                "detail",
                "รายละเอียด",
                "ขนาดปลายทาง",
            )
        ):
            idx = max(idx, 4)
        if any(k in t for k in ("baseline", "บันทึก", "เสร็จ", "complete")):
            idx = max(idx, 5)

        self._stage_index = idx
        for i, led in enumerate(self._stage_labels):
            led.configure(
                fg=GREEN if i < idx else (BLUE if i == idx else "#647483")
            )

        if any(k in t for k in ("เสร็จ", "complete")):
            for led in self._stage_labels:
                led.configure(fg=GREEN)

    def stop_and_clear(self):
        self._stop.set()
        self._set_status("STOP requested — กำลังหยุดและล้างงาน")
        self.after(400, self._clear_workspace)

    def _clear_workspace(self):
        self.files = []
        self.current_index = None
        self._last_result = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.left_image.configure(image="", text="No preview")
        self.right_image.configure(image="", text="No preview")
        self.left_caption.configure(text="ยังไม่ได้เลือกภาพ")
        self.right_caption.configure(text="ผลลัพธ์ AI จะแสดงที่นี่")
        self.progress["value"] = 0
        self._stage_index = 0
        for led in self._stage_labels:
            led.configure(fg="#647483")
        self._set_status("พร้อมใช้งาน — เพิ่มภาพเพื่อเริ่ม")

    def save_last_as(self):
        if not self._last_result or not self._last_result.exists():
            messagebox.showinfo(APP_DISPLAY_NAME, "ยังไม่มีผลลัพธ์ให้บันทึก")
            return

        ext = self._last_result.suffix
        dest = filedialog.asksaveasfilename(
            title="บันทึกผลลัพธ์เป็น…",
            defaultextension=ext,
            initialfile=self._last_result.name,
            filetypes=[("Output file", f"*{ext}"), ("All files", "*.*")],
        )
        if dest:
            shutil.copy2(self._last_result, dest)
            self._set_status(f"บันทึกไฟล์: {dest}")

    def open_last_result(self):
        if not self._last_result or not self._last_result.exists():
            messagebox.showinfo(APP_DISPLAY_NAME, "ยังไม่มีไฟล์ผลลัพธ์")
            return
        try:
            if os.name == "nt":
                os.startfile(self._last_result)  # type: ignore[attr-defined]
            else:
                self.open_output_folder()
        except Exception as exc:
            messagebox.showerror(APP_DISPLAY_NAME, str(exc))

    def show_help(self):
        messagebox.showinfo(
            APP_DISPLAY_NAME,
            "1) Import Image\n"
            "2) กำหนด Width / Height / DPI\n"
            "3) เลือก AI Scale\n"
            "4) กด AI ENHANCE TO TARGET\n"
            "5) ตรวจ Before / After และ Export\n\n"
            "V1 Quality Core รักษาแกนประมวลผลเดิมไว้เป็นค่าเริ่มต้น",
        )


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
