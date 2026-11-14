"""VA Request が使っている部品のライセンスの表示（THIRD_PARTY_NOTICES.txt）を作る（VA Case の make_notices.py と同じ作り）。

exe に入る部品（Python・Tcl/Tk・ReportLab・charset-normalizer・pypdf・Pillow・pypdfium2 と PDFium・PyInstaller の
ブートローダー）と、ボタンのアイコン（Fluent UI System Icons）のライセンスの全文を、いま入っている部品のファイルから集める。
部品を足したとき・版を上げたときは、作り直してコミットする（exe に入る部品は、PyInstaller の
build\\va_request\\PKG-00.toc・PYZ-00.toc で確かめられる）。

実行のしかた：
    python scripts\\make_notices.py
"""

from __future__ import annotations

import importlib.metadata as metadata
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "THIRD_PARTY_NOTICES.txt"
PY_HOME = Path(sys.base_prefix)


def _dist_license_files(dist: str) -> list[Path]:
    """配布 dist の dist-info の licenses の下のファイル。なければ dist-info の LICENSE などのファイル。"""
    d = metadata.distribution(dist)
    out, fallback = [], []
    for f in d.files or []:
        s = str(f).replace("\\", "/")
        if ".dist-info/licenses/" in s:
            out.append(Path(d.locate_file(f)))
        elif ".dist-info/" in s and s.rsplit("/", 1)[-1].upper().startswith(("LICENSE", "COPYING", "LICENCE")):
            fallback.append(Path(d.locate_file(f)))
    return sorted(out or fallback)


# (表示する名前, 配布の名前〔版を読む。None は版を書かない〕, 用途, ライセンス, 全文〔ファイルの並び か 関数〕)
COMPONENTS = [
    ("Python", None, "プログラムの言語（exe に入る）", "PSF License Version 2（Windows 版に入っている部品のライセンスを含む）",
     [PY_HOME / "LICENSE.txt"]),
    ("Tcl/Tk", None, "画面", "Tcl/Tk License（BSD 形式）", [PY_HOME / "tcl" / "tk8.6" / "license.terms"]),
    ("ReportLab", "reportlab", "PDF の作成（請求の字と、用紙の画像）", "BSD License",
     lambda: _dist_license_files("reportlab")),
    ("charset-normalizer", "charset-normalizer", "ReportLab が使う部品", "MIT License",
     lambda: _dist_license_files("charset-normalizer")),
    ("pypdf", "pypdf", "保存した PDF に、開き直すための情報を入れる・読む", "BSD License（3条項）",
     lambda: _dist_license_files("pypdf")),
    ("Pillow", "pillow", "画像（用紙の画像・プレビュー・アイコン）",
     "MIT-CMU License（Pillow に入っている画像の部品のライセンスを含む）", lambda: _dist_license_files("pillow")),
    ("pypdfium2（PDFium を含む）", "pypdfium2", "プレビューと印刷（PDF のページを画像にする）",
     "Apache-2.0・BSD-3-Clause（PDFium とその部品のライセンスを含む）", lambda: _dist_license_files("pypdfium2")),
    ("PyInstaller", "pyinstaller", "実行ファイルの作成（ブートローダーが exe に入る）",
     "GNU General Public License 第2版以降（ブートローダーの例外条項付き）", lambda: _dist_license_files("pyinstaller")),
    ("Fluent UI System Icons", None, "ボタンのアイコン", "MIT License",
     [ROOT / "src" / "va_request" / "ui" / "icons" / "LICENSE"]),
]


def build() -> Path:
    parts = [
        "VA Request が使っている部品のライセンスの表示",
        "",
        "VA Request そのものは、MIT License で公開しています（LICENSE）。",
        "実行ファイル（VA_Request.exe）には、次の部品が入っています。",
        "",
    ]
    for name, dist, use, lic, files in COMPONENTS:
        if name == "Python":
            version = sys.version.split()[0]
        elif name == "Tcl/Tk":
            import tkinter
            version = str(tkinter.Tcl().eval("info patchlevel"))
        else:
            version = metadata.version(dist) if dist else ""
        parts += ["=" * 78, f"{name} {version}".rstrip(), f"用途：{use}", f"ライセンス：{lic}", "=" * 78]
        paths = files() if callable(files) else files
        if not paths:
            raise SystemExit(f"{name} のライセンスの文が見つかりません。")
        for path in paths:
            parts += [f"--- {path.name} ---", path.read_text(encoding="utf-8-sig", errors="replace").rstrip(), ""]
        parts.append("")
    OUTPUT.write_text("\n".join(parts) + "\n", encoding="utf-8", newline="\n")
    return OUTPUT


if __name__ == "__main__":
    print(f"作りました：{build()}")
