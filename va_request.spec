# -*- mode: python ; coding: utf-8 -*-
# VA Request の実行ファイル（dist\VA_Request.exe）を作る（VA Case の va_case.spec と同じ作り。1つのファイルの exe）。
# 作り方：python -m PyInstaller va_request.spec --noconfirm
#
# 入れるもの：
# ・様式（A〜D の欄の定義の JSON と、ダミーの用紙の画像）。forms.py は va_request\forms から読む
# ・ボタンのアイコン（Fluent UI System Icons の PNG と LICENSE）。icons.py は va_request\ui\icons から読む
# ・ウィンドウ（タイトルバー・タスクバー）のアイコン（assets の .ico）。exe そのもののアイコンは EXE(icon=...) で埋め込むが、
#   Tk のウィンドウには実行時にファイルとして読ませるため、展開先（sys._MEIPASS）の assets に入れる（ui\window_icon.py）
# ・pypdfium2 の pdfium.dll（プレビューと印刷）
# 入れないもの：試験の部品、ほかの GUI、PyMuPDF（AGPL。開発のときのアイコン作りでだけ使う）、numpy（試作でだけ使う）

from PyInstaller.utils.hooks import collect_dynamic_libs

datas = [
    ('src/va_request/forms', 'va_request/forms'),
    ('src/va_request/ui/icons', 'va_request/ui/icons'),
    ('assets/VA_Request.ico', 'assets'),
]
binaries = collect_dynamic_libs('pypdfium2_raw')
excludes = ['pytest', 'fitz', 'pymupdf', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'matplotlib', 'numpy', 'pandas']

a = Analysis(
    ['main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VA_Request',
    icon='assets/VA_Request.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
