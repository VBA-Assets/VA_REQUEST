"""リボンのボタンのアイコン（VA Case の icons.py を写したもの）。

アイコンは Microsoft の Fluent UI System Icons（MIT License。icons\\LICENSE）で、VA Document と同じ2色の形。
scripts\\make_icons.py で SVG から大きめの PNG にしたもの（icons\\<名前>.png・<名前>_disabled.png・<名前>_large.png）を、
起動したときに Pillow で画面の拡大率に合った大きさに縮める（拡大してもぼやけない。PyMuPDF〔AGPL〕を配るものに
入れないため。VA Document は起動のたびに SVG を画像にしている）。
"""
from pathlib import Path

ICON_DIR = Path(__file__).resolve().parent / "icons"
ICON_SIZE = 16          # 小さいアイコンの大きさ（拡大率 100% のとき。画素）
LARGE_ICON = 32         # 大きいボタンのアイコンの大きさ

# ボタンの字（改行と「…」を除く）→ アイコンの名前（icons\<名前>.png）
BUTTON_ICONS = {
    "開く": "folder_open", "保存": "save", "印刷": "print", "閉じる": "document_dismiss",
    "用紙の画像": "image", "欄の位置": "table",
    "例文の選択": "clipboard_paste", "例文の登録": "text_bullet_list_square", "既定の値にする": "save_edit",
    "既定の値を消す": "delete", "今日の日付": "calendar_checkmark",
}


def icon_name(text):
    return BUTTON_ICONS.get(str(text).replace("\n", "").replace("…", ""))


class IconSet:
    """アイコンの画像を作って覚えておく（Tk の画像は、参照がなくなると消えるため）。"""

    def __init__(self, root):
        self.root = root
        self.scale = max(1.0, root.winfo_fpixels("1i") / 96)        # 画面の拡大率
        self._cache = {}

    def image(self, name, disabled=False, large=False):
        """アイコンの画像（なければ None）。large なら大きいボタンの大きさで、色付きのアイコン（_large）があればそれを
        使う（押せないときは、灰色の線画を大きくする）。"""
        size = round((LARGE_ICON if large else ICON_SIZE) * self.scale)
        key = (name, disabled, large, size)
        if key not in self._cache:
            candidates = [f"{name}_large.png"] if large and not disabled else []
            candidates.append(f"{name}_disabled.png" if disabled else f"{name}.png")
            path = next((ICON_DIR / c for c in candidates if (ICON_DIR / c).exists()), None)
            if path is None:
                return None
            from PIL import Image, ImageTk
            with Image.open(path) as img:
                small = img.convert("RGBA").resize((size, size), Image.LANCZOS)
            self._cache[key] = ImageTk.PhotoImage(small, master=self.root)
        return self._cache[key]
