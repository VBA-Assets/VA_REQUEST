"""画面の配色と部品のスタイル（フラットデザイン。班長の UI 設計方針の「既定配色（Office風）」）。

色の定義は、ここに集める（色を変えるときは、ここだけを直す）。VA Document の theme.py にそろえ、ttk は 'clam' テーマを基に
見た目を直接指定する。主要な操作のボタンは、地色ではなく枠線の色をアクセント色にして区別する（Accent.TButton）。
"""
from tkinter import font as tkfont
from tkinter import ttk

WINDOW_BG = "#f0f0f0"      # ウィンドウ・フレームの背景
FIELD_BG = "#ffffff"       # 入力欄・カード等の背景
CONTROL_BG = "#fdfdfd"     # ボタンの通常時の地色
HOVER_BG = "#e0eef9"       # ボタンのホバー時の地色（淡い青）
PRESSED_BG = "#cce4f7"     # ボタンの押下時の地色（濃い青）
TEXT = "#1a1a1a"           # 通常テキスト
NOTE = "#666666"           # 補足・注記テキスト
BORDER = "#c8c8c8"         # 枠線・区切り線
ACCENT = "#0078d4"         # アクセント（フォーカス枠線・主要ボタンの強調枠）
PAPER_INSERT_WIDTH = 2     # 用紙の上の入力欄のカーソルの太さ（96 dpi の画素。VA Request）
DISABLED_TEXT = "#a0a0a0"
READONLY_BG = "#f7f7f7"    # 閲覧モードの入力欄の地
# リボンのボタンのアイコン（VA Document と同じ色。2026-11-13 班長指示「リボンのコマンドボタンをVA Documentのように変更」）
ICON_TINT = "#9cc9f0"           # アイコンの塗りつぶし版を敷く色（薄い青）
ICON_TINT_DISABLED = "#e2e2e2"  # 押せないときの、塗りつぶし版の色
RIBBON_HOVER_BORDER = "#a9cdee"  # リボンのボタンに重ねたときの枠


UI_FONT_FAMILY = "Yu Gothic UI"
UI_FONT_SIZE = 9
FIELD_FONT_FAMILIES = ("BIZ UDゴシック", "BIZ UDGothic", "Yu Gothic UI", "ＭＳ ゴシック", "MS Gothic")
FIELD_FONT_SIZE = 10


def scale(widget):
    """画面の拡大率（96 dpi を 1.0 とする）。DPI を知らせて動かすので、画素で決めた幅・高さに掛けて使う。"""
    try:
        return max(1.0, widget.winfo_fpixels("1i") / 96.0)
    except Exception:
        return 1.0


def px(widget, n):
    """96 dpi のときの n 画素を、いまの画面の画素にする。"""
    return int(round(n * scale(widget)))


def field_font(root):
    families = set(tkfont.families(root))
    for f in FIELD_FONT_FAMILIES:
        if f in families:
            return (f, FIELD_FONT_SIZE)
    return ("TkTextFont", FIELD_FONT_SIZE)


