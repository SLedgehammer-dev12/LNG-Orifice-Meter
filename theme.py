"""Aydınlık/karanlık tema yönetimi.

- `PALETTES` ve `apply(root, mode)`: ttk Style (clam tabanı) + tk katmanını tek
  seferde renklendirir. Sonuç/şema bileşenleri stil adlarına (good/warn/bad/emph)
  bağlanır; tema değişince otomatik güncellenirler.
- `CURRENT`: çalışma anı paleti (ToolTip, şema çizimi, durum çubuğu okur).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

LIGHT = {
    "name": "light",
    "bg": "#eef2f7",
    "surface": "#ffffff",
    "surface_alt": "#f0f3f8",
    "border": "#c9d4e0",
    "text": "#1c2733",
    "text_muted": "#5a6b7a",
    "accent": "#0b6ea8",
    "accent_active": "#095a8a",
    "button_bg": "#e6ecf3",
    "button_active": "#d3dce7",
    "button_fg": "#1c2733",
    "entry_bg": "#ffffff",
    "entry_fg": "#1c2733",
    "success": "#0a6b2e",
    "warn": "#856404",
    "error": "#a02b2b",
    "grid": "#c9d4e0",
    "pipe": "#b9c8d8",
    "pipe_fill": "#dce6ef",
    "flow": "#0b6ea8",
    "plate": "#7a8ea3",
    "dimension": "#5a6b7a",
    "flow_inner": "#ffffff",
    "tip_bg": "#ffffe0",
    "tip_fg": "#333333",
}

DARK = {
    "name": "dark",
    "bg": "#161b22",
    "surface": "#1e2530",
    "surface_alt": "#232c3a",
    "border": "#374152",
    "text": "#e6edf3",
    "text_muted": "#9aa7b5",
    "accent": "#58a6ff",
    "accent_active": "#6fb6ff",
    "button_bg": "#2d3744",
    "button_active": "#3a4656",
    "button_fg": "#e6edf3",
    "entry_bg": "#0d1117",
    "entry_fg": "#e6edf3",
    "success": "#4ade80",
    "warn": "#f5c542",
    "error": "#ff7b72",
    "grid": "#374152",
    "pipe": "#3d4d61",
    "pipe_fill": "#28333f",
    "flow": "#58a6ff",
    "plate": "#6e849b",
    "dimension": "#9aa7b5",
    "flow_inner": "#0d1117",
    "tip_bg": "#2d3744",
    "tip_fg": "#e6edf3",
}

PALETTES: dict[str, dict[str, str]] = {"light": LIGHT, "dark": DARK}

CURRENT: dict[str, str] = LIGHT


def palette(mode: str | None = None) -> dict[str, str]:
    if mode is None:
        return CURRENT
    return PALETTES.get(mode, LIGHT)


def _style_name(tag: str) -> str:
    return {
        "good": "good.TLabel",
        "warn": "warn.TLabel",
        "bad": "bad.TLabel",
        "emph": "emph.TLabel",
        "muted": "muted.TLabel",
    }.get(tag, "TLabel")


def apply(root: tk.Tk, mode: str) -> None:
    global CURRENT
    pal = PALETTES.get(mode, LIGHT)
    CURRENT = pal

    st = ttk.Style(root)
    try:
        st.theme_use("clam")
    except tk.TclError:
        pass

    st.configure("TFrame", background=pal["surface"])
    st.configure("TLabel", background=pal["surface"], foreground=pal["text"])
    st.configure("TLabelframe", background=pal["surface"], bordercolor=pal["border"],
                 foreground=pal["accent"], lightcolor=pal["border"], darkcolor=pal["border"])
    st.configure("TLabelframe.Label", background=pal["surface"], foreground=pal["accent"])
    st.configure("TButton", background=pal["button_bg"], foreground=pal["button_fg"],
                 bordercolor=pal["border"], lightcolor=pal["border"], darkcolor=pal["border"],
                 padding=(8, 3))
    st.map("TButton",
           background=[("active", pal["button_active"]), ("pressed", pal["button_active"]),
                       ("disabled", pal["button_bg"])],
           foreground=[("disabled", pal["text_muted"])])
    st.configure("TEntry", fieldbackground=pal["entry_bg"], foreground=pal["entry_fg"],
                 bordercolor=pal["border"], lightcolor=pal["border"], darkcolor=pal["border"],
                 insertcolor=pal["text"], selectbackground=pal["accent"], selectforeground="#ffffff")
    st.configure("TCombobox", fieldbackground=pal["entry_bg"], background=pal["entry_bg"],
                 foreground=pal["entry_fg"], arrowcolor=pal["text"], bordercolor=pal["border"],
                 lightcolor=pal["border"], darkcolor=pal["border"])
    st.map("TCombobox",
           fieldbackground=[("readonly", pal["entry_bg"])],
           foreground=[("readonly", pal["entry_fg"])],
           selectbackground=[("readonly", pal["entry_bg"])],
           selectforeground=[("readonly", pal["entry_fg"])])
    st.configure("Vertical.TScrollbar", background=pal["button_bg"], troughcolor=pal["surface_alt"],
                 bordercolor=pal["border"], arrowcolor=pal["text"], relief="flat")
    st.configure("Horizontal.TScrollbar", background=pal["button_bg"], troughcolor=pal["surface_alt"],
                 bordercolor=pal["border"], arrowcolor=pal["text"], relief="flat")
    st.configure("TPanedwindow", background=pal["bg"])

    st.configure("good.TLabel", background=pal["surface"], foreground=pal["success"])
    st.configure("warn.TLabel", background=pal["surface"], foreground=pal["warn"])
    st.configure("bad.TLabel", background=pal["surface"], foreground=pal["error"])
    st.configure("muted.TLabel", background=pal["surface"], foreground=pal["text_muted"])
    st.configure("emph.TLabel", background=pal["surface"], foreground=pal["text"])
    st.configure("hdr.TLabel", background=pal["surface"], foreground=pal["text"])
    st.configure("sec.TLabel", background=pal["surface"], foreground=pal["accent"])
    st.configure("hint.TLabel", background=pal["surface"], foreground=pal["text_muted"],
                 font=("TkDefaultFont", 8))

    root.configure(bg=pal["bg"])
    try:
        root.option_add("*TCombobox*Listbox*Background", pal["entry_bg"])
        root.option_add("*TCombobox*Listbox*Foreground", pal["entry_fg"])
        root.option_add("*TCombobox*Listbox*selectBackground", pal["accent"])
        root.option_add("*TCombobox*Listbox*selectForeground", "#ffffff")
    except tk.TclError:
        pass
