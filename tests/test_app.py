"""画面の試験。Tk は、試験の全体で1つだけ（conftest.py の root）。

ファイルの画面・確かめの画面は、差し替えて自動で答える。設定は一時フォルダ（conftest.py）。字は架空のもの。
"""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest

from va_request import app as app_mod
from va_request import forms, pdfdoc
from va_request.config import Config


@pytest.fixture
def app(root, tmp_path, monkeypatch):
    for w in root.winfo_children():
        w.destroy()
    answers = {"askyesno": True, "askokcancel": True, "askyesnocancel": True}
    for name in ("askyesno", "askokcancel", "askyesnocancel"):
        monkeypatch.setattr(app_mod.messagebox, name, lambda *a, _n=name, **k: answers[_n])
    shown = []
    for name in ("showinfo", "showerror", "showwarning"):
        monkeypatch.setattr(app_mod.messagebox, name, lambda *a, _n=name, **k: shown.append((_n, a)))
    a = app_mod.App(root, Config(tmp_path / "設定"))
    a.answers, a.shown = answers, shown
    root.update()
    a.render_now()
    return a


def event(a, mm_x, mm_y, state=0):
    """用紙の mm の位置の、マウスの出来事。"""
    x = app_mod.MARGIN + mm_x * a._ppm - a.canvas.canvasx(0)
    y = app_mod.MARGIN + mm_y * a._ppm - a.canvas.canvasy(0)
    return SimpleNamespace(x=x, y=y, state=state)


def click(a, mm_x, mm_y, state=0):
    """用紙の mm の位置をクリックする。"""
    ev = event(a, mm_x, mm_y, state)
    a._on_press(ev)
    return ev


