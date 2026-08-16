"""Motor doğrulama testleri. Çalıştır: python3 test_engine.py"""

from __future__ import annotations

import math
import os
import sys
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from engine import RunInputs, run_engineering
from report import print_console_summary, write_html
from ui_data import build_sections
from updater import compare_versions, platform_asset

BOTAŞ_COMP = {
    "CH4": 0.915,
    "C2H6": 0.055,
    "C3H8": 0.018,
    "iC4": 0.004,
    "nC4": 0.004,
    "iC5": 0.001,
    "nC5": 0.001,
    "N2": 0.002,
}

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def main() -> None:
    # [MÜHENDİSLİK DÜZELTMESİ v1.3.0]: D20_mm verilmez; Do_mm ve t_actual_mm'den otomatik türetilir
    inp = RunInputs(
        comp=BOTAŞ_COMP,
        T1_C=-163.0,
        P1_barg=8.5,
        qm_nom_ton_h=150.0,
        dP_target_mbar=250.0,
        q_min_ratio=0.30,
        q_max_ratio=1.20,
        L_pipe_m=50.0,
        Do_mm=323.85,
        t_actual_mm=9.53,
    )
    r = run_engineering(inp)
    s, t, sf = r.sizing, r.thermo, r.safety

    print("\n-- Geometrik Tutarlılık ve Otomatik İç Çap (v1.3.0) --")
    expected_d20 = 323.85 - 2.0 * 9.53  # 304.79 mm
    check("D20 otomatik hesaplandı (OD - 2t)", abs(inp.D20_mm - expected_d20) < 1e-4, f"D20 = {inp.D20_mm:.3f} mm")

    print("\n-- Fiziksel sağduyu --")
    check("yoğunluk 420–480 kg/m³", 420 < t.rho_oper_kgm3 < 480, f"{t.rho_oper_kgm3:.2f}")
    check("Pv_PR 0.4–2.0 bar-a", 0.4 < t.Pv_pr_bara < 2.0, f"{t.Pv_pr_bara:.4f}")
    check("M_mix 16.5–18.6", 16.5 < t.M_mix < 18.6, f"{t.M_mix:.3f}")

    print("\n-- Isıl değer (enerji motoru) --")
    check("GCV 48–56 MJ/kg (LNG)", 48.0 < r.energy.GCV_mj_kg < 56.0, f"{r.energy.GCV_mj_kg:.3f}")
    check("NCV < GCV", r.energy.NCV_mj_kg < r.energy.GCV_mj_kg)
    check("GCV kansistent MJ/kmol", abs(r.energy.GCV_mj_kmol - r.energy.GCV_mj_kg * t.M_mix) < 1e-6)
    check("termal güç > 0", r.energy.MW_mj_s > 0)

    print("\n-- Hidrolik --")
    check("β 0.35–0.55", 0.35 < s.beta < 0.55, f"{s.beta:.4f}")
    check("C 0.59–0.61", 0.59 < s.C < 0.61, f"{s.C:.5f}")
    check("Re > 1e5", s.Re_D > 1e5, f"{s.Re_D:.0f}")
    check("d20 125–145 mm", 125 < s.d20_mm < 145, f"{s.d20_mm:.2f}")
    check("hız 1–3 m/s", 1.0 < s.velocity_m_s < 3.0, f"{s.velocity_m_s:.3f}")

    print("\n-- Belirsizlik ve Kalıcı Basınç Kaybı --")
    check("u(q)/q < 1.2 %", s.u_flow_pct < 1.2, f"{s.u_flow_pct:.3f} %")
    check("kalıcı dP > 0 ve < dP_nom", 0.0 < s.dP_perm_loss_mbar < 250.0, f"{s.dP_perm_loss_mbar:.1f} mbar")
    check("pompa güç kaybı > 0", s.pump_power_loss_kw > 0.0, f"{s.pump_power_loss_kw:.2f} kW")

    print("\n-- Emniyet ve ASME B36.19M Boru Normu --")
    check("faz güvenli (flashing yok)", not sf.phase.flashing, sf.phase.status)
    check("kavitasyon yok", not sf.phase.cavitation, sf.phase.status)
    check("P2 > Pv (10x marj)", sf.phase.margin_P2_over_Pv > 5.0, f"{sf.phase.margin_P2_over_Pv:.2f}")
    check("B31.3 uygun", sf.wall.ok, str(sf.wall.notes))
    check("Boru tanımlandı (NPS 12 Sch 40S)", "NPS 12" in sf.wall.identified_pipe and "40S" in sf.wall.identified_pipe, sf.wall.identified_pipe)
    check("Önerilen schedule mevcut", "Sch" in sf.wall.recommended_schedule, sf.wall.recommended_schedule)
    check("β aralıkta", sf.beta_in_range)
    check("boru kaybı < 100 mbar", sf.phase.dP_pipe_bar * 1000 < 100, f"{sf.phase.dP_pipe_bar*1000:.1f} mbar")

    print("\n-- ISO 5167-2 Küçük Çap (D < 71.12 mm) R-H/G Testi --")
    from orifice_engine import rhg_flange_C
    c_small = rhg_flange_C(beta=0.50, Re_D=2e5, D_mm=50.0)
    check("D=50mm C fiziksel (0.59-0.62)", 0.59 < c_small < 0.62, f"{c_small:.5f}")

    print("\n-- ASME B36.19M / B36.10M Kütüphane Testleri (NPS 36'ya kadar) --")
    from safety_engine import identify_pipe, recommend_schedule
    label_12, sch_12 = identify_pipe(323.85, 9.53)
    check("323.85 / 9.53 -> NPS 12 Sch 40S", "NPS 12" in label_12 and sch_12 in ("40S", "STD"), label_12)
    rec_lbl_5s, rec_t_5s = recommend_schedule(323.85, t_required_mm=2.5)
    check("t_req=2.5mm için Sch 5S önerir", "5S" in rec_lbl_5s, f"{rec_lbl_5s} (t={rec_t_5s}mm)")
    rec_lbl_10s, rec_t_10s = recommend_schedule(323.85, t_required_mm=3.6)
    check("t_req=3.6mm için Sch 10S önerir", "10S" in rec_lbl_10s, f"{rec_lbl_10s} (t={rec_t_10s}mm)")

    # NPS 36" (914.4 mm) ve harfli/mm testleri
    label_36, sch_36 = identify_pipe(914.40, 12.70)
    check("914.40 / 12.70 -> NPS 36 XS", "NPS 36" in label_36 and (sch_36 == "XS" or "12.70" in label_36), label_36)
    rec_36, t_36 = recommend_schedule(914.40, t_required_mm=6.5)
    check("NPS 36 t_req=6.5mm öneri", "NPS 36" in rec_36 and t_36 >= 7.0, f"{rec_36} (t={t_36}mm)")

    print("\n-- GIIGNL K-Z ve Termo Testleri --")
    nasty = dict(BOTAŞ_COMP)
    nasty["N2"] = 0.050  # > 4.25% GIIGNL limiti aşımı
    r2 = run_engineering(RunInputs(comp=nasty, T1_C=-163.0, P1_barg=8.5, D20_mm=300.0,
                                   qm_nom_ton_h=150.0, dP_target_mbar=250.0))
    check("GIIGNL N2 limit aşımı uyarısı", any("GIIGNL" in w and "N2" in w for w in r2.warnings))
    check("Dinamik viskozite hesaplandı (>0)", t.viscosity_pa_s > 0, f"{t.viscosity_pa_s:.6f} Pa.s")

    print("\n-- B31.3 atlanır (girdi yok) --")
    r3 = run_engineering(RunInputs(comp=BOTAŞ_COMP, T1_C=-163.0, P1_barg=8.5, D20_mm=300.0,
                                   qm_nom_ton_h=150.0, dP_target_mbar=250.0))
    check("uygulanabilir atlama", r3.safety.wall.ok)

    print("\n-- Kritik flashing senaryosu (düşük P1) --")
    r4 = run_engineering(RunInputs(comp=BOTAŞ_COMP, T1_C=-163.0, P1_barg=1.0, D20_mm=300.0,
                                   qm_nom_ton_h=150.0, dP_target_mbar=900.0, q_max_ratio=1.4))
    print(f"    status={r4.safety.phase.status} P2={r4.safety.phase.P2_barA:.3f} Pv={r4.thermo.Pv_final_bara:.4f}")

    print("\n-- N2 duyarlılık tablosu --")
    for row in r.sensitivity:
        print(f"    N2=%{row.n2_pct:.2f}  Pv={row.pv_bara:.4f}  ρ={row.rho_kgm3:.1f}  marj={row.margin_p2:6.2f}  {row.safe}")

    print("\n-- HTML rapor --")
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "rapor.html")
        write_html(r, path)
        size = os.path.getsize(path)
        check("HTML yazıldı", size > 7000, f"{size} B")
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
        check("HTML utf-8 + Türkçe", "Türkçe" in content or "UYGUN" in content)
        check("SVG şema gömülü", "<svg" in content and ">0. Şematik Gösterim</h2>" in content)
        check("Enerji bölümü", "Isıl değer GCV" in content)
        check("Kalıcı basınç kaybı HTML'de", "Kalıcı basınç kaybı" in content)

    print("\n-- GUI veri yapısı (Tk gerektirmez) --")
    sections = build_sections(r)
    check("5 bölüm üretir", len(sections) >= 5, str(len(sections)))
    check("termo bölümü dolu", len(sections[0][1]) >= 5)

    print("\n-- Güncelleme modülü (ağ gerektirmez) --")
    check("1.0 < 1.1", compare_versions("1.0", "1.1"))
    check("v1.0.0 < v1.1", compare_versions("v1.0.0", "v1.1"))
    check("1.1 == 1.1", not compare_versions("1.1", "v1.1"))
    check("1.2 > 1.1", not compare_versions("1.2", "1.1"))
    check("1.0.9 < 1.0.10", compare_versions("1.0.9", "1.0.10"))
    check("önemli değil 2.0 > 1.x", compare_versions("1.9.9", "2.0.0"))
    win_assets = {"LNG-Orifice-Meter-windows-x64.exe": "u1", "LNG-Orifice-Meter-macOS-arm64.zip": "u2"}
    mac_assets = {"LNG-Orifice-Meter-macOS-arm64.zip": "u1", "LNG-Orifice-Meter-macOS-x64.zip": "u2"}
    if sys.platform.startswith("win"):
        sel = (platform_asset(win_assets) or (None, None))[0]
        check("windows exe seçer", sel == "LNG-Orifice-Meter-windows-x64.exe", sel or "-")
    elif sys.platform == "darwin":
        sel = (platform_asset(win_assets) or (None, None))[0]
        check("mac arm64 öncelikli", sel == "LNG-Orifice-Meter-macOS-arm64.zip", sel or "-")
    else:
        sel = (platform_asset(mac_assets) or (None, None))[0]
        check("linux asset seçer", sel is not None, sel or "-")
    check("asset yoksa None", platform_asset({}) is None)

    print_console_summary(r)

    print("=" * 62)
    print(f"  SONUÇ: {PASS} geçti, {FAIL} kaldı")
    print("=" * 62)
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()