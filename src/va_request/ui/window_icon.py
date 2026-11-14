"""ウィンドウ・タスクバーのアイコン（VA Case の shared_app.set_window_icon と同じ付け方）。

exe そのもののアイコンは PyInstaller の spec（EXE の icon=）で埋め込む。Tk のウィンドウには、実行のときにファイルとして
読ませるので、exe では展開先（sys._MEIPASS）の assets に入れる。見つからない・読めないときは既定のまま（起動を妨げない）。
"""
import io
import os
import sys
import tkinter as tk
from pathlib import Path

ICON_FILE = "VA_Request.ico"


def icon_path(name=ICON_FILE):
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    else:
        base = Path(__file__).resolve().parents[3]
    return base / "assets" / name


def set_window_icon(root, name=ICON_FILE):
    path = icon_path(name)
    if not path.exists():
        return
    try:
        if os.name == "nt":
            root.iconbitmap(default=str(path))
        from PIL import Image
        photos = []
        with Image.open(path) as im:
            for size in sorted(im.info.get("sizes", []), reverse=True):
                if size[0] not in (256, 48, 32, 16):
                    continue
                im.size = size
                buf = io.BytesIO()
                im.convert("RGBA").save(buf, format="PNG")
                photos.append(tk.PhotoImage(master=root, data=buf.getvalue()))
        if photos:
            root._va_icon_images = photos                  # 画像の参照を残す（消えないように）
            root.iconphoto(True, *photos)                  # これから作るウィンドウ（確かめの画面など）にも
    except Exception:
        pass
