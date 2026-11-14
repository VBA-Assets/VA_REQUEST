"""IME の入力中の字（変換前の字）の書体を、入力欄の書体に合わせる（Windows だけ）。

Tk は、IME の入力中の字の位置は入力欄に合わせるが、書体は合わせない。そのため入力中の字が、Windows の既定の
書体（System。拡大率 125％の画面で 22 画素）で出て、入力欄の字（BIZ UDゴシック 10 ポイント。17 画素）より
大きくなっていた（2026-11-11 班長指摘「IME の未確定時の文字のフォントサイズが大きい」）。入力欄に入るたびに、
IME の入力中の書体（ImmSetCompositionFontW）を、その欄の書体と大きさにする（同日 班長決定。VA Document の
ime.py と同じ方法）。合わせるのは見た目だけで、入力した字の扱いは変えない。うまくいかなくても入力には
差し支えないので、失敗は無視する。
"""
import os
import tkinter.font as tkfont
from tkinter import ttk

# 字を入力する部品（Tk の部品の種類の名前）
INPUT_CLASSES = ("TEntry", "TCombobox", "TSpinbox", "Entry", "Spinbox", "Text")

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class LOGFONTW(ctypes.Structure):
        _fields_ = [("lfHeight", wintypes.LONG), ("lfWidth", wintypes.LONG), ("lfEscapement", wintypes.LONG),
                    ("lfOrientation", wintypes.LONG), ("lfWeight", wintypes.LONG), ("lfItalic", wintypes.BYTE),
                    ("lfUnderline", wintypes.BYTE), ("lfStrikeOut", wintypes.BYTE), ("lfCharSet", wintypes.BYTE),
                    ("lfOutPrecision", wintypes.BYTE), ("lfClipPrecision", wintypes.BYTE),
                    ("lfQuality", wintypes.BYTE), ("lfPitchAndFamily", wintypes.BYTE),
                    ("lfFaceName", wintypes.WCHAR * 32)]

    _imm32 = ctypes.windll.imm32
    _user32 = ctypes.windll.user32
    _imm32.ImmGetContext.argtypes = [wintypes.HWND]
    _imm32.ImmGetContext.restype = wintypes.HANDLE
    _imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
    _imm32.ImmSetCompositionFontW.argtypes = [wintypes.HANDLE, ctypes.POINTER(LOGFONTW)]
    _imm32.ImmGetCompositionFontW.argtypes = [wintypes.HANDLE, ctypes.POINTER(LOGFONTW)]
    _user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.GetAncestor.restype = wintypes.HWND
    _user32.GetFocus.restype = wintypes.HWND
    _GA_ROOT = 2
    _DEFAULT_CHARSET = 1


def _windows(widget):
    """IME の文脈を持ちうるウィンドウ（部品自身・入力の場所・いちばん外のウィンドウ）。"""
    hwnd = widget.winfo_id()
    found = [hwnd, _user32.GetFocus(), _user32.GetAncestor(hwnd, _GA_ROOT)]
    return [h for k, h in enumerate(found) if h and h not in found[:k]]


def widget_font(widget):
    """部品の書体 (書体名, 高さの画素) を返す（取れなければ None）。"""
    try:
        name = str(widget.cget("font"))
    except Exception:
        name = ""
    if not name:      # ttk の部品で書体を指定していないとき：その見た目の書体
        try:
            name = str(ttk.Style(widget).lookup(widget.winfo_class(), "font") or "TkTextFont")
        except Exception:
            name = "TkTextFont"
    try:
        actual = tkfont.Font(root=widget, font=name).actual()
        size = int(actual["size"])
        # 正の値はポイント、負の値は画素（Tk の決まり）
        pixels = round(size * widget.winfo_fpixels("1i") / 72) if size > 0 else -size
        return actual["family"], pixels
    except Exception:
        return None


def set_composition_font(widget, family, pixels):
    """widget の IME の入力中の書体を、family・pixels（字の高さの画素）にする。

    合わせられたウィンドウの数を返す（Windows 以外・失敗したときは 0）。
    """
    if os.name != "nt":
        return 0
    try:
        lf = LOGFONTW()
        lf.lfHeight = -pixels
        lf.lfWeight = 400
        lf.lfCharSet = _DEFAULT_CHARSET
        lf.lfFaceName = family[:31]
        done = 0
        for hwnd in _windows(widget):
            himc = _imm32.ImmGetContext(hwnd)
            if not himc:
                continue
            try:
                if _imm32.ImmSetCompositionFontW(himc, ctypes.byref(lf)):
                    done += 1
            finally:
                _imm32.ImmReleaseContext(hwnd, himc)
        return done
    except Exception:
        return 0


def composition_font(widget):
    """確かめるため：widget の IME の入力中の書体 (書体名, 高さ) を返す（取れなければ None）。"""
    if os.name != "nt":
        return None
    for hwnd in _windows(widget):
        himc = _imm32.ImmGetContext(hwnd)
        if not himc:
            continue
        try:
            lf = LOGFONTW()
            if _imm32.ImmGetCompositionFontW(himc, ctypes.byref(lf)):
                return lf.lfFaceName, lf.lfHeight
        finally:
            _imm32.ImmReleaseContext(hwnd, himc)
    return None


def fit(widget):
    """widget が字を入力する部品なら、IME の入力中の書体をその部品の書体にする。合わせたら True。"""
    try:
        if widget.winfo_class() not in INPUT_CLASSES:
            return False
    except Exception:
        return False
    font = widget_font(widget)
    return bool(font) and set_composition_font(widget, *font) > 0


def follow_focus(root):
    """どの画面のどの入力欄に入っても、IME の入力中の書体をその欄の書体にする（Windows だけ）。

    欄ごとに書体が違う（検索の欄は画面の字、入力欄は BIZ UDゴシック）ので、入るたびに合わせ直す。
    入った直後は Windows 側の入力の場所がまだ移っていないことがあるので、手が空いてから合わせる。
    """
    if os.name != "nt":
        return

    def on_focus(event):
        w = event.widget
        if isinstance(w, str):      # メニューなど、Tk の部品の名前で来るもの
            return
        root.after_idle(lambda: fit(w) if w.winfo_exists() else None)

    root.bind_all("<FocusIn>", on_focus, add="+")
