"""GUI'den bağımsız sonuç sunum verisi — birim bilgili katalog.

- `build_catalog(r)`: her satır (etiket, kanonik değer, kategori, tag) döner;
  biçimlendirme GUI/rapor tarafında seçilen birimle yapılır.
- `build_sections(r)`: eski geri-uyumlu sürüm (kanonik birimle string üretir),
  test ve konsol özeti için korunmuştur.
Tkinter gerektirmez; headless test edilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass

from units import CANONICAL_UNIT, format_canonical


@dataclass
class ResultRow:
    label: str
    value: float | str
    category: str | None = None
    tag: str = "normal"
    prefix: str = ""
    suffix: str = ""
    digits: int | None = None
    default_unit: str | None = None


def result_context(r) -> dict:
    return {
        "rho_kgm3": r.sizing.rho,
        "M_mix_kg_kmol": r.thermo.M_mix,
        "gcv_mj_kg": r.energy.GCV_mj_kg if r.energy else None,
    }


def build_catalog(r) -> list[tuple[str, list[ResultRow]]]:
    t, s, sf = r.thermo, r.sizing, r.safety
    e = r.energy
    sections: list[tuple[str, list[ResultRow]]] = []
    rows: list[ResultRow] = []

    rows += [
        ResultRow("Ortalama molar kütle M_mix", t.M_mix, "molar_mass"),
        ResultRow("Doymuş sıvı yoğunluğu ρ_sat (K-Z)", t.rho_sat_kgm3, "density"),
        ResultRow("Çalışma yoğunluğu ρ (subcooled)", t.rho_oper_kgm3, "density"),
        ResultRow("Bubble point Pv — Peng-Robinson", t.Pv_pr_bara, "pressure"),
        ResultRow("Bubble point Pv — Antoine/Raoult", t.Pv_raoult_bara, "pressure"),
        ResultRow("Kullanılan Pv modeli", t.pv_model),
    ]
    if t.first_vapor_y:
        ytxt = ", ".join(
            f"{k} %{v*100:.1f}" for k, v in sorted(t.first_vapor_y.items(), key=lambda kv: -kv[1]) if v > 1e-4
        )
        rows.append(ResultRow("İlk buhar bileşimi (PR)", ytxt))
    sections.append(("Termofiziksel Özellikler", rows))

    rows = [
        ResultRow("Beta (β = d/D)", s.beta, "number", "good" if 0.20 <= s.beta <= 0.75 else "bad", digits=5),
        ResultRow("Deşarj katsayısı C (R-H/G flange)", s.C, "number", digits=5),
        ResultRow("Reynolds sayısı Re_D", s.Re_D, "number", digits=0),
        ResultRow("Ortalama hat hızı", s.velocity_m_s, "velocity", digits=3),
        ResultRow("Soğuk boru iç çapı D_T", s.DT_mm, "diameter"),
        ResultRow("Soğuk orifis çapı d_T", s.dT_mm, "diameter"),
        ResultRow("İmalat orifis çapı d₂₀ (@20°C)", s.d20_mm, "diameter", "emph"),
        ResultRow("Çözücü", s.solver),
    ]
    sections.append(("ISO 5167-2 Hidrolik Boyutlandırma", rows))

    rows = [
        ResultRow("ΔP nominal", s.dP_nom_pa / 100.0, "dp", digits=0),   # Pa -> mbar
        ResultRow("ΔP @ Qmax", s.dP_max_mbar, "dp"),
        ResultRow("ΔP @ Qmin", s.dP_min_mbar, "dp"),
        ResultRow("Akış belirsizliği u(q)/q", s.u_flow_pct / 100.0, "percent", prefix="± ", digits=2),
        ResultRow("Deşarj katsayısı belirsizliği u(C)/C", s.uC_C_pct / 100.0, "percent", prefix="± ", digits=2),
    ]
    sections.append(("Akış Aralığı ve Belirsizlik", rows))

    if e is not None:
        rows = [
            ResultRow("Isıl değer GCV", e.GCV_mj_kg, "heating_value", "emph"),
            ResultRow("Isıl değer NCV", e.NCV_mj_kg, "heating_value"),
            ResultRow("GCV (molar)", e.GCV_mj_kg, "heating_value", default_unit="MJ/kmol"),
            ResultRow("GCV (gaz, Nm³)", e.GCV_mj_kg, "heating_value", default_unit="MJ/Nm³"),
            ResultRow("NCV (gaz, Nm³)", e.NCV_mj_kg, "heating_value", default_unit="MJ/Nm³"),
            ResultRow("Termal güç Q×GCV", e.MW_mj_s, "energy_flow", "emph"),
            ResultRow("Termal güç Q×NCV", e.MW_lv_mj_s, "energy_flow"),
            ResultRow("Nominal hacimsel debi (sıvı)", s.qm_kg_s * 3.6, "mass_flow", default_unit="m³/h (sıvı)"),
        ]
        sections.append(("Enerji (Isıl Değer)", rows))

    ph = sf.phase
    rows = []
    if ph.flashing:
        rows.append(ResultRow("Faz değişimi durumu", "KRİTİK: FLASHING", tag="bad"))
    elif ph.cavitation:
        rows.append(ResultRow("Faz değişimi durumu", "UYARI: KAVİTASYON", tag="warn"))
    else:
        rows.append(ResultRow("Faz değişimi durumu", "GÜVENLİ", tag="good"))
    rows += [
        ResultRow("P₂ (plaka + boru kaybı)", ph.P2_barA, "pressure"),
        ResultRow("Pvc (vena contracta)", ph.Pvc_barA, "pressure"),
        ResultRow("Plaka ΔP (Qmax)", ph.dP_plate_max_bar * 1000.0, "dp", digits=0),
        ResultRow("Boru sürtünme ΔP", ph.dP_pipe_bar * 1000.0, "dp"),
        ResultRow("Marj P₂/Pv", ph.margin_P2_over_Pv, "number", suffix=" x", digits=2),
        ResultRow("Marj Pvc/Pv", ph.margin_Pvc_over_Pv, "number", suffix=" x", digits=2),
    ]
    if str(sf.wall.t_actual_mm) == "nan":
        rows.append(ResultRow("ASME B31.3 et kalınlığı", "GİRİLMEDİ", tag="warn"))
    elif sf.wall.ok:
        rows.append(ResultRow("ASME B31.3 et kalınlığı", "UYGUN", tag="good"))
    else:
        rows.append(ResultRow("ASME B31.3 et kalınlığı", "YETERSİZ", tag="bad"))
    if not str(sf.wall.t_actual_mm) == "nan":
        rows += [
            ResultRow("  t_hesap → t_gerekli", f"{sf.wall.t_calc_mm:.2f} → {sf.wall.t_required_mm:.2f} mm"),
            ResultRow("  t_mevcut (değirmen tol.)", sf.wall.t_available_mm, "diameter"),
        ]
    rows += [
        ResultRow("Upstream düz boru (≥20D)", sf.straight_up_m, "length"),
        ResultRow("Downstream düz boru (≥5D)", sf.straight_down_m, "length"),
    ]
    sections.append(("Emniyet Denetim Matrisi", rows))

    if r.warnings:
        sections.append(("Uyarılar", [ResultRow("⚠", w, tag="warn") for w in r.warnings]))

    return sections


def render_row(row: ResultRow, unit: str | None = None, ctx: dict | None = None) -> str:
    if row.category is None:
        return str(row.value)
    u = unit or row.default_unit or CANONICAL_UNIT.get(row.category, "")
    txt = format_canonical(row.value, row.category, u, ctx, digits=row.digits)
    return f"{row.prefix}{txt}{row.suffix}"


def build_sections(r) -> list[tuple[str, list[tuple[str, str, str]]]]:
    """Eski API: kanonik birimlerle biçimlendirilmiş (label, value, tag)."""
    ctx = result_context(r)
    out: list[tuple[str, list[tuple[str, str, str]]]] = []
    for title, rows in build_catalog(r):
        out.append((title, [(row.label, render_row(row, ctx=ctx), row.tag) for row in rows]))
    return out