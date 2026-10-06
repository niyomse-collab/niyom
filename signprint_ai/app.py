from __future__ import annotations

import os
import queue
import threading
import time
import tempfile
from dataclasses import replace
from pathlib import Path
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageOps, ImageTk

from .pipeline import PrintEnhancementPipeline
from .processing import EnhanceSettings, print_pixels

APP_NAME = "SignPrint AI Enhancer"
APP_VERSION = "0.1.1 Private Build"
IMAGE_TYPES = [("Image files", "*.png;*.jpg;*.jpeg;*.bmp;*.tif;*.tiff;*.webp"), ("All files", "*.*")]


def resource_root() -> Path:
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

        self._build_style()
        self._build_ui()
        self._enable_drag_drop()
        self.after(80, self._drain_events)
        self._set_status("พร้อมใช้งาน — เพิ่มภาพเพื่อเริ่ม")

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

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass

        family = self._pick_ui_font()
        self.ui_font_family = family
        body = (family, 10, "normal")
        body_small = (family, 9, "normal")
        body_bold = (family, 10, "bold")
        header = (family, 17, "bold")
        button = (family, 10, "normal")
        button_bold = (family, 10, "bold")

        # Tk/ttk can otherwise pick a Thai fallback font whose slant/weight differs
        # from the Latin font.  Updating named fonts keeps Thai text consistent.
        for name, size, weight in (
            ("TkDefaultFont", 10, "normal"),
            ("TkTextFont", 10, "normal"),
            ("TkMenuFont", 10, "normal"),
            ("TkHeadingFont", 10, "bold"),
            ("TkCaptionFont", 10, "bold"),
            ("TkSmallCaptionFont", 9, "normal"),
            ("TkIconFont", 10, "normal"),
            ("TkTooltipFont", 9, "normal"),
        ):
            try:
                font = tkfont.nametofont(name)
                font.configure(family=family, size=size, weight=weight, slant="roman")
            except tk.TclError:
                pass

        self.option_add("*Font", body)

        # Apply readable Thai font to every common ttk widget.
        style.configure(".", font=body)
        style.configure("TLabel", font=body)
        style.configure("TButton", font=button, padding=(8, 5))
        style.configure("TCheckbutton", font=body)
        style.configure("TRadiobutton", font=body)
        style.configure("TEntry", font=body)
        style.configure("TCombobox", font=body)
        style.configure("TLabelframe.Label", font=body_bold)
        style.configure("Treeview", font=body, rowheight=27)
        style.configure("Treeview.Heading", font=body_bold)
        style.configure("Header.TLabel", font=header)
        style.configure("SubHeader.TLabel", font=body)
        style.configure("PaneTitle.TLabel", font=body_bold)
        style.configure("Section.TLabelframe.Label", font=body_bold)
        style.configure("Primary.TButton", font=button_bold, padding=(12, 9))
        style.configure("Small.TButton", font=body_small, padding=(7, 4))

    def _build_ui(self):
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        root.rowconfigure(1, weight=1)
        root.columnconfigure(1, weight=1)

        # Header
        head = ttk.Frame(root)
        head.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(head, text=APP_NAME, style="Header.TLabel").pack(side="left")
        ttk.Label(head, text="  งานภาพสำหรับป้ายและงานพิมพ์ขนาดใหญ่", style="SubHeader.TLabel").pack(side="left", pady=(8, 0))
        ai_state = "Real-ESRGAN NCNN พร้อมใช้งาน" if self.pipeline.ai.available else "AI backend ยังไม่ได้ติดตั้ง — ใช้ Lanczos fallback"
        self.ai_state_label = ttk.Label(head, text=ai_state)
        self.ai_state_label.pack(side="right", pady=(8, 0))

        # Left controls
        left_outer = ttk.Frame(root, width=325)
        left_outer.grid(row=1, column=0, sticky="nsw", padx=(0, 8))
        left_outer.grid_propagate(False)
        left = tk.Canvas(left_outer, highlightthickness=0, width=318)
        sb = ttk.Scrollbar(left_outer, orient="vertical", command=left.yview)
        self.left_inner = ttk.Frame(left)
        self.left_inner.bind("<Configure>", lambda e: left.configure(scrollregion=left.bbox("all")))
        left.create_window((0, 0), window=self.left_inner, anchor="nw", width=300)
        left.configure(yscrollcommand=sb.set)
        left.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._build_controls(self.left_inner)

        # Right workspace
        work = ttk.Frame(root)
        work.grid(row=1, column=1, sticky="nsew")
        work.rowconfigure(0, weight=3)
        work.rowconfigure(1, weight=2)
        work.columnconfigure(0, weight=1)

        compare = ttk.LabelFrame(work, text="เปรียบเทียบภาพ", style="Section.TLabelframe")
        compare.grid(row=0, column=0, sticky="nsew")
        compare.rowconfigure(1, weight=1)
        compare.columnconfigure(0, weight=1)
        compare.columnconfigure(1, weight=1)

        tools = ttk.Frame(compare, padding=(6, 4))
        tools.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(tools, text="พอดีหน้าต่าง", command=self._refresh_preview_images, style="Small.TButton").pack(side="left")
        ttk.Button(tools, text="อัปเดต Preview", command=self.update_preview, style="Small.TButton").pack(side="left", padx=6)
        self.auto_preview = tk.BooleanVar(value=True)
        ttk.Checkbutton(tools, text="Auto Preview", variable=self.auto_preview).pack(side="right")

        left_pane = ttk.Frame(compare, padding=5)
        right_pane = ttk.Frame(compare, padding=5)
        left_pane.grid(row=1, column=0, sticky="nsew")
        right_pane.grid(row=1, column=1, sticky="nsew")
        left_pane.rowconfigure(1, weight=1); left_pane.columnconfigure(0, weight=1)
        right_pane.rowconfigure(1, weight=1); right_pane.columnconfigure(0, weight=1)
        ttk.Label(left_pane, text="ภาพต้นฉบับ", style="PaneTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(right_pane, text="ผลลัพธ์ / Preview", style="PaneTitle.TLabel").grid(row=0, column=0, sticky="w")
        self.left_image = ttk.Label(left_pane, anchor="center", relief="sunken")
        self.right_image = ttk.Label(right_pane, anchor="center", relief="sunken")
        self.left_image.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.right_image.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        self.left_caption = ttk.Label(left_pane, text="ยังไม่ได้เลือกภาพ", anchor="center")
        self.right_caption = ttk.Label(right_pane, text="Preview จะใช้ Pipeline ปรับ Noise/สี/ขอบโดยไม่รัน AI เต็ม", anchor="center")
        self.left_caption.grid(row=2, column=0, sticky="ew", pady=4)
        self.right_caption.grid(row=2, column=0, sticky="ew", pady=4)
        self.left_image.bind("<Configure>", lambda e: self._refresh_preview_images())
        self.right_image.bind("<Configure>", lambda e: self._refresh_preview_images())

        queue_box = ttk.LabelFrame(work, text="รายการไฟล์และสถานะ", style="Section.TLabelframe")
        queue_box.grid(row=1, column=0, sticky="nsew", pady=(8, 0))
        queue_box.rowconfigure(1, weight=1)
        queue_box.columnconfigure(0, weight=1)
        qtools = ttk.Frame(queue_box, padding=4)
        qtools.grid(row=0, column=0, sticky="ew")
        ttk.Button(qtools, text="เพิ่มภาพ", command=self.choose_files).pack(side="left")
        ttk.Button(qtools, text="ลบรายการ", command=self.remove_selected).pack(side="left", padx=5)
        ttk.Button(qtools, text="เปิดโฟลเดอร์ผลลัพธ์", command=self.open_output_folder).pack(side="left")
        self.output_note = ttk.Label(qtools, text="ลากไฟล์ภาพมาวางในหน้าต่างนี้ได้")
        self.output_note.pack(side="right")

        cols = ("name", "original", "output", "status")
        self.tree = ttk.Treeview(queue_box, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("name", text="ชื่อไฟล์")
        self.tree.heading("original", text="ต้นฉบับ")
        self.tree.heading("output", text="ขนาดส่งออก")
        self.tree.heading("status", text="สถานะ")
        self.tree.column("name", width=330)
        self.tree.column("original", width=150, anchor="center")
        self.tree.column("output", width=180, anchor="center")
        self.tree.column("status", width=250)
        self.tree.grid(row=1, column=0, sticky="nsew")
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        tree_sb = ttk.Scrollbar(queue_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_sb.set)
        tree_sb.grid(row=1, column=1, sticky="ns")

        bottom = ttk.Frame(root)
        bottom.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(1, weight=1)
        self.status_label = ttk.Label(bottom, text="")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=1, sticky="ew", padx=10)
        ttk.Button(bottom, text="หยุดทั้งหมด", command=self.stop_processing).grid(row=0, column=2)

    def _build_controls(self, parent):
        choose = ttk.LabelFrame(parent, text="ไฟล์ต้นฉบับ", style="Section.TLabelframe", padding=7)
        choose.pack(fill="x", pady=(0, 7))
        ttk.Button(choose, text="เลือกไฟล์ต้นฉบับ…", command=self.choose_files).pack(fill="x")

        size = ttk.LabelFrame(parent, text="ขนาดงานพิมพ์", style="Section.TLabelframe", padding=7)
        size.pack(fill="x", pady=7)
        self.use_print_size = tk.BooleanVar(value=False)
        ttk.Checkbutton(size, text="กำหนดขนาดงานพิมพ์", variable=self.use_print_size, command=self._settings_changed).grid(row=0, column=0, columnspan=4, sticky="w")
        self.width_var = tk.StringVar(value="200")
        self.height_var = tk.StringVar(value="80")
        self.dpi_var = tk.StringVar(value="150")
        self.unit_var = tk.StringVar(value="cm")
        self.lock_ratio = tk.BooleanVar(value=True)
        ttk.Label(size, text="Width").grid(row=1, column=0, sticky="w", pady=3)
        w = ttk.Entry(size, textvariable=self.width_var, width=9); w.grid(row=1, column=1, sticky="ew")
        ttk.Label(size, text="Height").grid(row=1, column=2, sticky="w", padx=(7, 0))
        h = ttk.Entry(size, textvariable=self.height_var, width=9); h.grid(row=1, column=3, sticky="ew")
        ttk.Label(size, text="DPI").grid(row=2, column=0, sticky="w", pady=3)
        dpi = ttk.Combobox(size, textvariable=self.dpi_var, values=(72, 96, 100, 150, 200, 300, 600), width=7); dpi.grid(row=2, column=1, sticky="ew")
        ttk.Label(size, text="หน่วย").grid(row=2, column=2, sticky="w", padx=(7, 0))
        unit = ttk.Combobox(size, textvariable=self.unit_var, values=("mm", "cm", "m", "inch"), state="readonly", width=7); unit.grid(row=2, column=3, sticky="ew")
        ttk.Checkbutton(size, text="ล็อกอัตราส่วน — Width/Height ปรับตามกันอัตโนมัติ", variable=self.lock_ratio).grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))
        self.pixel_info = ttk.Label(size, text="ขนาดพิกเซลปลายทาง: —")
        self.pixel_info.grid(row=4, column=0, columnspan=4, sticky="w", pady=(4, 0))
        size.columnconfigure(1, weight=1); size.columnconfigure(3, weight=1)
        w.bind("<KeyRelease>", lambda e: self._size_edited("w"))
        h.bind("<KeyRelease>", lambda e: self._size_edited("h"))
        dpi.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())
        dpi.bind("<KeyRelease>", lambda e: self._settings_changed())
        unit.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())

        ai = ttk.LabelFrame(parent, text="AI Upscale", style="Section.TLabelframe", padding=7)
        ai.pack(fill="x", pady=7)
        self.scale_var = tk.StringVar(value="4x")
        ttk.Label(ai, text="AI Upscale").grid(row=0, column=0, sticky="w")
        scale = ttk.Combobox(ai, textvariable=self.scale_var, values=("2x", "4x", "8x"), state="readonly", width=10)
        scale.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        scale.bind("<<ComboboxSelected>>", lambda e: self._settings_changed())
        ttk.Label(ai, text="4x ใช้ Real-ESRGAN โดยตรง; 2x/8x ปรับขนาดต่อแบบคุณภาพสูง", wraplength=270).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ai.columnconfigure(1, weight=1)

        quality = ttk.LabelFrame(parent, text="ปรับคุณภาพสำหรับงานป้าย", style="Section.TLabelframe", padding=7)
        quality.pack(fill="x", pady=7)
        self.denoise_var = tk.IntVar(value=48)
        self.flat_var = tk.IntVar(value=52)
        self.text_var = tk.IntVar(value=58)
        self.contrast_var = tk.IntVar(value=20)
        self.sharp_var = tk.IntVar(value=46)
        self.sat_var = tk.IntVar(value=6)
        self._slider(quality, "ลด Noise / เม็ดสี", self.denoise_var, 0)
        self._slider(quality, "เกลี่ยพื้นสีเรียบ", self.flat_var, 1)
        self._slider(quality, "ตัวอักษร/โลโก้", self.text_var, 2)
        self._slider(quality, "Local Contrast", self.contrast_var, 3)
        self._slider(quality, "Anti-Halo Sharpen", self.sharp_var, 4)
        self._slider(quality, "Saturation", self.sat_var, 5, -30, 30)

        out = ttk.LabelFrame(parent, text="ส่งออก", style="Section.TLabelframe", padding=7)
        out.pack(fill="x", pady=7)
        self.format_var = tk.StringVar(value="PNG")
        self.output_dir_var = tk.StringVar(value="")
        ttk.Label(out, text="รูปแบบ").grid(row=0, column=0, sticky="w")
        fmt = ttk.Combobox(out, textvariable=self.format_var, values=("PNG", "TIFF", "PDF", "JPG"), state="readonly", width=9)
        fmt.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        ttk.Button(out, text="เลือกโฟลเดอร์…", command=self.choose_output_dir).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.output_dir_label = ttk.Label(out, text="ค่าเริ่มต้น: โฟลเดอร์เดียวกับภาพต้นฉบับ", wraplength=270)
        self.output_dir_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))
        out.columnconfigure(1, weight=1)

        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=(8, 15))
        ttk.Button(actions, text="เริ่มปรับภาพ", command=self.start_processing, style="Primary.TButton").pack(fill="x")
        ttk.Label(actions, text="Private independent build • ไม่เชื่อม/แก้ไข Repository ของ ARM AI Image Enhancer", wraplength=280).pack(fill="x", pady=(6, 0))

    def _slider(self, parent, text, var, row, lo=0, hi=100):
        ttk.Label(parent, text=text).grid(row=row, column=0, sticky="w")
        value = ttk.Label(parent, text=str(var.get()), width=4, anchor="e")
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
                self.tree.insert("", "end", iid=iid, values=(p.name, f"{size[0]:,} × {size[1]:,}", "—", "พร้อม"))
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
                    ps = replace(settings, ai_scale=1, print_width=None, print_height=None, dpi=96)
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
        return outdir / f"{src.stem}_SignPrint_AI{ext}"

    def start_processing(self):
        if not self.files:
            messagebox.showinfo(APP_NAME, "กรุณาเพิ่มภาพก่อน")
            return
        try:
            settings = self._settings()
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"ค่าการตั้งค่าไม่ถูกต้อง: {exc}")
            return
        self._stop.clear()
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
                    self._events.put(("progress", overall, f"ไฟล์ {idx+1}/{total}: {msg}"))
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
                elif kind == "row_status":
                    i, st = ev[1], ev[2]
                    if self.tree.exists(str(i)):
                        vals = list(self.tree.item(str(i), "values"))
                        vals[3] = st
                        self.tree.item(str(i), values=vals)
                elif kind == "preview_done":
                    self._last_result = Path(ev[1])
                    self.right_caption.configure(text="Preview: ลด Noise + เกลี่ยพื้นสี + ตัวอักษร/กราฟิก + Anti-Halo Sharpen")
                    self._refresh_preview_images()
                elif kind == "preview_error":
                    self.right_caption.configure(text="Preview ผิดพลาด: " + ev[1])
                elif kind == "result_done":
                    _, idx, path, result = ev
                    if idx == self.current_index:
                        self._last_result = Path(path)
                        self.right_caption.configure(text=f"ผลลัพธ์จริง: {result['output_size'][0]:,} × {result['output_size'][1]:,} px")
                        self._refresh_preview_images()
                elif kind == "all_done":
                    stopped = ev[1]
                    self.progress["value"] = 100 if not stopped else self.progress["value"]
                    self._set_status("หยุดแล้ว" if stopped else "ประมวลผลไฟล์ทั้งหมดเสร็จแล้ว")
        except queue.Empty:
            pass
        self.after(80, self._drain_events)


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
