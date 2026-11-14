"""例文のファイル（2026-11-14 班長指示「例文は別ファイルに保存し、共有できるようにする」。同日「様式ごとではなく、
１つのファイルにまとめる」）。

・A〜D の様式の例文を、1つのファイル「職務上請求書例文.json」にまとめる。置き場所は［ファイル］→［オプション］で
  決める（既定は、この PC の設定の場所 %APPDATA%\\VA Request）。事務所の共有フォルダ（同期フォルダを含む）に
  すれば、何人かで同じ例文を使える。
・中身は、様式ごと・欄の番号ごとの例文の並び（UTF-8 の JSON。人が読めるよう、様式名と欄の呼び名も添える）。
・書くときは、別の名前で書いてから置き換える（書く途中で落ちても、ファイルが壊れないように）。
・何人かで使うときに、ほかの人の直しを消さないよう、書く直前に読み直し（直した欄のほかは、読み直したものを残す）、
  読んだときからファイルが変わっていれば知らせる（PhrasesChanged）。読み書きできないとき（共有フォルダに
  つながっていないなど）は PhrasesError。
"""
import json
import os
from pathlib import Path

from . import forms

APP = "VA Request"
FORMAT = 1
FILE_NAME = "職務上請求書例文.json"


class PhrasesError(Exception):
    """例文のファイルを読めない・書けない。"""


class PhrasesChanged(Exception):
    """読んだ後に、ほかの人が例文のファイルを変えた。"""


class PhraseStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.path = self.folder / FILE_NAME

    def exists(self):
        return self.path.exists()

    def stamp(self):
        """ファイルの更新の印（なければ None）。読んだときと書く前で比べる。"""
        try:
            st = self.path.stat()
            return (st.st_mtime_ns, st.st_size)
        except FileNotFoundError:
            return None
        except OSError as e:
            raise PhrasesError(str(e)) from e

    def load_all(self):
        """様式の記号 → 欄の番号 → 例文の並び。ファイルがなければ空。"""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:
            raise PhrasesError(str(e)) from e
        out = {}
        for key, form in (data.get("forms", {}) if isinstance(data, dict) else {}).items():
            fields = form.get("fields", {}) if isinstance(form, dict) else {}
            table = {}
            for k, v in fields.items():
                items = v.get("phrases", []) if isinstance(v, dict) else []
                if str(k).isdigit() and items:
                    table[int(k)] = [str(s) for s in items]
            if table:
                out[str(key)] = table
        return out

    def phrases(self, key, field_id):
        return list(self.load_all().get(key, {}).get(field_id, []))

    def save_field(self, key, field_id, items, expected_stamp=None, force=False):
        """1つの欄の例文を書く（ほかの欄の例文は、書く直前に読んだものを残す）。
        expected_stamp は読んだときの印。変わっていて force でなければ PhrasesChanged。"""
        if not force and self.stamp() != expected_stamp:
            raise PhrasesChanged()
        data = self.load_all()
        table = data.setdefault(key, {})
        if items:
            table[field_id] = list(items)
        else:
            table.pop(field_id, None)
        self.save_all(data)

    def save_all(self, data):
        """すべての例文を書く（様式名・欄の呼び名は、組み込みの様式から添える）。"""
        body_forms = {}
        for key in sorted(data):
            form = forms.builtin(key) if key in forms.FORM_KEYS else None
            labels = {f["id"]: f.get("label", "") for f in form["fields"]} if form else {}
            fields = {str(k): {"label": labels.get(k, ""), "phrases": v} for k, v in sorted(data[key].items()) if v}
            if fields:
                body_forms[key] = {"title": form["title"] if form else key, "fields": fields}
        body = {"app": APP, "format": FORMAT, "forms": body_forms}
        tmp = self.path.with_name(self.path.name + ".tmp")
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes((json.dumps(body, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
            os.replace(tmp, self.path)
        except OSError as e:
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise PhrasesError(str(e)) from e
