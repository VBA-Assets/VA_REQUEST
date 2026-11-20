"""VA Request の画面（仕様.md の 4.3〜4.7）。

・用紙の画像と、その上に刷る字を重ねて表示する（プレビュー）。欄をクリックすると、用紙の上のその欄の位置に入力欄を
  重ねて出し、その場で字を入れる（ツールは欄の名前を持たない。利用者は、用紙の画像に刷ってある項目名を見て入れる）。
  囲み・印・元号は、用紙の上をクリックして付け外しする。右の欄は持たない（2026-11-15 班長指示「右側のペイン全体を削除」）。
・例文は、リボンの［例文の選択］で開く画面から選ぶ（同日 班長指示）。例文の登録と既定の値も、リボンのボタンで行う。
  選んでいる欄の呼び名と既定の値は、下の状態の行に出す。
・欄の呼び名は、日付欄・宛名欄と、表の左の列の空欄を上から数えた欄1・欄1-1 など（様式の定義の label）。
・［欄の位置］で、欄をドラッグして用紙に合わせる（ロットによる違い）。［用紙の画像］で、自分の用紙のスキャン画像を読み込む。
・PDF は用紙の画像入りで保存し、開き直して直せる。直した後の保存は上書きだけ（［別の名前で保存］はない）。
・印刷は字だけを、A4 の実際の大きさで刷る。保存していないか、保存した後に変えていれば、先に保存する。
"""
import io
import tkinter as tk
import tkinter.font as tkfont
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import pypdfium2 as pdfium
from PIL import Image, ImageTk

from . import ABOUT_LINE, APP_NAME, VERSION_LABEL, diagnostics, forms, pdfdoc, printing, render
from .config import Config
from .phrases import FILE_NAME as PHRASES_FILE, PhrasesChanged, PhrasesError, PhraseStore
from .dialogs import DpiDialog, OptionsDialog, PhraseSelectDialog, PhrasesDialog, PrintDialog
from .ui import ime, theme
from .ui.icons import IconSet
from .ui.ribbon import Ribbon
from .ui.window_icon import set_window_icon

FORM_LABELS = {"A": "A用紙　戸籍謄本等職務上請求書", "B": "B用紙　住民票の写し等職務上請求書",
               "C": "C用紙　戸籍謄本等請求書", "D": "D用紙　住民票の写し等請求書"}
KIND_LABELS = {"text": "1行の字", "multiline": "何行かの字", "number": "数", "circle": "囲み（○）",
               "check": "印（✓）", "date": "日付"}
PAGE_MM = (210.0, 297.0)
PAPER_FONTS = ("ＭＳ 明朝", "MS Mincho")      # 用紙の上の入力欄の書体（刷る字と同じ）
EDITOR_MIN_PX = 11          # 用紙の上の入力欄の字の高さの下限（96 dpi の画素。用紙を小さく表示したときも読めるように）
MARGIN = 12                 # プレビューの用紙のまわりの余白（画素）
RENDER_DELAY = 120          # 入力してからプレビューを描き直すまでの間（ms）
SNAP = 0.1                  # 位置を合わせるときの刻み（mm）
HANDLE = 7                  # 大きさを変えるつまみの大きさ（画素）

FIELD_OUTLINE = "#9cc8ef"
SELECT_OUTLINE = theme.ACCENT
OVERFLOW_OUTLINE = "#c00000"
POSITION_OUTLINE = "#ed7d31"
POSITION_FILL = "#fbe4d5"


