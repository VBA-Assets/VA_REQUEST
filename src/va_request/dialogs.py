"""確かめ・選ぶための小さな画面（印刷・例文の登録・例文の選択・解像度）。"""
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk
from pathlib import Path

from . import APP_NAME, printing
from .ui import theme
from .ui.wrapped_list import WrappedList

# 例文の一覧の高さ（行）。何行かの字の欄は折り返すので 20 行、ほかは 10 行。［例文の選択］の画面の一覧も同じ高さにする
# （2026-11-14 班長指示。そのときは本体の右の欄の一覧。右の欄は 2026-11-15 に除いた）
PHRASE_ROWS_WRAP = 20
PHRASE_ROWS = 10


class _Dialog(tk.Toplevel):
    def __init__(self, master, title):
        super().__init__(master)
        self.withdraw()
        self.title(title)
        self.configure(background=theme.WINDOW_BG)
        self.transient(master)
        self.resizable(False, False)
        self.result = None
        self.body = ttk.Frame(self, padding=12)
        self.body.pack(fill="both", expand=True)
        self.protocol("WM_DELETE_WINDOW", self.cancel)
        self.bind("<Escape>", lambda e: self.cancel())

    def show(self):
        self.update_idletasks()
        m = self.master
        x = m.winfo_rootx() + max(0, (m.winfo_width() - self.winfo_reqwidth()) // 2)
        y = m.winfo_rooty() + max(0, (m.winfo_height() - self.winfo_reqheight()) // 3)
        self.geometry(f"+{x}+{y}")
        self.deiconify()
        self.grab_set()
        self.focus_set()
        self.wait_window()
        return self.result

    def cancel(self):
        self.result = None
        self.destroy()


def _mm(text):
    return float(str(text).strip().replace("－", "-").replace("．", ".").translate(
        str.maketrans("０１２３４５６７８９", "0123456789")) or 0)


class PrintDialog(_Dialog):
    """プリンター・プリンターごとのずれ（mm）を選ぶ。結果は (プリンター, DEVMODE か None, 右へ mm, 下へ mm)。"""

    def __init__(self, master, cfg, title="印刷"):
        super().__init__(master, title)
        self.cfg = cfg
        self.mode = None
        names = printing.printers()
        last = cfg.get("printer") or printing.default_printer()
        b = self.body
        ttk.Label(b, text="プリンター").grid(row=0, column=0, sticky="w")
        self.printer = tk.StringVar(value=last if last in names else (names[0] if names else ""))
        box = ttk.Combobox(b, textvariable=self.printer, values=names, state="readonly", width=36)
        box.grid(row=0, column=1, columnspan=3, sticky="we", pady=2)
        box.bind("<<ComboboxSelected>>", lambda e: self._load_offset())
        ttk.Button(b, text="プロパティ…", command=self._properties).grid(row=0, column=4, padx=(6, 0))
        ttk.Label(b, text="このプリンターのずれ").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.dx, self.dy = tk.StringVar(), tk.StringVar()
        f = ttk.Frame(b)
        f.grid(row=1, column=1, columnspan=4, sticky="w", pady=(8, 0))
        ttk.Label(f, text="右へ").pack(side="left")
        ttk.Entry(f, textvariable=self.dx, width=6).pack(side="left", padx=(2, 2))
        ttk.Label(f, text="mm　下へ").pack(side="left")
        ttk.Entry(f, textvariable=self.dy, width=6).pack(side="left", padx=(2, 2))
        ttk.Label(f, text="mm").pack(side="left")
        ttk.Label(b, text="字が用紙の欄より左に刷られるときは「右へ」を、上に刷られるときは「下へ」を増やします（負の数も使えます）。"
                         "給紙の方法（手差しなど）は［プロパティ］で選びます。",
                  style="Note.TLabel", wraplength=theme.px(self, 430), justify="left").grid(
            row=2, column=0, columnspan=5, sticky="w", pady=(6, 0))
        btns = ttk.Frame(b)
        btns.grid(row=4, column=0, columnspan=5, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="印刷", style="Accent.TButton", command=self.ok).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="キャンセル", command=self.cancel).pack(side="left")
        self.bind("<Return>", lambda e: self.ok())
        self._load_offset()
        if not names:
            messagebox.showwarning(APP_NAME, "使えるプリンターがありません。", parent=master)

    def _load_offset(self):
        dx, dy = self.cfg.printer_offset(self.printer.get())
        self.dx.set(f"{dx:g}")
        self.dy.set(f"{dy:g}")
        self.mode = None

    def _properties(self):
        name = self.printer.get()
        if not name:
            return
        try:
            out = printing.show_properties(self.winfo_id(), name, self.mode)
        except printing.PrintError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self)
            return
        if out is not None:
            self.mode = out

    def ok(self):
        name = self.printer.get()
        if not name:
            return
        try:
            dx, dy = _mm(self.dx.get()), _mm(self.dy.get())
        except ValueError:
            messagebox.showerror(APP_NAME, "ずれは、mm の数で入れてください。", parent=self)
            return
        if abs(dx) > 30 or abs(dy) > 30:
            messagebox.showerror(APP_NAME, "ずれは、30mm までにしてください。", parent=self)
            return
        self.cfg.set("printer", name)
        self.cfg.set_printer_offset(name, dx, dy)
        self.cfg.save()
        self.result = (name, self.mode, dx, dy)
        self.destroy()


