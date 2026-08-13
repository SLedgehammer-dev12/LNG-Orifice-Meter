"""GUI'den bağımsız sonuç sunum verisi. Tkinter gerektirmez; testlerde headless kullanılır."""

from __future__ import annotations


def build_sections(r) -> list[tuple[str, list[tuple[str, str, str]]]]:
    t, s, sf = r.thermo, r.sizing, r.safety
    sections: list[tuple[str, list[tuple[str, str, str]]]] = []

    def row(items, label, value, tag="normal"):
        items.append((label, value, tag))

    items: list[tuple[str, str, str]] = []
    row(items, "Ortalama molar kütle M_mix", f"{t.M_mix:.3f} kg/kmol")
    row(items, "Doymuş sıvı yoğunluğu ρ_sat (K-Z)", f"{t.rho_sat_kgm3:.2f} kg/m³")
    row(items, "Çalışma yoğunluğu ρ (subcooled)", f"{t.rho_oper_kgm3:.2f} kg/m³")
    row(items, "Bubble point Pv — Peng-Robinson", f"{t.Pv_pr_bara:.4f} bar-a")
    row(items, "Bubble point Pv — Antoine/Raoult", f"{t.Pv_raoult_bara:.4f} bar-a")
    row(items, "Kullanılan Pv modeli", t.pv_model)
    if t.first_vapor_y:
        ytxt = ", ".join(
            f"{k} %{v*100:.1f}" for k, v in sorted(t.first_vapor_y.items(), key=lambda kv: -kv[1]) if v > 1e-4
        )
        row(items, "İlk buhar bileşimi (PR)", ytxt)
    sections.append(("Termofiziksel Özellikler", items))

    items = []
    row(items, "Beta (β = d/D)", f"{s.beta:.5f}", "good" if 0.20 <= s.beta <= 0.75 else "bad")
    row(items, "Deşarj katsayısı C (R-H/G flange)", f"{s.C:.5f}")
    row(items, "Reynolds sayısı Re_D", f"{s.Re_D:,.0f}")
    row(items, "Ortalama hat hızı", f"{s.velocity_m_s:.3f} m/s")
    row(items, "Soğuk boru iç çapı D_T", f"{s.DT_mm:.3f} mm")
    row(items, "Soğuk orifis çapı d_T", f"{s.dT_mm:.3f} mm")
    row(items, "İmalat orifis çapı d₂₀ (@20°C)", f"{s.d20_mm:.3f} mm", "emph")
    row(items, "Çözücü", s.solver)
    sections.append(("ISO 5167-2 Hidrolik Boyutlandırma", items))

    items = []
    row(items, "ΔP nominal", f"{s.dP_nom_pa:.0f} Pa")
    row(items, "ΔP @ Qmax", f"{s.dP_max_mbar:.1f} mbar")
    row(items, "ΔP @ Qmin", f"{s.dP_min_mbar:.1f} mbar")
    row(items, "Akış belirsizliği u(q)/q", f"± {s.u_flow_pct:.2f} %")
    row(items, "Deşarj katsayısı belirsizliği u(C)/C", f"± {s.uC_C_pct:.2f} %")
    sections.append(("Akış Aralığı ve Belirsizlik", items))

    ph = sf.phase
    items = []
    if ph.flashing:
        row(items, "Faz değişimi durumu", "KRİTİK: FLASHING", "bad")
    elif ph.cavitation:
        row(items, "Faz değişimi durumu", "UYARI: KAVİTASYON", "warn")
    else:
        row(items, "Faz değişimi durumu", "GÜVENLİ", "good")
    row(items, "P₂ (plaka + boru kaybı)", f"{ph.P2_barA:.3f} bar-a")
    row(items, "Pvc (vena contracta)", f"{ph.Pvc_barA:.3f} bar-a")
    row(items, "Plaka ΔP (Qmax)", f"{ph.dP_plate_max_bar*1000:.0f} mbar")
    row(items, "Boru sürtünme ΔP", f"{ph.dP_pipe_bar*1000:.1f} mbar")
    row(items, "Marj P₂/Pv", f"{ph.margin_P2_over_Pv:.2f} x")
    row(items, "Marj Pvc/Pv", f"{ph.margin_Pvc_over_Pv:.2f} x")
    if str(sf.wall.t_actual_mm) == "nan":
        row(items, "ASME B31.3 et kalınlığı", "GİRİLMEDİ", "warn")
    elif sf.wall.ok:
        row(items, "ASME B31.3 et kalınlığı", "UYGUN", "good")
    else:
        row(items, "ASME B31.3 et kalınlığı", "YETERSİZ", "bad")
    if not str(sf.wall.t_actual_mm) == "nan":
        row(items, "  t_hesap → t_gerekli", f"{sf.wall.t_calc_mm:.2f} → {sf.wall.t_required_mm:.2f} mm")
        row(items, "  t_mevcut (değirmen tol.)", f"{sf.wall.t_available_mm:.2f} mm")
    row(items, "Upstream düz boru (≥20D)", f"{sf.straight_up_m:.2f} m")
    row(items, "Downstream düz boru (≥5D)", f"{sf.straight_down_m:.2f} m")
    sections.append(("Emniyet Denetim Matrisi", items))

    if r.warnings:
        sections.append(("Uyarılar", [("⚠", w, "warn") for w in r.warnings]))

    return sections
