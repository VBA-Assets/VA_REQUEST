"""様式・字の配置・PDF の保存と開き直し・設定の試験。"""
import io
from pathlib import Path

import pytest
from pypdf import PdfReader
from reportlab.pdfgen import canvas

from va_request import forms, pdfdoc, render


# ---- 様式 ----
# A は 10 が欠番（見出しの行を欄から外した。2026-11-15 班長指示）で、26 が番号欄
IDS = {"A": [i for i in range(1, 27) if i != 10], "B": list(range(1, 28)), "C": list(range(1, 24)),
       "D": list(range(1, 26))}


@pytest.mark.parametrize("key", ["A", "B", "C", "D"])
def test_builtin_forms(key):
    form = forms.builtin(key)
    assert [f["id"] for f in form["fields"]] == IDS[key]
    for name, (l, t, r, b), f in forms.items(form):
        assert 0 <= l < r <= 210 and 0 <= t < b <= 297, name
    # 欄の名前（実物の様式の項目名）を持たない
    assert all(set(f) <= {"id", "label", "type", "box", "align", "options", "parts", "era", "direction"} for f in form["fields"])


def test_field_labels():
    """日付欄・宛名欄と、左の列の空欄を上から数えた欄1・欄1-1（2026-11-14 班長指示）。"""
    labels = {k: [forms.label(f) for f in forms.builtin(k)["fields"]] for k in forms.FORM_KEYS}
    for k, ls in labels.items():
        assert ls[:2] == ["日付欄", "宛名欄"], k
        assert len(set(ls)) == len(ls), k                 # 呼び名が重ならない
    assert labels["A"][2:6] == ["欄1-1", "欄1-2", "欄1-3", "欄2"]
    assert labels["A"][-3:] == ["欄9-1", "欄9-2", "番号欄"]       # 番号欄は後から足した（2026-11-15）
    # A の見出しの行（もとの欄5）は欄から外した。その下の欄は1つずつ繰り上がる（2026-11-15 班長指示「欄から外す」）
    assert labels["A"][7:11] == ["欄4-1", "欄4-2", "欄5", "欄6"]
    assert all(f["id"] != 10 for f in forms.builtin("A")["fields"])
    # C の字を入れる欄のない空欄（請求に際し明らかにしなければならない事項の行）は数えない
    assert labels["C"][7:10] == ["欄4-1", "欄4-2", "欄5-1"] and labels["C"][-3:] == ["欄9-1", "欄9-2", "番号欄"]
    a = forms.builtin("A")
    assert forms.item_label(a, "3.o1") == "欄1-1（左から 2 番目の語）"
    assert forms.item_label(a, "9.year") == "欄4-2（年）"


# 番号欄：(様式, 番号欄の番号, 欄5・欄6・欄7 の行の最初の欄, 左の列の左右・行の上の罫線〔測った用紙の mm〕)
NUMBER_FIELDS = [
    ("A", 26, (11, 12, 13), (15.5, 56.9), (89.4, 109.1, 124.3)),     # 2026-11-15 班長了承「この案で作る」
    ("C", 23, (10, 12, 14), (18.6, 59.4), (86.2, 115.4, 144.1)),     # 同日 班長指示「C用紙の欄5,6,7の左の列にも◯を配置」
]


@pytest.mark.parametrize("key,fid,first,col,tops", NUMBER_FIELDS)
def test_number_field(key, fid, first, col, tops):
    """番号欄：左の列の欄5・欄6・欄7 の行の左上の番号 1・2・3 のどれか1つを ○ で囲む。"""
    form = forms.builtin(key)
    f = next(f for f in form["fields"] if f["id"] == fid)
    assert f["type"] == "circle" and f["direction"] == "down" and len(f["options"]) == 3
    assert forms.label(f) == "番号欄"
    for (l, t, r, b), row, top in zip(f["options"], first, tops):
        box = next(x for x in form["fields"] if x["id"] == row)["box"]
        assert col[0] < l < r < col[1]                    # 表の左の列の中
        assert r < box[0]                                 # 右の列の欄より左
        assert l - col[0] == pytest.approx(1.0, abs=0.1) and t - top == pytest.approx(1.0, abs=0.1)   # 左上から 1mm 内側
        assert r - l == pytest.approx(5.0, abs=0.05) and b - t == pytest.approx(5.0, abs=0.05)
    assert forms.item_label(form, f"{fid}.o2") == "番号欄（上から 3 番目の番号）"
    # 刷る：選んだ番号の所に ○（楕円）を描く。ほかの欄の字には影響しない
    data, overflow = render.make_pdf(form, {fid: 2}, with_image=False)
    assert overflow == [] and data[:4] == b"%PDF"


def test_is_empty_keeps_zero():
    assert not forms.is_empty(0)            # 囲みの 0 番目
    assert forms.is_empty(False) and forms.is_empty("") and forms.is_empty(None)
    assert forms.is_empty({"year": "", "month": ""})
    assert not forms.is_empty({"era": 0})