class PhraseSelectDialog(_Dialog):
    """［例文の選択］：1つの欄の例文から1つを選ぶ（2026-11-15 班長指示「「例文の選択」ボタンを押すと選択フォームが
    表示」。それまでは本体の右の欄に一覧を出していた）。結果は選んだ例文（やめれば None）。

    何行かの字の欄（wrap）は、例文を折り返して表示する（WrappedList）。ほかの欄は1行に1つ（改行は ⏎ で示す）。
    ダブルクリック・Enter・［入れる］で選ぶ。入れる先は、本体の入力欄のいまの文字の位置。
    """

    def __init__(self, master, items, field_label, field_font, wrap=False):
        super().__init__(master, "例文の選択")
        self.resizable(True, True)
        self.items = list(items)
        b = self.body
        ttk.Label(b, text=f"{field_label} の例文").grid(row=0, column=0, sticky="w")
        frame = ttk.Frame(b)
        frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        if wrap:
            lb = WrappedList(frame, height=PHRASE_ROWS_WRAP, font=field_font, width=50)
            for it in self.items:
                lb.insert("end", it)
            lb.grid(row=0, column=0, sticky="nsew")
            lb.bind("<<ListboxDouble>>", lambda e: self.ok())
        else:
            lb = tk.Listbox(frame, height=PHRASE_ROWS, width=50, font=field_font, activestyle="none",
                            exportselection=False, background=theme.FIELD_BG, foreground=theme.TEXT, relief="solid",
                            borderwidth=1, highlightthickness=0, selectbackground=theme.PRESSED_BG,
                            selectforeground=theme.TEXT)
            for it in self.items:
                lb.insert("end", it.replace("\n", " ⏎ "))
            bar = ttk.Scrollbar(frame, orient="vertical", command=lb.yview)
            lb.configure(yscrollcommand=bar.set)
            lb.grid(row=0, column=0, sticky="nsew")
            bar.grid(row=0, column=1, sticky="ns")
            lb.bind("<Double-Button-1>", lambda e: self.ok())
            lb.activate(0)
            self.after_idle(lb.focus_set)        # 矢印キーで選べるように
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        lb.selection_set(0)
        self.list = lb
        ttk.Label(b, text="ダブルクリックか［入れる］で、入力欄の、いまの文字の位置に入れます。",
                  style="Note.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 0))
        btns = ttk.Frame(b)
        btns.grid(row=3, column=0, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="入れる", style="Accent.TButton", command=self.ok).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="キャンセル", command=self.cancel).pack(side="left")
        b.columnconfigure(0, weight=1)
        b.rowconfigure(1, weight=1)
        self.bind("<Return>", lambda e: self.ok())

    def ok(self):
        sel = self.list.curselection()
        if not sel:
            return
        self.result = self.items[sel[0]]
        self.destroy()


