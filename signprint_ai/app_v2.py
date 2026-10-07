from __future__ import annotations

import os
import base64
import io
import queue
import threading
import time
import tempfile
import subprocess
from dataclasses import replace
from pathlib import Path
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk, ImageChops, ImageCms
import numpy as np

from .pipeline import PrintEnhancementPipeline
from .processing import EnhanceSettings, print_pixels

APP_NAME = "Niyomsil Design AI Enhancer"
APP_VERSION = "V2.0 UI Build"
BRAND_THAI = "นิยมศิลป์ดีไซน์"
BRAND_EN = "NIYOMSIL DESIGN"
IMAGE_TYPES = [("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"), ("All files", "*.*")]


def resource_root() -> Path:
    # PyInstaller extracts bundled data under _MEIPASS in onedir/onefile builds.
    if hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS"))
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} — {APP_VERSION}")
        self.geometry("1600x920")
        self.minsize(1180, 720)

        self.pipeline = PrintEnhancementPipeline()
        self.files: list[Path] = []
        self.current_index: int | None = None
        self.original_ratio = 1.0
        self._syncing_size = False
        self._stop = threading.Event()
        self._events: queue.Queue = queue.Queue()
        self._preview_job = None
        self._photo_left = None
        self._photo_right = None
        self._last_result: Path | None = None
        self._brand_logo_photo = None
        self._app_started_at = time.monotonic()
        self._processing_started_at = None
        self.hardware_info = self._detect_hardware()

        self.configure(bg="#080B0F")
        self._build_style()
        self._build_ui()
        self._enable_drag_drop()
        self.after(80, self._drain_events)
        self.after(1000, self._tick_elapsed)
        self._set_status("พร้อมใช้งาน")

    def _pick_ui_font(self) -> str:
        """Choose a Thai-friendly Windows UI font and avoid italic fallback."""
        try:
            available = {name.lower(): name for name in tkfont.families(self)}
        except tk.TclError:
            available = {}
        for wanted in ("Tahoma", "Leelawadee UI", "Segoe UI", "Arial"):
            if wanted.lower() in available:
                return available[wanted.lower()]
        return "TkDefaultFont"

    def _load_brand_logo(self, max_size: tuple[int, int] = (150, 86)):
        try:
            p = resource_root() / "assets" / "logo.b64"
            raw = base64.b64decode(p.read_text(encoding="utf-8").strip())
            im = Image.open(io.BytesIO(raw)).convert("RGBA")

            # Remove the white background from the user's original logo while
            # preserving red/dark artwork and anti-aliased edges.
            data = np.array(im, dtype=np.uint8)
            rgb = data[..., :3]
            white_distance = 255 - rgb.min(axis=2)
            alpha = np.clip((white_distance.astype(np.float32) - 3.0) * 18.0, 0, 255).astype(np.uint8)
            data[..., 3] = np.minimum(data[..., 3], alpha)
            im = Image.fromarray(data, "RGBA")
            bbox = im.getchannel("A").getbbox()
            if bbox:
                im = im.crop(bbox)
            im.thumbnail(max_size, Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    def _find_installed_icc_profiles(self) -> dict[str, str]:
        profiles: dict[str, str] = {}
        if os.name == "nt":
            windows = Path(os.environ.get("WINDIR", r"C:\Windows"))
            color_dir = windows / "System32" / "spool" / "drivers" / "color"
            if color_dir.exists():
                for p in sorted(list(color_dir.glob("*.icc")) + list(color_dir.glob("*.icm"))):
                    try:
                        opened = ImageCms.getOpenProfile(str(p))
                        color_space = str(getattr(opened.profile, "xcolor_space", "")).upper()
                        if "CMYK" in color_space:
                            profiles[p.name] = str(p)
                    except Exception:
                        continue
        return profiles

    def _choose_icc_profile(self):
        p = filedialog.askopenfilename(
            title="เลือก ICC / ICM Profile สำหรับ CMYK",
            filetypes=[
                ("ICC/ICM profile", "*.icc;*.icm"),
                ("ICC profile", "*.icc"),
                ("ICM profile", "*.icm"),
                ("All files", "*.*"),
            ],
        )
        if p:
            self.icc_profile_path_var.set(p)
            self.icc_profile_name_var.set(Path(p).name)
            self._settings_changed(schedule_preview=False)

    def _installed_icc_selected(self, _event=None):
        name = self.icc_profile_name_var.get()
        path = self._installed_icc_profiles.get(name)
        if path:
            self.icc_profile_path_var.set(path)
            self._settings_changed(schedule_preview=False)

    def _color_mode_changed(self, _event=None):
        self._settings_changed(schedule_preview=False)

    def _detect_hardware(self) -> dict[str, str]:
        info = {
            "gpu": "Vulkan / Auto",
            "vram": "—",
            "engine": "Real-ESRGAN NCNN/Vulkan",
            "device": "Vulkan (Auto)",
        }
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=flags,
            )
            if result.returncode == 0 and result.stdout.strip():
                first = result.stdout.strip().splitlines()[0]
                parts = [x.strip() for x in first.split(",", 1)]
                info["gpu"] = parts[0]
                if len(parts) > 1:
                    try:
                        mib = int(parts[1])
                        info["vram"] = f"{mib / 1024:.0f} GB"
                    except Exception:
                        info["vram"] = f"{parts[1]} MB"
        except Exception:
            pass
        return info

    def _tick_elapsed(self):
        try:
            start = self._processing_started_at or self._app_started_at
            elapsed = max(0, int(time.monotonic() - start))
            h, rem = divmod(elapsed, 3600)
            m, s = divmod(rem, 60)
            if hasattr(self, "elapsed_var"):
                self.elapsed_var.set(f"{h:02d}:{m:02d}:{s:02d}")
        finally:
            self.after(1000, self._tick_elapsed)

    def _section(self, parent, number: str, title: str):
        shell = tk.Frame(parent, bg="#111820", bd=1, relief="solid", highlightthickness=0)
        shell.pack(fill="x", pady=(0, 8), padx=2)
        head = tk.Frame(shell, bg="#D71920", height=31)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(
            head,
            text=f"{number}. {title}",
            bg="#D71920",
            fg="white",
            font=(self.ui_font_family, 10, "bold"),
            anchor="w",
            padx=10,
        ).pack(fill="both", expand=True)
        body = tk.Frame(shell, bg="#111820", padx=9, pady=8)
        body.pack(fill="x")
        return body

    def _top_action(self, parent, title: str, subtitle: str, command, accent="#D71920"):
        box = tk.Frame(parent, bg="#0D1319", bd=1, relief="solid", highlightthickness=1, highlightbackground=accent)
        box.pack(side="left", padx=4, pady=8)
        btn = tk.Button(
            box,
            text=title,
            command=command,
            bg="#0D1319",
            fg="#FFFFFF",
            activebackground=accent,
            activeforeground="#FFFFFF",
            relief="flat",
            bd=0,
            width=10,
            font=(self.ui_font_family, 10, "bold"),
            cursor="hand2",
        )
        btn.pack(padx=8, pady=(8, 1))
        tk.Label(
            box,
            text=subtitle,
            bg="#0D1319",
            fg="#AEB7C0",
            font=(self.ui_font_family, 8, "normal"),
        ).pack(pady=(0, 7))
        return box

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        family = self._pick_ui_font()
        self.ui_font_family = family
        body = (family, 9, "normal")
        body_bold = (family, 9, "bold")

        for name, size, weight in (
            ("TkDefaultFont", 9, "normal"),
            ("TkTextFont", 9, "normal"),
            ("TkMenuFont", 9, "normal"),
            ("TkHeadingFont", 9, "bold"),
            ("TkCaptionFont", 9, "bold"),
            ("TkSmallCaptionFont", 8, "normal"),
            ("TkIconFont", 9, "normal"),
            ("TkTooltipFont", 8, "normal"),
        ):
            try:
                font = tkfont.nametofont(name)
                font.configure(family=family, size=size, weight=weight, slant="roman")
            except tk.TclError:
                pass

        self.option_add("*Font", body)
        self.option_add("*TCombobox*Listbox.background", "#141B22")
        self.option_add("*TCombobox*Listbox.foreground", "#FFFFFF")
        self.option_add("*TCombobox*Listbox.selectBackground", "#C9151B")
        self.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

        style.configure(".", font=body, background="#0B1015", foreground="#E9EDF1")
        style.configure("TFrame", background="#0B1015")
        style.configure("TLabel", background="#0B1015", foreground="#E9EDF1")
        style.configure("TButton", font=body_bold, background="#18212A", foreground="#FFFFFF", padding=(8, 5), borderwidth=1)
        style.map("TButton", background=[("active", "#27333E"), ("pressed", "#C9151B")])
        style.configure("Red.TButton", font=body_bold, background="#D71920", foreground="#FFFFFF", padding=(12, 8), borderwidth=0)
        style.map("Red.TButton", background=[("active", "#F01F27"), ("pressed", "#A50E14")])
        style.configure("Dark.TCheckbutton", background="#111820", foreground="#FFFFFF", font=body)
        style.map("Dark.TCheckbutton", background=[("active", "#111820")])
        style.configure("Dark.TEntry", fieldbackground="#0B1015", foreground="#FFFFFF", insertcolor="#FFFFFF", bordercolor="#3A4650")
        style.configure("Dark.TCombobox", fieldbackground="#0B1015", background="#18212A", foreground="#FFFFFF", arrowcolor="#FFFFFF", bordercolor="#3A4650")
        style.map("Dark.TCombobox", fieldbackground=[("readonly", "#0B1015")], foreground=[("readonly", "#FFFFFF")])
        style.configure("Treeview", background="#10171D", fieldbackground="#10171D", foreground="#E8EDF2", rowheight=29, borderwidth=0)
        style.configure("Treeview.Heading", background="#171F27", foreground="#FFFFFF", font=body_bold, relief="flat")
        style.map("Treeview", background=[("selected", "#7C1117")], foreground=[("selected", "#FFFFFF")])
        style.configure("Brand.Horizontal.TProgressbar", background="#00C853", troughcolor="#26323C", bordercolor="#26323C", lightcolor="#00C853", darkcolor="#00A844")

    def _build_ui(self):
        root = tk.Frame(self, bg="#080B0F", padx=7, pady=5)
        root.pack(fill="both", expand=True)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(1, weight=1)

        # ===== V2 HEADER =====
        head = tk.Frame(root, bg="#080B0F", height=132, highlightthickness=1, highlightbackground="#27313A")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 7))
        head.grid_propagate(False)

        art = tk.Canvas(head, bg="#080B0F", highlightthickness=0, bd=0)
        art.place(relx=0, rely=0, relwidth=1, relheight=1)
        art.create_polygon(0, 0, 780, 0, 650, 132, 0, 132, fill="#111820", outline="")
        art.create_polygon(355, 0, 760, 0, 650, 132, 485, 132, fill="#26080B", outline="")
        art.create_polygon(520, 0, 720, 0, 595, 132, 545, 132, fill="#5D0A0F", outline="")
        art.create_rectangle(0, 127, 1900, 132, fill="#E31B23", outline="")

        self._brand_logo_photo = self._load_brand_logo((118, 108))
        if self._brand_logo_photo:
            tk.Label(head, image=self._brand_logo_photo, bg="#111820", bd=0).place(x=20, y=10)
            try:
                self.iconphoto(True, self._brand_logo_photo)
            except Exception:
                pass

        title = tk.Frame(head, bg="#111820")
        title.place(x=145, y=17)
        line1 = tk.Frame(title, bg="#111820")
        line1.pack(anchor="w")
        tk.Label(line1, text="นิยมศิลป์", bg="#111820", fg="#FFFFFF",
                 font=(self.ui_font_family, 24, "bold")).pack(side="left")
        tk.Label(line1, text="ดีไซน์", bg="#111820", fg="#FF2028",
                 font=(self.ui_font_family, 24, "bold")).pack(side="left")
        tk.Label(line1, text=" V2.0", bg="#111820", fg="#FFFFFF",
                 font=(self.ui_font_family, 16, "bold")).pack(side="left", padx=(6, 0), pady=(8, 0))
        tk.Label(
            title,
            text="โปรแกรมปรับปรุงภาพสำหรับงานป้ายไวนิล • AI Image Enhancer",
            bg="#111820",
            fg="#E0E4E8",
            font=(self.ui_font_family, 10, "bold"),
        ).pack(anchor="w", pady=(3, 0))

        actions = tk.Frame(head, bg="#080B0F")
        actions.place(relx=0.47, y=6)
        self._top_action(actions, "เปิดไฟล์", "Open Image", self.choose_files)
        self._top_action(actions, "ตั้งค่า", "Settings", lambda: self.left_canvas.yview_moveto(0.35), accent="#3B82F6")
        self._top_action(actions, "ประมวลผล", "Enhance", self.start_processing)
        self._top_action(actions, "ผลลัพธ์", "Output", self.open_output_folder, accent="#4B5563")
        self._top_action(actions, "โฟลเดอร์", "Open Folder", self.open_output_folder, accent="#2563EB")

        hw = tk.Frame(head, bg="#10161C", bd=1, relief="solid", highlightthickness=1, highlightbackground="#58636E")
        hw.place(relx=0.985, y=18, anchor="ne", width=320, height=91)
        tk.Label(hw, text="GPU", bg="#10161C", fg="#D7DEE5", font=(self.ui_font_family, 8, "bold")).place(x=12, y=10)
        tk.Label(hw, text=self.hardware_info["gpu"], bg="#10161C", fg="#7CFF4A", font=(self.ui_font_family, 8, "bold")).place(x=62, y=10)
        tk.Label(hw, text="VRAM", bg="#10161C", fg="#D7DEE5", font=(self.ui_font_family, 8, "bold")).place(x=12, y=30)
        tk.Label(hw, text=self.hardware_info["vram"], bg="#10161C", fg="#7CFF4A", font=(self.ui_font_family, 8, "bold")).place(x=62, y=30)
        tk.Label(hw, text="AI Engine", bg="#10161C", fg="#D7DEE5", font=(self.ui_font_family, 8, "bold")).place(x=12, y=50)
        tk.Label(hw, text=self.hardware_info["engine"], bg="#10161C", fg="#7CFF4A", font=(self.ui_font_family, 8, "bold")).place(x=75, y=50)
        tk.Label(hw, text="Device", bg="#10161C", fg="#D7DEE5", font=(self.ui_font_family, 8, "bold")).place(x=12, y=70)
        tk.Label(hw, text=self.hardware_info["device"], bg="#10161C", fg="#7CFF4A", font=(self.ui_font_family, 8, "bold")).place(x=62, y=70)

        # ===== LEFT CONTROL COLUMN =====
        left_outer = tk.Frame(root, bg="#080B0F", width=345)
        left_outer.grid(row=1, column=0, sticky="nsw", padx=(0, 7))
        left_outer.grid_propagate(False)
        self.left_canvas = tk.Canvas(left_outer, bg="#080B0F", highlightthickness=0, width=330)
        sb = ttk.Scrollbar(left_outer, orient="vertical", command=self.left_canvas.yview)
        self.left_inner = tk.Frame(self.left_canvas, bg="#080B0F")
        self.left_inner.bind("<Configure>", lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self.left_canvas.create_window((0, 0), window=self.left_inner, anchor="nw", width=326)
        self.left_canvas.configure(yscrollcommand=sb.set)
        self.left_canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._build_controls(self.left_inner)

        # ===== RIGHT WORKSPACE =====
        work = tk.Frame(root, bg="#080B0F")
        work.grid(row=1, column=1, sticky="nsew")
        work.rowconfigure(0, weight=3)
        work.rowconfigure(1, weight=2)
        work.columnconfigure(0, weight=1)

        # 5. Preview
        preview_shell = tk.Frame(work, bg="#111820", bd=1, relief="solid")
        preview_shell.grid(row=0, column=0, sticky="nsew")
        preview_shell.rowconfigure(1, weight=1)
        preview_shell.columnconfigure(0, weight=1)

        phead = tk.Frame(preview_shell, bg="#111820", height=37)
        phead.grid(row=0, column=0, sticky="ew")
        phead.grid_propagate(False)
        tk.Label(phead, text="5. ตัวอย่างภาพ", bg="#D71920", fg="white",
                 font=(self.ui_font_family, 10, "bold"), padx=12).pack(side="left", fill="y")
        ttk.Button(phead, text="−", command=self._refresh_preview_images, width=4).pack(side="left", padx=(8, 3), pady=4)
        ttk.Button(phead, text="+", command=self._refresh_preview_images, width=4).pack(side="left", padx=3, pady=4)
        ttk.Button(phead, text="พอดีหน้าจอ", command=self._refresh_preview_images).pack(side="left", padx=3, pady=4)
        ttk.Button(phead, text="1:1", command=self._refresh_preview_images, width=6).pack(side="left", padx=3, pady=4)
        self.auto_preview = tk.BooleanVar(value=True)
        ttk.Checkbutton(phead, text="Auto Preview", variable=self.auto_preview, style="Dark.TCheckbutton").pack(side="right", padx=10)

        compare = tk.Frame(preview_shell, bg="#0B1015")
        compare.grid(row=1, column=0, sticky="nsew", padx=7, pady=(0, 7))
        compare.rowconfigure(0, weight=1)
        compare.columnconfigure(0, weight=1)
        compare.columnconfigure(1, weight=1)

        left_pane = tk.Frame(compare, bg="#0B1015", bd=1, relief="solid")
        right_pane = tk.Frame(compare, bg="#0B1015", bd=1, relief="solid")
        left_pane.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        right_pane.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        for pane in (left_pane, right_pane):
            pane.rowconfigure(1, weight=1)
            pane.columnconfigure(0, weight=1)

        tk.Label(left_pane, text="ภาพต้นฉบับ (Before)", bg="#5C6268", fg="#FFFFFF",
                 font=(self.ui_font_family, 10, "bold"), pady=6).grid(row=0, column=0, sticky="ew")
        tk.Label(right_pane, text="ภาพหลังปรับปรุง (After)", bg="#D71920", fg="#FFFFFF",
                 font=(self.ui_font_family, 10, "bold"), pady=6).grid(row=0, column=0, sticky="ew")

        self.left_image = tk.Label(left_pane, bg="#171717", anchor="center", bd=0)
        self.right_image = tk.Label(right_pane, bg="#171717", anchor="center", bd=0)
        self.left_image.grid(row=1, column=0, sticky="nsew")
        self.right_image.grid(row=1, column=0, sticky="nsew")

        self.left_caption = tk.Label(left_pane, text="ยังไม่ได้เลือกภาพ", bg="#20262B", fg="#D7DDE2", pady=6)
        self.right_caption = tk.Label(right_pane, text="V1 Baseline • รักษาแกนประมวลผลเดิม", bg="#4B0D10", fg="#FFFFFF", pady=6)
        self.left_caption.grid(row=2, column=0, sticky="ew")
        self.right_caption.grid(row=2, column=0, sticky="ew")
        self.left_image.bind("<Configure>", lambda e: self._refresh_preview_images())
        self.right_image.bind("<Configure>", lambda e: self._refresh_preview_images())

        # 6. Queue / progress
        queue_shell = tk.Frame(work, bg="#111820", bd=1, relief="solid")
        queue_shell.grid(row=1, column=0, sticky="nsew", pady=(7, 0))
        queue_shell.rowconfigure(1, weight=1)
        queue_shell.columnconfigure(0, weight=1)

        qhead = tk.Frame(queue_shell, bg="#111820", height=36)
        qhead.grid(row=0, column=0, columnspan=2, sticky="ew")
        qhead.grid_propagate(False)
        tk.Label(qhead, text="6. รายการไฟล์ที่ดำเนินการ", bg="#D71920", fg="#FFFFFF",
                 font=(self.ui_font_family, 10, "bold"), padx=12).pack(side="left", fill="y")
        ttk.Button(qhead, text="เพิ่มไฟล์", command=self.choose_files).pack(side="left", padx=(10, 4), pady=4)
        ttk.Button(qhead, text="ลบที่เลือก", command=self.remove_selected).pack(side="left", padx=4, pady=4)
        ttk.Button(qhead, text="เปิดโฟลเดอร์ผลลัพธ์", command=self.open_output_folder).pack(side="left", padx=4, pady=4)
        tk.Label(qhead, text="ลากไฟล์ภาพมาวางในหน้าต่างนี้ได้", bg="#111820", fg="#BFC8D0").pack(side="right", padx=10)

        cols = ("name", "original", "output", "status", "progress", "result")
        self.tree = ttk.Treeview(queue_shell, columns=cols, show="headings", selectmode="browse")
        headings = {
            "name": "ชื่อไฟล์",
            "original": "ขนาดต้นฉบับ",
            "output": "ขนาดปลายทาง",
            "status": "สถานะ",
            "progress": "ความคืบหน้า",
            "result": "ผลลัพธ์",
        }
        for key, text_value in headings.items():
            self.tree.heading(key, text=text_value)
        self.tree.column("name", width=260)
        self.tree.column("original", width=140, anchor="center")
        self.tree.column("output", width=160, anchor="center")
        self.tree.column("status", width=180, anchor="center")
        self.tree.column("progress", width=110, anchor="center")
        self.tree.column("result", width=150, anchor="center")
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        tree_sb = ttk.Scrollbar(queue_shell, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)
        tree_sb.grid(row=1, column=1, sticky="ns")

        # ===== 7/8/9 OUTPUT STRIP =====
        export = tk.Frame(root, bg="#10161C", bd=1, relief="solid")
        export.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(7, 0))
        export.columnconfigure(2, weight=1)

        self.format_var = tk.StringVar(value="PNG")
        self.color_mode_var = tk.StringVar(value="RGB")
        self.output_dir_var = tk.StringVar(value="")
        self._installed_icc_profiles = self._find_installed_icc_profiles()
        self.icc_profile_name_var = tk.StringVar(value="")
        self.icc_profile_path_var = tk.StringVar(value="")

        b7 = tk.Frame(export, bg="#10161C", padx=8, pady=6)
        b7.grid(row=0, column=0, sticky="w")
        tk.Label(b7, text="7. รูปแบบการส่งออก", bg="#10161C", fg="#E8EDF2", font=(self.ui_font_family, 8, "bold")).pack(anchor="w")
        fmt = ttk.Combobox(b7, textvariable=self.format_var, values=("PNG", "TIFF", "PDF", "JPG"),
                           state="readonly", width=17, style="Dark.TCombobox")
        fmt.pack(pady=(3, 0))

        b8 = tk.Frame(export, bg="#10161C", padx=8, pady=6)
        b8.grid(row=0, column=1, sticky="w")
        tk.Label(b8, text="8. โหมดสี / ICC Profile", bg="#10161C", fg="#E8EDF2", font=(self.ui_font_family, 8, "bold")).grid(row=0, column=0, columnspan=3, sticky="w")
        color_mode = ttk.Combobox(b8, textvariable=self.color_mode_var, values=("RGB", "CMYK"),
                                  state="readonly", width=13, style="Dark.TCombobox")
        color_mode.grid(row=1, column=0, padx=(0, 5), pady=(3, 0))
        color_mode.bind("<<ComboboxSelected>>", self._color_mode_changed)
        icc_combo = ttk.Combobox(
            b8,
            textvariable=self.icc_profile_name_var,
            values=tuple(self._installed_icc_profiles.keys()),
            state="readonly",
            width=28,
            style="Dark.TCombobox",
        )
        icc_combo.grid(row=1, column=1, padx=5, pady=(3, 0))
        icc_combo.bind("<<ComboboxSelected>>", self._installed_icc_selected)
        ttk.Button(b8, text="เลือก ICC…", command=self._choose_icc_profile).grid(row=1, column=2, padx=(5, 0), pady=(3, 0))

        b9 = tk.Frame(export, bg="#10161C", padx=8, pady=6)
        b9.grid(row=0, column=2, sticky="ew")
        tk.Label(b9, text="9. โฟลเดอร์ปลายทาง", bg="#10161C", fg="#E8EDF2", font=(self.ui_font_family, 8, "bold")).pack(anchor="w")
        row9 = tk.Frame(b9, bg="#10161C")
        row9.pack(fill="x", pady=(3, 0))
        self.output_dir_label = tk.Label(row9, text="โฟลเดอร์เดียวกับภาพต้นฉบับ", bg="#0B1015", fg="#E8EDF2",
                                         anchor="w", padx=8, bd=1, relief="solid")
        self.output_dir_label.pack(side="left", fill="x", expand=True, ipady=5)
        ttk.Button(row9, text="เลือกโฟลเดอร์", command=self.choose_output_dir).pack(side="left", padx=(6, 0))

        # ===== STATUS BAR =====
        status = tk.Frame(root, bg="#071016", height=31)
        status.grid(row=3, column=0, columnspan=2, sticky="ew")
        status.grid_propagate(False)
        status.columnconfigure(2, weight=1)

        self.status_label = tk.Label(status, text="", bg="#071016", fg="#DDE6EC", anchor="w")
        self.status_label.grid(row=0, column=0, sticky="w", padx=(10, 8))
        tk.Label(
            status,
            text=f"GPU: {self.hardware_info['gpu']}  |  AI Engine: {self.hardware_info['engine']}  |  Device: {self.hardware_info['device']}",
            bg="#071016", fg="#B6C0C8", anchor="w"
        ).grid(row=0, column=1, sticky="w")

        self.progress = ttk.Progressbar(status, mode="determinate", maximum=100, style="Brand.Horizontal.TProgressbar")
        self.progress.grid(row=0, column=2, sticky="ew", padx=12, pady=8)
        self.elapsed_var = tk.StringVar(value="00:00:00")
        tk.Label(status, textvariable=self.elapsed_var, bg="#071016", fg="#DDE6EC", width=9).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(status, text="หยุด", command=self.stop_processing).grid(row=0, column=4, padx=(0, 8), pady=3)

    def _build_controls(self, parent):
        # 1. Input and print size
        size = self._section(parent, "1", "เลือกไฟล์และขนาดงานพิมพ์")
        ttk.Button(size, text="เลือกไฟล์ภาพ…", command=self.choose_files).grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 7))

        self.use_print_size = tk.BooleanVar(value=False)
        ttk.Checkbutton(size, text="กำหนดขนาดงานพิมพ์", variable=self.use_print_size,
                        command=self._settings_changed, style="Dark.TCheckbutton").grid(row=1, column=0, columnspan=4, sticky="w")

        self.width_var = tk.StringVar(value="200")
        self.height_var = tk.StringVar(value="80")
        self.dpi_var = tk.StringVar(value="150")
        self.unit_var = tk.StringVar(value="cm")
        self.lock_ratio = tk.BooleanVar(value=True)

        tk.Label(size, text="Width", bg="#111820", fg="#E8EDF2").grid(row=2, column=0, sticky="w", pady=3)
        w = ttk.Entry(size, textvariable=self.width_var, width=9, style="Dark.TEntry")
        w.grid(row=2, column=1, sticky="ew", padx=(5, 8))
        tk.Label(size, text="Height", bg="#111820", fg="#E8EDF2").grid(row=2, column=2, sticky="w")
        h = ttk.Entry(size, textvariable=self.height_var, width=9, style="Dark.TEntry")
        h.grid(row=2, column=3, sticky="ew", padx=(5, 0))

        tk.Label(size, text="DPI", bg="#111820", fg="#E8EDF2").grid(row=3, column=0, sticky="w", pady=3)
        dpi = ttk.Combobox(size, textvariable=self.dpi_var, values=(72, 96, 100, 150, 200, 300, 600),
                           width=7, style="Dark.TCombobox")
        dpi.grid(row=3, column=1, sticky="ew", padx=(5, 8))
        tk.Label(size, text="หน่วย", bg="#111820", fg="#E8EDF2").grid(row=3, column=2, sticky="w")
        unit = ttk.Combobox(size, textvariable=self.unit_var, values=("mm", "cm", "m", "inch"),
                            state="readonly", width=7, style="Dark.TCombobox")
        unit.grid(row=3, column=3, sticky="ew", padx=(5, 0))

        ttk.Checkbutton(size, text="ล็อกอัตราส่วน Width / Height", variable=self.lock_ratio,
                        style="Dark.TCheckbutton").grid(row=4, column=0, columnspan=4, sticky="w", pady=(5, 0))
        self.pixel_info = tk.Label(size, text="ขนาดพิกเซลปลายทาง: ตาม AI Upscale", bg="#111820", fg="#B8C2CB", anchor="w")
        self.pixel_info.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(5, 0))
        size.columnconfigure(1, weight=1)
        size.columnconfigure(3, weight=1)
        w.bind("<KeyRelease>", lambda e: self._size_edited("w"))
        h.bind("<KeyRelease>", lambda e: self._size_edited("h"))
        dpi.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())
        dpi.bind("<KeyRelease>", lambda e: self._settings_changed())
        unit.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        # 2. AI quality — same V1 settings/semantics, redesigned only.
        ai = self._section(parent, "2", "AI ปรับปรุงคุณภาพ")
        self.scale_var = tk.StringVar(value="4x")
        tk.Label(ai, text="AI Upscale", bg="#111820", fg="#FFFFFF").grid(row=0, column=0, sticky="w")
        scale = ttk.Combobox(ai, textvariable=self.scale_var, values=("2x", "4x", "8x"),
                             state="readonly", width=17, style="Dark.TCombobox")
        scale.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        scale.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        self.v1_mode = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            ai,
            text="V1 Baseline (แนะนำ) — รักษารายละเอียดเดิม",
            variable=self.v1_mode,
            command=self._settings_changed,
            style="Dark.TCheckbutton",
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(7, 2))
        tk.Label(ai, text="Real-ESRGAN 4x เป็นแกนหลัก • ไม่เปลี่ยน Pipeline V1",
                 bg="#111820", fg="#84D8FF", anchor="w").grid(row=2, column=0, columnspan=2, sticky="ew")
        ai.columnconfigure(1, weight=1)

        # 3. Existing advanced controls, unchanged values/logic.
        quality = self._section(parent, "3", "การตั้งค่าขั้นสูง")
        self.denoise_var = tk.IntVar(value=18)
        self.flat_var = tk.IntVar(value=18)
        self.text_var = tk.IntVar(value=28)
        self.contrast_var = tk.IntVar(value=8)
        self.sharp_var = tk.IntVar(value=26)
        self.sat_var = tk.IntVar(value=0)
        self._slider(quality, "ลด Noise / เม็ดสี", self.denoise_var, 0)
        self._slider(quality, "เกลี่ยพื้นสีเรียบ", self.flat_var, 1)
        self._slider(quality, "ตัวอักษร / โลโก้", self.text_var, 2)
        self._slider(quality, "Local Contrast", self.contrast_var, 3)
        self._slider(quality, "Anti-Halo Sharpen", self.sharp_var, 4)
        self._slider(quality, "Saturation", self.sat_var, 5, -30, 30)

        # 4. Device status — display only; processing backend is untouched.
        device = self._section(parent, "4", "เลือกอุปกรณ์ประมวลผล")
        tk.Label(device, text="AUTO (แนะนำ)", bg="#0B1015", fg="#FFFFFF", anchor="w",
                 padx=8, pady=7, bd=1, relief="solid").pack(fill="x")
        tk.Label(device, text=f"GPU  {self.hardware_info['gpu']}  ({self.hardware_info['vram']})",
                 bg="#111820", fg="#9BFF70", anchor="w").pack(fill="x", pady=(6, 0))
        tk.Label(device, text=f"Device  {self.hardware_info['device']}",
                 bg="#111820", fg="#BFC8D0", anchor="w").pack(fill="x", pady=(2, 0))

        actions = tk.Frame(parent, bg="#080B0F")
        actions.pack(fill="x", padx=2, pady=(0, 10))
        ttk.Button(actions, text="▶  เริ่มปรับภาพ  /  AI Enhance", command=self.start_processing,
                   style="Red.TButton").pack(fill="x", ipady=5)
        row = tk.Frame(actions, bg="#080B0F")
        row.pack(fill="x", pady=(5, 0))
        ttk.Button(row, text="หยุดการทำงาน", command=self.stop_processing).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ttk.Button(row, text="ล้างรายการ", command=lambda: [self.tree.delete(i) for i in self.tree.get_children()]).pack(side="left", fill="x", expand=True, padx=(3, 0))

    def _slider(self, parent, text, var, row, lo=0, hi=100):
        tk.Label(parent, text=text, bg="#111820", fg="#E8EDF2", anchor="w").grid(row=row, column=0, sticky="w")
        value = tk.Label(parent, text=str(var.get()), bg="#111820", fg="#FFFFFF", width=4, anchor="e")
        value.grid(row=row, column=2, sticky="e")
        scale = ttk.Scale(parent, from_=lo, to=hi, variable=var, orient="horizontal")
        scale.grid(row=row, column=1, sticky="ew", padx=6, pady=3)
        def changed(_=None):
            value.config(text=str(round(var.get())))
            self._settings_changed()
        scale.configure(command=changed)
        parent.columnconfigure(1, weight=1)

    def _enable_drag_drop(self):
        # windnd uses the native Windows drop target and works with a normal Tk root.
        # It is optional so source mode remains usable on macOS/Linux.
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
            return

    def choose_files(self):
        paths = filedialog.askopenfilenames(title="เลือกภาพ", filetypes=IMAGE_TYPES)
        if paths:
            self.add_files(paths)

    def add_files(self, paths):
        added = 0
        for raw in paths:
            p = Path(raw)
            if p.exists() and p not in self.files:
                try:
                    with Image.open(p) as im:
                        size = im.size
                except Exception:
                    continue
                self.files.append(p)
                iid = str(len(self.files)-1)
                self.tree.insert("", "end", iid=iid, values=(p.name, f"{size[0]:,} × {size[1]:,}", "—", "พร้อม", "0%", "-"))
                added += 1
        if added and self.current_index is None:
            self.tree.selection_set("0")
            self.tree.focus("0")
            self._select_index(0)
        self._set_status(f"เพิ่มภาพแล้ว {added} ไฟล์")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = int(sel[0])
        # Rebuild list/tree so iid remains contiguous.
        self.files.pop(idx)
        self.current_index = None
        for item in self.tree.get_children():
            self.tree.delete(item)
        old = list(self.files)
        self.files = []
        self.add_files(old)
        if not self.files:
            self.left_image.configure(image="")
            self.right_image.configure(image="")
            self.left_caption.configure(text="ยังไม่ได้เลือกภาพ")

    def _on_tree_select(self, _event=None):
        sel = self.tree.selection()
        if sel:
            self._select_index(int(sel[0]))

    def _select_index(self, idx: int):
        if idx < 0 or idx >= len(self.files):
            return
        self.current_index = idx
        p = self.files[idx]
        try:
            with Image.open(p) as im:
                w, h = im.size
            self.original_ratio = w / max(1, h)
            if self.lock_ratio.get():
                try:
                    width = float(self.width_var.get())
                    self.height_var.set(self._fmt(width / self.original_ratio))
                except ValueError:
                    pass
            self.left_caption.configure(text=f"{p.name}   •   {w:,} × {h:,} px")
            self._refresh_preview_images()
            self._settings_changed(schedule_preview=True)
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))

    def _fmt(self, value: float) -> str:
        return f"{value:.4f}".rstrip("0").rstrip(".")

    def _size_edited(self, side: str):
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

    def _settings_changed(self, schedule_preview=True):
        self._update_pixel_info()
        self._update_tree_output_sizes()
        if schedule_preview and self.auto_preview.get() and self.current_index is not None:
            if self._preview_job:
                self.after_cancel(self._preview_job)
            self._preview_job = self.after(550, self.update_preview)

    def _update_pixel_info(self):
        if not self.use_print_size.get():
            self.pixel_info.configure(text="ขนาดพิกเซลปลายทาง: ตาม AI Upscale")
            return
        try:
            px = print_pixels(float(self.width_var.get()), float(self.height_var.get()), self.unit_var.get(), int(float(self.dpi_var.get())))
            self.pixel_info.configure(text=f"ขนาดพิกเซลปลายทาง: {px[0]:,} × {px[1]:,} px")
        except Exception:
            self.pixel_info.configure(text="ขนาดพิกเซลปลายทาง: —")

    def _update_tree_output_sizes(self):
        scale = int(self.scale_var.get().rstrip("x"))
        target = None
        if self.use_print_size.get():
            try:
                target = print_pixels(float(self.width_var.get()), float(self.height_var.get()), self.unit_var.get(), int(float(self.dpi_var.get())))
            except Exception:
                target = None
        for i, p in enumerate(self.files):
            if not self.tree.exists(str(i)):
                continue
            try:
                with Image.open(p) as im:
                    w, h = im.size
                ow, oh = target if target else (w * scale, h * scale)
                vals = list(self.tree.item(str(i), "values"))
                vals[2] = f"{ow:,} × {oh:,}"
                self.tree.item(str(i), values=vals)
            except Exception:
                pass

    def _settings(self) -> EnhanceSettings:
        s = EnhanceSettings(
            denoise=round(self.denoise_var.get()),
            flat_smoothing=round(self.flat_var.get()),
            text_graphic_boost=round(self.text_var.get()),
            contrast=round(self.contrast_var.get()),
            sharpness=round(self.sharp_var.get()),
            saturation=round(self.sat_var.get()),
            ai_scale=int(self.scale_var.get().rstrip("x")),
            dpi=max(1, int(float(self.dpi_var.get() or 150))),
            print_unit=self.unit_var.get(),
            export_format=self.format_var.get(),
            v1_baseline=self.v1_mode.get(),
            color_mode=self.color_mode_var.get(),
            icc_profile_path=(self.icc_profile_path_var.get() or None),
        )
        if self.use_print_size.get():
            s.print_width = float(self.width_var.get())
            s.print_height = float(self.height_var.get())
        return s

    def update_preview(self):
        self._preview_job = None
        if self.current_index is None:
            return
        p = self.files[self.current_index]
        try:
            settings = self._settings()
        except Exception:
            return
        self.right_caption.configure(text="กำลังสร้าง Preview…")
        def worker():
            try:
                with tempfile.TemporaryDirectory(prefix="signprint_preview_") as td:
                    td = Path(td)
                    with Image.open(p) as im:
                        im = ImageOps.exif_transpose(im).convert("RGB")
                        im.thumbnail((1200, 800), Image.Resampling.LANCZOS)
                        preview_in = td / "preview_input.png"
                        preview_out = td / "preview_output.png"
                        im.save(preview_in)
                    # Screen preview always stays RGB; ICC/CMYK is an export-only
                    # stage so it cannot alter the proven V1 processing result.
                    ps = replace(
                        settings,
                        ai_scale=1,
                        print_width=None,
                        print_height=None,
                        dpi=96,
                        color_mode="RGB",
                        icc_profile_path=None,
                    )
                    self.pipeline.process(preview_in, preview_out, ps, use_ai=False)
                    # Copy to a stable per-user temp path because TemporaryDirectory
                    # is removed as soon as this worker exits.
                    stable = Path(tempfile.gettempdir()) / "SignPrintAI_preview.png"
                    Image.open(preview_out).save(stable)
                self._events.put(("preview_done", str(stable)))
            except Exception as exc:
                self._events.put(("preview_error", str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _refresh_preview_images(self):
        if self.current_index is None or self.current_index >= len(self.files):
            return
        try:
            self._photo_left = self._photo_for_label(self.files[self.current_index], self.left_image)
            self.left_image.configure(image=self._photo_left)
        except Exception:
            pass
        if self._last_result and self._last_result.exists():
            try:
                self._photo_right = self._photo_for_label(self._last_result, self.right_image)
                self.right_image.configure(image=self._photo_right)
            except Exception:
                pass

    def _photo_for_label(self, path: Path, label: ttk.Label):
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            w = max(250, label.winfo_width() - 12)
            h = max(180, label.winfo_height() - 12)
            im.thumbnail((w, h), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(im.copy())

    def choose_output_dir(self):
        d = filedialog.askdirectory(title="เลือกโฟลเดอร์ผลลัพธ์")
        if d:
            self.output_dir_var.set(d)
            self.output_dir_label.configure(text=d)

    def _output_path(self, src: Path, fmt: str) -> Path:
        ext = {"PNG": ".png", "TIFF": ".tif", "PDF": ".pdf", "JPG": ".jpg"}[fmt]
        outdir = Path(self.output_dir_var.get()) if self.output_dir_var.get() else src.parent
        color_suffix = "_CMYK" if getattr(self, "color_mode_var", None) and self.color_mode_var.get() == "CMYK" else ""
        return outdir / f"{src.stem}_Niyomsil_AI{color_suffix}{ext}"

    def start_processing(self):
        if not self.files:
            messagebox.showinfo(APP_NAME, "กรุณาเพิ่มภาพก่อน")
            return
        try:
            requested_scale = int(self.scale_var.get().rstrip("x"))
        except Exception:
            requested_scale = 1
        if requested_scale > 1 and not self.pipeline.ai.available:
            messagebox.showerror(
                APP_NAME,
                "Build นี้ไม่พบ Real-ESRGAN AI backend\n\n"
                "โปรแกรมจะไม่ใช้ Lanczos แทน AI เพราะคุณภาพต่ำกว่ารุ่นต้นแบบ "
                "กรุณาใช้ Niyomsil Design V1 Build ที่แพ็ก AI backend ครบ"
            )
            return
        if self.color_mode_var.get() == "CMYK":
            if self.format_var.get() == "PNG":
                messagebox.showerror(
                    APP_NAME,
                    "PNG ไม่รองรับ CMYK\n\nกรุณาเลือก TIFF, JPG หรือ PDF สำหรับงาน CMYK"
                )
                return
            icc_path = self.icc_profile_path_var.get().strip()
            if not icc_path or not Path(icc_path).is_file():
                messagebox.showerror(
                    APP_NAME,
                    "กรุณาเลือก ICC / ICM Profile สำหรับ CMYK ก่อนเริ่มประมวลผล"
                )
                return

        try:
            settings = self._settings()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"ค่าการตั้งค่าไม่ถูกต้อง: {exc}")
            return
        self._stop.clear()
        self._processing_started_at = time.monotonic()
        self.progress["value"] = 0
        def worker():
            total = len(self.files)
            for i, src in enumerate(list(self.files)):
                if self._stop.is_set():
                    break
                out = self._output_path(src, settings.export_format)
                self._events.put(("row_status", i, "กำลังประมวลผล…"))
                def pcb(v, msg, idx=i):
                    overall = int(((idx + v/100.0) / total) * 100)
                    self._events.put(("progress", overall, f"ไฟล์ {idx+1}/{total}: {msg}", idx, max(0, min(100, int(v)))))
                try:
                    result = self.pipeline.process(src, out, settings, progress=pcb, cancel=self._stop.is_set, use_ai=True)
                    self._events.put(("row_status", i, "เสร็จแล้ว"))
                    self._events.put(("result_done", i, str(out), result))
                except InterruptedError:
                    self._events.put(("row_status", i, "หยุดแล้ว"))
                    break
                except Exception as exc:
                    self._events.put(("row_status", i, f"ผิดพลาด: {exc}"))
            self._events.put(("all_done", self._stop.is_set()))
        threading.Thread(target=worker, daemon=True).start()

    def stop_processing(self):
        self._stop.set()
        self._set_status("กำลังหยุด…")

    def open_output_folder(self):
        if self.output_dir_var.get():
            p = Path(self.output_dir_var.get())
        elif self.current_index is not None and self.files:
            p = self.files[self.current_index].parent
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

    def _set_status(self, text: str):
        self.status_label.configure(text=text)

    def _drain_events(self):
        try:
            while True:
                ev = self._events.get_nowait()
                kind = ev[0]
                if kind == "progress":
                    self.progress["value"] = ev[1]
                    self._set_status(ev[2])
                    if len(ev) >= 5:
                        idx, file_progress = ev[3], ev[4]
                        if self.tree.exists(str(idx)):
                            vals = list(self.tree.item(str(idx), "values"))
                            while len(vals) < 6:
                                vals.append("")
                            vals[4] = f"{file_progress}%"
                            self.tree.item(str(idx), values=vals)
                elif kind == "row_status":
                    i, st = ev[1], ev[2]
                    if self.tree.exists(str(i)):
                        vals = list(self.tree.item(str(i), "values"))
                        while len(vals) < 6:
                            vals.append("")
                        vals[3] = st
                        if st == "เสร็จแล้ว":
                            vals[4] = "100%"
                        self.tree.item(str(i), values=vals)
                elif kind == "preview_done":
                    self._last_result = Path(ev[1])
                    self.right_caption.configure(text="Preview: V1 Baseline" if self.v1_mode.get() else "Preview: Advanced Detail Preserve")
                    self._refresh_preview_images()
                elif kind == "preview_error":
                    self.right_caption.configure(text="Preview ผิดพลาด: " + ev[1])
                elif kind == "result_done":
                    _, idx, path, result = ev
                    if self.tree.exists(str(idx)):
                        vals = list(self.tree.item(str(idx), "values"))
                        while len(vals) < 6:
                            vals.append("")
                        vals[5] = "สำเร็จ"
                        self.tree.item(str(idx), values=vals)
                    if idx == self.current_index:
                        self._last_result = Path(path)
                        self.right_caption.configure(text=f"ผลลัพธ์จริง: {result['output_size'][0]:,} × {result['output_size'][1]:,} px")
                        self._refresh_preview_images()
                elif kind == "all_done":
                    stopped = ev[1]
                    self.progress["value"] = 100 if not stopped else self.progress["value"]
                    self._processing_started_at = None
                    self._set_status("หยุดแล้ว" if stopped else "ประมวลผลไฟล์ทั้งหมดเสร็จแล้ว")
        except queue.Empty:
            pass
        self.after(80, self._drain_events)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
