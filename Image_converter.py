import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import pillow_heif

pillow_heif.register_heif_opener()

FOLDER     = r"C:\Users\djmor\Desktop\Knitting_Portfolio"
THUMB_SIZE = (72, 72)   # pixels (square crop)

# ─────────────────────────────────────────────
# Colour / style tokens  (warm knitting palette)
# ─────────────────────────────────────────────
BG        = "#2a1f14"
SURFACE   = "#3d2c1e"
SURFACE2  = "#4a3525"
ACCENT    = "#b85520"
ACCENT_LT = "#d4713a"
TEXT      = "#fdf6ee"
TEXT_MUTED= "#a08878"
SUCCESS   = "#4caf7d"
FONT_HDR  = ("Georgia", 18, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)
FONT_SMALL= ("Segoe UI", 8)

TW, TH = THUMB_SIZE   # thumbnail width / height


# ─────────────────────────────────────────────
# Helper: scan folder for .heic files
# ─────────────────────────────────────────────
def find_heic_files():
    return sorted(f for f in os.listdir(FOLDER) if f.lower().endswith(".heic"))


def make_square_thumb(path: str, size: tuple[int, int]) -> Image.Image:
    """Open an image, centre-crop to square, resize to *size*."""
    with Image.open(path) as img:
        img = img.convert("RGB")
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = (h - side) // 2
        img  = img.crop((left, top, left + side, top + side))
        img  = img.resize(size, Image.LANCZOS)
        return img.copy()   # detach from the file handle