class App:
    def __init__(self, root, cfg=None, open_path=None):
        self.root = root
        self.cfg = cfg or Config()
        self.errors = diagnostics.ErrorLog(Path(self.cfg.folder) / "errors.json")
        root.report_callback_exception = self._on_callback_error
        theme.apply_theme(root)
        ime.follow_focus(root)      # IME の入力中の字を、入力欄の書体で出す（VA Case と同じ）
        root.title(APP_NAME)
        set_window_icon(root)
        self.field_font = theme.field_font(root)
        self.icons = IconSet(root)
        self.phrase_store = PhraseStore(self.cfg.phrases_folder())
        self._migrate_phrases()

        self.key = self.cfg.get("form") if self.cfg.get("form") in forms.FORM_KEYS else "A"
        self.form = forms.effective(self.cfg, self.key)
        self.values = forms.known_values(self.form, self.cfg.defaults(self.key))
        self.path = None            # 保存した（開いた）PDF の場所。あれば、保存は上書きだけ
        self.opened = False         # PDF を開いた請求か（欄の位置と用紙の画像は、保存したときのもの）
        self.image_bytes = None     # 開いた PDF の用紙の画像
        self.dirty = False
        self.overflow = []
        self.mode = "input"         # input・position・corner
        self.selected = None        # 入力：選んだ欄の番号
        self.pos_sel = set()        # 位置合わせ：選んだ項目の名前
        self._render_job = None
        self._bg_cache = None
        self._photo = None
        self._ppm = 3.0
        self._drag = None
        self._corner_image = None
        self._suspend = False       # 入力欄を作り直している間、値の変化を拾わない
        self.editors = []           # 用紙の上に重ねた入力欄（日付は年・月・日の3つ）
        self.editor = None          # 例文を入れる先（いま字を入れている入力欄）
        families = set(tkfont.families(root))
        self.paper_family = next((f for f in PAPER_FONTS if f in families), None)

        self._build()
        self._load_modebar()
        self._update_title()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._restore_window()
        if open_path:
            root.after(50, lambda: self.open_pdf(open_path))

    # ================================================================ 画面の組み立て
    def _build(self):
        root = self.root
        self._build_menu()
        self.ribbon = Ribbon(root, self.icons)
        self.ribbon.pack(fill="x")
        g = self.ribbon.group("ファイル")
        # 並びはメニューと同じ（開く・保存・印刷・閉じる。標準 02「メニュー」）。［新しい請求］は置かない。起動したときから
        # 空の請求があり、書き終えたら［閉じる］で空の請求に戻す（2026-11-21 班長決定）
        self.btn_open = g.large("開く", self.open_dialog, icon="folder_open",
                                tip="VA Request で保存した PDF を開き、直したり、刷り直したりします（Ctrl+O）。")
        self.btn_save = g.large("保存", self.save, icon="save",
                                tip="用紙の画像と字を重ねた PDF を保存します（Ctrl+S）。弁護士に確かめてもらうためのものです。"
                                    "開き直した請求は、同じファイルに上書きします。")
        self.btn_print = g.large("印刷", self.print_request, icon="print",
                                 tip="字だけを、用紙に刷ります（Ctrl+P）。保存していなければ、先に PDF を保存します。")
        self.btn_close = g.small("閉じる", self.close_request, icon="document_dismiss",
                                 tip="今の請求を閉じて、空の請求にします（Ctrl+W）。既定の値を入れた欄は、初めから入っています。"
                                     "空の請求のまま何も入れていない間は、押せません。")

        g = self.ribbon.group("様式")
        self.form_var = tk.StringVar(value=FORM_LABELS[self.key])
        box = ttk.Combobox(g.body, textvariable=self.form_var, values=[FORM_LABELS[k] for k in forms.FORM_KEYS],
                           state="readonly", width=30, takefocus=False)
        box.bind("<<ComboboxSelected>>", lambda e: self.change_form())
        self.form_box = g.block(box)
        self.btn_paper = g.small("用紙の画像", self.paper_menu, icon="image",
                                 tip="自分の用紙（何も書いていないもの）をスキャンした画像を読み込みます。")
        self.btn_position = g.small("欄の位置", self.toggle_position, icon="table",
                                    tip="欄をドラッグして、用紙に合わせます。用紙のロットが替わったときに使います。")

        g = self.ribbon.group("入力")
        self.btn_choose = g.large("例文の選択", self.choose_phrase, icon="clipboard_paste",
                                  tip="選んでいる欄の例文を、一覧から選んで入れます。入力欄の、いまの文字の位置に入ります。")
        self.btn_phrases = g.small("例文の登録", self.edit_phrases, icon="text_bullet_list_square",
                                   tip="選んでいる欄の例文を、足したり直したりします。")
        self.btn_default = g.small("既定の値にする", self.set_default, icon="save_edit",
                                   tip="選んでいる欄の今の値を、新しい請求の初めから入れておきます（弁護士の氏名・登録番号など）。")
        self.btn_clear_default = g.small("既定の値を消す", self.clear_default, icon="delete",
                                         tip="選んでいる欄の既定の値を消します。新しい請求の初めから入らなくなります。")
        self.btn_today = g.small("今日の日付", self.today, icon="calendar_checkmark",
                                 tip="選んでいる日付の欄（選んでいなければ日付欄）に、今日の日付を入れます。")

        self.status = ttk.Label(root, style="Status.TLabel", anchor="w")
        self.status.pack(fill="x", side="bottom")
        # 欄の位置合わせ・用紙の左上の角を決める間だけ、リボンの下に出す帯（右の欄を除いたので、ここに置く）
        self.modebar = ttk.Frame(root, padding=(10, 6))

        body = ttk.Frame(root)
        body.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(body, background="#d9d9d9", highlightthickness=0, takefocus=True)
        vbar = ttk.Scrollbar(body, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)
        self.body = body

        c = self.canvas
        c.bind("<Configure>", lambda e: self.schedule_render(resize=True))
        c.bind("<ButtonPress-1>", self._on_press)
        c.bind("<B1-Motion>", self._on_motion)
        c.bind("<ButtonRelease-1>", self._on_release)
        c.bind("<MouseWheel>", self._wheel)
        c.bind("<Escape>", lambda e: self.deselect() if self.mode == "input" else None)
        for key, d in (("Left", (-1, 0)), ("Right", (1, 0)), ("Up", (0, -1)), ("Down", (0, 1))):
            c.bind(f"<{key}>", lambda e, d=d: self._nudge(d, 0.5))
            c.bind(f"<Shift-{key}>", lambda e, d=d: self._nudge(d, SNAP))
        # ショートカット。Mac では Ctrl に加えて ⌘ でも同じ働きにする（⌘ は Mac のときだけ。標準 02「メニュー」）。
        # Caps Lock でも効くよう大文字にも付ける
        mods = ("Control", "Command") if root.tk.call("tk", "windowingsystem") == "aqua" else ("Control",)
        for letter, cmd in (("s", self.save), ("p", self.print_request), ("o", self.open_dialog),
                            ("w", self.close_request)):
            for mod in mods:
                for k in (letter, letter.upper()):
                    root.bind_all(f"<{mod}-Key-{k}>", lambda e, cmd=cmd: (cmd(), "break")[1])

    def _build_menu(self):
        bar = tk.Menu(self.root)
        # ［ファイル］：開く・保存・閉じる（2026-11-14 班長指示。［新しい請求］を［閉じる］に改めた。2026-11-21 班長決定。
        # 標準 02「メニュー」）とオプション
        fm = tk.Menu(bar, tearoff=False)
        fm.add_command(label="開く…", accelerator="Ctrl+O", command=self.open_dialog)
        fm.add_command(label="保存", accelerator="Ctrl+S", command=self.save)
        fm.add_command(label="閉じる", accelerator="Ctrl+W", command=self.close_request)
        fm.add_separator()
        fm.add_command(label="オプション…", command=self.options)
        bar.add_cascade(label="ファイル", menu=fm)
        self.file_menu = fm
        h = tk.Menu(bar, tearoff=False)
        h.add_command(label="診断情報をコピー", command=self.copy_diagnostics)
        h.add_separator()
        h.add_command(label=f"{APP_NAME} について", command=self.about)
        bar.add_cascade(label="ヘルプ", menu=h)
        self.root.configure(menu=bar)

    # ================================================================ 状態の表示
    def _update_title(self):
        name = Path(self.path).name if self.path else "新しい請求"
        self.root.title(f"{'＊' if self.dirty else ''}{name} - {APP_NAME}")
        parts = [FORM_LABELS[self.key]]
        if self.mode == "input":
            parts.append(self._field_status())
        if self.opened:
            parts.append("開いた PDF（保存は上書き）")
        elif self.path:
            parts.append("保存は上書き")
        if self.dirty:
            parts.append("保存していない変更があります")
        if self.overflow:
            parts.append(f"入りきらない欄：{self._labels(self.overflow)}")
        if self.mode == "position":
            parts.append("欄の位置を合わせています")
        elif self.mode == "corner":
            parts.append("用紙の左上の角をクリックしてください")
        self.status.configure(text="　｜　".join(parts))
        state = "disabled" if self.mode != "input" else "normal"
        for b in (self.btn_save, self.btn_print, self.btn_choose, self.btn_phrases, self.btn_default,
                  self.btn_clear_default, self.btn_today):
            b.configure(state=state)
        for label in ("開く…", "保存", "オプション…"):     # 位置合わせの間は、ファイルの操作をしない
            self.file_menu.entryconfigure(label, state=state)
        self.btn_open.configure(state=state)
        # ［閉じる］は、空の請求のまま何も入れていない間も押せない（標準 02「メニュー」。2026-11-21 班長決定）
        close_state = "disabled" if self.mode != "input" or self.is_blank() else "normal"
        self.file_menu.entryconfigure("閉じる", state=close_state)
        self.btn_close.configure(state=close_state)
        for b in (self.btn_paper, self.btn_position):
            b.configure(state="disabled" if self.opened or self.mode == "corner" else "normal")
        self.form_box.configure(state="disabled" if self.opened or self.mode != "input" else "readonly")

    def _field_status(self):
        """状態の行に出す、選んでいる欄の呼び名・種類・既定の値と、操作の案内（右の欄に出していたもの）。"""
        if self.selected is None:
            return "欄（点線の四角）をクリックすると、その場で字を入れられます。○ と ✓ は、用紙の上の語や□をクリックします"
        f = self.field(self.selected)
        kind = f["type"]
        text = f"{forms.label(f)}（{KIND_LABELS[kind]}）"
        # 既定の値は、あるときだけ、その値を出す（2026-11-14 班長指示。「既定の値：なし」は出さない）
        default = self.cfg.defaults(self.key).get(f["id"])
        if default is not None:
            text += "　既定の値：" + self.value_text(f, default)
        hint = {"text": "Enter・Tab で次の欄", "number": "Enter・Tab で次の欄",
                "multiline": "欄の幅で折り返します。Enter で改行、Tab で次の欄",
                "date": "Tab で年・月・日を移ります" + ("。元号は、用紙の上の語をクリック" if "era" in f else ""),
                "circle": f"用紙の上の{'番号' if f.get('direction') == 'down' else '語'}をクリックすると ○ が付き、"
                          "もう一度で外れます",
                "check": "□ をクリックすると ✓ が付き、もう一度で外れます"}[kind]
        return f"{text}　（{hint}）"

    def _labels(self, ids):
        return "・".join(forms.label(self.field(i)) for i in ids)

    def set_dirty(self, value=True):
        if self.dirty != value:
            self.dirty = value
        self._update_title()

    # ================================================================ プレビュー
    def schedule_render(self, resize=False):
        if resize:
            self._bg_cache = None
        if self._render_job is not None:
            self.root.after_cancel(self._render_job)
        self._render_job = self.root.after(RENDER_DELAY, self.render_now)

    def _page_px(self):
        width = max(self.canvas.winfo_width(), 200)
        ppm = max(1.5, (width - 2 * MARGIN) / PAGE_MM[0])
        return ppm, round(PAGE_MM[0] * ppm), round(PAGE_MM[1] * ppm)

    def _background(self, ppm, w, h):
        """用紙の画像を、プレビューの大きさにしたもの（覚えておく）。"""
        src = self._corner_image if self.mode == "corner" else (self.image_bytes or self.form["image_path"])
        box = None if self.mode == "corner" else tuple(self.form["image"]["box"])
        key = (id(src) if isinstance(src, (bytes, Image.Image)) else src, box, round(ppm, 3))
        if self._bg_cache and self._bg_cache[0] == key:
            return self._bg_cache[1]
        page = Image.new("RGB", (w, h), "white")
        if self.mode == "corner":
            img, dpi = self._corner_image
            sw = round(img.width / dpi * 25.4 * ppm)
            sh = round(img.height / dpi * 25.4 * ppm)
            page = Image.new("RGB", (max(w, sw), max(h, sh)), "white")
            page.paste(img.convert("RGB").resize((sw, sh), Image.LANCZOS), (0, 0))
        else:
            with Image.open(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src) as img:
                l, t, r, b = box
                img = img.convert("RGB").resize((max(1, round((r - l) * ppm)), max(1, round((b - t) * ppm))),
                                                Image.LANCZOS)
                page.paste(img, (round(l * ppm), round(t * ppm)))
        self._bg_cache = (key, page)
        return page

    def render_now(self):
        self._render_job = None
        if not self.canvas.winfo_exists():
            return
        ppm, w, h = self._page_px()
        self._ppm = ppm
        page = self._background(ppm, w, h).copy()
        if self.mode != "corner":
            data, self.overflow = render.make_pdf(self.form, self.values, with_image=False)
            doc = pdfium.PdfDocument(data)
            layer = doc[0].render(scale=ppm * 25.4 / 72, fill_color=(255, 255, 255, 0)).to_pil().convert("RGBA")
            doc.close()
            page = page.convert("RGBA")
            page.alpha_composite(layer.resize(page.size) if layer.size != page.size else layer)
        self._photo = ImageTk.PhotoImage(page.convert("RGB"), master=self.root)
        c = self.canvas
        c.delete("page", "overlay")         # 用紙の上の入力欄（editor）は消さない（入力の途中で描き直すため）
        c.create_image(MARGIN, MARGIN, image=self._photo, anchor="nw", tags="page")
        c.tag_lower("page")
        c.configure(scrollregion=(0, 0, page.width + 2 * MARGIN, page.height + 2 * MARGIN))
        self.draw_overlay()
        self._layout_editors()
        self._update_title()

    def _to_px(self, box):
        p = self._ppm
        return (MARGIN + box[0] * p, MARGIN + box[1] * p, MARGIN + box[2] * p, MARGIN + box[3] * p)

    def _to_mm(self, event):
        c = self.canvas
        return ((c.canvasx(event.x) - MARGIN) / self._ppm, (c.canvasy(event.y) - MARGIN) / self._ppm)

    def draw_overlay(self):
        c = self.canvas
        c.delete("overlay")
        if self.mode == "corner":
            return
        for name, box, f in forms.items(self.form):
            x0, y0, x1, y1 = self._to_px(box)
            if self.mode == "position":
                sel = name in self.pos_sel
                c.create_rectangle(x0, y0, x1, y1, outline=POSITION_OUTLINE, width=2 if sel else 1,
                                   fill=POSITION_FILL if sel else "", stipple="gray25" if sel else "", tags="overlay")
                if sel and len(self.pos_sel) == 1 and "." not in name and f["type"] != "check":
                    c.create_rectangle(x1 - HANDLE, y1 - HANDLE, x1, y1, outline=POSITION_OUTLINE,
                                       fill=POSITION_OUTLINE, tags="overlay")
                continue
            if f["id"] in self.overflow:
                c.create_rectangle(x0, y0, x1, y1, outline=OVERFLOW_OUTLINE, width=2, tags="overlay")
            elif f["id"] == self.selected:
                c.create_rectangle(x0, y0, x1, y1, outline=SELECT_OUTLINE, width=2, tags="overlay")
            else:
                c.create_rectangle(x0, y0, x1, y1, outline=FIELD_OUTLINE, dash=(2, 2), tags="overlay")

    def hit(self, x, y):
        """mm の位置にある項目 (名前, 欄)。重なるときは小さいほう。"""
        found = [(abs((b[2] - b[0]) * (b[3] - b[1])), n, f) for n, b, f in forms.items(self.form)
                 if b[0] - 0.8 <= x <= b[2] + 0.8 and b[1] - 0.8 <= y <= b[3] + 0.8]
        if not found:
            return None, None
        _, n, f = min(found, key=lambda t: t[0])
        return n, f

    # ================================================================ 入力
    def field(self, fid):
        return next(f for f in self.form["fields"] if f["id"] == fid)

    def set_value(self, fid, value):
        if forms.is_empty(value):
            self.values.pop(fid, None)
        else:
            self.values[fid] = value
        self.set_dirty()
        self.schedule_render()

    def _on_press(self, event):
        self.canvas.focus_set()
        x, y = self._to_mm(event)
        if self.mode == "corner":
            self._corner_click(x, y)
            return
        if self.mode == "position":
            self._pos_press(event, x, y)
            return
        name, f = self.hit(x, y)
        if f is None:
            if self.selected is not None:
                self.deselect()             # 用紙の空いた所をクリックすると、入力欄を閉じて刷り上がりの形を見せる
            return
        fid, sub = f["id"], name.partition(".")[2]
        if f["type"] == "circle":
            i = int(sub[1:])
            self.set_value(fid, None if self.values.get(fid) == i else i)
        elif f["type"] == "check":
            self.set_value(fid, not self.values.get(fid, False))
        elif f["type"] == "date" and sub.startswith("e"):
            v = dict(self.values.get(fid) or {})
            i = int(sub[1:])
            v["era"] = None if v.get("era") == i else i
            self.set_value(fid, {k: x for k, x in v.items() if x is not None})
        self.select(fid, focus_part=sub if sub in forms.PARTS else None)

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120) * 3, "units")
        return "break"

    # ================================================================ 用紙の上の入力欄
    # 右の欄の入力欄に代えて、用紙の上のその欄の位置に入力欄を重ねて出す（2026-11-15 班長指示「プレビュー画面に直接
    # 入力するようにできないか」「右側のペイン全体を削除」）。入力欄はキャンバスの窓の項目（create_window）で、用紙と
    # 一緒にスクロールし、用紙の大きさが変わると、位置・大きさ・字の大きさを合わせ直す。入力している間の字は画面の
    # 書体（ＭＳ 明朝）で出し、入りきらないときの縮小は、ほかの欄に移ると（入力欄を閉じると）刷り上がりの形で見える。
    def select(self, fid, focus_part=None):
        """欄を選び、入力欄を出す。同じ欄を選び直したときは、入力欄はそのままで focus_part（年・月・日）に移る。"""
        if fid is not None and fid == self.selected and self.editors:
            self._focus_part(focus_part)
        else:
            self.selected = fid
            self._open_editor(focus_part)
        self.draw_overlay()
        self._update_title()

    def deselect(self):
        self.selected = None
        self._close_editor()
        self.draw_overlay()
        self._update_title()
        self.canvas.focus_set()

    def _close_editor(self):
        self.canvas.delete("editor")
        for ed in self.editors:
            ed["widget"].destroy()
        self.editors = []
        self.editor = None

    def _open_editor(self, focus_part=None):
        self._close_editor()
        if self.selected is None or self.mode != "input":
            return
        f = self.field(self.selected)
        kind = f["type"]
        self._suspend = True
        try:
            if kind in ("text", "number"):
                self._editor_line(f)
            elif kind == "multiline":
                self._editor_multi(f)
            elif kind == "date":
                self._editor_date(f)
        finally:
            self._suspend = False
        self._layout_editors()
        self._focus_part(focus_part)

    def _paper_font(self):
        if self.paper_family:
            return tkfont.Font(root=self.root, family=self.paper_family, size=-12)
        return tkfont.Font(root=self.root, font=self.field_font)

    def _add_editor(self, widget, box, kind, font, part=None, var=None):
        item = self.canvas.create_window(0, 0, window=widget, anchor="nw", tags="editor")
        widget.bind("<MouseWheel>", self._wheel)
        widget.bind("<Escape>", lambda e: (self.deselect(), "break")[1])
        widget.bind("<FocusIn>", lambda e, w=widget: setattr(self, "editor", w), add="+")
        self.editors.append({"widget": widget, "item": item, "box": box, "kind": kind, "font": font, "part": part,
                             "var": var})

    def _editor_px(self, kind, box):
        """入力欄の字の高さ（画素）。刷る字の大きさ（render の上限）を、いまの表示の縮尺にしたもの。"""
        if kind == "multiline":
            pt = render.SIZE_MULTI
        else:
            pt = min(render.SIZE_MAX, (box[3] - box[1]) / 25.4 * 72 * 0.85)
        # 切り捨てる（画面の書体は刷る字より少し幅を取るので、入力欄が刷り上がりより早く折り返さないように）
        return max(theme.px(self.root, EDITOR_MIN_PX), int(pt / 72 * 25.4 * self._ppm))

    def _layout_editors(self):
        """入力欄を、欄の位置と大きさに合わせる（用紙の大きさが変わったときも）。字が欄より高ければ、入力欄を広げる。"""
        c = self.canvas
        for ed in self.editors:
            x0, y0, x1, y1 = self._to_px(ed["box"])
            font = ed["font"]
            size = self._editor_px(ed["kind"], ed["box"])
            if ed.get("size") != size:      # 入力のたびに描き直すので、大きさが変わったときだけ付け直す
                ed["size"] = size
                font.configure(size=-size)
                if isinstance(ed["widget"], ttk.Entry):
                    # ttk の入力欄は、書体の大きさを変えても、字が変わるまでカーソルの高さを前の大きさ（作ったときの
                    # 12 画素）のままにする（2026-11-15 班長指摘「カーソルの縦の長さが短い」。1行の字の欄だけで、何行かの字の
                    # 欄〔Text〕は正常）。書体を付け直して、カーソルの高さを測り直させる
                    ed["widget"].configure(font=font)
            line = font.metrics("linespace")
            w, h = x1 - x0, y1 - y0
            if ed["part"] == "year" and not self._form_has_era_printed():
                w = max(w, font.measure("令和00") + 6)      # A・B は年に元号を付けて入れる（［今日の日付］も）
            if ed["kind"] == "multiline":
                ed["widget"].configure(spacing3=round(size * (render.LINE_GAP - 1)))
                h = max(h, 2 * line + 4)
            else:
                h = max(h, line + 4)
            c.coords(ed["item"], x0, y0)
            c.itemconfigure(ed["item"], width=round(w), height=round(h))

    def _focus_part(self, part=None):
        if not self.editors:
            self.canvas.focus_set()
            return
        ed = next((e for e in self.editors if e["part"] == part), self.editors[0])
        w = ed["widget"]
        w.focus_set()
        if isinstance(w, tk.Text):
            w.mark_set("insert", "end")
        else:
            w.icursor("end")
        self.editor = w

    def _see_editor(self):
        """入力欄が見えていなければ、見える所までスクロールする（Tab で次の欄に移ったとき）。"""
        if not self.editors:
            return
        c = self.canvas
        y0 = min(self._to_px(e["box"])[1] for e in self.editors)
        y1 = max(self._to_px(e["box"])[3] for e in self.editors)
        top = c.canvasy(0)
        height = c.winfo_height()
        try:
            total = float(str(c.cget("scrollregion")).split()[3])
        except (IndexError, ValueError):
            return
        if total > 0 and (y0 < top or y1 > top + height):
            c.yview_moveto(max(0.0, (y0 - height / 3) / total))

    def _keys(self, widget, tab=None, back=None):
        """Enter・Tab で次の欄、Shift+Tab で前の欄（何行かの字の欄は、Enter で改行するので Enter を拾わない）。"""
        if not isinstance(widget, tk.Text):
            widget.bind("<Return>", lambda ev: (self.next_field(1), "break")[1])
        widget.bind("<Tab>", lambda ev: ((tab or (lambda: self.next_field(1)))(), "break")[1])
        widget.bind("<Shift-Tab>", lambda ev: ((back or (lambda: self.next_field(-1)))(), "break")[1])

    def _editor_line(self, f):
        var = tk.StringVar(value=str(self.values.get(f["id"], "")))
        font = self._paper_font()
        e = ttk.Entry(self.canvas, textvariable=var, font=font, style="Paper.TEntry")
        var.trace_add("write", lambda *a: self._suspend or self.set_value(f["id"], var.get()))
        self._keys(e)
        self._add_editor(e, f["box"], f["type"], font, var=var)

    def _editor_multi(self, f):
        font = self._paper_font()
        insert = theme.px(self.root, theme.PAPER_INSERT_WIDTH)
        t = tk.Text(self.canvas, width=1, height=1, wrap="char", font=font, relief="flat", borderwidth=0, padx=1, pady=0,
                    background=theme.FIELD_BG, foreground=theme.TEXT, insertbackground=theme.TEXT, insertwidth=insert,
                    highlightthickness=1, highlightcolor=theme.ACCENT, highlightbackground=theme.ACCENT, undo=True)
        # Text はカーソルを字の境目を中心に描き、行の中の左端より左は描かない。行の頭（空の欄・2行目の頭）では左半分が
        # 消えて、1行の欄の半分の太さになる（2026-11-15 班長指摘「欄8-6や欄9-2は細い」。2 画素が 1 画素だった）。
        # 余白（padx）は行の外なので効かない。行の中の左の余白（lmargin）をカーソルの太さだけ付けて、隠れないようにする。
        # 打った字にも付くよう、字が変わるたびに全体に付け直す
        t.tag_configure("margin", lmargin1=insert, lmargin2=insert)
        t.insert("1.0", str(self.values.get(f["id"], "")))
        t.tag_add("margin", "1.0", "end")
        t.edit_modified(False)

        def changed(event=None):
            if t.edit_modified():
                t.edit_modified(False)
                t.tag_add("margin", "1.0", "end")
                if not self._suspend:
                    self.set_value(f["id"], t.get("1.0", "end-1c"))
        t.bind("<<Modified>>", changed)
        self._keys(t)
        self._add_editor(t, f["box"], "multiline", font)

    def _editor_date(self, f):
        v = dict(self.values.get(f["id"]) or {})
        parts = [p for p in forms.PARTS if p in f.get("parts", {})]
        vars_ = {}

        def changed(*a):
            if self._suspend:
                return
            cur = dict(self.values.get(f["id"]) or {})
            for p, var in vars_.items():
                cur[p] = var.get().strip()
            self.set_value(f["id"], {k: x for k, x in cur.items() if x not in ("", None)})

        def step(i, d):
            j = i + d
            if 0 <= j < len(self.editors):
                self._focus_part(self.editors[j]["part"])
            else:
                self.next_field(d)
        for i, part in enumerate(parts):
            var = tk.StringVar(value=str(v.get(part, "")))
            font = self._paper_font()
            e = ttk.Entry(self.canvas, textvariable=var, font=font, style="Paper.TEntry")
            var.trace_add("write", changed)
            vars_[part] = var
            self._keys(e, tab=lambda i=i: step(i, 1), back=lambda i=i: step(i, -1))
            self._add_editor(e, f["parts"][part], "date", font, part=part, var=var)

    def today(self):
        """［今日の日付］：選んでいる日付の欄（選んでいなければ日付欄）に、今日の日付を入れる。"""
        if self.mode != "input":
            return
        dates = [f for f in self.form["fields"] if f["type"] == "date"]
        if not dates:
            return
        if self.selected is None or self.field(self.selected)["type"] != "date":
            self.select(dates[0]["id"])
        d = date.today()
        year = str(d.year - 2018)
        if not self._form_has_era_printed():
            year = f"令和{year}"
        cur = dict(self.values.get(self.selected) or {})
        cur.update(year=year, month=str(d.month), day=str(d.day))
        self.set_value(self.selected, cur)
        self._suspend = True
        try:
            for ed in self.editors:
                if ed["var"] is not None and ed["part"] in cur:
                    ed["var"].set(cur[ed["part"]])
        finally:
            self._suspend = False

    @staticmethod
    def value_text(f, v):
        """欄の値を、画面に出す1つの文にする（既定の値の表示）。"""
        kind = f["type"]
        if kind == "circle":
            return f"○（{'上' if f.get('direction') == 'down' else '左'}から {int(v) + 1} 番目）"
        if kind == "check":
            return "✓"
        if kind == "date":
            era = f"元号は左から {v['era'] + 1} 番目、" if v.get("era") is not None else ""
            return era + "".join(f"{v[p]}{u}" for p, u in (("year", "年"), ("month", "月"), ("day", "日")) if v.get(p))
        return str(v)

    def _form_has_era_printed(self):
        """日付の欄の前に元号（平成）が刷ってある様式（C・D）。年は数だけを刷る（2026-11-14 班長決定）。"""
        return self.key in ("C", "D")

    def choose_phrase(self):
        """［例文の選択］：選んでいる欄の例文を、選択の画面で選んで入れる（2026-11-15 班長指示。右の欄の一覧に代えて）。"""
        if self.mode != "input":
            return
        if self.selected is None or self.field(self.selected)["type"] not in ("text", "number", "multiline"):
            messagebox.showinfo(APP_NAME, "例文は、字を入れる欄を選んでから選びます。", parent=self.root)
            return
        f = self.field(self.selected)
        try:
            items = self.phrase_store.phrases(self.key, f["id"])
        except PhrasesError:
            messagebox.showerror(APP_NAME, "例文のファイルを読めません。保存場所（［ファイル］→［オプション］）に"
                                        "つながっているかを確かめてください。", parent=self.root)
            return
        if not items:
            messagebox.showinfo(APP_NAME, f"この欄（{forms.label(f)}）の例文はありません。リボンの［例文の登録］で足せます。",
                                parent=self.root)
            return
        text = PhraseSelectDialog(self.root, items, forms.label(f), self.field_font,
                                  wrap=f["type"] == "multiline").show()
        if text is None:
            if self.editor is not None and self.editor.winfo_exists():
                self.editor.focus_set()
            return
        self.insert_phrase(text)

    def insert_phrase(self, text):
        e = self.editor
        if e is None or not e.winfo_exists():
            return
        if isinstance(e, tk.Text):
            e.insert("insert", text)
        else:
            e.insert("insert", text.replace("\n", " "))
        e.focus_set()

    def next_field(self, step):
        """入力する欄（字・数・何行か・日付）を、番号の順に移る。"""
        ids = [f["id"] for f in self.form["fields"] if f["type"] in ("text", "number", "multiline", "date")]
        if not ids:
            return
        cur = self.selected if self.selected in ids else ids[0] - step
        idx = (ids.index(cur) + step) % len(ids) if cur in ids else 0
        self.select(ids[idx])
        if step < 0 and len(self.editors) > 1:
            self._focus_part(self.editors[-1]["part"])      # 前の欄へ戻るときは、日付の日に入る
        self._see_editor()

    def edit_phrases(self):
        if self.selected is None or self.field(self.selected)["type"] not in ("text", "number", "multiline"):
            messagebox.showinfo(APP_NAME, "例文は、字を入れる欄を選んでから登録します。", parent=self.root)
            return
        fid = self.selected
        f = self.field(fid)
        store = self.phrase_store
        try:
            stamp = store.stamp()
            items = store.phrases(self.key, fid)
        except PhrasesError:
            messagebox.showerror(APP_NAME, "例文のファイルを読めません。保存場所（［ファイル］→［オプション］）に"
                                        "つながっているかを確かめてください。", parent=self.root)
            return
        result = PhrasesDialog(self.root, items, forms.label(f), self.field_font,
                               wrap=f["type"] == "multiline").show()
        if result is None:
            return
        try:
            try:
                store.save_field(self.key, fid, result, expected_stamp=stamp)
            except PhrasesChanged:
                if not messagebox.askyesno(
                        APP_NAME, "例文の登録の画面を開いている間に、ほかの人（またはほかの画面）が例文のファイルを"
                               f"変えました。\n\nこの欄（{forms.label(f)}）の例文を、いま登録した内容で書きますか？"
                               "（ほかの欄の例文は、変えられたもののまま残ります）", parent=self.root):
                    self._update_title()
                    return
                store.save_field(self.key, fid, result, force=True)
        except PhrasesError:
            messagebox.showerror(APP_NAME, "例文のファイルに書けませんでした。保存場所（［ファイル］→［オプション］）に"
                                        "つながっているか、ほかのソフトで開いていないかを確かめてください。",
                                 parent=self.root)
            return
        self._update_title()

    def _migrate_phrases(self):
        """前の版で設定ファイルに書いていた例文を、例文のファイルへ移す（ファイルにある例文の後ろに足す）。"""
        legacy = {k: self.cfg.legacy_phrases(k) for k in forms.FORM_KEYS}
        if not any(legacy.values()):
            return
        try:
            data = self.phrase_store.load_all()
            for key, table in legacy.items():
                for fid, items in table.items():
                    cur = data.setdefault(key, {}).setdefault(fid, [])
                    cur.extend(x for x in items if x not in cur)
            self.phrase_store.save_all(data)
        except PhrasesError:
            return              # 移せなければ、設定ファイルに残しておき、次に起動したときに移す
        for key in forms.FORM_KEYS:
            self.cfg.drop_legacy_phrases(key)
        self.cfg.save()

    def options(self):
        """［ファイル］→［オプション］：例文の保存場所。"""
        if self.mode != "input":
            return
        chosen = OptionsDialog(self.root, self.cfg, PHRASES_FILE).show()
        if chosen == "unchanged":
            return
        new_store = PhraseStore(chosen if chosen is not None else self.cfg.folder)
        try:
            if not new_store.exists():
                current = self.phrase_store.load_all()
                if any(current.values()) and messagebox.askyesno(
                        APP_NAME, f"新しい保存場所には「{PHRASES_FILE}」がありません。今の例文を、新しい保存場所に"
                               "写しますか？\n\n［いいえ］を選ぶと、例文のない状態から始めます。", parent=self.root):
                    new_store.save_all(current)
        except PhrasesError:
            messagebox.showerror(APP_NAME, "新しい保存場所に例文を写せませんでした。保存場所を変えずに戻ります。",
                                 parent=self.root)
            return
        self.cfg.set_phrases_folder(chosen)
        self.cfg.save()
        self.phrase_store = new_store
        self._update_title()

    def set_default(self):
        if self.selected is None:
            messagebox.showinfo(APP_NAME, "既定の値にする欄を選んでください。", parent=self.root)
            return
        v = self.values.get(self.selected)
        if forms.is_empty(v):
            messagebox.showinfo(APP_NAME, "欄が空です。字を入れてから［既定の値にする］を押してください。", parent=self.root)
            return
        self.cfg.set_default(self.key, self.selected, v)
        self.cfg.save()
        self._update_title()

    def clear_default(self):
        if self.selected is None:
            return
        self.cfg.set_default(self.key, self.selected, None)
        self.cfg.save()
        self._update_title()

    # ================================================================ 請求（新しい・開く・保存）
    def _confirm_discard(self):
        if not self.dirty:
            return True
        return messagebox.askyesno(APP_NAME, "保存していない変更があります。変更を捨てますか？", icon="warning",
                                   default="no", parent=self.root)

    def _reset(self, key, form, values, path=None, opened=False, image=None):
        self.key, self.form, self.values = key, form, forms.known_values(form, values)
        self.path, self.opened, self.image_bytes = path, opened, image
        self.selected = None
        self.pos_sel.clear()
        self.mode = "input"
        self.dirty = False
        self._bg_cache = None
        self.form_var.set(FORM_LABELS[key])
        self._close_editor()
        self._load_modebar()
        self.render_now()

    def is_blank(self):
        """空の請求のまま何も入れていないか（保存も開きもしておらず、変更がない。［閉じる］を押せない）。"""
        return not self.path and not self.dirty

    def close_request(self):
        """［閉じる］：今の請求を閉じて、空の請求にする（既定の値だけを入れる。前の請求の内容を残さない）。"""
        if self.mode != "input" or self.is_blank() or not self._confirm_discard():
            return
        self._reset(self.key, forms.effective(self.cfg, self.key), self.cfg.defaults(self.key))

    def change_form(self):
        key = next(k for k, v in FORM_LABELS.items() if v == self.form_var.get())
        if key == self.key:
            return
        if not self._confirm_discard():
            self.form_var.set(FORM_LABELS[self.key])
            return
        self.cfg.set("form", key)
        self.cfg.save()
        self._reset(key, forms.effective(self.cfg, key), self.cfg.defaults(key))

    def open_dialog(self):
        if self.mode != "input" or not self._confirm_discard():
            return
        path = filedialog.askopenfilename(parent=self.root, title="開く", filetypes=[("PDF", "*.pdf")],
                                          initialdir=self.cfg.get("last_folder") or None)
        if path:
            self.open_pdf(path, confirmed=True)

    def open_pdf(self, path, confirmed=False):
        if not confirmed and not self._confirm_discard():
            return
        try:
            opened = pdfdoc.read(path)
        except pdfdoc.NotRequestPdf:
            messagebox.showerror(APP_NAME, "この PDF は開けません。VA Request で保存した PDF だけを開けます。", parent=self.root)
            return
        except OSError:
            messagebox.showerror(APP_NAME, "PDF を読めませんでした。", parent=self.root)
            return
        key = opened["form"]
        form = pdfdoc.form_of(opened, forms.effective(self.cfg, key))
        form["image_path"] = None
        self.cfg.set("last_folder", str(Path(path).parent))
        self.cfg.save()
        self._reset(key, form, opened["values"], path=str(path), opened=True, image=opened["image"])

    def _check_overflow(self, action):
        _, overflow = render.make_pdf(self.form, self.values, with_image=False)
        self.overflow = overflow
        self.draw_overlay()
        if not overflow:
            return True
        return messagebox.askokcancel(
            APP_NAME, f"{self._labels(overflow)} は、字を小さくしても欄に入りきりません（赤い四角）。"
                   f"字は削らずにそのまま{action}ので、欄からはみ出します。続けますか？", icon="warning", parent=self.root)

    def save(self):
        """PDF を保存する。保存したら True。開いた請求・保存した請求は、同じファイルに上書きする。"""
        if self.mode != "input":
            return False
        if not self._check_overflow("保存します"):
            return False
        path = self.path
        if not path:
            path = filedialog.asksaveasfilename(
                parent=self.root, title="保存", defaultextension=".pdf", filetypes=[("PDF", "*.pdf")],
                initialdir=self.cfg.get("last_folder") or None,
                initialfile=f"職務上請求書_{date.today():%Y%m%d}.pdf")
            if not path:
                return False
        try:
            pdfdoc.save(path, self.form, self.values, image=self.image_bytes)
        except OSError:
            messagebox.showerror(APP_NAME, "PDF を書き込めませんでした。ほかのソフトでこの PDF を開いていれば、閉じてから、"
                                        "もう一度保存してください。", parent=self.root)
            return False
        self.path = str(path)
        self.cfg.set("last_folder", str(Path(path).parent))
        self.cfg.save()
        self.set_dirty(False)
        return True

    # ================================================================ 印刷
    def _print_form(self):
        """印刷に使う欄の位置。開いた請求で、今の設定の位置と違えば、どちらで刷るか尋ねる（None ならやめる）。"""
        if not self.opened:
            return self.form
        current = forms.effective(self.cfg, self.key)
        if forms.field_positions(current) == forms.field_positions(self.form):
            return self.form
        ans = messagebox.askyesnocancel(
            APP_NAME, "この請求を保存した後に、欄の位置を合わせ直しています（用紙のロットが替わったときなど）。\n\n"
                   "［はい］今の位置で刷る\n［いいえ］保存したときの位置で刷る", parent=self.root)
        if ans is None:
            return None
        return forms.apply_positions(self.form, forms.field_positions(current)) if ans else self.form

    def print_request(self):
        if self.mode != "input":
            return
        if self.dirty or not self.path:
            if not messagebox.askokcancel(APP_NAME, "印刷の前に、PDF を保存します。", parent=self.root):
                return
            if not self.save():
                return
        elif not self._check_overflow("刷ります"):
            return
        form = self._print_form()
        if form is None:
            return
        self._print(form, with_image=False, title="印刷")

    def _print(self, form, with_image, title):
        """［試し印刷］は持たない（2026-11-14 班長指示「保存したPDFを印刷すれば良い」）。用紙と字の重なりを普通紙で
        確かめるときは、保存した PDF（用紙の画像入り）を、PDF を見るソフトから実際の大きさで刷る。"""
        if not printing.available():
            messagebox.showinfo(APP_NAME, "印刷は Windows だけでできます。", parent=self.root)
            return
        chosen = PrintDialog(self.root, self.cfg, title=title).show()
        if not chosen:
            return
        name, mode, dx, dy = chosen
        data, _ = render.make_pdf(form, self.values, with_image=with_image, image=self.image_bytes, offset=(dx, dy))
        try:
            hdc = printing.make_dc(name, mode)
            printing.print_pdf(data, hdc, f"{APP_NAME} {title}")
        except printing.PrintError as e:
            messagebox.showerror(APP_NAME, str(e), parent=self.root)

    # ================================================================ 用紙の画像
    def paper_menu(self):
        m = tk.Menu(self.root, tearoff=False)
        m.add_command(label="用紙の画像を読み込む…", command=self.load_paper)
        m.add_command(label="ダミーの用紙に戻す", command=self.reset_paper,
                      state="normal" if self.form.get("custom_paper") else "disabled")
        b = self.btn_paper
        m.tk_popup(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height())

    def load_paper(self):
        path = filedialog.askopenfilename(parent=self.root, title="用紙の画像",
                                          filetypes=[("画像", "*.png *.jpg *.jpeg"), ("すべて", "*.*")])
        if not path:
            return
        try:
            img = Image.open(path)
            img.load()
        except Exception:
            messagebox.showerror(APP_NAME, "画像を読めませんでした。PNG か JPEG の画像を選んでください。", parent=self.root)
            return
        dpi = img.info.get("dpi", (0, 0))[0]
        if not dpi or dpi < 50:
            dpi = DpiDialog(self.root).show()
            if not dpi:
                return
        w_mm, h_mm = img.width / dpi * 25.4, img.height / dpi * 25.4
        if w_mm < 150 or h_mm < 200:
            if not messagebox.askokcancel(APP_NAME, f"画像の大きさが {w_mm:.0f}×{h_mm:.0f}mm です。用紙（A4）より小さいようです。"
                                                 "解像度が正しくないかもしれません。続けますか？", parent=self.root):
                return
        self._corner_image = (img, float(dpi))
        self._corner_source = path
        self.mode = "corner"
        self._bg_cache = None
        self._close_editor()
        self._load_modebar()
        self.render_now()

    def _corner_click(self, x, y):
        img, dpi = self._corner_image
        w_mm, h_mm = img.width / dpi * 25.4, img.height / dpi * 25.4
        if not (0 <= x <= w_mm and 0 <= y <= h_mm):
            return
        box = [-x, -y, w_mm - x, h_mm - y]
        self.cfg.set_paper(self.key, self._corner_source, box)
        self.cfg.save()
        self._corner_image = None
        self.mode = "input"
        self.form = forms.effective(self.cfg, self.key)
        self._bg_cache = None
        self._close_editor()
        self._load_modebar()
        self.render_now()
        messagebox.showinfo(APP_NAME, "用紙の画像を読み込みました。欄（点線の四角）が用紙の欄に合っているかを見て、ずれていれば"
                                   "［欄の位置］で合わせてください。", parent=self.root)

    def cancel_corner(self):
        self._corner_image = None
        self.mode = "input"
        self._bg_cache = None
        self._close_editor()
        self._load_modebar()
        self.render_now()

    def reset_paper(self):
        if not messagebox.askyesno(APP_NAME, "読み込んだ用紙の画像を消して、ダミーの用紙に戻しますか？（欄の位置は、そのままです）",
                                   parent=self.root):
            return
        self.cfg.clear_paper(self.key)
        self.cfg.save()
        self.form = forms.effective(self.cfg, self.key)
        self._bg_cache = None
        self.render_now()

    # ================================================================ 欄の位置
    def toggle_position(self):
        if self.opened:
            return
        self.mode = "input" if self.mode == "position" else "position"
        self.pos_sel.clear()
        self._close_editor()
        self._load_modebar()
        self.render_now()

    def _load_modebar(self):
        """欄の位置合わせ・用紙の左上の角を決める間だけ、リボンの下に帯を出す（右の欄にあったもの。2026-11-15）。"""
        bar = self.modebar
        for w in bar.winfo_children():
            w.destroy()
        if self.mode == "input":
            bar.pack_forget()
            return
        bar.pack(fill="x", before=self.body)
        if self.mode == "corner":
            ttk.Label(bar, text="用紙の左上の角をクリックしてください。", style="Section.TLabel").grid(
                row=0, column=0, sticky="w")
            ttk.Label(bar, text="スキャンした画像の、用紙の左上の角（紙の端）をクリックします。用紙の位置が決まります。",
                      wraplength=theme.px(bar, 520), justify="left").grid(row=1, column=0, sticky="w", pady=(2, 0))
            ttk.Button(bar, text="キャンセル", command=self.cancel_corner).grid(row=0, column=1, rowspan=2, sticky="ne",
                                                                          padx=(16, 0))
            bar.columnconfigure(0, weight=1)
            return
        self._load_position_panel()

    def _load_position_panel(self):
        s = self.modebar
        text = ttk.Frame(s)
        text.grid(row=0, column=0, sticky="nw")
        ttk.Label(text, text="欄の位置を合わせる", style="Section.TLabel").pack(anchor="w")
        # Tk は空白で折り返すので、日本語の文の中に半角の空白を置かない（置くと、そこで早く折り返す）
        ttk.Label(text, text="欄（オレンジの四角）をドラッグして、用紙の欄に合わせます。Ctrlを押しながらクリックするか、"
                             "空いた所からドラッグして囲むと、いくつも選んでまとめて動かせます。矢印キーで0.5mm、"
                             "Shiftを押しながらで0.1mm動きます。1つだけ選ぶと、右下の角で大きさを変えられます。"
                             "合わせた位置は、このPCに覚えます。",
                  wraplength=theme.px(s, 460), justify="left").pack(anchor="w", pady=(2, 0))
        nums = ttk.Frame(s)
        nums.grid(row=0, column=1, sticky="nw", padx=(16, 0))
        self.pos_vars = {}
        grid = ttk.Frame(nums)
        grid.pack(anchor="w")
        for i, (k, label) in enumerate((("l", "左"), ("t", "上"), ("w", "幅"), ("h", "高さ"))):
            ttk.Label(grid, text=label).grid(row=i // 2, column=(i % 2) * 3, sticky="e", padx=(0, 2), pady=2)
            var = tk.StringVar()
            e = ttk.Entry(grid, textvariable=var, width=8)
            e.grid(row=i // 2, column=(i % 2) * 3 + 1, sticky="w", pady=2)
            e.bind("<Return>", lambda ev: self._apply_numbers())
            ttk.Label(grid, text="mm").grid(row=i // 2, column=(i % 2) * 3 + 2, sticky="w", padx=(2, 10))
            self.pos_vars[k] = var
        row = ttk.Frame(nums)
        row.pack(anchor="w", pady=(2, 0))
        ttk.Button(row, text="数を当てる", command=self._apply_numbers).pack(side="left")
        self.pos_label = ttk.Label(row, style="Note.TLabel")
        self.pos_label.pack(side="left", padx=(8, 0))
        resets = ttk.Frame(s)
        resets.grid(row=0, column=2, sticky="nw", padx=(16, 0))
        ttk.Button(resets, text="選んだ欄を初めの位置に", command=self.reset_selected).pack(fill="x")
        ttk.Button(resets, text="すべて初めの位置に", command=self.reset_all).pack(fill="x", pady=(4, 0))
        ttk.Button(s, text="位置合わせを終える", style="Accent.TButton", command=self.toggle_position).grid(
            row=0, column=3, sticky="ne", padx=(16, 0))
        s.columnconfigure(3, weight=1)
        self._show_numbers()

    def _show_numbers(self):
        if self.mode != "position" or not hasattr(self, "pos_vars"):
            return
        if len(self.pos_sel) == 1:
            l, t, r, b = forms.item_box(self.form, next(iter(self.pos_sel)))
            for k, v in (("l", l), ("t", t), ("w", r - l), ("h", b - t)):
                self.pos_vars[k].set(f"{v:.1f}")
            self.pos_label.configure(text=f"選んでいる欄：{forms.item_label(self.form, next(iter(self.pos_sel)))}")
        else:
            for var in self.pos_vars.values():
                var.set("")
            self.pos_label.configure(text=f"{len(self.pos_sel)} 個の欄を選んでいます" if self.pos_sel else "欄を選んでいません")

    def _apply_numbers(self):
        if len(self.pos_sel) != 1:
            return
        try:
            l, t, w, h = (float(self.pos_vars[k].get()) for k in ("l", "t", "w", "h"))
        except ValueError:
            messagebox.showerror(APP_NAME, "位置と大きさは、mm の数で入れてください。", parent=self.root)
            return
        if w < 1 or h < 1:
            return
        forms.set_item_box(self.form, next(iter(self.pos_sel)), [l, t, l + w, t + h])
        self._commit_positions()

    def _commit_positions(self):
        self.cfg.set_positions(self.key, forms.positions_diff(self.form, self.key))
        self.cfg.save()
        self._show_numbers()
        self.render_now()

    def reset_selected(self):
        base = forms.builtin(self.key)
        for name in self.pos_sel:
            forms.set_item_box(self.form, name, forms.item_box(base, name))
        self._commit_positions()

    def reset_all(self):
        if not messagebox.askyesno(APP_NAME, "この様式のすべての欄を、初めの位置（ダミーの用紙での位置）に戻しますか？", parent=self.root):
            return
        self.cfg.set_positions(self.key, {})
        self.cfg.save()
        self.form = forms.effective(self.cfg, self.key)
        self.pos_sel.clear()
        self._show_numbers()
        self.render_now()

    def _pos_press(self, event, x, y):
        ctrl = bool(event.state & 0x0004)
        if len(self.pos_sel) == 1:
            name = next(iter(self.pos_sel))
            l, t, r, b = forms.item_box(self.form, name)
            hp = HANDLE / self._ppm
            if "." not in name and r - hp <= x <= r + 0.5 and b - hp <= y <= b + 0.5:
                self._drag = {"kind": "resize", "name": name, "start": (x, y), "box": [l, t, r, b]}
                return
        name, f = self.hit(x, y)
        if name is None:
            if not ctrl:
                self.pos_sel.clear()
            self._drag = {"kind": "band", "start": (x, y), "base": set(self.pos_sel)}
        else:
            if ctrl:
                self.pos_sel.symmetric_difference_update({name})
            elif name not in self.pos_sel:
                self.pos_sel = {name}
            self._drag = {"kind": "move", "start": (x, y),
                          "boxes": {n: list(forms.item_box(self.form, n)) for n in self.pos_sel}}
        self._show_numbers()
        self.draw_overlay()

    def _on_motion(self, event):
        if self.mode != "position" or not self._drag:
            return
        x, y = self._to_mm(event)
        d = self._drag
        dx, dy = x - d["start"][0], y - d["start"][1]
        snap = lambda v: round(round(v / SNAP) * SNAP, 2)  # noqa: E731
        if d["kind"] == "move":
            for n, (l, t, r, b) in d["boxes"].items():
                forms.set_item_box(self.form, n, [l + snap(dx), t + snap(dy), r + snap(dx), b + snap(dy)])
            d["moved"] = True
        elif d["kind"] == "resize":
            l, t, r, b = d["box"]
            forms.set_item_box(self.form, d["name"], [l, t, max(l + 2, r + snap(dx)), max(t + 2, b + snap(dy))])
            d["moved"] = True
        else:
            x0, y0 = d["start"]
            lo_x, hi_x, lo_y, hi_y = min(x0, x), max(x0, x), min(y0, y), max(y0, y)
            inside = {n for n, b, _ in forms.items(self.form)
                      if b[0] >= lo_x and b[2] <= hi_x and b[1] >= lo_y and b[3] <= hi_y}
            self.pos_sel = d["base"] | inside
            self.draw_overlay()
            self.canvas.delete("band")
            self.canvas.create_rectangle(*self._to_px((lo_x, lo_y, hi_x, hi_y)), outline=theme.ACCENT, dash=(3, 2),
                                         tags=("overlay", "band"))
            return
        self.draw_overlay()
        self._show_numbers()

    def _on_release(self, event):
        if self.mode != "position" or not self._drag:
            return
        d, self._drag = self._drag, None
        self.canvas.delete("band")
        if d.get("moved"):
            self._commit_positions()
        else:
            self._show_numbers()
            self.draw_overlay()

    def _nudge(self, d, step):
        if self.mode != "position" or not self.pos_sel:
            return
        for n in self.pos_sel:
            l, t, r, b = forms.item_box(self.form, n)
            forms.set_item_box(self.form, n, [l + d[0] * step, t + d[1] * step, r + d[0] * step, b + d[1] * step])
        self._commit_positions()
        return "break"

    # ================================================================ ヘルプ・終わり
    def about_text(self):
        """「について」の5行（標準 01「について」）。"""
        return f"{APP_NAME}  {VERSION_LABEL}\n{ABOUT_LINE}\n\nVBAアセット（vba-assets.net）\nMIT License"

    def about(self):
        messagebox.showinfo(APP_NAME, self.about_text(), parent=self.root)

    def diagnostic_settings(self):
        """診断情報に載せる、この PC の設定（数と有無だけ。既定の値・例文の中身・場所・プリンターの名前は入れない）。"""
        return {
            "用紙の画像": "読み込んだもの" if self.form.get("custom_paper") else "ダミー",
            "直した欄の位置の数": len(self.cfg.positions(self.key)),
            "例文の保存場所": "既定" if self.cfg.phrases_folder_is_default() else "指定した場所",
            "例文のある欄の数": self._phrase_count(),
            "既定の値の数": len(self.cfg.defaults(self.key)),
            "プリンターのずれを覚えている数": len(self.cfg.data.get("printer_offsets", {})),
        }

    def diagnostic_state(self):
        """診断情報に載せる状態（数と有無だけ。欄の値〔請求の内容〕・ファイルの名前と場所は入れない）。"""
        filled = sum(1 for v in self.values.values() if not forms.is_empty(v))
        return {
            "様式": self.key,
            "欄の数": len(self.form["fields"]),
            "入力した欄の数": filled,
            "開いた PDF か": "はい" if self.opened else "いいえ",
            "入りきらない欄の数": len(self.overflow),
        }

    def _phrase_count(self):
        try:
            return len(self.phrase_store.load_all().get(self.key, {}))
        except PhrasesError:
            return "読めない"

    def copy_diagnostics(self):
        settings = [f"{k}：{v}" for k, v in self.diagnostic_settings().items()]
        state = [f"{k}：{v}" for k, v in self.diagnostic_state().items()]
        text = diagnostics.diagnostic_text(self.root, APP_NAME, VERSION_LABEL, settings, state, self.errors)
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo(APP_NAME, "診断情報をコピーしました。\n\n欄の値（請求の内容）・例文・ファイルの名前と場所は入っていません。"
                                   "不具合を相談するときに、貼り付けて使ってください。", parent=self.root)

    def _on_callback_error(self, exc_type, exc, tb):
        self.errors.record(exc, "画面の処理")
        import traceback
        traceback.print_exception(exc_type, exc, tb)
        try:
            messagebox.showerror(APP_NAME, "思わぬ誤りが起きました。［ヘルプ］→［診断情報をコピー］で、誤りの種類と場所を"
                                        "コピーできます。", parent=self.root)
        except Exception:
            pass

    # ================================================================ ウィンドウの大きさ・最大化を覚える
    # （2026-11-14 班長指摘「プレビュー画面の大きさが保存されない」「ツール全体を最大化したことが保存されない」）
    def _restore_window(self):
        root = self.root
        geo = self.cfg.get("window_geometry")
        if geo and geo.split("+")[0] in ("1x1", ""):
            geo = None                  # 画面を組む前の大きさを覚えてしまったもの
        geo = geo or f"{theme.px(root, 1180)}x{theme.px(root, 820)}"
        root.geometry(geo)
        self._normal_geometry = geo
        if self.cfg.get("window_zoomed"):
            try:
                root.state("zoomed")
            except tk.TclError:
                pass
        root.bind("<Configure>", self._on_root_configure, add="+")

    def _on_root_configure(self, event):
        """最大化していないときの位置と大きさを覚えておく（最大化したまま閉じても、元の大きさに戻せるように）。"""
        root = self.root
        # 画面を組む前（1×1）や、最小化の間の大きさは覚えない
        if event.widget is root and root.state() == "normal" and root.winfo_width() > 100 and root.winfo_height() > 100:
            self._normal_geometry = root.geometry()

    def _save_window(self):
        root = self.root
        zoomed = root.state() == "zoomed"
        geo = self._normal_geometry if zoomed else root.geometry()
        if geo:
            self.cfg.set("window_geometry", geo)
        self.cfg.set("window_zoomed", zoomed)
        self.cfg.data.pop("side_width", None)       # 右の欄は除いた（2026-11-15）。前の版で覚えた幅は消す

    def close(self):
        if self.mode == "input" and not self._confirm_discard():
            return
        try:
            self._save_window()
            self.cfg.save()
        except OSError:
            pass
        self.root.destroy()


def main(argv=None):
    import os
    import sys
    argv = sys.argv[1:] if argv is None else argv
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    App(root, open_path=argv[0] if argv else None)
    root.mainloop()
