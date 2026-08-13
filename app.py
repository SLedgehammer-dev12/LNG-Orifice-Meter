"""Tkinter masaüstü GUI: LNG orifis ölçüm noktası tasarım aracı."""

from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from engine import RunInputs, run_engineering
from report import build_html, print_console_summary
from ui_data import build_sections

APP_TITLE = "LNG Orifis Ölçüm Noktası Tasarım Aracı"
APP_VERSION = "v1.0"

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
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + 24
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=("TkDefaultFont", 10),
        )
        label.pack()

    def _hide(self, _event=None) -> None:
        if self.tip:
            self.tip.destroy()
            self.tip = None


class App(ttk.Frame):
    def __init__(self, root: tk.Tk) -> None:
        super().__init__(root, padding=8)
        self.root = root
        self.pack(fill="both", expand=True)

        self.comp_vars: dict[str, tk.StringVar] = {}
        self.field_vars: dict[str, tk.StringVar] = {}
        self.result: object = None

        self._build_topbar()
        self._build_body()
        self.load_defaults()

    def _build_topbar(self) -> None:
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Button(bar, text="Hesapla", command=self.run_calc).pack(side="left")
        ttk.Button(bar, text="Varsayılanları Yükle", command=self.load_defaults).pack(side="left", padx=6)
        ttk.Button(bar, text="HTML Rapor Dışa Aktar", command=self.export_html).pack(side="left")
        ttk.Button(bar, text="Çıktıyı Temizle", command=self.clear_results).pack(side="left", padx=6)
        self.status_lbl = ttk.Label(bar, text="·", font=("TkDefaultFont", 11, "bold"))
        self.status_lbl.pack(side="right")
        ttk.Label(bar, text=APP_VERSION, foreground="#8a97a5").pack(side="right", padx=6)

    def _build_body(self) -> None:
        paned = ttk.PanedWindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True)

        left = ttk.Frame(paned, width=430)
        left.pack_propagate(False)
        right = ttk.Frame(paned)
        paned.add(left, weight=0)
        paned.add(right, weight=1)

        self._build_inputs(left)
        self._build_results(right)

    def _field(self, parent: tk.Widget, row: int, col: int, label: str, default: str, tip: str | None = None):
        frm = ttk.Frame(parent)
        frm.grid(row=row, column=col, sticky="ew", padx=6, pady=3)
        frm.columnconfigure(0, weight=1)
        ttk.Label(frm, text=label).grid(row=0, column=0, sticky="w")
        var = tk.StringVar(value=default)
        ent = ttk.Entry(frm, textvariable=var, width=12, justify="right")
        ent.grid(row=0, column=1, sticky="e", padx=(6, 0))
        if tip:
            ToolTip(ent, tip)
            ttk.Label(frm, text="?", foreground="#0b6ea8", cursor="hand2").grid(row=0, column=2, padx=(2, 0))
        self.field_vars[label] = var
        return ent

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
        self.comp_sum_lbl = ttk.Label(comp_frm, text="", foreground="#0b6ea8", font=("TkDefaultFont", 10, "bold"))
        self.comp_sum_lbl.grid(row=4, column=1, columnspan=2, sticky="w")

        proc_frm = ttk.LabelFrame(left, text=" 2. Proses Şartları ")
        proc_frm.pack(fill="x", pady=4)
        self._field(proc_frm, 0, 0, "Sıcaklık T₁", "-163.0",
                    "Çalışma sıcaklığı (°C). LNG için ≈ -160 … -150.")
        self._field(proc_frm, 0, 1, "Emiş basıncı P₁", "8.5",
                    "Hat emiş basıncı (bar-g).")

        pipe_frm = ttk.LabelFrame(left, text=" 3. Boru ve Akış ")
        pipe_frm.pack(fill="x", pady=4)
        self._field(pipe_frm, 0, 0, "İç çap D₂₀", "300.0", "Boru iç çapı @20°C (mm).")
        self._field(pipe_frm, 0, 1, "Nominal debi Qm", "150.0", "Nominal kütlesel debi (ton/saat).")
        self._field(pipe_frm, 1, 0, "Hedef ΔP", "250.0", "Nominal akıştaki hedeflenen plaka basınç farkı (mbar).")
        self._field(pipe_frm, 1, 1, "Turndown min", "30", "Minimum debi oranı (%).")
        self._field(pipe_frm, 2, 0, "Turndown max", "120", "Maksimum debi oranı (%).")
        self._field(pipe_frm, 2, 1, "Hat uzunluğu L", "50", "Boru uzunluğu (m) — flashing hesabında sürtünme kaybı içindir.")

        mat_frm = ttk.Frame(pipe_frm)
        mat_frm.grid(row=3, column=0, columnspan=2, sticky="ew", padx=6, pady=3)
        ttk.Label(mat_frm, text="Malzeme").pack(side="left")
        self.mat_var = tk.StringVar(value="AISI 304")
        mat_combo = ttk.Combobox(mat_frm, textvariable=self.mat_var, state="readonly", width=9,
                                 values=("AISI 304", "AISI 316"))
        mat_combo.pack(side="left", padx=6)
        ttk.Label(mat_frm, text="Boru OD").pack(side="left", padx=(10, 2))
        self.field_vars["Boru OD"] = tk.StringVar(value="323.9")
        ttk.Entry(mat_frm, textvariable=self.field_vars["Boru OD"], width=8, justify="right").pack(side="left")
        ttk.Label(mat_frm, text="mm  t:").pack(side="left", padx=(6, 2))
        self.field_vars["Et kalınlığı t"] = tk.StringVar(value="9.53")
        ttk.Entry(mat_frm, textvariable=self.field_vars["Et kalınlığı t"], width=7, justify="right").pack(side="left")
        ttk.Label(mat_frm, text="mm").pack(side="left", padx=(2, 0))

        adv_frm = ttk.LabelFrame(left, text=" 4. Gelişmiş (belirsizlik girdileri) ")
        adv_frm.pack(fill="x", pady=4)
        self._field(adv_frm, 0, 0, "u(C)/C", "0.5", "Deşarj katsayısı belirsizliği (%). R-H/G: 0.5 önerilir.")
        self._field(adv_frm, 0, 1, "u(D)/D", "0.1", "Boru çapı belirsizliği (%).")
        self._field(adv_frm, 1, 0, "u(d)/d", "0.05", "Orifis çapı belirsizliği (%).")
        self._field(adv_frm, 1, 1, "u(ΔP)/ΔP", "0.5", "Basınç farkı transmiteri belirsizliği (%).")

    def _build_results(self, right: tk.Widget) -> None:
        header = ttk.Label(right, text="Sonuçlar", font=("TkDefaultFont", 12, "bold"))
        header.pack(anchor="w")
        columns = ("param", "value", "status")
        self.tree = ttk.Treeview(right, columns=columns, show="tree headings", height=28)
        self.tree.heading("#0", text="Bölüm")
        self.tree.heading("param", text="Parametre")
        self.tree.heading("value", text="Değer")
        self.tree.heading("status", text="Durum")
        self.tree.column("#0", width=180, anchor="w")
        self.tree.column("param", width=240, anchor="w")
        self.tree.column("value", width=130, anchor="e")
        self.tree.column("status", width=140, anchor="w")
        self.tree.tag_configure("good", foreground="#0a6b2e")
        self.tree.tag_configure("warn", foreground="#856404")
        self.tree.tag_configure("bad", foreground="#a02b2b")
        self.tree.tag_configure("emph", font=("TkDefaultFont", 10, "bold"))
        vsb = ttk.Scrollbar(right, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _update_comp_sum(self) -> None:
        try:
            total = sum(float(v.get() or 0.0) for v in self.comp_vars.values())
        except ValueError:
            self.comp_sum_lbl.config(text="Hatalı girdi", foreground="#a02b2b")
            return
        ok = abs(total - 1.0) < 1e-3
        color = "#0a6b2e" if ok else "#856404"
        self.comp_sum_lbl.config(text=f"{total:.4f}" + ("  ✓" if ok else "  (norm.)"), foreground=color)

    def _float(self, label: str) -> float:
        try:
            return float(self.field_vars[label].get().replace(",", "."))
        except ValueError:
            raise ValueError(f"'{label}' sayısal değil: {self.field_vars[label].get()!r}")

    def collect_inputs(self) -> RunInputs:
        comp = {c: float(v.get() or 0.0) for c, v in self.comp_vars.items()}
        material = self.mat_var.get()
        S_mpa = 138.0 if material == "AISI 304" else 138.0
        return RunInputs(
            comp=comp,
            T1_C=self._float("Sıcaklık T₁"),
            P1_barg=self._float("Emiş basıncı P₁"),
            D20_mm=self._float("İç çap D₂₀"),
            qm_nom_ton_h=self._float("Nominal debi Qm"),
            dP_target_mbar=self._float("Hedef ΔP"),
            q_min_ratio=self._float("Turndown min") / 100.0,
            q_max_ratio=self._float("Turndown max") / 100.0,
            L_pipe_m=self._float("Hat uzunluğu L"),
            Do_mm=self._float("Boru OD"),
            t_actual_mm=self._float("Et kalınlığı t"),
            material=material,
            S_mpa=S_mpa,
            uC_C=self._float("u(C)/C") / 100.0,
            uD_D=self._float("u(D)/D") / 100.0,
            ud_d=self._float("u(d)/d") / 100.0,
            udP_dP=self._float("u(ΔP)/ΔP") / 100.0,
        )

    def run_calc(self) -> None:
        try:
            inp = self.collect_inputs()
        except ValueError as e:
            messagebox.showerror("Girdi Hatası", str(e))
            return
        try:
            self.result = run_engineering(inp)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Hesaplama Hatası", str(e))
            return
        self._populate_tree(self.result)
        self._update_status(self.result)
        print_console_summary(self.result)

    def _populate_tree(self, r) -> None:
        self.tree.delete(*self.tree.get_children())
        for title, items in build_sections(r):
            parent = self.tree.insert("", "end", text=title, open=True)
            for label, value, tag in items:
                self.tree.insert(parent, "end", values=(label, value, ""), tags=(tag,))

    def _update_status(self, r) -> None:
        sf = r.safety.phase
        if sf.flashing:
            text, fg = "KRİTİK: FLASHING", "#a02b2b"
        elif sf.cavitation:
            text, fg = "UYARI: KAVİTASYON", "#856404"
        else:
            text, fg = "GÜVENLİ", "#0a6b2e"
        self.status_lbl.config(text=text, foreground=fg)

    def load_defaults(self) -> None:
        for c, v in self.comp_vars.items():
            v.set(f"{BOTAŞ_DEFAULT_COMP[c]:.4f}")
        defaults = {
            "Sıcaklık T₁": "-163.0",
            "Emiş basıncı P₁": "8.5",
            "İç çap D₂₀": "300.0",
            "Nominal debi Qm": "150.0",
            "Hedef ΔP": "250.0",
            "Turndown min": "30",
            "Turndown max": "120",
            "Hat uzunluğu L": "50",
            "Boru OD": "323.9",
            "Et kalınlığı t": "9.53",
            "u(C)/C": "0.5",
            "u(D)/D": "0.1",
            "u(d)/d": "0.05",
            "u(ΔP)/ΔP": "0.5",
        }
        for label, val in defaults.items():
            self.field_vars[label].set(val)
        self.mat_var.set("AISI 304")
        self._update_comp_sum()
        self.clear_results()

    def clear_results(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.status_lbl.config(text="·", foreground="#8a97a5")

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


def main() -> None:
    root = tk.Tk()
    root.title(f"{APP_TITLE} — {APP_VERSION}")
    root.geometry("1180x820")
    root.minsize(980, 680)
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()