# ─────────────────────────────────────────────
# Main application window
# ─────────────────────────────────────────────
class ConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("HEIC → JPEG Converter")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(600, 420)

        # Keep ImageTk references alive (GC would delete them otherwise)
        self._thumb_refs: list[ImageTk.PhotoImage] = []

        self._build_ui()
        self._refresh_file_list()

        # Centre on screen
        self.update_idletasks()
        w, h = 740, 580
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    # ── UI construction ───────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=28, pady=(28, 6))
        tk.Label(hdr, text="HEIC → JPEG Converter", font=FONT_HDR,
                 bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(hdr, text=f"Folder: {FOLDER}", font=FONT_SMALL,
                 bg=BG, fg=TEXT_MUTED, wraplength=680, justify="left").pack(anchor="w", pady=(2, 0))

        # Accent divider
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x", padx=28, pady=(8, 0))

        # Instructions
        tk.Label(self,
                 text="Edit output names below (without extension). "
                      "Files will be saved as .jpg and the original .heic deleted.",
                 font=FONT_SMALL, bg=BG, fg=TEXT_MUTED,
                 wraplength=680, justify="left").pack(anchor="w", padx=28, pady=(8, 4))

        # ── Scrollable table ──
        table_frame = tk.Frame(self, bg=BG)
        table_frame.pack(fill="both", expand=True, padx=28, pady=4)

        # Column headers
        col_hdr = tk.Frame(table_frame, bg=SURFACE2)
        col_hdr.pack(fill="x")
        tk.Label(col_hdr, text=" " * 11, font=FONT_SMALL,       # thumb placeholder
                 bg=SURFACE2, fg=TEXT_MUTED, width=10).pack(side="left")
        tk.Label(col_hdr, text="Original filename", font=FONT_SMALL,
                 bg=SURFACE2, fg=TEXT_MUTED, anchor="w", width=26).pack(side="left", padx=(4, 0))
        tk.Label(col_hdr, text="Output name (editable)", font=FONT_SMALL,
                 bg=SURFACE2, fg=TEXT_MUTED, anchor="w").pack(side="left", padx=8)

        # Canvas + scrollbar
        canvas_wrap = tk.Frame(table_frame, bg=BG)
        canvas_wrap.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_wrap, bg=SURFACE, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.rows_frame = tk.Frame(self.canvas, bg=SURFACE)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        self.rows_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>",
                             lambda e: self.canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # ── Bottom controls ──
        bottom = tk.Frame(self, bg=BG)
        bottom.pack(fill="x", padx=28, pady=(8, 20))

        refresh_btn = tk.Button(bottom, text="⟳  Refresh list", font=FONT_BODY,
                                bg=SURFACE2, fg=TEXT, activebackground=SURFACE2,
                                activeforeground=ACCENT_LT, relief="flat", bd=0,
                                padx=14, pady=8, cursor="hand2",
                                command=self._refresh_file_list)
        refresh_btn.pack(side="left")
        self._bind_hover(refresh_btn, SURFACE2, ACCENT)

        self.convert_btn = tk.Button(bottom, text="Convert  →",
                                     font=("Segoe UI", 11, "bold"),
                                     bg=ACCENT, fg=TEXT, activebackground=ACCENT_LT,
                                     activeforeground=TEXT, relief="flat", bd=0,
                                     padx=22, pady=10, cursor="hand2",
                                     command=self._start_conversion)
        self.convert_btn.pack(side="right")
        self._bind_hover(self.convert_btn, ACCENT, ACCENT_LT)

        # Progress bar (hidden until conversion)
        self.progress_var = tk.DoubleVar(value=0)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor=SURFACE, background=ACCENT,
                        darkcolor=ACCENT, lightcolor=ACCENT_LT,
                        bordercolor=BG, thickness=10)
        self.progress_bar = ttk.Progressbar(self, variable=self.progress_var,
                                            maximum=100,
                                            style="Custom.Horizontal.TProgressbar")

        # Status label (hidden until conversion)
        self.status_var = tk.StringVar(value="")
        self.status_lbl = tk.Label(self, textvariable=self.status_var,
                                   font=FONT_SMALL, bg=BG, fg=TEXT_MUTED)

    # ── Table population ──────────────────────
    def _refresh_file_list(self):
        for widget in self.rows_frame.winfo_children():
            widget.destroy()
        self._thumb_refs.clear()
        self.entries: list[tuple[str, tk.StringVar]] = []

        heic_files = find_heic_files()

        if not heic_files:
            tk.Label(self.rows_frame,
                     text="No .heic files found in the portfolio folder.",
                     font=FONT_BODY, bg=SURFACE, fg=TEXT_MUTED,
                     pady=20).pack()
            self.convert_btn.configure(state="disabled", bg=SURFACE2)
            return

        self.convert_btn.configure(state="normal", bg=ACCENT)

        # Build placeholder image once (dark square shown while thumb loads)
        placeholder = Image.new("RGB", THUMB_SIZE, color="#3d2c1e")
        self._placeholder_ref = ImageTk.PhotoImage(placeholder)

        self._thumb_labels: dict[str, tk.Label] = {}

        for i, filename in enumerate(heic_files):
            row_bg = SURFACE if i % 2 == 0 else SURFACE2
            row = tk.Frame(self.rows_frame, bg=row_bg)
            row.pack(fill="x")

            # ── Thumbnail slot ──
            thumb_lbl = tk.Label(row, image=self._placeholder_ref,
                                 bg=row_bg, width=TW, height=TH,
                                 relief="flat", bd=0)
            thumb_lbl.pack(side="left", padx=(6, 4), pady=4)
            self._thumb_labels[filename] = thumb_lbl

            # ── Original name ──
            tk.Label(row, text=filename, font=FONT_MONO,
                     bg=row_bg, fg=TEXT_MUTED, anchor="w",
                     width=26, pady=6).pack(side="left", padx=(0, 2))

            # ── Arrow ──
            tk.Label(row, text="→", font=FONT_BODY,
                     bg=row_bg, fg=ACCENT_LT).pack(side="left", padx=4)

            # ── Editable output name ──
            stem = filename.rsplit(".", 1)[0]
            var  = tk.StringVar(value=stem)
            entry = tk.Entry(row, textvariable=var, font=FONT_MONO,
                             bg=BG, fg=TEXT, insertbackground=TEXT,
                             relief="flat", bd=0,
                             highlightthickness=1,
                             highlightcolor=ACCENT,
                             highlightbackground=SURFACE2)
            entry.pack(side="left", fill="x", expand=True, padx=(0, 4), ipady=4)

            # ── .jpg hint ──
            tk.Label(row, text=".jpg", font=FONT_MONO,
                     bg=row_bg, fg=TEXT_MUTED).pack(side="left", padx=(0, 8))

            self.entries.append((filename, var))

        # Reset progress UI
        self.progress_bar.pack_forget()
        self.status_lbl.pack_forget()
        self.progress_var.set(0)
        self.status_var.set("")

        # Load thumbnails in a background thread
        threading.Thread(target=self._load_thumbnails,
                         args=(list(heic_files),), daemon=True).start()

    # ── Thumbnail loading (background thread) ─
    def _load_thumbnails(self, filenames: list[str]):
        for filename in filenames:
            path = os.path.join(FOLDER, filename)
            try:
                pil_img = make_square_thumb(path, THUMB_SIZE)
                photo   = ImageTk.PhotoImage(pil_img)
                # Schedule UI update back on the main thread
                self.after(0, self._set_thumbnail, filename, photo)
            except Exception:
                pass   # silently skip unreadable files

    def _set_thumbnail(self, filename: str, photo: ImageTk.PhotoImage):
        lbl = self._thumb_labels.get(filename)
        if lbl and lbl.winfo_exists():
            lbl.configure(image=photo)
            self._thumb_refs.append(photo)   # prevent GC

    # ── Conversion ────────────────────────────
    def _start_conversion(self):
        if not self.entries:
            return

        output_names = [v.get().strip() for _, v in self.entries]

        if len(output_names) != len(set(output_names)):
            messagebox.showerror("Duplicate names",
                                 "Two or more files share the same output name.\n"
                                 "Please make them unique before converting.")
            return

        if any(n == "" for n in output_names):
            messagebox.showerror("Empty name",
                                 "One or more output names are blank.\n"
                                 "Please fill them in before converting.")
            return

        self.progress_bar.pack(fill="x", padx=28, pady=(0, 4))
        self.status_lbl.pack(anchor="w", padx=28, pady=(0, 8))
        self.progress_var.set(0)
        self.convert_btn.configure(state="disabled", bg=SURFACE2)
        self.status_var.set("Starting…")

        threading.Thread(target=self._run_conversion,
                         args=(list(self.entries),), daemon=True).start()

    def _run_conversion(self, entries):
        total  = len(entries)
        done   = 0
        errors = []

        for original, name_var in entries:
            output_stem = name_var.get().strip()
            input_path  = os.path.join(FOLDER, original)
            output_path = os.path.join(FOLDER, output_stem + ".jpg")

            self.after(0, self.status_var.set, f"Converting {original}…")

            try:
                with Image.open(input_path) as img:
                    img.convert("RGB").save(output_path, "JPEG", quality=95)
                os.remove(input_path)
            except Exception as e:
                errors.append(f"{original}: {e}")

            done += 1
            self.after(0, self.progress_var.set, done / total * 100)

        self.after(0, self._conversion_done, done, total, errors)

    def _conversion_done(self, done, total, errors):
        self.progress_var.set(100)

        if errors:
            self.status_var.set(f"⚠  Completed with {len(errors)} error(s).")
            self.status_lbl.configure(fg="#e07070")
            messagebox.showwarning("Conversion issues",
                                   f"{done}/{total} files converted.\n\nErrors:\n" +
                                   "\n".join(errors))
        else:
            self.status_var.set(f"✓  All {total} file(s) converted successfully!")
            self.status_lbl.configure(font=("Segoe UI", 10, "bold"), fg=SUCCESS)

        self.convert_btn.configure(state="normal", bg=ACCENT, text="⟳  Convert again",
                                   command=self._refresh_file_list)
        self._bind_hover(self.convert_btn, ACCENT, ACCENT_LT)

    # ── Scroll helpers ────────────────────────
    def _on_frame_configure(self, event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.canvas_window, width=event.width)

    # ── Hover effect helper ───────────────────
    @staticmethod
    def _bind_hover(widget, normal_bg, hover_bg):
        widget.bind("<Enter>", lambda e: widget.configure(bg=hover_bg))
        widget.bind("<Leave>", lambda e: widget.configure(bg=normal_bg))


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = ConverterApp()
    app.mainloop()