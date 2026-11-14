"""欄の値を、様式の位置に置いた PDF にする（試作の段階。2026-11-14）。

- 位置はすべて「用紙（A4）の左上からの mm」。reportlab は左下が原点なので、書くときに直す。
- with_image=True で、用紙の画像を下に敷く（保存する PDF。弁護士に確かめてもらうためのもの）。
  False で、字だけ（用紙に刷るためのもの）。
- 字が欄に入りきらないときは、字を小さくし、それでも入らなければ字の幅を詰める。
  決めた最小でも入らない欄は、字を削らずにそのまま書き、overflow に番号を返す（利用者の文章を変えない）。
"""
import io
import json
import os
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .forms import is_empty

FORMS_DIR = Path(__file__).resolve().parent / "forms"
FONT = "VARequestMincho"
FONT_FILES = ((r"C:\Windows\Fonts\msmincho.ttc", 0),)   # ＭＳ 明朝

SIZE_MAX = 10.5        # 1行の欄の字の大きさの上限（pt）
SIZE_MULTI = 10.0      # 何行かの欄の字の大きさ（pt）
SIZE_MIN = 6.5         # これより小さくしない（pt）
SCALE_MIN = 60         # 字の幅を詰めるときの下限（%）
LINE_GAP = 1.25        # 何行かの欄の行送り（字の大きさに対する倍率）
PEN = 0.5              # ○ と ✓ の線の太さ（pt）

PAGE_W, PAGE_H = A4


def _register_font():
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    for path, index in FONT_FILES:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT, path, subfontIndex=index))
            return
    raise RuntimeError("ＭＳ 明朝が見つかりません。")


def load_form(key):
    """様式の定義（forms\\<key>.json）を読む。"""
    return json.loads((FORMS_DIR / f"{key}.json").read_text(encoding="utf-8"))


def _x(v):
    return v * mm


def _y(v):
    return PAGE_H - v * mm


def _fit_line(text, width_pt, height_pt):
    """1行に入る字の大きさと幅の詰め方（%）を返す。入らなければ fits=False。"""
    size = min(SIZE_MAX, height_pt * 0.85)
    while size > SIZE_MIN and pdfmetrics.stringWidth(text, FONT, size) > width_pt:
        size -= 0.25
    size = max(size, SIZE_MIN)
    w = pdfmetrics.stringWidth(text, FONT, size)
    scale = 100
    if w > width_pt:
        scale = max(SCALE_MIN, int(100 * width_pt / w))
    fits = w * scale / 100 <= width_pt + 0.01
    return size, scale, fits


def _wrap(text, width_pt, size):
    """字の幅で行を分ける（利用者の改行は残す）。"""
    lines = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            if line and pdfmetrics.stringWidth(line + ch, FONT, size) > width_pt:
                lines.append(line)
                line = ch
            else:
                line += ch
        lines.append(line)
    return lines


def _draw_text(c, text, box, align):
    l, t, r, b = box
    width, height = (r - l) * mm, (b - t) * mm
    size, scale, fits = _fit_line(text, width, height)
    w = pdfmetrics.stringWidth(text, FONT, size) * scale / 100
    if align == "right":
        x = _x(r) - w
    elif align == "center":
        x = (_x(l) + _x(r) - w) / 2
    else:
        x = _x(l)
    baseline = _y((t + b) / 2) - size * 0.35
    t_obj = c.beginText(x, baseline)
    t_obj.setFont(FONT, size)
    t_obj.setHorizScale(scale)
    t_obj.textOut(text)
    c.drawText(t_obj)
    return fits


def _draw_multiline(c, text, box):
    l, t, r, b = box
    width, height = (r - l) * mm, (b - t) * mm
    size = SIZE_MULTI
    while True:
        lines = _wrap(text, width, size)
        if len(lines) * size * LINE_GAP <= height + 0.01 or size <= SIZE_MIN:
            break
        size -= 0.25
    fits = len(lines) * size * LINE_GAP <= height + 0.01
    y = _y(t) - size * (LINE_GAP - 1) / 2 - size * 0.88
    for line in lines:
        c.setFont(FONT, size)
        c.drawString(_x(l), y, line)
        y -= size * LINE_GAP
    return fits


def _draw_circle(c, box):
    l, t, r, b = box
    c.setLineWidth(PEN)
    c.ellipse(_x(l), _y(b), _x(r), _y(t), stroke=1, fill=0)


def _draw_check(c, box):
    l, t, r, b = box
    w, h = r - l, b - t
    p = c.beginPath()
    p.moveTo(_x(l + w * 0.15), _y(t + h * 0.55))
    p.lineTo(_x(l + w * 0.42), _y(t + h * 0.85))
    p.lineTo(_x(l + w * 0.95), _y(t + h * 0.05))
    c.setLineWidth(PEN * 1.6)
    c.drawPath(p, stroke=1, fill=0)


def draw_fields(c, form, values, offset=(0.0, 0.0)):
    """欄の値を描く。offset は、プリンターのずれ（mm。右・下が正）。入りきらなかった欄の番号を返す。"""
    _register_font()
    dx, dy = offset
    c.saveState()
    c.translate(dx * mm, -dy * mm)
    overflow = []
    for f in form["fields"]:
        v = values.get(f["id"])
        if is_empty(v):
            continue
        kind = f["type"]
        if kind in ("text", "number"):
            ok = _draw_text(c, str(v), f["box"], f.get("align", "left"))
        elif kind == "multiline":
            ok = _draw_multiline(c, str(v), f["box"])
        elif kind == "circle":
            _draw_circle(c, f["options"][int(v)])
            ok = True
        elif kind == "check":
            _draw_check(c, f["box"])
            ok = True
        elif kind == "date":
            ok = True
            for part in ("year", "month", "day"):
                if not is_empty(v.get(part)):
                    ok = _draw_text(c, str(v[part]), f["parts"][part], "right") and ok
            if v.get("era") is not None and "era" in f:
                _draw_circle(c, f["era"][int(v["era"])])
        else:
            raise ValueError(f"欄の種類が分かりません：{kind}")
        if not ok:
            overflow.append(f["id"])
    c.restoreState()
    return overflow


def make_pdf(form, values, with_image, image=None, offset=(0.0, 0.0), fields=True):
    """PDF（バイト列）と、入りきらなかった欄の番号を返す。

    image は下に敷く用紙の画像（場所かバイト列）。省くと form["image_path"]、それもなければ様式の画像（ダミー）を使う。
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=1)
    c.setTitle("")
    c.setAuthor("")
    c.setCreator("VA Request")
    overflow = []
    if with_image:
        l, t, r, b = form["image"]["box"]
        src = image or form.get("image_path") or str(FORMS_DIR / form["image"]["file"])
        if isinstance(src, (bytes, bytearray)):
            src = ImageReader(io.BytesIO(src))
        c.drawImage(src, _x(l), _y(b), (r - l) * mm, (b - t) * mm)
    if fields:
        overflow = draw_fields(c, form, values, offset)
    c.showPage()
    c.save()
    return buf.getvalue(), overflow
