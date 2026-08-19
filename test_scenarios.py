"""14 senaryoluk hesaplama doğrulama testi (v1.4.0 inceleme aracı).

Amacı: motorun geometrik, hidrolik, termodinamik, enerji ve emniyet
çıktılarını fiziksel tutarlılık ve senaryolar arası monotonluk açısından
denetlemek. Sonraki incelemelerde değişiklik sonrası yeniden çalıştırılabilir:
    python3 test_scenarios.py

Kapsam (14 senaryo):
  S1  temel (BOTAŞ, D304.79/Q150/dP250)      S8  N₂ zengin (%5)
  S2  küçük boru D200                         S9  ağır bileşim zengin
  S3  büyük boru D400                         S10 düşük P₁ (1 barg, yüksek ΔP)
  S4  yüksek debi Q300                        S11 yüksek P₁ (50 barg)
  S5  düşük debi Q50                          S12 β>0.75 sınırı (D100/Q300)
  S6  yüksek ΔP 1000 mbar                     S13 β<0.10 sınırı (D400/Q30/dP5000)
  S7  düşük ΔP 100 mbar                       S14 geniş turndown (0.10–1.50)
"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from engine import RunInputs, run_engineering

BOTAŞ = {
    "CH4": 0.915,
    "C2H6": 0.055,
    "C3H8": 0.018,
    "iC4": 0.004,
    "nC4": 0.004,
    "iC5": 0.001,
    "nC5": 0.001,
    "N2": 0.002,
}

ALPHA_1K = 16.0e-6

SCENARIOS = {
    "S1": {},
    "S2": {"D20_mm": 200.0},
    "S3": {"D20_mm": 400.0},
    "S4": {"qm_nom_ton_h": 300.0},
    "S5": {"qm_nom_ton_h": 50.0},
    "S6": {"dP_target_mbar": 1000.0},
    "S7": {"dP_target_mbar": 100.0},
    "S8": {"comp": {**BOTAŞ, "N2": 0.05, "CH4": 0.867}},
    "S9": {"comp": {**BOTAŞ, "C3H8": 0.06, "CH4": 0.873, "N2": 0.0}},
    "S10": {"P1_barg": 1.0, "dP_target_mbar": 900.0, "q_max_ratio": 1.4},
    "S11": {"P1_barg": 50.0, "T1_C": -150.0},
    "S12": {"D20_mm": 100.0, "qm_nom_ton_h": 300.0},
    "S13": {"D20_mm": 400.0, "qm_nom_ton_h": 30.0, "dP_target_mbar": 5000.0},
    "S14": {"q_min_ratio": 0.10, "q_max_ratio": 1.50},
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


def run(tag: str):
    kw = dict(comp=BOTAŞ, T1_C=-163.0, P1_barg=8.5, D20_mm=304.79,
              qm_nom_ton_h=150.0, dP_target_mbar=250.0,
              q_min_ratio=0.30, q_max_ratio=1.20)
    kw.update(SCENARIOS[tag])
    return run_engineering(RunInputs(**kw))


def main() -> None:
    res = {tag: run(tag) for tag in SCENARIOS}

    print("\n-- A. Geometrik tutarlılık --")
    for tag, r in res.items():
        s = r.sizing
        check(f"{tag}: dT = β·DT (işletme sıcaklığında)",
              abs(s.dT_mm - s.beta * s.DT_mm) < 1e-6,
              f"dT={s.dT_mm:.3f} β·DT={s.beta * s.DT_mm:.3f}")
        check(f"{tag}: d20 = dT/(1+α(T-20)) üretim çapı",
              abs(s.d20_mm - s.dT_mm / (1.0 + ALPHA_1K * (r.inputs.T1_C - 20.0))) < 1e-6,
              f"{s.d20_mm:.3f} vs {s.dT_mm / (1.0 + ALPHA_1K * (r.inputs.T1_C - 20.0)):.3f}")
        check(f"{tag}: 0 < d20 < D", 0.0 < s.d20_mm < s.D20_mm,
              f"d20={s.d20_mm:.2f} D={s.D20_mm:.2f}")
        check(f"{tag}: C fiziksel (0.59–0.78)", 0.59 < s.C < 0.78, f"C={s.C:.4f}")
        check(f"{tag}: Re_D > 0 ve hız > 0", s.Re_D > 0.0 and s.velocity_m_s > 0.0)

    print("\n-- B. ΔP ölçekleme (dP∝q²) --")
    for tag, r in res.items():
        inp = r.inputs
        check(f"{tag}: dPmax = hedef·qmax²",
              abs(r.sizing.dP_max_mbar - inp.dP_target_mbar * inp.q_max_ratio ** 2) < 1e-6,
              f"{r.sizing.dP_max_mbar:.1f}")
        check(f"{tag}: dPmin = hedef·qmin²",
              abs(r.sizing.dP_min_mbar - inp.dP_target_mbar * inp.q_min_ratio ** 2) < 1e-6,
              f"{r.sizing.dP_min_mbar:.2f}")

    print("\n-- C. Termodinamik / enerji tutarlılığı --")
    for tag, r in res.items():
        t, e, s = r.thermo, r.energy, r.sizing
        check(f"{tag}: ρ 400–520 kg/m³ (LNG)", 400.0 < t.rho_oper_kgm3 < 520.0,
              f"{t.rho_oper_kgm3:.1f}")
        check(f"{tag}: Pv > 0", t.Pv_final_bara > 0.0, f"{t.Pv_final_bara:.4f}")
        check(f"{tag}: GCV 48–56 MJ/kg", 48.0 < e.GCV_mj_kg < 56.0, f"{e.GCV_mj_kg:.3f}")
        check(f"{tag}: NCV < GCV", e.NCV_mj_kg < e.GCV_mj_kg)
        check(f"{tag}: GCV molar uyumu",
              abs(e.GCV_mj_kmol - e.GCV_mj_kg * t.M_mix) < 1e-6)
        check(f"{tag}: MW = qm·GCV", abs(e.MW_mj_s - s.qm_kg_s * e.GCV_mj_kg) < 1e-6,
              f"{e.MW_mj_s:.2f}")

    print("\n-- D. Senaryolar arası tutarlılık --")
    base = res["S1"]
    check("S1-S4-S5-S6-S7 aynı termo (ρ, Pv, GCV)",
          len({round(res[n].thermo.rho_oper_kgm3, 4) for n in ("S1", "S4", "S5", "S6", "S7")}) == 1
          and len({round(res[n].thermo.Pv_final_bara, 4) for n in ("S1", "S4", "S5", "S6", "S7")}) == 1)
    check("MW debiyle orantılı (S4=2×S1, S5=⅓×S1)",
          abs(res["S4"].energy.MW_mj_s - 2.0 * base.energy.MW_mj_s) < 1e-6
          and abs(res["S5"].energy.MW_mj_s - base.energy.MW_mj_s / 3.0) < 1e-6)
    check("β ΔP ile azalır (S7=100 > S1=250 > S6=1000 mbar)",
          res["S7"].sizing.beta > res["S1"].sizing.beta > res["S6"].sizing.beta)
    check("β D ile azalır (S2=200 > S3=400 mm)",
          res["S2"].sizing.beta > res["S3"].sizing.beta)
    check("N₂ zengin: Pv ve ρ artar",
          res["S8"].thermo.Pv_final_bara > base.thermo.Pv_final_bara
          and res["S8"].thermo.rho_oper_kgm3 > base.thermo.rho_oper_kgm3)
    check("Ağır bileşim: Pv azalır, ρ artar",
          res["S9"].thermo.Pv_final_bara < base.thermo.Pv_final_bara
          and res["S9"].thermo.rho_oper_kgm3 > base.thermo.rho_oper_kgm3)
    check("S14 turndown: dPmax↑ dPmin↓, aynı β",
          res["S14"].sizing.dP_max_mbar > base.sizing.dP_max_mbar
          and res["S14"].sizing.dP_min_mbar < base.sizing.dP_min_mbar
          and abs(res["S14"].sizing.beta - base.sizing.beta) < 1e-6)

    print("\n-- E. Emniyet bayrakları ve β sınır uyarıları --")
    check("S10 (düşük P₁): flashing + kavitasyon uyarısı",
          res["S10"].safety.phase.flashing and res["S10"].safety.phase.cavitation)
    check("S13: vena contracta kavitasyonu (ΔP@Qmax=7.2 bar), flashing yok",
          res["S13"].safety.phase.cavitation and not res["S13"].safety.phase.flashing)
    check("S12 β*>0.75: ISO üst sınır uyarısı",
          res["S12"].sizing.beta > 0.75
          and any("0.75" in w and "üst" in w for w in res["S12"].warnings))
    check("S13 β*<0.10: ISO alt sınır uyarısı",
          res["S13"].sizing.beta < 0.10
          and any("0.10" in w and "alt" in w for w in res["S13"].warnings))
    safe_tags = ("S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S11", "S14")
    check("Diğer senaryolarda faz bayrağı yok",
          all(not res[n].safety.phase.flashing and not res[n].safety.phase.cavitation
              for n in safe_tags))
    check("Tüm senaryolarda B31.3 kontrolü uygun",
          all(res[n].safety.wall.ok for n in res))

    print("=" * 62)
    print(f"  SONUÇ: {PASS} geçti, {FAIL} kaldı")
    print("=" * 62)
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