def center(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def test_click_text_field_and_type(app):
    box = forms.item_box(app.form, "6")
    click(app, *center(box))
    assert app.selected == 6
    app.editor.insert("end", "架空の字")
    app.root.update()
    assert app.values[6] == "架空の字" and app.dirty


def test_click_circle_and_check(app):
    click(app, *center(forms.item_box(app.form, "3.o0")))
    assert app.values[3] == 0                     # 0 番目でも消えない
    click(app, *center(forms.item_box(app.form, "3.o0")))
    assert 3 not in app.values                    # もう一度で外れる
    click(app, *center(forms.item_box(app.form, "15")))
    assert app.values[15] is True


def test_save_open_overwrite_only(app, tmp_path, monkeypatch):
    path = tmp_path / "請求.pdf"
    monkeypatch.setattr(app_mod.filedialog, "asksaveasfilename", lambda **k: str(path))
    app.values = {2: "架空市", 6: "架空の字"}
    assert app.save() and path.exists() and not app.dirty
    # 新しい請求にしてから開き直す
    app.new_request()
    assert app.values == {} and app.path is None
    app.open_pdf(path, confirmed=True)
    assert app.opened and app.values == {2: "架空市", 6: "架空の字"}
    assert str(app.btn_position.cget("state")) == "disabled"      # 開いた請求では、位置合わせをしない
    # 直して保存すると、同じファイルに上書きする（ファイルの画面を出さない）
    monkeypatch.setattr(app_mod.filedialog, "asksaveasfilename", lambda **k: pytest.fail("別の名前で保存しない"))
    app.set_value(6, "直した字")
    assert app.save()
    assert pdfdoc.read(path)["values"][6] == "直した字"


def test_defaults_for_new_request(app):
    app.select(21)
    assert app.default_label is None                 # 既定の値がなければ、何も出さない
    app.editor.insert("end", "架空 一郎")
    app.set_default()
    assert app.default_label.cget("text") == "既定の値：架空 一郎"
    app.new_request()
    assert app.values == {21: "架空 一郎"}


def test_position_drag_and_nudge(app):
    app.toggle_position()
    assert app.mode == "position"
    box = forms.item_box(app.form, "6")
    cx, cy = center(box)
    click(app, cx, cy)
    assert app.pos_sel == {"6"}
    app._on_motion(event(app, cx + 2.0, cy + 1.0))
    app._on_release(event(app, cx + 2.0, cy + 1.0))
    moved = forms.item_box(app.form, "6")
    tol = 1 / app._ppm + 0.11            # 画面の1画素（隠したウィンドウでは用紙が小さく、1画素が大きい）と刻み
    assert moved[0] == pytest.approx(box[0] + 2.0, abs=tol) and moved[1] == pytest.approx(box[1] + 1.0, abs=tol)
    assert app.cfg.positions("A")["6"] == moved
    app._nudge((1, 0), 0.5)
    assert forms.item_box(app.form, "6")[0] == pytest.approx(moved[0] + 0.5)
    app.reset_selected()
    assert forms.item_box(app.form, "6") == box and "6" not in app.cfg.positions("A")
    app.toggle_position()
    assert app.mode == "input"


def test_side_panel_and_ribbon(app):
    """右の欄にボタン（例文の登録・既定の値にする・既定の値を消す）を置かず、リボンに置く（2026-11-14 班長指示）。"""
    app.phrase_store.save_field("A", 18, ["架空の長い例文" * 10, "架空の例文\n2行目"], force=True)
    app.select(18)
    texts = []

    def walk(w):
        for c in w.winfo_children():
            try:
                texts.append(str(c.cget("text")))
            except tk.TclError:
                pass
            walk(c)
    walk(app.side)
    assert not {"例文の登録…", "既定の値にする", "既定の値を消す"} & set(texts)
    assert texts[0] == "欄8-6　何行かの字"
    assert isinstance(app.phrase_list, app_mod.WrappedList)         # 何行かの字は折り返す一覧
    assert str(app.phrase_list.text.cget("wrap")) == "char"
    assert int(app.phrase_list.text.cget("height")) == 20       # 例文の登録の画面の一覧と同じ高さ
    app.phrase_list.selection_set(1)
    app.phrase_list.event_generate("<<ListboxDouble>>")
    app.root.update()                       # 何行かの欄の <<Modified>> は、後から届く
    assert app.values[18] == "架空の例文\n2行目"
    # 既定の値を消すボタン
    app.set_default()
    assert 18 in app.cfg.defaults("A")
    app.btn_clear_default.invoke()
    assert 18 not in app.cfg.defaults("A")
    # 1行の字の欄は、今までどおりの一覧
    app.phrase_store.save_field("A", 6, ["架空"], force=True)
    app.select(6)
    assert isinstance(app.phrase_list, tk.Listbox) and int(app.phrase_list.cget("height")) == 10


def test_phrases_dialog_edit_in_list(root):
    """例文の一覧で直接書いて直す（下の入力欄はない。2026-11-14 班長指示）。"""
    from va_request.dialogs import PhrasesDialog
    font = ("TkTextFont", 10)
    d = PhrasesDialog(root, ["架空の例文1", "架空の例文2\n2行目"], "欄6", font, wrap=True)
    assert not hasattr(d, "text") and all(isinstance(w, tk.Text) for w in d.rows)
    assert str(d.rows[0].cget("wrap")) == "char"
    d.rows[0].insert("end", "を直した")                  # 一覧の中で直す
    d._add()                                             # 一番下に空の例文を足して書く
    d.rows[2].insert("1.0", "架空の例文3")
    d._entered(2)
    d._move(-1)                                          # 書いている例文を上へ
    assert d.values() == ["架空の例文1を直した", "架空の例文3", "架空の例文2\n2行目"]
    d._entered(0)
    d._delete()
    d._add()                                             # 空の例文は OK のときに除く
    d.ok()
    assert d.result == ["架空の例文3", "架空の例文2\n2行目"]
    # 1行の字の欄は、1行の入力欄を並べる。例文がなければ、空の欄を1つ出しておく
    d = PhrasesDialog(root, [], "欄2", font)
    assert len(d.rows) == 1 and isinstance(d.rows[0], ttk.Entry)
    d.rows[0].insert(0, "架空の宛名")
    d.ok()
    assert d.result == ["架空の宛名"]


def test_file_menu_and_save_button(app):
    """［ファイル］に新しい請求・開く・保存、リボンの保存は「保存」（2026-11-14 班長指示）。"""
    m = app.file_menu
    labels = [m.entrycget(i, "label") for i in range(m.index("end") + 1) if m.type(i) == "command"]
    assert labels == ["新しい請求", "開く…", "保存", "オプション…"]
    assert app.btn_save.cget("text") == "保存"
    assert not hasattr(app, "btn_test") and not hasattr(app, "test_print")      # 試し印刷は持たない
    app.toggle_position()
    assert m.entrycget("保存", "state") == "disabled"
    app.toggle_position()
    assert m.entrycget("保存", "state") == "normal"


def test_remember_window(app, monkeypatch, tmp_path):
    """最大化と右の欄の幅を覚え、次に開いたときに戻す（2026-11-14 班長指摘）。"""
    app._normal_geometry = "1000x700+10+20"
    monkeypatch.setattr(app.root, "state", lambda *a: "zoomed")
    monkeypatch.setattr(app.side, "winfo_width", lambda: round(450 * app_mod.theme.scale(app.root)))
    app._save_window()
    assert app.cfg.get("window_zoomed") is True
    assert app.cfg.get("window_geometry") == "1000x700+10+20"      # 最大化する前の大きさ
    assert app.cfg.get("side_width") == 450
    # 次に開いたとき：最大化し、右の欄の幅を戻す
    calls = []
    monkeypatch.setattr(app.root, "state", lambda *a: calls.append(a) or "normal")
    app._restore_window()
    assert ("zoomed",) in calls
    for w in app.root.winfo_children():
        w.destroy()
    again = app_mod.App(app.root, app.cfg)
    assert int(again.body.panecget(again.side, "width")) == app_mod.theme.px(app.root, 450)


def test_change_form(app):
    app.form_var.set(app_mod.FORM_LABELS["C"])
    app.change_form()
    assert app.key == "C" and len(app.form["fields"]) == 22
    assert app.cfg.get("form") == "C"


def test_diagnostics_has_no_values(app):
    app.values = {6: "架空の秘密の字"}
    app.copy_diagnostics()
    text = app.root.clipboard_get()
    assert "架空の秘密の字" not in text and "VA Request" in text
