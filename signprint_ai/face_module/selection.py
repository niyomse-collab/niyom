"""Tk consent dialog; must only run on the main UI thread."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk


def choose_faces(parent, path, regions):
    dialog = tk.Toplevel(parent)
    dialog.title('ตรวจพบใบหน้า — เลือกใบหน้าที่ต้องการปรับปรุง')
    dialog.configure(bg='#111820')
    dialog.transient(parent)
    result = [None]
    photos = []
    with Image.open(path) as source:
        image = source.convert('RGB')
    overview = image.copy()
    overview.thumbnail((620, 420), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(overview)
    for number, (x1,y1,x2,y2) in enumerate(regions, 1):
        draw.rectangle((x1*overview.width,y1*overview.height,x2*overview.width,y2*overview.height), outline='#ff3333', width=2)
        draw.text((x1*overview.width,y1*overview.height), str(number), fill='white')
    photos.append(ImageTk.PhotoImage(overview))
    tk.Label(dialog, image=photos[-1], bg='#111820').pack(padx=10, pady=10)
    ttk.Label(dialog, text=f'{path.name} • พบ {len(regions)} ใบหน้า\nเลือกเฉพาะใบหน้าที่ต้องการ แล้วกดยืนยัน').pack(padx=10)
    canvas = tk.Canvas(dialog, height=150, bg='#111820', highlightthickness=0)
    canvas.pack(fill='x', padx=10, pady=5)
    scrollbar = ttk.Scrollbar(dialog, orient='horizontal', command=canvas.xview)
    scrollbar.pack(fill='x', padx=10)
    canvas.configure(xscrollcommand=scrollbar.set)
    strip = ttk.Frame(canvas)
    canvas.create_window((0,0), window=strip, anchor='nw')
    variables = []
    for i, (x1,y1,x2,y2) in enumerate(regions):
        crop = image.crop((int(x1*image.width),int(y1*image.height),int(x2*image.width),int(y2*image.height)))
        crop.thumbnail((100,100), Image.Resampling.LANCZOS)
        photos.append(ImageTk.PhotoImage(crop))
        frame = ttk.Frame(strip)
        frame.pack(side='left', padx=5)
        ttk.Label(frame, image=photos[-1]).pack()
        var = tk.BooleanVar(value=True)
        variables.append(var)
        ttk.Checkbutton(frame, text=f'ใบหน้า {i+1}', variable=var).pack()
    strip.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox('all'))
    def finish(selection):
        result[0] = selection
        dialog.destroy()
    actions = ttk.Frame(dialog)
    actions.pack(fill='x', padx=10, pady=10)
    ttk.Button(actions, text='ยืนยันใบหน้าที่เลือก', command=lambda: finish(tuple(r for r,v in zip(regions,variables) if v.get()))).pack(side='left')
    ttk.Button(actions, text='ใช้ภาพเดิม / ไม่ปรับใบหน้า', command=lambda: finish(())).pack(side='left', padx=8)
    ttk.Button(actions, text='ยกเลิก', command=dialog.destroy).pack(side='right')
    dialog.grab_set()
    parent.wait_window(dialog)
    return result[0]
