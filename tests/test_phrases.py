"""例文のファイル（1つのファイルにまとめ、共有できる。2026-11-14 班長指示）の試験。例文は架空のもの。"""
import json

import pytest

from va_request import app as app_mod
from va_request.config import Config
from va_request.phrases import FILE_NAME, PhrasesChanged, PhrasesError, PhraseStore


def test_one_file_for_all_forms(tmp_path):
    store = PhraseStore(tmp_path / "共有")
    store.save_field("A", 18, ["架空の例文1", "架空の例文2\n2行目"])
    store.save_field("B", 6, ["架空の宛先"], expected_stamp=store.stamp())
    assert [p.name for p in (tmp_path / "共有").iterdir()] == [FILE_NAME] == ["職務上請求書例文.json"]
    assert store.load_all() == {"A": {18: ["架空の例文1", "架空の例文2\n2行目"]}, "B": {6: ["架空の宛先"]}}
    body = json.loads(store.path.read_text(encoding="utf-8"))
    assert body["forms"]["A"]["title"] == "A用紙" and body["forms"]["A"]["fields"]["18"]["label"] == "欄8-6"
    store.save_field("A", 18, [], expected_stamp=store.stamp())        # 空にすると消える
    assert store.load_all() == {"B": {6: ["架空の宛先"]}}


def test_changed_by_someone_else(tmp_path):
    a = PhraseStore(tmp_path)
    b = PhraseStore(tmp_path)              # 同じ共有フォルダを使う別の PC
    stamp = a.stamp()
    b.save_field("A", 6, ["ほかの人の例文"])
    with pytest.raises(PhrasesChanged):
        a.save_field("A", 18, ["自分の例文"], expected_stamp=stamp)
    a.save_field("A", 18, ["自分の例文"], force=True)
    assert a.load_all()["A"] == {6: ["ほかの人の例文"], 18: ["自分の例文"]}      # ほかの人の直しを消さない


def test_unreadable(tmp_path):
    (tmp_path / "ふつうのファイル").write_text("x", encoding="utf-8")
    store = PhraseStore(tmp_path / "ふつうのファイル")          # フォルダでない（つながっていない共有フォルダの代わり）
    with pytest.raises(PhrasesError):
        store.save_field("A", 6, ["架空"], force=True)
    (tmp_path / FILE_NAME).write_text("{壊れた", encoding="utf-8")
    with pytest.raises(PhrasesError):
        PhraseStore(tmp_path).load_all()


def test_migrate_from_settings(root, tmp_path, monkeypatch):
    """前の版で設定ファイルに書いていた例文を、起動したときに例文のファイルへ移す。"""
    cfg = Config(tmp_path / "設定")
    cfg._form("A")["phrases"] = {"18": ["前の版の例文"]}
    cfg.save()
    a = app_mod.App(root, Config(tmp_path / "設定"))
    assert a.phrase_store.load_all() == {"A": {18: ["前の版の例文"]}}
    assert "phrases" not in Config(tmp_path / "設定")._form("A")
    for w in root.winfo_children():
        w.destroy()


def test_options_change_folder(root, tmp_path, monkeypatch):
    cfg = Config(tmp_path / "設定")
    a = app_mod.App(root, cfg)
    a.phrase_store.save_field("A", 6, ["架空の例文"], force=True)
    shared = tmp_path / "事務所の共有"
    shared.mkdir()
    monkeypatch.setattr(app_mod.OptionsDialog, "show", lambda self: shared)
    monkeypatch.setattr(app_mod.messagebox, "askyesno", lambda *x, **k: True)     # 今の例文を写す
    a.options()
    assert cfg.phrases_folder() == shared and Config(tmp_path / "設定").phrases_folder() == shared
    assert PhraseStore(shared).load_all() == {"A": {6: ["架空の例文"]}}
    # 既定に戻す
    monkeypatch.setattr(app_mod.OptionsDialog, "show", lambda self: None)
    a.options()
    assert cfg.phrases_folder_is_default() and a.phrase_store.folder == cfg.folder
    for w in root.winfo_children():
        w.destroy()