def test_positions_override(cfg):
    form = forms.effective(cfg, "A")
    forms.set_item_box(form, "3.o1", [80, 40, 90, 45])
    forms.set_item_box(form, "1.year", [130, 20, 140, 25])
    diff = forms.positions_diff(form, "A")
    assert set(diff) == {"3.o1", "1.year"}
    cfg.set_positions("A", diff)
    again = forms.effective(cfg, "A")
    assert forms.item_box(again, "3.o1") == [80, 40, 90, 45]
    assert forms.item_box(again, "2") == forms.item_box(forms.builtin("A"), "2")


# ---- 字の配置 ----
def test_overflow_is_reported_not_cut():
    form = forms.builtin("A")
    long = "あ" * 200
    _, overflow = render.make_pdf(form, {2: long, 6: "短い字"}, with_image=False)
    assert overflow == [2]
    text = PdfReader(io.BytesIO(render.make_pdf(form, {2: long}, with_image=False)[0])).pages[0].extract_text()
    assert text.count("あ") == 200          # 字を削らない


def test_multiline_fits_two_lines():
    form = forms.builtin("A")
    _, overflow = render.make_pdf(form, {11: "架空の字を入れる。" * 6}, with_image=False)
    assert overflow == []


def test_offset_moves_everything():
    form = forms.builtin("B")
    a, _ = render.make_pdf(form, {6: "架空"}, with_image=False)
    b, _ = render.make_pdf(form, {6: "架空"}, with_image=False, offset=(1.5, -2.0))
    assert a != b


# ---- PDF の保存と開き直し ----
def test_save_and_read_roundtrip(cfg, tmp_path):
    form = forms.effective(cfg, "B")
    values = {2: "架空市", 3: 0, 5: 0, 9: True, 13: {"year": "40", "month": "1", "day": "2", "era": 5},
              18: "架空の事由\n2行目"}
    path = tmp_path / "請求.pdf"
    assert pdfdoc.save(path, form, values) == []
    opened = pdfdoc.read(path)
    assert opened["form"] == "B"
    assert opened["values"] == values
    assert opened["image"][:3] == b"\xff\xd8\xff"           # ページの用紙の画像（JPEG）をそのまま取り出す
    again = pdfdoc.form_of(opened, forms.effective(cfg, "B"))
    assert forms.field_positions(again) == forms.field_positions(form)
    meta = PdfReader(str(path)).metadata
    assert not meta.get("/Author") and not meta.get("/Title")


def test_saved_positions_survive_later_changes(cfg, tmp_path):
    form = forms.effective(cfg, "A")
    path = tmp_path / "請求.pdf"
    pdfdoc.save(path, form, {6: "架空"})
    cfg.set_positions("A", {"6": [70, 51, 188, 58.7]})      # 保存した後に位置を合わせ直す
    opened = pdfdoc.read(path)
    again = pdfdoc.form_of(opened, forms.effective(cfg, "A"))
    assert forms.item_box(again, "6") == forms.item_box(form, "6")


def test_other_pdf_is_refused(tmp_path):
    path = tmp_path / "ほか.pdf"
    c = canvas.Canvas(str(path))
    c.drawString(100, 100, "x")
    c.save()
    with pytest.raises(pdfdoc.NotRequestPdf):
        pdfdoc.read(path)
    (tmp_path / "壊れた.pdf").write_bytes(b"%PDF-1.4 broken")
    with pytest.raises(pdfdoc.NotRequestPdf):
        pdfdoc.read(tmp_path / "壊れた.pdf")


# ---- 設定 ----
def test_config_values(cfg, tmp_path):
    cfg.set_default("A", 21, "架空 一郎")
    cfg.set_default("A", 3, 0)                       # 囲みの 0 番目も既定の値にできる
    cfg.set_printer_offset("プリンター", 1.25, -0.5)
    cfg.save()
    from va_request.config import Config
    again = Config(cfg.folder)
    assert again.defaults("A") == {21: "架空 一郎", 3: 0}
    assert again.printer_offset("プリンター") == (1.25, -0.5)
    assert again.printer_offset("ほか") == (0.0, 0.0)
    assert "請求" not in again.path.read_text(encoding="utf-8")


def test_paper_image_copy(cfg, tmp_path):
    src = Path(forms.FORMS_DIR / "A.jpg")
    cfg.set_paper("A", src, [-3, -2, 205, 295])
    paper = cfg.paper("A")
    assert paper["path"].parent == cfg.folder / "images" and paper["path"].exists()
    form = forms.effective(cfg, "A")
    assert form["custom_paper"] and form["image"]["box"] == [-3, -2, 205, 295]
    cfg.clear_paper("A")
    assert cfg.paper("A") is None and not forms.effective(cfg, "A")["custom_paper"]


def test_no_agpl_in_src():
    """配るプログラムでは PyMuPDF（AGPL）を使わない（MIT License）。"""
    import re
    src = Path(__file__).resolve().parents[1] / "src"
    pattern = re.compile(r"^\s*(import|from)\s+(fitz|pymupdf)\b", re.M | re.I)
    for p in src.rglob("*.py"):
        assert not pattern.search(p.read_text(encoding="utf-8")), p
