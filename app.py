"""Tkinter masaüstü GUI: LNG orifis ölçüm noktası tasarım aracı.

Özellikler: seçilebilir/çevrilebilir birimler (SI/US/karışık), satır bazlı sonuç
birimi seçimi, canlı şematik gösterim, aydınlık/karanlık tema ve tercih kalıcılığı.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import units as U
from engine import RunInputs, run_engineering
from report import build_html, print_console_summary
from schematic import draw as draw_schematic
from settings import load as load_settings, save as save_settings
from theme import _style_name, apply as apply_theme, palette
from ui_data import build_catalog, render_row, result_context
from units import default_unit
from updater import APP_VERSION, check_for_updates, download, platform_asset, reveal_in_folder

APP_TITLE = "LNG Orifis Ölçüm Noktası Tasarım Aracı"

BOTAŞ_DEFAULT_COMP = {
    "CH4": 0.915,
    "C2H6": 0.055,
    "C3H8": 0.018,
    "iC4": 0.004,
    "nC4": 0.004,
    "iC5": 0.001,
    "nC5": 0.001,
    "N2": 0.002,
}

COMP_LABELS = {
    "CH4": "CH₄ (Metan)",
    "C2H6": "C₂H₆ (Etan)",
    "C3H8": "C₃H₈ (Propan)",
    "iC4": "i-C₄H₁₀",
    "nC4": "n-C₄H₁₀",
    "iC5": "i-C₅H₁₂",
    "nC5": "n-C₅H₁₂",
    "N2": "N₂ (Azot)",
}

# key, label, kategori, varsayılan değer, tooltip
FIELD_DEFS: list[tuple[str, str, str, str, str]] = [
    ("T1", "Sıcaklık T₁", "temperature", "-163.0",
     "Çalışma sıcaklığı. LNG için ≈ -160 … -150 °C."),
    ("P1", "Emiş basıncı P₁", "pressure", "8.5",
     "Hat emiş basıncı (varsayılan bar-g; gösterge/mutlak seçilebilir)."),
    ("D20", "İç çap D₂₀", "diameter", "300.0", "Boru iç çapı @20°C."),
    ("Qm", "Nominal debi Qm", "flow", "150.0",
     "Nominal debi. Kütle, hacimsel (sıvı) ve enerji birimleri desteklenir;\n"
     "hacimsel/enerji birimleri son hesaplanan yoğunluk/GCV ile çevrilir."),
    ("dP", "Hedef ΔP", "dp", "250.0", "Nominal akıştaki hedeflenen plaka basınç farkı."),
    ("qmin", "Turndown min", "percent", "30", "Minimum debi oranı (%)."),
    ("qmax", "Turndown max", "percent", "120", "Maksimum debi oranı (%)."),
    ("L", "Hat uzunluğu L", "length", "50", "Boru uzunluğu — flashing hesabında sürtünme kaybı içindir."),
    ("OD", "Boru OD", "diameter", "323.9", "Boru dış çapı."),
    ("t", "Et kalınlığı t", "diameter", "9.53", "Et kalınlığı."),
]

ADV_DEFS: list[tuple[str, str, str, str]] = [
    ("uC", "u(C)/C", "0.5", "Deşarj katsayısı belirsizliği (%). R-H/G: 0.5 önerilir."),
    ("uD", "u(D)/D", "0.1", "Boru çapı belirsizliği (%)."),
    ("ud", "u(d)/d", "0.05", "Orifis çapı belirsizliği (%)."),
    ("udP", "u(ΔP)/ΔP", "0.5", "Basınç farkı transmiteri belirsizliği (%)."),
]

FIELD_CATS = {key: cat for key, _, cat, _, _ in FIELD_DEFS}
ADV_CATS = {key: "percent" for key, _, _, _ in ADV_DEFS}
RESULT_CATS = ("pressure", "diameter", "length", "dp", "velocity", "density",
               "heating_value", "energy_flow", "mass_flow", "molar_mass", "flow")


class ToolTip:
    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, _event=None) -> None:
        if self.tip:
            return
        pal = palette()
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + 24
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            background=pal["tip_bg"],
            foreground=pal["tip_fg"],
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 10),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


class ScrollFrame(ttk.Frame):
    """Dikey kaydırılabilir içerik alanı."""

    def __init__(self, master, **kw) -> None:
        super().__init__(master, **kw)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vsb.set)
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfigure(self._win, width=e.width))
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _bind_wheel(self, _e=None) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

    def _unbind_wheel(self, _e=None) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_wheel(self, event) -> None:
        self.canvas.yview_scroll(int(-event.delta / 120), "units")


class App(ttk.Frame):
    def __init__(self, root: tk.Tk) -> None:
        super().__init__(root, padding=8)
        self.root = root
        self.pack(fill="both", expand=True)

        self.cfg = load_settings()
        self.comp_vars: dict[str, tk.StringVar] = {}
        self.field_vars: dict[str, tk.StringVar] = {}
        self.unit_vars: dict[str, tk.StringVar] = {}
        self.output_units: dict[str, tk.StringVar] = {}
        self.result = None
        self._checking = False
        self._redraw_job: str | None = None
        self._prev_unit: dict[tuple[str, str], str] = {}
        self._suppress_convert = False

        self._build_topbar()
        self._build_body()
        self.load_defaults()
        apply_theme(root, self.cfg["theme"])
        self._sync_theme_btn()
        self._draw_schematic()
        self.root.after(1200, lambda: self.check_updates(auto=True))
        self.root.after(900, lambda: threading.Thread(target=self._verify_units_bg, daemon=True).start())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------ üst bar
    def _build_topbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Hesapla", command=self.run_calc).pack(side="left")
        ttk.Button(bar, text="Varsayılanları Yükle", command=self.load_defaults).pack(side="left", padx=6)
        ttk.Button(bar, text="HTML Rapor Dışa Aktar", command=self.export_html).pack(side="left")

        ttk.Label(bar, text="Birim profili:").pack(side="left", padx=(12, 2))
        self._preset_var = tk.StringVar(value=self.cfg["preset"])
        preset = ttk.Combobox(bar, textvariable=self._preset_var, state="readonly", width=8,
                              values=tuple(U.PRESET_NAMES))
        preset.bind("<<ComboboxSelected>>", lambda _e: self._apply_preset(self._preset_var.get()))
        preset.pack(side="left")

        self.theme_btn = ttk.Button(bar, text="🌙 Karanlık", command=self._toggle_theme)
        self.theme_btn.pack(side="left", padx=(12, 0))
        ttk.Button(bar, text="Birimleri Doğrula", command=self.verify_units).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Çıktıyı Temizle", command=self.clear_results).pack(side="left", padx=(6, 0))
        ttk.Button(bar, text="Güncelleme Kontrolü", command=self.check_updates).pack(side="left")

        self.status_lbl = ttk.Label(bar, text="·", style="muted.TLabel")
        self.status_lbl.pack(side="right")
        ttk.Label(bar, text=f"v{APP_VERSION}", style="muted.TLabel").pack(side="right", padx=6)

    # -------------------------------------------------------------------- gövde
    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, width=440)
        left.pack_propagate(False)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        self._build_inputs(left)

        rp = ttk.PanedWindow(right, orient="vertical")
        rp.pack(fill="both", expand=True)
        self.results_scroll = ScrollFrame(rp)
        rp.add(self.results_scroll, weight=3)
        sch = ttk.Frame(rp)
        rp.add(sch, weight=2)
        try:
            rp.paneconfigure(sch, minsize=240)
        except tk.TclError:
            pass
        self.schematic_canvas = tk.Canvas(sch, highlightthickness=0, bg=palette()["bg"])
        self.schematic_canvas.pack(fill="both", expand=True)
        self.schematic_canvas.bind("<Configure>", lambda _e: self._schedule_redraw())
        self.results_inner = self.results_scroll.inner

    def _simple_field(self, frm, row: int, col: int, key: str, label: str, default: str,
                      tip: str) -> None:
        frm.grid_columnconfigure(col * 2, weight=1)
        ttk.Label(frm, text=label).grid(row=row, column=col * 2, sticky="w", padx=(8, 2), pady=2)
        var = tk.StringVar(value=default)
        ent = ttk.Entry(frm, textvariable=var, width=10, justify="right")
        ent.grid(row=row, column=col * 2 + 1, sticky="e", padx=(2, 8), pady=2)
        if tip:
            ToolTip(ent, tip)
            ttk.Label(frm, text="?", style="sec.TLabel", cursor="hand2").grid(
                row=row, column=col * 2 + 2, padx=(0, 2))
        self.field_vars[key] = var

    def _unit_field(self, frm, row: int, col: int, key: str, label: str, cat: str,
                    default: str, tip: str) -> None:
        cell = ttk.Frame(frm)
        cell.grid(row=row, column=col, sticky="ew", padx=6, pady=3)
        cell.columnconfigure(0, weight=1)
        lab = ttk.Label(cell, text=label)
        lab.grid(row=0, column=0, sticky="w")
        if tip:
            ttk.Label(cell, text="?", style="sec.TLabel", cursor="hand2").grid(row=0, column=1)
            ToolTip(lab, tip)

        var = tk.StringVar(value=default)
        ent = ttk.Entry(cell, textvariable=var, width=12, justify="right")
        ent.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        uvar = tk.StringVar(value=default_unit(cat, self.cfg["preset"]))
        combo = ttk.Combobox(cell, textvariable=uvar, state="readonly", width=9,
                             values=U.unit_options(cat))
        combo.grid(row=1, column=1, sticky="e")
        if tip:
            ToolTip(ent, tip)

        self.field_vars[key] = var
        self.unit_vars[key] = uvar
        self._prev_unit[(key, cat)] = uvar.get()
        combo.bind("<<ComboboxSelected>>",
                   lambda _e, k=key, c=cat, v=uvar: self._on_unit_changed(k, c, v))
        uvar.trace_add("write", lambda *_, k=key, c=cat, v=uvar: self._on_unit_var_write(k, c, v))
        var.trace_add("write", lambda *_: self._schedule_redraw())

    def _on_unit_var_write(self, key: str, cat: str, var: tk.StringVar, *_args) -> None:
        new = var.get()
        old = self._prev_unit.get((key, cat))
        self._prev_unit[(key, cat)] = new
        if self._suppress_convert or old is None or old == new:
            return
        try:
            canon = U.to_canonical(self._float(key), old, cat, self._input_ctx())
            self.field_vars[key].set(self._fmt_canonical(canon, cat, new, self._input_ctx()))
        except ValueError:
            pass

    def _on_unit_changed(self, key: str, cat: str, var: tk.StringVar) -> None:
        self._schedule_redraw()
        if self.result is not None:
            self.run_calc(silent=True)

    def _build_inputs(self, left: tk.Widget) -> None:
        comp_frm = ttk.LabelFrame(left, text=" 1. LNG Bileşimi (mol kesri) ")
        comp_frm.pack(fill="x", pady=4)
        for i, comp in enumerate(("CH4", "C2H6", "C3H8", "iC4", "nC4", "iC5", "nC5", "N2")):
            r, c = divmod(i, 2)
            var = tk.StringVar(value="0.000")
            ent = ttk.Entry(comp_frm, textvariable=var, width=10, justify="right")
            ent.grid(row=r, column=c * 2, sticky="ew", padx=(8, 2), pady=2)
            ttk.Label(comp_frm, text=COMP_LABELS[comp]).grid(row=r, column=c * 2 + 1, sticky="w")
            self.comp_vars[comp] = var
            var.trace_add("write", lambda *_: self._update_comp_sum())
        ttk.Label(comp_frm, text="Toplam:").grid(row=4, column=0, sticky="e", pady=(4, 2))
        self.comp_sum_lbl = ttk.Label(comp_frm, text="", style="sec.TLabel")
        self.comp_sum_lbl.grid(row=4, column=1, columnspan=2, sticky="w")

        proc_frm = ttk.LabelFrame(left, text=" 2. Proses Şartları ")
        proc_frm.pack(fill="x", pady=4)
        proc_frm.columnconfigure(0, weight=1)
        proc_frm.columnconfigure(1, weight=1)
        self._unit_field(proc_frm, 0, 0, "T1", "Sıcaklık T₁", "temperature", "-163.0",
                         "Çalışma sıcaklığı. LNG için ≈ -160 … -150 °C.")
        self._unit_field(proc_frm, 0, 1, "P1", "Emiş basıncı P₁", "pressure", "8.5",
                         "Hat emiş basıncı (varsayılan bar-g; gösterge/mutlak seçilebilir).")

        pipe_frm = ttk.LabelFrame(left, text=" 3. Boru ve Akış ")
        pipe_frm.pack(fill="x", pady=4)
        pipe_frm.columnconfigure(0, weight=1)
        pipe_frm.columnconfigure(1, weight=1)
        self._unit_field(pipe_frm, 0, 0, "D20", "İç çap D₂₀", "diameter", "300.0",
                         "Boru iç çapı @20°C.")
        self._unit_field(pipe_frm, 0, 1, "Qm", "Nominal debi Qm", "flow", "150.0",
                         "Nominal debi. Kütle, hacimsel (sıvı) ve enerji birimleri desteklenir;\n"
                         "hacimsel/enerji birimleri son hesaplanan yoğunluk/GCV ile çevrilir.")
        self._unit_field(pipe_frm, 1, 0, "dP", "Hedef ΔP", "dp", "250.0",
                         "Nominal akıştaki hedeflenen plaka basınç farkı.")
        self._simple_field(pipe_frm, 1, 1, "qmin", "Turndown min (%)", "30",
                           "Minimum debi oranı (%).")
        self._simple_field(pipe_frm, 2, 0, "qmax", "Turndown max (%)", "120",
                           "Maksimum debi oranı (%).")
        self._unit_field(pipe_frm, 2, 1, "L", "Hat uzunluğu L", "length", "50",
                         "Boru uzunluğu — flashing hesabında sürtünme kaybı içindir.")

        mat_frm = ttk.Frame(pipe_frm)
        mat_frm.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        ttk.Label(mat_frm, text="Malzeme").pack(side="left")
        self.mat_var = tk.StringVar(value="AISI 304")
        mat_combo = ttk.Combobox(mat_frm, textvariable=self.mat_var, state="readonly", width=9,
                                 values=("AISI 304", "AISI 316"))
        mat_combo.pack(side="left", padx=6)
        ttk.Label(mat_frm, text="Boru OD").pack(side="left", padx=(10, 2))
        odvar = tk.StringVar(value="323.9")
        ttk.Entry(mat_frm, textvariable=odvar, width=7, justify="right").pack(side="left")
        odunit = tk.StringVar(value="mm")
        odcombo = ttk.Combobox(mat_frm, textvariable=odunit, state="readonly", width=4,
                               values=("mm", "in"))
        odcombo.pack(side="left", padx=(2, 0))
        ttk.Label(mat_frm, text="t:").pack(side="left", padx=(6, 2))
        tvar = tk.StringVar(value="9.53")
        ttk.Entry(mat_frm, textvariable=tvar, width=6, justify="right").pack(side="left")
        tunit = tk.StringVar(value="mm")
        tcombo = ttk.Combobox(mat_frm, textvariable=tunit, state="readonly", width=4,
                              values=("mm", "in"))
        tcombo.pack(side="left", padx=(2, 0))
        self.field_vars["OD"] = odvar
        self.field_vars["t"] = tvar
        self.unit_vars["OD"] = odunit
        self.unit_vars["t"] = tunit
        self._prev_unit[("OD", "diameter")] = "mm"
        self._prev_unit[("t", "diameter")] = "mm"
        odcombo.bind("<<ComboboxSelected>>", lambda _e: self._on_unit_changed("OD", "diameter", odunit))
        tcombo.bind("<<ComboboxSelected>>", lambda _e: self._on_unit_changed("t", "diameter", tunit))
        odunit.trace_add("write", lambda *_: self._on_unit_var_write("OD", "diameter", odunit))
        tunit.trace_add("write", lambda *_: self._on_unit_var_write("t", "diameter", tunit))

        adv_frm = ttk.LabelFrame(left, text=" 4. Gelişmiş (belirsizlik girdileri) ")
        adv_frm.pack(fill="x", pady=4)
        adv_frm.columnconfigure(0, weight=1)
        adv_frm.columnconfigure(1, weight=1)
        for i, (key, label, default, tip) in enumerate(ADV_DEFS):
            r, c = divmod(i, 2)
            self._simple_field(adv_frm, r, c, key, label + " (%)", default, tip)

    # ------------------------------------------------------------ girdi/birimler
    def _input_ctx(self) -> dict:
        if self.result is not None:
            e = self.result.energy
            return {
                "rho_kgm3": self.result.sizing.rho,
                "gcv_mj_kg": e.GCV_mj_kg if e else None,
                "M_mix_kg_kmol": self.result.thermo.M_mix,
            }
        return {}

    def _float(self, key: str) -> float:
        try:
            return float(self.field_vars[key].get().replace(",", "."))
        except ValueError:
            raise ValueError(f"'{key}' sayısal değil: {self.field_vars[key].get()!r}")

    def _fmt_canonical(self, value: float, cat: str, unit: str, ctx: dict | None = None) -> str:
        disp = U.from_canonical(value, unit, cat, ctx) if cat != "number" else value
        if disp is None or disp != disp or abs(disp) > 1e12:
            return "0"
        return f"{disp:.6g}"

    def _canonical(self, key: str) -> float:
        cat = FIELD_CATS.get(key) or ADV_CATS.get(key)
        if cat == "percent":
            return float(self.field_vars[key].get().replace(",", ".")) / 100.0
        return U.to_canonical(self._float(key), self.unit_vars[key].get(), cat, self._input_ctx())

    def collect_inputs(self) -> RunInputs:
        comp = {c: float(v.get() or 0.0) for c, v in self.comp_vars.items()}
        material = self.mat_var.get()
        S_mpa = 138.0
        p1_bara = self._canonical("P1")
        return RunInputs(
            comp=comp,
            T1_C=self._canonical("T1"),
            P1_barg=p1_bara - 1.01325,
            D20_mm=self._canonical("D20"),
            qm_nom_ton_h=self._canonical("Qm"),
            dP_target_mbar=self._canonical("dP"),
            q_min_ratio=self._canonical("qmin"),
            q_max_ratio=self._canonical("qmax"),
            L_pipe_m=self._canonical("L"),
            Do_mm=self._canonical("OD"),
            t_actual_mm=self._canonical("t"),
            material=material,
            S_mpa=S_mpa,
            uC_C=self._canonical("uC"),
            uD_D=self._canonical("uD"),
            ud_d=self._canonical("ud"),
            udP_dP=self._canonical("udP"),
        )

    def _validate(self, inp: RunInputs) -> None:
        if not -180.0 <= inp.T1_C <= 100.0:
            raise ValueError(f"Sıcaklık {inp.T1_C:.1f} °C fiziksel aralığın (-180…100 °C) dışında.")
        if inp.P1_barg < 0.0:
            raise ValueError(f"Emiş basıncı negatif olamaz: {inp.P1_barg:.3f} bar-g.")
        for name, val in (("Boru çapı D₂₀", inp.D20_mm), ("Nominal debi", inp.qm_nom_ton_h),
                          ("Hedef ΔP", inp.dP_target_mbar)):
            if val <= 0.0:
                raise ValueError(f"{name} pozitif olmalı: {val:.3f}.")
        if inp.q_min_ratio >= inp.q_max_ratio:
            raise ValueError("Turndown min, max'tan küçük olmalı.")
        if inp.q_max_ratio <= 0.0:
            raise ValueError("Turndown max pozitif olmalı.")

    def run_calc(self, silent: bool = False) -> None:
        try:
            inp = self.collect_inputs()
            self._validate(inp)
        except ValueError as e:
            if not silent:
                messagebox.showerror("Girdi Hatası", str(e))
            return
        try:
            self.result = run_engineering(inp)
        except Exception as e:  # noqa: BLE001
            if not silent:
                messagebox.showerror("Hesaplama Hatası", str(e))
            return
        self._populate_results(self.result)
        self._update_status(self.result)
        self._draw_schematic()
        print_console_summary(self.result)

    # ------------------------------------------------------------------- sonuçlar
    def _populate_results(self, r) -> None:
        for w in self.results_inner.winfo_children():
            w.destroy()
        ctx = result_context(r)
        for title, rows in build_catalog(r):
            lf = ttk.LabelFrame(self.results_inner, text=title)
            lf.pack(fill="x", pady=4, padx=2)
            lf.columnconfigure(1, weight=1)
            for i, row in enumerate(rows):
                ttk.Label(lf, text=row.label, style="muted.TLabel").grid(
                    row=i, column=0, sticky="w", padx=(8, 6), pady=1)
                val = ttk.Label(lf, style=_style_name(row.tag))
                val.grid(row=i, column=1, sticky="e", padx=(6, 2))
                if row.category and row.category != "number" and len(U.unit_options(row.category)) > 1:
                    unit = (row.default_unit
                            or self.output_units.get(row.category, tk.StringVar()).get()
                            or default_unit(row.category, self.cfg["preset"]))
                    uvar = tk.StringVar(value=unit)
                    combo = ttk.Combobox(lf, textvariable=uvar, state="readonly", width=9,
                                         values=U.unit_options(row.category))
                    combo.grid(row=i, column=2, padx=(2, 8), pady=1)
                    combo.bind("<<ComboboxSelected>>",
                               lambda _e, rw=row, v=val, uv=uvar: self._on_result_unit(rw, v, uv, ctx))
                else:
                    ttk.Label(lf, text="", width=9).grid(row=i, column=2)
                val.config(text=render_row(row, row.default_unit or
                                           self._output_unit(row.category), ctx))

    def _output_unit(self, category: str) -> str:
        var = self.output_units.get(category)
        if var is not None:
            return var.get()
        return default_unit(category, self.cfg["preset"])

    def _on_result_unit(self, row, value_lbl: ttk.Label, var: tk.StringVar, ctx: dict) -> None:
        cat = row.category
        self.output_units.setdefault(cat, tk.StringVar()).set(var.get())
        value_lbl.config(text=render_row(row, var.get(), ctx))
        self._save_cfg()
        self._draw_schematic()

    def _update_status(self, r) -> None:
        sf = r.safety.phase
        if sf.flashing:
            self.status_lbl.config(text="KRİTİK: FLASHING", style="bad.TLabel")
        elif sf.cavitation:
            self.status_lbl.config(text="UYARI: KAVİTASYON", style="warn.TLabel")
        else:
            self.status_lbl.config(text="GÜVENLİ", style="good.TLabel")

    def _clear_results_widgets(self) -> None:
        for w in self.results_inner.winfo_children():
            w.destroy()

    # -------------------------------------------------------------------- şema
    def _schedule_redraw(self) -> None:
        if self._redraw_job is not None:
            self.root.after_cancel(self._redraw_job)
        self._redraw_job = self.root.after(120, self._draw_schematic)

    def _draw_schematic(self) -> None:
        self._redraw_job = None
        um = {}
        for key, cat in FIELD_CATS.items():
            if cat == "percent":
                continue
            v = self.unit_vars.get(key)
            um[cat] = v.get() if v else default_unit(cat, self.cfg["preset"])
        for cat in RESULT_CATS:
            um[cat] = self._output_unit(cat)
        inp = None
        try:
            inp = self.collect_inputs()
        except ValueError:
            inp = None
        draw_schematic(self.schematic_canvas, inp, self.result, palette(), um)

    # -------------------------------------------------------------------- tema
    def _toggle_theme(self) -> None:
        mode = "dark" if palette()["name"] == "light" else "light"
        self.cfg["theme"] = mode
        apply_theme(self.root, mode)
        self._sync_theme_btn()
        self._draw_schematic()
        self._save_cfg()

    def _sync_theme_btn(self) -> None:
        dark = palette()["name"] == "dark"
        self.theme_btn.config(text="☀ Aydınlık" if dark else "🌙 Karanlık")

    # ------------------------------------------------------------------- profil
    def _apply_preset(self, name: str, convert: bool = True) -> None:
        ctx = self._input_ctx()
        self._suppress_convert = True
        try:
            for key, cat in FIELD_CATS.items():
                if cat == "percent":
                    continue
                new = default_unit(cat, name)
                if convert:
                    cur = self.unit_vars.get(key)
                    cur_u = cur.get() if cur else new
                    if cur_u != new:
                        try:
                            canon = U.to_canonical(self._float(key), cur_u, cat, ctx)
                            self.field_vars[key].set(self._fmt_canonical(canon, cat, new, ctx))
                        except ValueError:
                            pass
                self.unit_vars[key].set(new)
                self._prev_unit[(key, cat)] = new
        finally:
            self._suppress_convert = False
        self.cfg["preset"] = name
        for cat in RESULT_CATS:
            self.output_units.setdefault(cat, tk.StringVar()).set(default_unit(cat, name))
        self._save_cfg()
        self._draw_schematic()
        if self.result is not None:
            self._populate_results(self.result)

    # ----------------------------------------------------------------- varsayılan
    def load_defaults(self) -> None:
        for c, v in self.comp_vars.items():
            v.set(f"{BOTAŞ_DEFAULT_COMP[c]:.4f}")
        self._suppress_convert = True
        try:
            for key, label, cat, default, tip in FIELD_DEFS:
                self.field_vars[key].set(default)
                if cat != "percent":
                    self.unit_vars[key].set(default_unit(cat, self.cfg["preset"]))
                    self._prev_unit[(key, cat)] = default_unit(cat, self.cfg["preset"])
            for key, label, default, tip in ADV_DEFS:
                self.field_vars[key].set(default)
            self.field_vars["OD"].set("323.9")
            self.field_vars["t"].set("9.53")
            self.unit_vars["OD"].set("mm")
            self.unit_vars["t"].set("mm")
            self._prev_unit[("OD", "diameter")] = "mm"
            self._prev_unit[("t", "diameter")] = "mm"
        finally:
            self._suppress_convert = False
        self.mat_var.set("AISI 304")
        self._update_comp_sum()
        self._clear_results_widgets()
        self.status_lbl.config(text="·", style="muted.TLabel")
        self.result = None

    def clear_results(self) -> None:
        self._clear_results_widgets()
        self.status_lbl.config(text="·", style="muted.TLabel")
        self.result = None
        self._draw_schematic()

    def _update_comp_sum(self) -> None:
        try:
            total = sum(float(v.get() or 0.0) for v in self.comp_vars.values())
        except ValueError:
            self.comp_sum_lbl.config(text="Hatalı girdi", style="bad.TLabel")
            return
        ok = abs(total - 1.0) < 1e-3
        style = "good.TLabel" if ok else "warn.TLabel"
        self.comp_sum_lbl.config(text=f"{total:.4f}" + ("  ✓" if ok else "  (norm.)"), style=style)

    # ----------------------------------------------------------------- rapor
    def export_html(self) -> None:
        if self.result is None:
            messagebox.showinfo("Bilgi", "Önce hesaplama çalıştırın.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML", "*.html"), ("Tüm dosyalar", "*.*")],
            initialfile="lng_orifice_rapor.html",
        )
        if not path:
            return
        html = build_html(self.result, title=APP_TITLE)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(html)
        messagebox.showinfo("Rapor", f"Rapor kaydedildi:\n{path}")

    # ---------------------------------------------------------------- doğrulama
    def verify_units(self) -> None:
        threading.Thread(target=self._verify_units_bg, args=(False,), daemon=True).start()

    def _verify_units_bg(self, auto: bool = True) -> None:
        errs = U.verify_conversions()
        if not errs:
            self.root.after(0, lambda: self.status_lbl.config(
                text="Birimler ✓", style="good.TLabel"))
            if not auto:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Birim Doğrulama", "Tüm birim dönüşümleri başarıyla doğrulandı."))
            return
        msg = "\n".join(errs[:8])
        self.root.after(0, lambda: messagebox.showwarning(
            "Birim Doğrulama Hatası", f"{len(errs)} dönüşüm sorunu:\n\n{msg}"))

    # --------------------------------------------------------------- güncelleme
    def check_updates(self, auto: bool = False) -> None:
        if self._checking:
            return
        self._checking = True

        def worker() -> None:
            info = check_for_updates()
            self.root.after(0, lambda: self._on_check_done(info, auto))

        threading.Thread(target=worker, daemon=True).start()

    def _on_check_done(self, info, auto: bool) -> None:
        self._checking = False
        if info.error:
            if not auto:
                messagebox.showwarning("Güncelleme Kontrolü",
                                       f"Sürüm kontrolü yapılamadı.\n\n{info.error}")
            return
        if not info.has_update:
            if not auto:
                messagebox.showinfo("Güncelleme Kontrolü",
                                    f"Program güncel: v{info.current_version}")
            return
        if not messagebox.askyesno(
            "Yeni Sürüm",
            f"Yeni sürüm v{info.latest_version} mevcut!\n"
            f"Şu anki sürümünüz: v{info.current_version}\n\n"
            f"İndirilip klasörde açılsın mı?\nSatır: {info.release_url}",
        ):
            return
        self._download_latest(info)

    def _download_latest(self, info) -> None:
        name_url = platform_asset(info.assets)
        if name_url is None:
            messagebox.showinfo("İndirme",
                                f"Bu platform için indirilebilir dosya bulunamadı.\n"
                                f"Sayfadan elle indirebilirsiniz:\n{info.release_url}")
            return
        name, url = name_url

        def worker() -> None:
            try:
                path = download(url, filename=name)
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda err=e: messagebox.showerror("İndirme Hatası", str(err)))
                return
            reveal_in_folder(path)
            self.root.after(0, lambda p=path: messagebox.showinfo(
                "İndirme Tamam",
                f"v{info.latest_version} indirildi:\n{p}\n\n"
                f"Dosyayı açıp LNG-Orifice-Meter uygulamasını çalıştırın.",
            ))

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ ayarlar
    def _save_cfg(self) -> None:
        self.cfg["input_units"] = {k: v.get() for k, v in self.unit_vars.items()}
        self.cfg["output_units"] = {c: v.get() for c, v in self.output_units.items()}
        self.cfg["preset"] = self._preset_var.get() if hasattr(self, "_preset_var") else self.cfg["preset"]
        self.cfg["theme"] = palette()["name"]
        save_settings(self.cfg)

    def _on_close(self) -> None:
        self._save_cfg()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    root.title(f"{APP_TITLE} — {APP_VERSION}")
    root.geometry("1220x860")
    root.minsize(1040, 720)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
