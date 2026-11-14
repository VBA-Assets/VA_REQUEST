"""試験の道具。設定は、試験ごとの一時フォルダに置く（班長の設定〔%APPDATA%\\VA Request〕に書かない）。

欄に入れる字はすべて架空のもの（実データは使わない）。
"""
import pytest

from va_request.config import Config


@pytest.fixture(autouse=True)
def _config_dir(tmp_path, monkeypatch):
    folder = tmp_path / "設定"
    monkeypatch.setenv("VA_REQUEST_CONFIG_DIR", str(folder))
    return folder


@pytest.fixture
def cfg(_config_dir):
    return Config(_config_dir)


@pytest.fixture(scope="session")
def root():
    """Tk は、試験の全体で1つだけ作る（Windows の Python では、作り直すとまれに初期化に失敗する）。"""
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    yield r
    r.destroy()