def apply_theme(root):
    """テーマを適用する。部品を作る前に一度呼ぶ。"""
    families = set(tkfont.families(root))
    if UI_FONT_FAMILY in families:
        for name in ("TkDefaultFont", "TkTextFont", "TkHeadingFont", "TkMenuFont"):
            tkfont.nametofont(name).configure(family=UI_FONT_FAMILY, size=UI_FONT_SIZE)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    root.configure(background=WINDOW_BG)
    style.configure(".", background=WINDOW_BG, foreground=TEXT, bordercolor=BORDER, focuscolor=ACCENT,
                    lightcolor=WINDOW_BG, darkcolor=WINDOW_BG)
    style.map(".", foreground=[("disabled", DISABLED_TEXT)])

    states = dict(
        background=[("disabled", CONTROL_BG), ("pressed", PRESSED_BG), ("active", HOVER_BG)],
        lightcolor=[("disabled", CONTROL_BG), ("pressed", PRESSED_BG), ("active", HOVER_BG)],
        darkcolor=[("disabled", CONTROL_BG), ("pressed", PRESSED_BG), ("active", HOVER_BG)],
        bordercolor=[("disabled", BORDER), ("pressed", ACCENT), ("active", ACCENT)])
    style.configure("TButton", background=CONTROL_BG, bordercolor=BORDER, lightcolor=CONTROL_BG,
                    darkcolor=CONTROL_BG, padding=(10, 3), width=-6)
    style.map("TButton", **states)
    style.configure("Accent.TButton", bordercolor=ACCENT)
    style.map("Accent.TButton", bordercolor=[("disabled", BORDER), ("!disabled", ACCENT)])
    style.configure("Small.TButton", padding=(6, 1), width=-4)
    # リボンのボタン（VA Document と同じ。2026-11-13 班長指示「リボンのコマンドボタンをVA Documentのように変更」）：
    # Word のリボンと同じく、ふだんは枠も地もなく、重ねたときだけ淡い青の地と枠を出す（班長の UI 方針の「常時、細い
    # 枠線」の、リボンだけの例外。VA Document の 2026-10-24 班長決定と同じ）。大きいボタン（RibbonLarge）はアイコンの
    # 下に字、小さいボタン（Ribbon）はアイコンの右に字。
    ribbon_states = dict(
        background=[("disabled", WINDOW_BG), ("pressed", PRESSED_BG), ("active", HOVER_BG)],
        lightcolor=[("disabled", WINDOW_BG), ("pressed", PRESSED_BG), ("active", HOVER_BG)],
        darkcolor=[("disabled", WINDOW_BG), ("pressed", PRESSED_BG), ("active", HOVER_BG)],
        bordercolor=[("disabled", WINDOW_BG), ("pressed", RIBBON_HOVER_BORDER), ("active", RIBBON_HOVER_BORDER)])
    for name, padding, anchor in (("Ribbon.TButton", (3, 1), "w"), ("RibbonLarge.TButton", (4, 2), "center")):
        style.configure(name, background=WINDOW_BG, bordercolor=WINDOW_BG, lightcolor=WINDOW_BG, darkcolor=WINDOW_BG,
                        padding=padding, width=0, anchor=anchor, justify="center")
        style.map(name, **ribbon_states)
    style.configure("Ribbon.TFrame", background=WINDOW_BG)
    style.configure("Ribbon.TLabel", background=WINDOW_BG)
    style.configure("RibbonGroup.TLabel", background=WINDOW_BG, foreground=NOTE, padding=(0, 0, 0, 2))

    style.configure("Note.TLabel", foreground=NOTE)
    style.configure("Status.TLabel", foreground=NOTE, padding=(6, 2))
    style.configure("Section.TLabel", foreground=TEXT, font=(UI_FONT_FAMILY, UI_FONT_SIZE, "bold"))
    style.configure("TEntry", fieldbackground=FIELD_BG, bordercolor=BORDER, lightcolor=FIELD_BG,
                    darkcolor=FIELD_BG, insertcolor=TEXT, padding=2)
    # 用紙の上に重ねる入力欄（VA Request。2026-11-15 班長指示「プレビュー画面に直接入力」）。選んでいる欄と分かるよう、
    # 枠はいつもアクセントの青。欄の高さに字を収めるため、余白はほとんど取らない。カーソル（縦の棒）は太くする
    # （2026-11-15 班長指摘「カーソルが小さい」。既定の 1 画素では、用紙の上で見つけにくい）
    style.configure("Paper.TEntry", fieldbackground=FIELD_BG, bordercolor=ACCENT, lightcolor=FIELD_BG,
                    darkcolor=FIELD_BG, insertcolor=TEXT, padding=(1, 0), insertwidth=px(root, PAPER_INSERT_WIDTH))
    style.map("Paper.TEntry", bordercolor=[("focus", ACCENT)])
    style.map("TEntry", bordercolor=[("focus", ACCENT)], fieldbackground=[("readonly", READONLY_BG)])
    style.configure("TSpinbox", fieldbackground=FIELD_BG, background=CONTROL_BG, bordercolor=BORDER,
                    lightcolor=FIELD_BG, darkcolor=FIELD_BG, arrowcolor=TEXT, insertcolor=TEXT, padding=2)
    style.map("TSpinbox", bordercolor=[("focus", ACCENT)], background=[("active", HOVER_BG)])
    style.configure("TCombobox", fieldbackground=FIELD_BG, background=CONTROL_BG, bordercolor=BORDER,
                    lightcolor=FIELD_BG, darkcolor=FIELD_BG, arrowcolor=TEXT, padding=2)
    style.map("TCombobox", bordercolor=[("focus", ACCENT), ("active", ACCENT)],
              fieldbackground=[("disabled", READONLY_BG), ("readonly", FIELD_BG)],
              background=[("active", HOVER_BG)],
              selectbackground=[("readonly", FIELD_BG)], selectforeground=[("readonly", TEXT)],
              # clam の既定は、選ぶだけの欄に Tab などで入ると文字を白にする。地は白にしているので、文字が消えて
              # 見えた（2026-11-10 班長指摘「ドロップダウンボックスの表示が一旦消える」）。いつもの文字の色にする
              foreground=[("readonly", "focus", TEXT)])
    root.option_add("*TCombobox*Listbox.background", FIELD_BG)
    root.option_add("*TCombobox*Listbox.selectBackground", PRESSED_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    style.configure("TRadiobutton", background=WINDOW_BG, indicatorbackground=FIELD_BG,
                    indicatorforeground=ACCENT, bordercolor=BORDER)
    style.map("TRadiobutton", background=[("active", WINDOW_BG)],
              indicatorbackground=[("pressed", PRESSED_BG), ("active", HOVER_BG)])
    style.configure("TLabelframe", background=WINDOW_BG, bordercolor=BORDER)
    # 枠で囲んだ欄（カード）
    style.configure("Card.TFrame", background=WINDOW_BG, borderwidth=1, relief="solid", bordercolor=BORDER,
                    lightcolor=BORDER, darkcolor=BORDER)
    style.configure("TLabelframe.Label", background=WINDOW_BG, foreground=TEXT)
    style.configure("Treeview", background=FIELD_BG, fieldbackground=FIELD_BG, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=FIELD_BG, darkcolor=FIELD_BG, rowheight=px(root, 20))
    # 一覧をクリックして入力先になっても、外周の罫線を変えない（'clam' の既定は濃い色になり、太く見える。2026-11-09
    # 班長指摘「クリックした際に外周の罫線が太くなる。常に同じに」）
    # 選んだ行の字の色は決めない（行の印の字の色〔直していてまだ書き込んでいない値の青・終了の灰など〕を、選んだ行でも
    # そのまま出す。印のない行は、ふつうの字の色）。2026-11-13 までは選んだ行を黒字に決めていて、カードで直している行
    # （選んでいる行）が青字にならなかった（班長指摘「青字ではなく、黒字で入力される」「黒字で表示されている」）。
    # 'clam' の既定（選んだ行は白字）も使わないよう、空にする
    style.map("Treeview", background=[("selected", PRESSED_BG)], foreground=[],
              bordercolor=[("focus", BORDER)])
    style.configure("Treeview.Heading", background=WINDOW_BG, foreground=TEXT, bordercolor=BORDER,
                    lightcolor=WINDOW_BG, darkcolor=WINDOW_BG, relief="flat")
    style.map("Treeview.Heading", background=[("active", HOVER_BG)])
    style.configure("TScrollbar", troughcolor=WINDOW_BG, background="#c1c1c1", bordercolor=WINDOW_BG,
                    lightcolor="#c1c1c1", darkcolor="#c1c1c1", arrowcolor="#606060")
    style.map("TScrollbar", background=[("pressed", "#8a8a8a"), ("active", "#a8a8a8")],
              lightcolor=[("pressed", "#8a8a8a"), ("active", "#a8a8a8")],
              darkcolor=[("pressed", "#8a8a8a"), ("active", "#a8a8a8")])
    style.configure("TSeparator", background=BORDER)
    style.configure("TProgressbar", background=ACCENT, troughcolor=FIELD_BG, bordercolor=BORDER,
                    lightcolor=ACCENT, darkcolor=ACCENT)

    # classic tk の部品（ttk に対応品がないもの）
    root.option_add("*Text.background", FIELD_BG)
    root.option_add("*Text.foreground", TEXT)
    root.option_add("*Text.relief", "flat")
    root.option_add("*Text.borderWidth", 2)
    root.option_add("*Text.highlightThickness", 1)
    root.option_add("*Text.highlightBackground", BORDER)
    root.option_add("*Text.highlightColor", ACCENT)
    root.option_add("*Text.selectBackground", PRESSED_BG)
    root.option_add("*Text.selectForeground", TEXT)
    root.option_add("*Text.insertBackground", TEXT)
    root.option_add("*Toplevel.background", WINDOW_BG)
    root.option_add("*Menu.background", FIELD_BG)
    root.option_add("*Menu.foreground", TEXT)
    root.option_add("*Menu.activeBackground", HOVER_BG)
    root.option_add("*Menu.activeForeground", TEXT)
    root.option_add("*Menu.relief", "flat")
    root.option_add("*Menu.borderWidth", 1)
    root.option_add("*Canvas.background", WINDOW_BG)
    root.option_add("*Canvas.highlightThickness", 0)
    # Tab で入力欄に入ったときに、中の文字全体を選ばない（ttk の既定は全体を選ぶ。選んだ文字は地の色が変わり、
    # 確定前の文字のように見えるため。2026-11-10 班長指摘）。カーソルを最後に置くだけにする
    root.bind_class("TEntry", "<<TraverseIn>>", _traverse_in)
    root.bind_class("TCombobox", "<<TraverseIn>>", _traverse_in)
    # 欄から出たら、選んだ文字を外す（Windows のふつうの入力欄と同じ。2026-11-13 班長指摘「カードの番号や読み込み
    # ファイルの値を選択した状態で、他のテキストボックス等をクリックしても、選択状態が解除されない」。Tk の既定では、
    # 入力先が移っても、選んだ字の地の色が残る）
    root.bind_class("TEntry", "<FocusOut>", _clear_selection, add="+")
    root.bind_class("TCombobox", "<FocusOut>", _clear_selection, add="+")
    # 1行の欄に、何行かの文字を貼り付けたときは、1行につなげる（2026-11-13。プレビューで囲んでコピーした文字は、
    # 何行かになることが多い。Tk の既定では、改行のまま欄に入り、見えない字が残る）
    root.bind_class("TEntry", "<<Paste>>", _paste_one_line)
    root.bind_class("TCombobox", "<<Paste>>", _paste_one_line)


def one_line(text):
    """何行かの文字を1行につなげる。行の間は詰め、英数字どうしの間だけ空白を入れる（「東京都千代田区\n1丁目」→
    「東京都千代田区1丁目」、「VA\nFiling」→「VA Filing」）。"""
    out = ""
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        if out and out[-1].isascii() and out[-1].isalnum() and line[0].isascii() and line[0].isalnum():
            out += " "
        out += line
    return out


def _paste_one_line(event):
    """ttk の欄の貼り付け（Tk の既定の貼り付けを置き換える。選んだ字を貼り付けた字で置き換える動きは、既定と同じ）。"""
    w = event.widget
    try:
        text = w.clipboard_get()
    except Exception:          # クリップボードが空・文字でない：何もしない（Tk の既定と同じ）
        return "break"
    try:
        if w.instate(["disabled"]) or w.instate(["readonly"]):
            return "break"
        if w.selection_present():
            w.delete("sel.first", "sel.last")
        w.insert("insert", one_line(text))
    except Exception:          # 消えかけの部品など
        pass
    return "break"


def _clear_selection(event):
    try:
        event.widget.selection_clear()
    except Exception:   # 消えかけの部品など
        pass


def _traverse_in(event):
    w = event.widget
    try:
        w.selection_clear()
        w.icursor("end")
    except Exception:   # 消えかけの部品など。選ばないだけなので、何もしない
        pass


def tab_stop(widget, readable):
    """閲覧モードの入力欄にも、Tab で移れるようにする（2026-11-10 班長指摘）。

    ドロップダウン（ttk.Combobox）と何行かの欄（tk.Text）は、閲覧モードでは直せない状態（disabled）にして
    いる。この状態の部品は、Tk の既定では Tab で飛ばされる。readable が真なら、Tab で止まるようにする
    （直せない状態のままなので、値は変えられない）。偽なら、元の決まり（直せない状態なら飛ばす）に戻す。
    """
    if not hasattr(widget, "_va_takefocus"):
        widget._va_takefocus = str(widget.cget("takefocus"))
    widget.configure(takefocus=1 if readable else widget._va_takefocus)


def show_choice(combo, edit_state, readable):
    """ドロップダウン（ttk.Combobox）を、直せるときはそのまま出し、直せないときは、同じ値を出す読み取り専用の欄に
    替える（2026-11-10 班長決定：閲覧モードでも、選択の欄の文字をなぞって選び、Ctrl+C でコピーできるように。直せない
    状態〔disabled〕のドロップダウンは、文字を選べない）。

    edit_state：直せるときの状態（"readonly" か "normal"）。直せないときは None。readable：値を見せるか（行を
    選んでいるか）。読み取り専用の欄は、ドロップダウンと同じ場所（grid）に置き、Tab で移る順も同じにする。
    """
    mirror = getattr(combo, "_va_mirror", None)
    if mirror is None:
        mirror = ttk.Entry(combo.master, textvariable=combo.cget("textvariable"), font=combo.cget("font"),
                           width=combo.cget("width"), state="disabled")
        mirror.grid(**combo.grid_info())
        mirror.grid_remove()
        mirror.lift(combo)       # Tab で移る順（重なりの順）を、ドロップダウンのすぐ後にする
        combo._va_mirror = mirror
    if edit_state:
        combo.configure(state=edit_state)
        mirror.grid_remove()
        combo.grid()
    else:
        combo.configure(state="disabled")
        mirror.configure(state="readonly" if readable else "disabled")
        combo.grid_remove()
        mirror.grid()
    tab_stop(mirror, readable)
    return mirror


def _text_width(text):
    """Entry の幅（字数。全角は2として数える）。"""
    return sum(2 if ord(ch) > 0xFF else 1 for ch in text)


def value_text(parent, textvariable, *, fill=False):
    """ラベルの代わりに、文字として選べる値を出す（読み取り専用の欄。見た目はラベルと同じ。2026-11-13 班長指摘
    「カードで番号がコピーできない」）。なぞって選び、Ctrl+C でコピーできる。Tab では止まらない。fill：幅いっぱいに
    広げるか（偽なら、値の長さに合わせる）。"""
    w = ttk.Entry(parent, textvariable=textvariable, style="Value.TEntry", font="TkDefaultFont", takefocus=0)
    w.configure(state="readonly")

    def fit(*args):
        w.configure(width=max(2, _text_width(textvariable.get()) + 1))
    if not fill:
        textvariable.trace_add("write", fit)
        fit()
    return w
