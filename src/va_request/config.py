"""この PC だけの設定（%APPDATA%\\VA Request\\settings.json。仕様.md の 4.8）。

置くもの：様式ごとの用紙の画像（写し）と、その置き場所・欄の位置、既定の値、プリンターごとのずれ、前に保存したフォルダ、
例文のファイルの置き場所（例文そのものは、様式ごとの別のファイル。phrases.py）。
置かないもの：請求の内容（入力した字）。請求の内容が残るのは、利用者が保存した PDF だけ。

試験のときは、環境変数 VA_REQUEST_CONFIG_DIR で置き場所を替える（班長の設定に書かないため）。
"""
import json
import os
import shutil
from pathlib import Path

from . import forms

APP_DIR_NAME = "VA Request"


def config_dir():
    override = os.environ.get("VA_REQUEST_CONFIG_DIR")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / APP_DIR_NAME


def _key(field_id):
    return str(field_id)


class Config:
    """設定の読み書き。値を変えたら save() で書く（呼ぶ側が決める）。"""

    def __init__(self, folder=None):
        self.folder = Path(folder) if folder else config_dir()
        self.path = self.folder / "settings.json"
        self.data = {}
        self.load()

    # ---- 読み書き ----
    def load(self):
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.data, dict):
                self.data = {}
        except (OSError, ValueError):
            self.data = {}

    def save(self):
        self.folder.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_bytes((json.dumps(self.data, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        os.replace(tmp, self.path)

    def _form(self, key):
        return self.data.setdefault("forms", {}).setdefault(key, {})

    # ---- 用紙の画像と欄の位置 ----
    def paper(self, key):
        """利用者が読み込んだ用紙の画像（写し）の場所と置き場所（mm）。なければ None（ダミーを使う）。"""
        p = self._form(key).get("paper")
        if not p:
            return None
        path = self.folder / "images" / p["file"]
        return {"path": path, "box": p["box"]} if path.exists() else None

    def set_paper(self, key, source, box):
        """用紙の画像を設定の場所に写し、置き場所を覚える。"""
        images = self.folder / "images"
        images.mkdir(parents=True, exist_ok=True)
        name = f"{key}{Path(source).suffix.lower()}"
        for old in images.glob(f"{key}.*"):
            old.unlink()
        shutil.copyfile(source, images / name)
        self._form(key)["paper"] = {"file": name, "box": [round(v, 2) for v in box]}

    def clear_paper(self, key):
        self._form(key).pop("paper", None)
        for old in (self.folder / "images").glob(f"{key}.*"):
            old.unlink()

    def positions(self, key):
        """利用者が直した欄の位置（項目の名前 → [左, 上, 右, 下]）。"""
        return dict(self._form(key).get("positions", {}))

    def set_positions(self, key, positions):
        if positions:
            self._form(key)["positions"] = {k: [round(v, 2) for v in box] for k, box in positions.items()}
        else:
            self._form(key).pop("positions", None)

    # ---- 例文の置き場所（例文そのものは phrases.py のファイル。2026-11-14 班長指示）----
    def phrases_folder(self):
        """例文のファイルを置くフォルダ。指定がなければ、この設定の場所。"""
        p = self.data.get("phrases_folder")
        return Path(p) if p else self.folder

    def phrases_folder_is_default(self):
        return not self.data.get("phrases_folder")

    def set_phrases_folder(self, folder):
        if folder and Path(folder) != self.folder:
            self.data["phrases_folder"] = str(folder)
        else:
            self.data.pop("phrases_folder", None)

    def legacy_phrases(self, key):
        """前の版で設定ファイルに書いていた例文（欄の番号 → 並び）。ファイルへ移すときに使う。"""
        return {int(k): list(v) for k, v in self._form(key).get("phrases", {}).items() if v}

    def drop_legacy_phrases(self, key):
        self._form(key).pop("phrases", None)

    # ---- 既定の値 ----
    def defaults(self, key):
        """既定の値（欄の番号 → 値）。"""
        return {int(k): v for k, v in self._form(key).get("defaults", {}).items()}

    def set_default(self, key, field_id, value):
        table = self._form(key).setdefault("defaults", {})
        if forms.is_empty(value):
            table.pop(_key(field_id), None)
        else:
            table[_key(field_id)] = value

    # ---- プリンター ----
    def printer_offset(self, printer):
        o = self.data.get("printer_offsets", {}).get(printer, [0.0, 0.0])
        return float(o[0]), float(o[1])

    def set_printer_offset(self, printer, dx, dy):
        self.data.setdefault("printer_offsets", {})[printer] = [round(float(dx), 2), round(float(dy), 2)]

    def get(self, name, default=None):
        return self.data.get(name, default)

    def set(self, name, value):
        self.data[name] = value
