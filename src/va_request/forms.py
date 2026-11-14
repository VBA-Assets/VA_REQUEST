"""様式（A〜D）の欄の定義と、利用者が直した位置・読み込んだ用紙の画像を合わせたもの（仕様.md の 4.1・4.2）。

欄の中の、動かせる1つ1つの四角を「項目」と呼び、次の名前で区別する（設定ファイルの位置の名前にもなる）。
  "<番号>"          … 字・数・印の欄
  "<番号>.o<i>"     … 囲みの欄の i 番目の語
  "<番号>.year" など … 日付の欄の年・月・日
  "<番号>.e<i>"     … 日付の欄の元号の i 番目
位置は「用紙（A4）の左上からの mm」で、[左, 上, 右, 下]。
"""
import copy
import json
from pathlib import Path

FORMS_DIR = Path(__file__).resolve().parent / "forms"
FORM_KEYS = ("A", "B", "C", "D")
PARTS = ("year", "month", "day")


def is_empty(value):
    """欄の値が空か。囲みの 0 番目（0）は空ではない（0 == False に気をつける）。"""
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return value == ""
    if isinstance(value, dict):
        return all(is_empty(value.get(p)) for p in PARTS) and value.get("era") is None
    return False


def known_values(form, values):
    """様式にある欄の値だけを残す。欄から外した欄（A の 10。2026-11-15）の値は、前に保存した PDF や既定の値に
    残っていても、表示も印刷もしないので、持ち続けない（保存し直したときに PDF に残さない）。"""
    ids = {f["id"] for f in form["fields"]}
    return {k: v for k, v in values.items() if k in ids}


def label(field):
    """欄の呼び名（日付欄・宛名欄・欄1-1 など。様式の定義の label。2026-11-14 班長指示）。"""
    return field.get("label") or f"欄{field['id']}"


def item_label(form, name):
    """項目の呼び名（位置合わせの画面に出す）。"""
    fid, _, sub = name.partition(".")
    f = next(f for f in form["fields"] if str(f["id"]) == fid)
    base = label(f)
    if not sub:
        return base
    if sub[0] == "o":
        if f.get("direction") == "down":        # 縦に並んだ番号（A の番号欄）
            return f"{base}（上から {int(sub[1:]) + 1} 番目の番号）"
        return f"{base}（左から {int(sub[1:]) + 1} 番目の語）"
    if sub[0] == "e":
        return f"{base}（元号の左から {int(sub[1:]) + 1} 番目）"
    return f"{base}（{ {'year': '年', 'month': '月', 'day': '日'}[sub] }）"


def builtin(key):
    """組み込みの様式（ダミーの様式での位置）。"""
    return json.loads((FORMS_DIR / f"{key}.json").read_text(encoding="utf-8"))


def items(form):
    """様式の項目の (名前, 四角, 欄) の並び。"""
    out = []
    for f in form["fields"]:
        fid = f["id"]
        if "box" in f:
            out.append((str(fid), f["box"], f))
        for i, box in enumerate(f.get("options", [])):
            out.append((f"{fid}.o{i}", box, f))
        for part in PARTS:
            if part in f.get("parts", {}):
                out.append((f"{fid}.{part}", f["parts"][part], f))
        for i, box in enumerate(f.get("era", [])):
            out.append((f"{fid}.e{i}", box, f))
    return out


def set_item_box(form, name, box):
    """項目 name の四角を box にする（form を書き換える）。"""
    fid, _, sub = name.partition(".")
    f = next(f for f in form["fields"] if str(f["id"]) == fid)
    box = [round(float(v), 2) for v in box]
    if not sub:
        f["box"] = box
    elif sub[0] == "o" and sub[1:].isdigit():
        f["options"][int(sub[1:])] = box
    elif sub[0] == "e" and sub[1:].isdigit():
        f["era"][int(sub[1:])] = box
    elif sub in PARTS:
        f["parts"][sub] = box
    else:
        raise KeyError(name)


def item_box(form, name):
    for n, box, _ in items(form):
        if n == name:
            return box
    raise KeyError(name)


def effective(cfg, key):
    """組み込みの様式に、利用者の用紙の画像と、直した欄の位置を当てたもの。
    image_path は下に敷く画像の場所、custom_paper は利用者の用紙を読み込んでいるか。"""
    form = builtin(key)
    for name, box in cfg.positions(key).items():
        try:
            set_item_box(form, name, box)
        except (KeyError, StopIteration, IndexError):
            pass                # 様式の定義が変わって無くなった項目は無視する
    paper = cfg.paper(key)
    if paper:
        form["image"] = {"file": str(paper["path"]), "box": paper["box"]}
        form["image_path"] = str(paper["path"])
        form["custom_paper"] = True
    else:
        form["image_path"] = str(FORMS_DIR / form["image"]["file"])
        form["custom_paper"] = False
    return form


def positions_diff(form, key):
    """組み込みの位置と違う項目の位置（設定に書く分）。"""
    base = dict((n, b) for n, b, _ in items(builtin(key)))
    return {n: list(b) for n, b, _ in items(form) if [round(v, 2) for v in b] != [round(v, 2) for v in base.get(n, [])]}


def field_positions(form):
    """PDF に入れる、欄の位置（開き直したときに、保存したときの位置で表示・印刷するため）。"""
    return {n: list(b) for n, b, _ in items(form)}


def apply_positions(form, positions):
    form = copy.deepcopy(form)
    for name, box in positions.items():
        try:
            set_item_box(form, name, box)
        except (KeyError, StopIteration, IndexError):
            pass
    return form