class PhrasesDialog(_Dialog):
    """1つの欄の例文を、足す・直す・消す・並べ替える。結果は例文のリスト。

    例文の一覧で、直接書いて直す（2026-11-14 班長指示「下側のテキストボックスを削除し、上側に直接入力できるようにする」。
    それまでは、一覧で選んだ例文を下の入力欄に出し、［足す］［直す］で一覧に戻していた）。例文ごとに入力欄を縦に並べ、
    何行かの字の欄（wrap）は、例文ごとの入力欄を折り返して表示し、字の量に合わせて高さを変える。1行の字・数の欄は、
    1行の入力欄。［上へ］［下へ］［消す］は、いま書いている（最後に入った）例文に効く。［足す］で、一番下に空の例文を足す。
    一覧の高さは、何行かの字の欄で 20 行、ほかで 10 行（右にスクロールバー）。空の例文は、OK のときに除く。
    """

    def __init__(self, master, items, field_label, field_font, wrap=False):
        super().__init__(master, "例文の登録")
        self.resizable(True, True)
        self.wrap = wrap
        self.font = field_font
        self.rows = []              # 例文ごとの入力欄（何行かの字は Text、ほかは ttk.Entry）
        self.current = None         # いま書いている例文の番号
        b = self.body
        ttk.Label(b, text=f"{field_label} の例文").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(b, text="例文は、一覧の中で直接書いて直します。依頼者や請求の対象者の名前は、例文に入れないでください"
                         "（例文は、請求をまたいで、この PC に残ります）。",
                  style="Note.TLabel", wraplength=theme.px(self, 460), justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(2, 6))
        line = tkfont.Font(root=self, font=field_font).metrics("linespace")
        rows = PHRASE_ROWS_WRAP if wrap else PHRASE_ROWS
        frame = ttk.Frame(b, style="Card.TFrame")
        frame.grid(row=2, column=0, sticky="nsew")
        self.canvas = tk.Canvas(frame, height=line * rows + 8, width=theme.px(self, 440), highlightthickness=0,
                                background=theme.FIELD_BG)
        bar = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(1, 0), pady=1)
        bar.grid(row=0, column=1, sticky="ns")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.inner = tk.Frame(self.canvas, background=theme.FIELD_BG)
        self._window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._fit_width)
        self.canvas.bind("<MouseWheel>", self._wheel)
        side = ttk.Frame(b)
        side.grid(row=2, column=1, sticky="n", padx=(8, 0))
        for text, cmd in (("足す", self._add), ("上へ", lambda: self._move(-1)), ("下へ", lambda: self._move(1)),
                          ("削除", self._delete)):
            ttk.Button(side, text=text, command=cmd, takefocus=False).pack(fill="x", pady=(0, 4))
        btns = ttk.Frame(b)
        btns.grid(row=3, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="OK", style="Accent.TButton", command=self.ok).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="キャンセル", command=self.cancel).pack(side="left")
        b.columnconfigure(0, weight=1)
        b.rowconfigure(2, weight=1)
        values = [s if wrap else s.replace("\n", " ") for s in items] or [""]
        self._build(values, focus=0 if not items else None)

    # ---- 一覧 ----
    def values(self):
        """いまの例文（書いたまま。空も含む）。"""
        out = []
        for w in self.rows:
            out.append(w.get("1.0", "end-1c") if isinstance(w, tk.Text) else w.get())
        return out

    def _build(self, values, focus=None):
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows = []
        for i, v in enumerate(values):
            if self.wrap:
                w = tk.Text(self.inner, height=2, wrap="char", font=self.font, relief="solid", borderwidth=1,
                            background=theme.FIELD_BG, foreground=theme.TEXT, highlightthickness=1,
                            highlightcolor=theme.ACCENT, highlightbackground=theme.FIELD_BG, undo=True, padx=4, pady=2)
                w.insert("1.0", v)
                w.edit_reset()
                w.bind("<KeyRelease>", lambda e, w=w: self._fit_height(w))
                w.bind("<Tab>", lambda e, i=i: (self._focus(i + 1), "break")[1])
                w.bind("<Shift-Tab>", lambda e, i=i: (self._focus(i - 1), "break")[1])
            else:
                w = ttk.Entry(self.inner, font=self.font)
                w.insert(0, v)
            w.pack(fill="x", padx=4, pady=(4, 0))
            w.bind("<FocusIn>", lambda e, i=i: self._entered(i))
            w.bind("<MouseWheel>", self._wheel)
            self.rows.append(w)
        tk.Frame(self.inner, height=4, background=theme.FIELD_BG).pack()
        self.update_idletasks()
        for w in self.rows:
            if isinstance(w, tk.Text):
                self._fit_height(w)
        if focus is not None:
            self._focus(focus)

    def _fit_width(self, event):
        self.canvas.itemconfigure(self._window, width=event.width)
        self.after_idle(lambda: [self._fit_height(w) for w in self.rows if isinstance(w, tk.Text)])

    def _fit_height(self, w):
        """何行かの字の例文の入力欄を、折り返した字の行の数に合わせる（2 行より低くしない）。"""
        if not w.winfo_exists():
            return
        try:
            lines = w.count("1.0", "end-1c", "displaylines")
        except tk.TclError:
            return
        n = (lines[0] if isinstance(lines, tuple) else lines) or 0
        n = max(2, n + 1)
        if int(w.cget("height")) != n:
            w.configure(height=n)

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120) * 2, "units")
        return "break"

    def _entered(self, i):
        self.current = i
        self._see(i)

    def _see(self, i):
        """例文 i の入力欄が見えるように、一覧を動かす。"""
        self.update_idletasks()
        w = self.rows[i]
        top, h = w.winfo_y(), w.winfo_height()
        total = max(self.inner.winfo_height(), 1)
        view0, view1 = self.canvas.yview()
        if top / total < view0:
            self.canvas.yview_moveto(max(0.0, (top - 4) / total))
        elif (top + h) / total > view1:
            self.canvas.yview_moveto(max(0.0, (top + h + 4) / total - (view1 - view0)))

    def _focus(self, i):
        if not self.rows:
            return
        i = max(0, min(i, len(self.rows) - 1))
        w = self.rows[i]
        w.focus_set()
        if isinstance(w, tk.Text):
            w.mark_set("insert", "end-1c")
        else:
            w.icursor("end")
        self.current = i
        self._see(i)

    # ---- ボタン ----
    def _add(self):
        values = self.values()
        if values and values[-1].strip() == "":
            self._focus(len(values) - 1)        # 一番下が空なら、そこに書く
            return
        self._build(values + [""], focus=len(values))

    def _delete(self):
        i = self.current
        if i is None or not self.rows:
            return
        values = self.values()
        del values[i]
        self._build(values or [""], focus=min(i, max(0, len(values) - 1)))

    def _move(self, d):
        i = self.current
        values = self.values()
        if i is None or not 0 <= i + d < len(values):
            return
        values[i], values[i + d] = values[i + d], values[i]
        self._build(values, focus=i + d)

    def ok(self):
        self.result = [v.strip("\n").rstrip() for v in self.values() if v.strip()]
        self.destroy()


