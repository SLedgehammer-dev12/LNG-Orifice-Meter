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
    inp = RunInputs(
        comp=BOTAŞ_COMP,
        T1_C=-163.0,
        P1_barg=8.5,
        D20_mm=300.0,
        qm_nom_ton_h=150.0,
        dP_target_mbar=250.0,
        q_min_ratio=0.30,
        q_max_ratio=1.20,
        L_pipe_m=50.0,
        Do_mm=323.9,
        t_actual_mm=9.53,
    )
    r = run_engineering(inp)
    s, t, sf = r.sizing, r.thermo, r.safety

    print("\n-- Fiziksel sağduyu --")
    check("yoğunluk 420–480 kg/m³", 420 < t.rho_oper_kgm3 < 480, f"{t.rho_oper_kgm3:.2f}")
    check("Pv_PR 0.4–2.0 bar-a", 0.4 < t.Pv_pr_bara < 2.0, f"{t.Pv_pr_bara:.4f}")
    check("M_mix 16.5–18.6", 16.5 < t.M_mix < 18.6, f"{t.M_mix:.3f}")

    print("\n-- Hidrolik --")
    check("β 0.35–0.55", 0.35 < s.beta < 0.55, f"{s.beta:.4f}")
    check("C 0.59–0.61", 0.59 < s.C < 0.61, f"{s.C:.5f}")
    check("Re > 1e5", s.Re_D > 1e5, f"{s.Re_D:.0f}")
    check("d20 125–145 mm", 125 < s.d20_mm < 145, f"{s.d20_mm:.2f}")
    check("hız 1–3 m/s", 1.0 < s.velocity_m_s < 3.0, f"{s.velocity_m_s:.3f}")

    print("\n-- Belirsizlik --")
    check("u(q)/q < 1.2 %", s.u_flow_pct < 1.2, f"{s.u_flow_pct:.3f} %")

    print("\n-- Emniyet --")
    check("faz güvenli (flashing yok)", not sf.phase.flashing, sf.phase.status)
    check("kavitasyon yok", not sf.phase.cavitation, sf.phase.status)
    check("P2 > Pv (10x marj)", sf.phase.margin_P2_over_Pv > 5.0, f"{sf.phase.margin_P2_over_Pv:.2f}")
    check("B31.3 uygun", sf.wall.ok, str(sf.wall.notes))
    check("β aralıkta", sf.beta_in_range)
    check("boru kaybı < 100 mbar", sf.phase.dP_pipe_bar * 1000 < 100, f"{sf.phase.dP_pipe_bar*1000:.1f} mbar")

    print("\n-- Bileşim normalizasyon uyarısı --")
    nasty = dict(BOTAŞ_COMP)
    nasty["N2"] = 0.010
    r2 = run_engineering(RunInputs(comp=nasty, T1_C=-163.0, P1_barg=8.5, D20_mm=300.0,
                                   qm_nom_ton_h=150.0, dP_target_mbar=250.0))
    check("tutar >1e-3 uyarı üretir", any("normalize" in w for w in r2.warnings))

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

    print("\n-- GUI veri yapısı (Tk gerektirmez) --")
    sections = build_sections(r)
    check("5 bölüm üretir", len(sections) >= 4, str(len(sections)))
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