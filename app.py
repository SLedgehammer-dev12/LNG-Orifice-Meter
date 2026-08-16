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
    ("OD", "Boru Dış Çapı OD", "diameter", "323.85",
     "Boru nominal dış çapı (ASME B36.19M / B36.10M)."),
    ("t", "Boru Et Kalınlığı t", "diameter", "9.53",
     "Boru et kalınlığı. İç çap D₂₀ = OD - 2×t olarak otomatik hesaplanır."),
    ("Qm", "Nominal debi Qm", "flow", "150.0",
     "Nominal debi. Kütle, hacimsel (sıvı) ve enerji birimleri desteklenir;\n"
     "hacimsel/enerji birimleri son hesaplanan yoğunluk/GCV ile çevrilir."),
    ("dP", "Hedef ΔP", "dp", "250.0", "Nominal akıştaki hedeflenen plaka basınç farkı."),
    ("qmin", "Turndown min", "percent", "30", "Minimum debi oranı (%)."),
    ("qmax", "Turndown max", "percent", "120", "Maksimum debi oranı (%)."),
    ("L", "Hat uzunluğu L", "length", "50", "Boru uzunluğu — flashing hesabında sürtünme kaybı içindir."),
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
               "heating_value", "energy_flow", "power", "mass_flow", "molar_mass", "flow")


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
        self._build_menu()
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

    # -------------------------------------------------------------------- menü
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Hakkında", command=self.show_about)
        help_menu.add_separator()
        help_menu.add_command(label="Birimleri Doğrula", command=self.verify_units)
        help_menu.add_command(label="Güncelleme Kontrolü", command=self.check_updates)
        menubar.add_cascade(label="Yardım", menu=help_menu)
        self.root.config(menu=menubar)

    def show_about(self) -> None:
        pal = palette()
        win = tk.Toplevel(self.root)
        win.title("Hakkında — LNG Orifis Ölçüm Noktası")
        win.geometry("660x580")
        win.minsize(500, 400)

        frame = ttk.Frame(win)
        frame.pack(fill="both", expand=True, padx=10, pady=(10, 6))

        text = tk.Text(frame, wrap="word", height=30,
                       bg=pal["surface"], fg=pal["text"], relief="flat",
                       borderwidth=0, padx=14, pady=10,
                       insertbackground=pal["text"], font=("TkDefaultFont", 10))
        vsb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vsb.set)
        text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        text.tag_configure("title", font=("TkDefaultFont", 13, "bold"),
                           foreground=pal["accent"], spacing3=2)
        text.tag_configure("sub", foreground=pal["text_muted"], spacing3=10)
        text.tag_configure("hdr", font=("TkDefaultFont", 11, "bold"),
                           foreground=pal["text"], spacing1=12, spacing3=2)
        text.tag_configure("body", spacing1=1, spacing3=1)
        text.tag_configure("bullet", lmargin1=20, lmargin2=34, spacing1=1)
        text.tag_configure("note", foreground=pal["text_muted"], lmargin1=20, lmargin2=34)
        text.tag_configure("warn", foreground=pal["warn"])

        about: list[tuple[str, str]] = [
            ("title", f"LNG Orifis Ölçüm Noktası Tasarım Aracı"),
            ("sub", f"\nSürüm {APP_VERSION} · kriyojenik LNG hatları için ISO 5167-2 tabanlı "
                    "ön boyutlandırma\n"),

            ("hdr", "Amaç\n"),
            ("body", "Araç; sıvı fazda (kriyojenik) LNG hatlarında orifis ölçüm noktasının "
                     "ön boyutlandırmasını ve emniyet değerlendirmesini yapar. Bileşimi, "
                     "çalışma şartlarını ve hedef basınç farkını girerek; deşarj katsayısını, "
                     "oranları (β, d/D), orifis çapını, debi belirsizliğini, faz ayrışması "
                     "(flashing/kavitasyon) riskini, ASME B31.3 et kalınlığı denetimini ve "
                     "ısıl değer/enerji akışını çıktı olarak verir.\n"),

            ("hdr", "Hesaplama Yöntemleri\n"),
            ("bullet", "Termofiziksel özellikler (Peng-Robinson EOS):\n"),
            ("body", "    Bileşim mol kesirlerinden ortalama molar kütle (M_mix) hesaplanır. "
                     "Peng-Robinson durum denklemi ile zengin faz (bubble point) buhar basıncı "
                     "Pv, fugacity eşitliğiyle iteratif olarak çözülür; bu, flashing "
                     "güvenlik payının temeli Pv değeridir.\n"),
            ("bullet", "Antoine / Raoult karşılaştırması:\n"),
            ("body", "    İkincil doymuş sıvı buhar basıncı modeli (Antoine + Raoult). Düşük "
                     "sıcaklıklarda (-163 °C) ekstrapolasyon içerdiği için birincil sonuç "
                     "Peng-Robinson'dur; fark rapor ve konsol özetinde gösterilir.\n"),
            ("bullet", "Sıvı yoğunluğu (Revised Klosek-Zander):\n"),
            ("body", "    Kriyojenik LNG karışımlarına uygun Klosek-Zander korelasyonu işletme "
                     "yoğunluğunu verir; debi, hız ve hacimsel çevrimler bu yoğunluğu kullanır.\n"),
            ("bullet", "Orifis boyutlandırma (ISO 5167-2):\n"),
            ("body", "    Tam Reader-Harris/Gallagher deşarj katsayısı C (flange taps; "
                     "β, Re_D ve D'ye bağlı) kullanılır. D₂₀, sıcaklıkla termal genleşme "
                     "(α₁K) ile işletme çapına taşınır. Kütle debisi eşitliği, Newton-Raphson "
                     "ile β çözümü yapılarak orifis çapı d = β·D bulunur; Reynolds sayısı "
                     "(Re_D) her iterasyonda güncellenir. β geçerlilik aralığı (ISO 5167-2 "
                     "sınırları) denetlenir ve aşım durumunda uyarılır.\n"),
            ("bullet", "Basınç farkı — debi ilişkisi:\n"),
            ("body", "    ΔP ∝ q² mantığıyla q_min ve q_max oranlarındaki fark basınçları "
                     "hesaplanır; hedeflenen ΔP ve seçilen plaka bu aralığı karşılar.\n"),
            ("bullet", "Debi belirsizliği (ISO 5167):\n"),
            ("body", "    Deşarj katsayısı (u(C)/C), boru çapı (u(D)/D), orifis çapı (u(d)/d) "
                     "ve fark basınç (u(ΔP)/ΔP) belirsizlikleri, kısmi türev yaklaşımıyla "
                     "bileşik debi belirsizliğine (u(q)/q) birleştirilir.\n"),
            ("bullet", "Emniyet denetimleri:\n"),
            ("body", "    Plaka sonrası toplam basınç (P₁ − ΔP − boru sürtünme kaybı; Haaland "
                     "faktörü) buhar basıncının (Pv) altına düşerse FLASHING/KAVİTASYON uyarısı. "
                     "ASME B31.3 ile minimum gereken et kalınlığı (P·D/(2(S·E + P·Y)) + c) "
                     "hesaplanıp girilen et kalınlığıyla karşılaştırılır.\n"),
            ("bullet", "Isıl değer ve enerji akışı:\n"),
            ("body", "    Bileşen molar yanma ısılarından (MJ/kmol, 25 °C / 1 atm) karışımın "
                     "üst (GCV/HHV) ve alt (NCV/LHV) ısıl değeri; MJ/kg, MJ/kmol ve MJ/Nm³ "
                     "türevleriyle hesaplanır. Kütle debisi × GCV ile termal güç (MW) verilir.\n"),
            ("bullet", "N₂ duyarlılık analizi:\n"),
            ("body", "    Azot içeriği 0–2× aralığında taranır; Pv, yoğunluk ve emniyet payının "
                     "değişimi raporlanır.\n"),

            ("hdr", "Birim Sistemi\n"),
            ("body", "Motor her zaman kanonik birimlerde çalışır (sıcaklık °C, basınç bar-a, çap "
                     "mm, kütle debisi t/h, ΔP mbar, yoğunluk kg/m³, hız m/s, ısıl değer MJ/kg, "
                     "enerji akışı MW). Arayüzde her girdi ve sonuç satırı için birim bağımsız "
                     "seçilebilir; hacimsel debi (m³/h, L/min, gpm…) ve enerji debisi (MW, "
                     "MMBtu/h) son hesaplanan yoğunluk/GCV kullanılarak çevrilir. 'Birimleri "
                     "Doğrula' tüm dönüşümleri round-trip ve referans sabitleriyle kontrol eder.\n"),

            ("hdr", "Kullanım\n"),
            ("bullet", "Sol paneldeki girdileri doldurun → 'Hesapla' (veya ilgili kutuda Enter).\n"),
            ("bullet", "Birim profilini değiştirmek ('SI / US / Karışık') tüm değerleri fiziksel "
                       "değeri koruyarak çevirir.\n"),
            ("bullet", "Sonuçlar satır bazlı birim seçimine açıktır; sağ alttaki şematik gösterim "
                       "canlı güncellenir.\n"),
            ("bullet", "'HTML Rapor Dışa Aktar' aydınlık şema dahil tam rapor; komut satırında "
                       "--json ile makine-okunur çıktı alınabilir.\n"),

            ("hdr", "Uyarı\n"),
            ("warn", "Bu araç ön tasarım ve fizibilite amaçlıdır. Resmî ölçüm noktası; "
                     "kalibrasyon, montaj, yasal metroloji onayı ve sahaya özel düz "
                     "boru/bağlantı değerlendirmesi gerektirir."),
        ]

        text.insert("1.0", "")
        for tag, content in about:
            text.insert("end", content, tag)
        text.configure(state="disabled")

        ttk.Button(win, text="Kapat", command=win.destroy).pack(pady=(0, 10))

    # -------------------------------------------------------------------- gövde
    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, width=440)
        left.pack_propagate(False)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        self.inputs_scroll = ScrollFrame(left)
        self.inputs_scroll.pack(fill="both", expand=True)
        self._build_inputs(self.inputs_scroll.inner)

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

    def _field_cell(self, frm, row: int, col: int, key: str, label: str, default: str,
                    tip: str, cat: str | None = None, suffix: str | None = None,
                    desc: str | None = None) -> None:
        """Hücre tabanlı girdi alanı: üstte etiket (+?), ortada giriş + birim/sonek,
        altta kısa açıklama metni (desc) — kalıcı ve görünür.

        - `cat` verildiğinde birim seçici (combobox) eklenir.
        - `suffix` verildiğinde (örn. "%") birim yerine sabit sonek gösterilir.
        """
        cell = ttk.Frame(frm)
        cell.grid(row=row, column=col, sticky="ew", padx=6, pady=3)
        cell.columnconfigure(0, weight=1)

        lab = ttk.Label(cell, text=label)
        lab.grid(row=0, column=0, sticky="w")
        if tip:
            ToolTip(lab, tip)
            mark = ttk.Label(cell, text="?", style="sec.TLabel", cursor="hand2")
            mark.grid(row=0, column=1, padx=(0, 2))
            ToolTip(mark, tip)

        var = tk.StringVar(value=default)
        ent = ttk.Entry(cell, textvariable=var, width=12, justify="right")
        ent.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ent.bind("<Return>", lambda _e: self.run_calc())
        if tip:
            ToolTip(ent, tip)

        if suffix:
            ttk.Label(cell, text=suffix).grid(row=1, column=1, sticky="w")
        else:
            uvar = tk.StringVar(value=default_unit(cat, self.cfg["preset"]))
            combo = ttk.Combobox(cell, textvariable=uvar, state="readonly", width=9,
                                 values=U.unit_options(cat))
            combo.grid(row=1, column=1, sticky="e")
            self.unit_vars[key] = uvar
            self._prev_unit[(key, cat)] = uvar.get()
            combo.bind("<<ComboboxSelected>>",
                       lambda _e, k=key, c=cat, v=uvar: self._on_unit_changed(k, c, v))
            uvar.trace_add("write",
                           lambda *_, k=key, c=cat, v=uvar: self._on_unit_var_write(k, c, v))

        if desc:
            ttk.Label(cell, text=desc, style="hint.TLabel", wraplength=180,
                      justify="left").grid(row=2, column=0, columnspan=2, sticky="w", pady=(1, 0))

        self.field_vars[key] = var
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
            lab = ttk.Label(comp_frm, text=COMP_LABELS[comp])
            lab.grid(row=r, column=c * 2 + 1, sticky="w")
            ent.bind("<Return>", lambda _e: self.run_calc())
            ToolTip(lab, f"{comp} mol kesri (0 … 1).")
            ToolTip(ent, f"{comp} mol kesri (0 … 1).")
            self.comp_vars[comp] = var
            var.trace_add("write", lambda *_: self._update_comp_sum())
        ttk.Label(comp_frm, text="Toplam:").grid(row=4, column=0, sticky="e", pady=(4, 2))
        self.comp_sum_lbl = ttk.Label(comp_frm, text="", style="sec.TLabel")
        self.comp_sum_lbl.grid(row=4, column=1, columnspan=2, sticky="w")
        ttk.Label(comp_frm, text="Mol kesirleri 0–1 aralığında verilir; toplam 1.0000 olmalıdır "
                  "(hesap öncesi otomatik normalize edilir).",
                  style="hint.TLabel", wraplength=400, justify="left").grid(
            row=5, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))

        proc_frm = ttk.LabelFrame(left, text=" 2. Proses Şartları ")
        proc_frm.pack(fill="x", pady=4)
        proc_frm.columnconfigure(0, weight=1)
        proc_frm.columnconfigure(1, weight=1)
        self._field_cell(proc_frm, 0, 0, "T1", "Sıcaklık T₁", "-163.0",
                         "Çalışma sıcaklığı. LNG için ≈ -160 … -150 °C.",
                         cat="temperature",
                         desc="Akışkan sıcaklığı; termofiziksel özellikleri belirler.")
        self._field_cell(proc_frm, 0, 1, "P1", "Emiş basıncı P₁", "8.5",
                         "Hat emiş basıncı (varsayılan bar-g; gösterge/mutlak seçilebilir).",
                         cat="pressure",
                         desc="Hattaki işletme basıncı; P₂ = P₁ − ΔP oranında düşer.")

        pipe_frm = ttk.LabelFrame(left, text=" 3. Boru ve Akış ")
        pipe_frm.pack(fill="x", pady=4)
        pipe_frm.columnconfigure(0, weight=1)
        pipe_frm.columnconfigure(1, weight=1)

        # [MÜHENDİSLİK DÜZELTMESİ v1.3.0]: Birincil girdi olarak Dış Çap (OD) ve Et Kalınlığı (t) alınır.
        self._field_cell(pipe_frm, 0, 0, "OD", "Boru Dış Çapı OD", "323.85",
                         "Boru nominal dış çapı (ASME B36.19M / B36.10M).", cat="diameter",
                         desc="Standart boru dış çapı; mukavemet ve iç çap hesabında temeldir.")
        self._field_cell(pipe_frm, 0, 1, "t", "Boru Et Kalınlığı t", "9.53",
                         "Et kalınlığı. İç çap D₂₀ = OD - 2×t olarak otomatik hesaplanır.", cat="diameter",
                         desc="Boru et kalınlığı; iç çapı ve basınca dayanımı belirler.")

        # [MÜHENDİSLİK DÜZELTMESİ v1.3.0]: Kullanıcının elle iç çap girmesine gerek yoktur.
        # D20 = OD - 2*t formülüyle canlı olarak hesaplanır ve ASME boru normuyla birlikte gösterilir.
        id_info_cell = ttk.Frame(pipe_frm)
        id_info_cell.grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=(1, 5))
        id_info_cell.columnconfigure(0, weight=1)
        self.d20_auto_lbl = ttk.Label(id_info_cell, text="Otomatik İç Çap D₂₀ = OD - 2t:  304.79 mm  (NPS 12\" (DN 300) Sch 40S)",
                                      font=("TkDefaultFont", 9, "bold"), foreground="#0b6ea8")
        self.d20_auto_lbl.grid(row=0, column=0, sticky="w")

        # OD ve t alanlarına canlı izleme (trace) bağla
        self.field_vars["OD"].trace_add("write", lambda *_: self._update_auto_id())
        self.field_vars["t"].trace_add("write", lambda *_: self._update_auto_id())
        self.unit_vars["OD"].trace_add("write", lambda *_: self._update_auto_id())
        self.unit_vars["t"].trace_add("write", lambda *_: self._update_auto_id())

        self._field_cell(pipe_frm, 2, 0, "Qm", "Nominal debi Qm", "150.0",
                         "Nominal debi. Kütle, hacimsel (sıvı) ve enerji birimleri desteklenir;\n"
                         "hacimsel/enerji birimleri son hesaplanan yoğunluk/GCV ile çevrilir.",
                         cat="flow",
                         desc="Tasarımın baz alındığı nominal kütle/hacim/enerji akışı.")
        self._field_cell(pipe_frm, 2, 1, "dP", "Hedef ΔP", "250.0",
                         "Nominal akıştaki hedeflenen plaka basınç farkı.", cat="dp",
                         desc="Ölçülecek fark basınç; plaka çapı seçimini (β) belirler.")
        self._field_cell(pipe_frm, 3, 0, "L", "Hat uzunluğu L", "50",
                         "Boru uzunluğu — flashing hesabında sürtünme kaybı içindir.",
                         cat="length",
                         desc="Flanştan sonraki hat uzunluğu; faz ayrışması kontrolünde sürtünme kaybı.")

        mat_cell = ttk.Frame(pipe_frm)
        mat_cell.grid(row=3, column=1, sticky="ew", padx=6, pady=3)
        mat_cell.columnconfigure(0, weight=1)
        ttk.Label(mat_cell, text="Malzeme").grid(row=0, column=0, sticky="w")
        self.mat_var = tk.StringVar(value="AISI 304")
        mat_combo = ttk.Combobox(mat_cell, textvariable=self.mat_var, state="readonly",
                                 width=12, values=("AISI 304", "AISI 316"))
        mat_combo.grid(row=1, column=0, sticky="w")

        self._field_cell(pipe_frm, 4, 0, "qmin", "Turndown min", "30",
                         "Minimum debi oranı (%).", suffix="%",
                         desc="Ölçüm aralığının alt sınırı (nominal debinin yüzdesi).")
        self._field_cell(pipe_frm, 4, 1, "qmax", "Turndown max", "120",
                         "Maksimum debi oranı (%).", suffix="%",
                         desc="Ölçüm aralığının üst sınırı; qmax ΔP üst limitini belirler.")

        adv_frm = ttk.LabelFrame(left, text=" 4. Gelişmiş (belirsizlik girdileri) ")
        adv_frm.pack(fill="x", pady=4)
        adv_frm.columnconfigure(0, weight=1)
        adv_frm.columnconfigure(1, weight=1)
        for i, (key, label, default, tip) in enumerate(ADV_DEFS):
            r, c = divmod(i, 2)
            self._field_cell(adv_frm, r, c, key, label, default, tip, suffix="%",
                             desc="Debi belirsizliğine (u(q)/q) katkı oranı.")

    def _update_auto_id(self) -> None:
        """[MÜHENDİSLİK DÜZELTMESİ v1.3.0]: OD ve t değiştikçe iç çapı ve ASME etiketini canlı güncelle."""
        try:
            od_mm = self._canonical("OD")
            t_mm = self._canonical("t")
            if od_mm > 0 and t_mm > 0 and od_mm > 2.0 * t_mm:
                id_mm = od_mm - 2.0 * t_mm
                from safety_engine import identify_pipe
                pipe_label, _ = identify_pipe(od_mm, t_mm)
                u_diam = self.unit_vars["OD"].get()
                disp_id = U.from_canonical(id_mm, u_diam, "diameter")
                self.d20_auto_lbl.config(
                    text=f"Otomatik İç Çap D₂₀ = OD - 2t:  {disp_id:.2f} {u_diam}  ({pipe_label})",
                    foreground="#0b6ea8"
                )
            else:
                self.d20_auto_lbl.config(text="Boru geometrisi geçersiz (OD ≤ 2t)", foreground="#c0392b")
        except Exception:
            pass

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
        # [MÜHENDİSLİK DÜZELTMESİ v1.3.0]: İç çap doğrudan D20 = OD - 2*t formülüyle otomatik hesaplanır
        od_mm = self._canonical("OD")
        t_mm = self._canonical("t")
        d20_mm = od_mm - 2.0 * t_mm
        return RunInputs(
            comp=comp,
            T1_C=self._canonical("T1"),
            P1_barg=p1_bara - 1.01325,
            D20_mm=d20_mm,
            qm_nom_ton_h=self._canonical("Qm"),
            dP_target_mbar=self._canonical("dP"),
            q_min_ratio=self._canonical("qmin"),
            q_max_ratio=self._canonical("qmax"),
            L_pipe_m=self._canonical("L"),
            Do_mm=od_mm,
            t_actual_mm=t_mm,
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
