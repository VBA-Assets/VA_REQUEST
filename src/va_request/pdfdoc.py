"""請求の PDF の保存と開き直し（仕様.md の 4.6）。

保存する PDF は、用紙の画像と字を重ねたもの。開き直すための情報（様式・欄の位置・用紙の画像の置き場所・入力の値）を、
PDF の添付のファイル（ATTACHMENT）として入れる。画面に出る字と同じ内容なので、PDF に新しく足される情報はない。
用紙の画像は、ページに入っている画像をそのまま取り出す（二重に持たない）。
"""
import io
import json
import os
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from . import forms, render

ATTACHMENT = "va_request.json"
APP = "VA Request"
FORMAT = 1


class NotRequestPdf(Exception):
    """VA Request が保存した PDF ではない、または壊れている。"""


def values_to_json(values):
    return {str(k): v for k, v in values.items() if not forms.is_empty(v)}


def values_from_json(data):
    return {int(k): v for k, v in data.items()}


def build(form, values, image=None):
    """保存する PDF のバイト列と、入りきらなかった欄の番号。"""
    body, overflow = render.make_pdf(form, values, with_image=True, image=image)
    info = {
        "app": APP, "format": FORMAT, "form": form["form"],
        "image_box": form["image"]["box"],
        "positions": forms.field_positions(form),
        "values": values_to_json(values),
    }
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(body)))
    writer.add_attachment(ATTACHMENT, json.dumps(info, ensure_ascii=False).encode("utf-8"))
    writer.add_metadata({"/Title": "", "/Author": "", "/Creator": APP, "/Producer": APP})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue(), overflow


def save(path, form, values, image=None):
    """PDF を path に書く（いったん別の名前で書いてから置き換える）。入りきらなかった欄の番号を返す。"""
    data, overflow = build(form, values, image)
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    try:
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return overflow


def read(path):
    """保存した PDF を読む。{"form", "values", "positions", "image_box", "image"（画像のバイト列）} を返す。"""
    try:
        reader = PdfReader(str(path))
        att = reader.attachments.get(ATTACHMENT)
        if not att:
            raise NotRequestPdf()
        info = json.loads(att[0].decode("utf-8"))
        if info.get("app") != APP or info.get("form") not in forms.FORM_KEYS:
            raise NotRequestPdf()
        images = reader.pages[0].images
        image = images[0].data if len(images) else None
    except NotRequestPdf:
        raise
    except Exception as e:
        raise NotRequestPdf() from e
    return {
        "form": info["form"],
        "values": values_from_json(info.get("values", {})),
        "positions": info.get("positions", {}),
        "image_box": info.get("image_box"),
        "image": image,
    }


def form_of(opened, base_form):
    """開いた PDF の、保存したときの欄の位置と画像の置き場所を、様式 base_form に当てたもの。"""
    form = forms.apply_positions(base_form, opened["positions"])
    if opened.get("image_box"):
        form["image"] = dict(form["image"], box=opened["image_box"])
    return form