class OptionsDialog(_Dialog):
    """［ファイル］→［オプション］。例文のファイルの置き場所を決める（2026-11-14 班長指示）。
    結果は、新しい置き場所（Path。既定に戻すときは None）。変えなければ、ダイアログの result は "unchanged"。"""

    def __init__(self, master, cfg, file_name):
        super().__init__(master, "オプション")
        self.cfg = cfg
        self.default = cfg.folder
        b = self.body
        ttk.Label(b, text="例文の保存場所", style="Section.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(b, text=f"例文は、この場所の「{file_name}」に保存します（A〜D 用紙の例文を1つのファイルにまとめます）。"
                         "事務所の共有フォルダを選ぶと、何人かで同じ例文を使えます。",
                  wraplength=theme.px(self, 460), justify="left").grid(row=1, column=0, columnspan=3, sticky="w",
                                                                      pady=(4, 6))
        self.var = tk.StringVar(value=str(cfg.phrases_folder()))
        ttk.Entry(b, textvariable=self.var, width=56, state="readonly").grid(row=2, column=0, sticky="we")
        ttk.Button(b, text="参照…", command=self._browse).grid(row=2, column=1, padx=(6, 0))
        ttk.Button(b, text="既定に戻す", command=lambda: self.var.set(str(self.default))).grid(row=2, column=2,
                                                                                         padx=(6, 0))
        ttk.Label(b, text="既定はこの PC の設定の場所です。依頼者や請求の対象者の名前は、例文に入れないでください。",
                  style="Note.TLabel", wraplength=theme.px(self, 460), justify="left").grid(
            row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))
        btns = ttk.Frame(b)
        btns.grid(row=4, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="OK", style="Accent.TButton", command=self.ok).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="キャンセル", command=self.cancel).pack(side="left")
        b.columnconfigure(0, weight=1)

    def _browse(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(parent=self, title="例文の保存場所", initialdir=self.var.get(), mustexist=True)
        if path:
            self.var.set(str(Path(path)))

    def ok(self):
        new = Path(self.var.get())
        if new == self.cfg.phrases_folder():
            self.result = "unchanged"
        else:
            self.result = None if new == self.default else new
        self.destroy()

    def cancel(self):
        self.result = "unchanged"
        self.destroy()


class DpiDialog(_Dialog):
    """画像に解像度の記録がないとき、スキャンしたときの解像度を尋ねる。"""

    def __init__(self, master):
        super().__init__(master, "用紙の画像")
        b = self.body
        ttk.Label(b, text="画像に解像度の記録がありません。スキャンしたときの解像度（dpi）を入れてください。",
                  wraplength=theme.px(self, 360), justify="left").grid(row=0, column=0, columnspan=2, sticky="w")
        self.var = tk.StringVar(value="300")
        ttk.Combobox(b, textvariable=self.var, values=["150", "200", "300", "400", "600"], width=8).grid(
            row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(b, text="dpi").grid(row=1, column=1, sticky="w", pady=(8, 0))
        btns = ttk.Frame(b)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="OK", style="Accent.TButton", command=self.ok).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="キャンセル", command=self.cancel).pack(side="left")
        self.bind("<Return>", lambda e: self.ok())

    def ok(self):
        try:
            v = _mm(self.var.get())
        except ValueError:
            v = 0
        if not 50 <= v <= 2400:
            messagebox.showerror(APP_NAME, "解像度は、50〜2400 の数で入れてください。", parent=self)
            return
        self.result = v
        self.destroy()
