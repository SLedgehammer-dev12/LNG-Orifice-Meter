"""Birim dönüşüm doğrulama testleri. Çalıştır: python3 test_units.py"""

from __future__ import annotations

import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

from units import verify_conversions, default_unit, from_canonical, to_canonical

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
    print("\n-- Yerleşik doğrulama (verify_conversions) --")
    errs = verify_conversions()
    check("tüm referans/roundtrip kontrolleri", not errs, "; ".join(errs[:3]))

    print("\n-- Kritik çarpanlar --")
    check("1 in = 25.4 mm", abs(from_canonical(25.4, "in", "diameter") - 1.0) < 1e-9)
    check("1 ft = 0.3048 m", abs(from_canonical(0.3048, "ft", "length") - 1.0) < 1e-9)
    check("1 bar-g = 1.01325 bar-a", abs(from_canonical(2.01325, "bar-g", "pressure") - 1.0) < 1e-9)
    check("0 °C = 32 °F", abs(from_canonical(0.0, "°F", "temperature") - 32.0) < 1e-9)
    check("-40 °C = -40 °F", abs(from_canonical(-40.0, "°F", "temperature") + 40.0) < 1e-9)
    check("250 mbar = 3.6259 psi", abs(from_canonical(250.0, "psi", "dp") - 250.0 / 68.947572932) < 1e-6)
    check("100 °C = 212 °F", abs(from_canonical(100.0, "°F", "temperature") - 212.0) < 1e-9)

    print("\n-- Basınç gösterge/mutlak --")
    check("psi-g -> bar-g doğru", abs(to_canonical(14.5038, "psi-g", "pressure") - 2.01325) < 1e-4)

    print("\n-- Hacimsel debi (yoğunluk bağımlı) --")
    c = {"rho_kgm3": 450.0}
    v = from_canonical(4.5, "m³/h (sıvı)", "mass_flow", c)
    check("4.5 t/h @450 kg/m³ = 10 m³/h", abs(v - 10.0) < 1e-9)

    print("\n-- Enerji akışı (GCV bağımlı) --")
    c = {"gcv_mj_kg": 50.0}
    t_h = from_canonical(150.0 * 1000.0 * 50.0 / 3600.0, "t/h (GCV)", "energy_flow", c)
    check("150 t/h @GCV50 = 150 t/h (display)", abs(t_h - 150.0) < 1e-6)

    print("\n-- Isıl değer (molar kütle bağımlı) --")
    c = {"M_mix_kg_kmol": 17.0}
    mj_kmol = from_canonical(50.0, "MJ/kmol", "heating_value", c)
    check("50 MJ/kg @M17 = 850 MJ/kmol", abs(mj_kmol - 850.0) < 1e-9)

    print("\n-- Profil varsayılanları --")
    check("SI sıcaklık °C", default_unit("temperature", "SI") == "°C", default_unit("temperature", "SI"))
    check("US basınç psi-g", default_unit("pressure", "US") == "psi-g", default_unit("pressure", "US"))
    check("SI debi t/h", default_unit("mass_flow", "SI") == "t/h")
    check("US debi lb/h", default_unit("mass_flow", "US") == "lb/h")
    check("SI ΔP mbar", default_unit("dp", "SI") == "mbar")
    check("US ΔP psi", default_unit("dp", "US") == "psi")

    print("\n-- Formatlama --")
    s = from_canonical(300.0, "in", "diameter")
    check("300 mm -> 11.81 in", abs(s - 11.8110) < 1e-3)

    print("=" * 62)
    print(f"  SONUÇ: {PASS} geçti, {FAIL} kaldı")
    print("=" * 62)
    raise SystemExit(1 if FAIL else 0)


if __name__ == "__main__":
    main()