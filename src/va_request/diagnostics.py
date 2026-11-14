"""［ヘルプ］→［診断情報をコピー］の文と、誤りの記録（VA Document・VA Case と同じ考え方）。

入れるもの：版・OS・Python・様式・欄の数・入力した欄の数・用紙の画像を読み込んでいるか・直した位置の数・例文と既定の値の数・
誤りの型と発生した場所（ファイル名・行・関数名）。
入れないもの：欄の値（請求の内容）・例文の中身・ファイルの名前と場所・プリンターの名前・例外のメッセージの本文。
誤りの記録は %APPDATA%\\VA Request\\errors.json（型と場所だけ。最近の 20 件）。
"""
import json
import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from . import VERSION_LABEL

MAX_ERRORS = 20


class ErrorLog:
    def __init__(self, folder):
        self.path = Path(folder) / "errors.json"

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except (OSError, ValueError):
            return []

    def record(self, exc, where):
        """誤りの型と、発生した場所（このパッケージの中の最後の場所）だけを覚える。"""
        place = ""
        for frame in traceback.extract_tb(exc.__traceback__):
            place = f"{Path(frame.filename).name}:{frame.lineno}:{frame.name}"
        items = self.load()
        items.append({"time": datetime.now().strftime("%Y-%m-%d %H:%M"), "type": type(exc).__name__,
                      "place": place, "where": where})
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(json.dumps(items[-MAX_ERRORS:], ensure_ascii=False, indent=1).encode("utf-8"))
        except OSError:
            pass


def text(state, errors):
    """診断情報の文。state は、数と有無だけを入れた辞書（呼ぶ側が作る）。"""
    lines = [
        f"VA Request {VERSION_LABEL}",
        f"OS: {platform.system()} {platform.release()} ({platform.version()})",
        f"Python: {sys.version.split()[0]}{'（実行ファイル）' if getattr(sys, 'frozen', False) else ''}",
        f"画面の拡大率: {state.get('scale', '-')}",
    ]
    for k, v in state.items():
        if k != "scale":
            lines.append(f"{k}: {v}")
    lines.append("最近の誤り：" + ("なし" if not errors else ""))
    for e in errors[-10:]:
        lines.append(f"  {e.get('time', '')} {e.get('type', '')} {e.get('place', '')}（{e.get('where', '')}）")
    return "\n".join(lines)


def config_folder_exists(folder):
    return "あり" if os.path.isdir(folder) else "なし"
