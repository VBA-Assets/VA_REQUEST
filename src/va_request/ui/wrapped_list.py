"""折り返して表示する一覧（何行かの字の欄の例文。2026-11-14 班長指示「折り返して表示に設定。右側にスクロールバーを付ける」）。

Tk の Listbox は1行に1つの項目しか出せず、長い例文が欄の幅で切れる。Text で項目を折り返して並べ、Listbox と同じ
呼び方（insert・delete・curselection・selection_set・see と <<ListboxSelect>>）で使えるようにする。
項目の改行は、そのまま改行して出す。項目の間は少し空け、1つおきに地の色を変えて区切りを見せる。
"""
import tkinter as tk
from tkinter import ttk

from . import theme

BAND = "#f5f5f5"        # 1つおきの項目の地


class WrappedList(ttk.Frame):
    def __init__(self, master, height=8, font=None, width=40):
        super().__init__(master)
        self.items = []
        self._sel = None
        self.text = tk.Text(self, height=height, width=width, wrap="char", font=font, cursor="arrow",
                            relief="solid", borderwidth=1, highlightthickness=0, padx=4, pady=2,
                            background=theme.FIELD_BG, foreground=theme.TEXT, takefocus=False)
        bar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=bar.set, state="disabled")
        self.text.grid(row=0, column=0, sticky="nsew")
        bar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text.tag_configure("band", background=BAND)
        self.text.tag_configure("selected", background=theme.PRESSED_BG)
        self.text.tag_raise("selected")
        self.text.bind("<Button-1>", self._click)
        self.text.bind("<Double-Button-1>", lambda e: self.event_generate("<<ListboxDouble>>"))

    # ---- Listbox と同じ呼び方 ----
    def delete(self, first, last=None):
        self.items = []
        self._sel = None
        self._redraw()

    def insert(self, index, text):
        self.items.append(str(text))
        self._redraw()

    def curselection(self):
        return () if self._sel is None else (self._sel,)

    def selection_set(self, i):
        self._sel = i if 0 <= i < len(self.items) else None
        self._paint_selection()

    def see(self, i):
        ranges = self.text.tag_ranges(f"item{i}")
        if ranges:
            self.text.see(ranges[0])

    # ---- 中 ----
    def _redraw(self):
        t = self.text
        t.configure(state="normal")
        t.delete("1.0", "end")
        for i, s in enumerate(self.items):
            tags = (f"item{i}", "band") if i % 2 else (f"item{i}",)
            t.insert("end", s + ("\n" if i < len(self.items) - 1 else ""), tags)
            t.tag_configure(f"item{i}", spacing1=2, spacing3=3)
        t.configure(state="disabled")
        self._paint_selection()

    def _paint_selection(self):
        t = self.text
        t.tag_remove("selected", "1.0", "end")
        if self._sel is not None:
            ranges = t.tag_ranges(f"item{self._sel}")
            if ranges:
                t.tag_add("selected", ranges[0], ranges[1])

    def _click(self, event):
        index = self.text.index(f"@{event.x},{event.y}")
        for name in self.text.tag_names(index):
            if name.startswith("item"):
                self._sel = int(name[4:])
                self._paint_selection()
                self.event_generate("<<ListboxSelect>>")
                break
        return "break"          # 字を選ぶ動き（なぞり）をさせない
