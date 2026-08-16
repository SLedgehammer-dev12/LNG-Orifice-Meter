"""Birim katalogu, dönüşüm ve doğrulama katmanı.

Tasarım ilkesi: motor dosyaları (engine/orifice/thermo/safety) her zaman kanonik
birimlerde çalışır; bu modül GUI/rapor katmanında kullanıcı birimi ile kanonik
birim arasında köprüdür. Tkinter gerektirmez, headless test edilebilir.

Kanonik birimler:
  temperature      -> °C
  pressure         -> bar-a   (gauge birimler içinde mutlak değer kullanılır)
  diameter/length  -> mm / m
  mass_flow        -> ton/saat (hacimsel birimler ctx["rho_kgm3"] ile dönüştürülür)
  energy_flow      -> MW      (ctx["gcv_mj_kg"] ile kütlesel debiye çevrilir)
  dp               -> mbar
  density          -> kg/m³
  velocity         -> m/s
  heating_value    -> MJ/kg
  molar_mass       -> kg/kmol
  percent          -> kesir (0..1)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable

P_ATM_BAR = 1.01325
LNG_DENSITY_FALLBACK_KGM3 = 420.0
LNG_GCV_FALLBACK_MJ_KG = 50.0
MOLAR_VOLUME_NM3_PER_KMOL = 22.414  # ideal gaz, 0 °C / 1 atm

KIND_LINEAR = "linear"


@dataclass(frozen=True)
class UnitDef:
    symbol: str
    kind: str
    factor: float = 1.0          # display -> canonical (linear)
    offset: float = 0.0          # display -> canonical (linear ek)
    to: Callable[[float, dict], float] | None = None
    from_: Callable[[float, dict], float] | None = None

    def to_canonical(self, value: float, ctx: dict | None = None) -> float:
        if self.to is not None:
            return self.to(value, ctx or {})
        return value * self.factor + self.offset

    def from_canonical(self, value: float, ctx: dict | None = None) -> float:
        if self.from_ is not None:
            return self.from_(value, ctx or {})
        return (value - self.offset) / self.factor


def _linear(symbol: str, factor: float, offset: float = 0.0) -> UnitDef:
    return UnitDef(symbol=symbol, kind=KIND_LINEAR, factor=factor, offset=offset)


# --- Sıcaklık ---------------------------------------------------------------
_TEMPERATURE: dict[str, UnitDef] = {
    "°C": _linear("°C", 1.0, 0.0),
    "°F": _linear("°F", 1.0 / 1.8, -32.0 / 1.8),
    "K": _linear("K", 1.0, -273.15),
    "°R": _linear("°R", 1.0 / 1.8, -273.15 - 32.0 / 1.8),
}

# --- Basınç (kanonik: bar-a) ------------------------------------------------
_PRESSURE: dict[str, UnitDef] = {
    "bar-a": _linear("bar-a", 1.0, 0.0),
    "bar-g": _linear("bar-g", 1.0, P_ATM_BAR),
    "kPa-a": _linear("kPa-a", 1.0 / 100.0, 0.0),
    "kPa-g": _linear("kPa-g", 1.0 / 100.0, P_ATM_BAR),
    "MPa-a": _linear("MPa-a", 10.0, 0.0),
    "MPa-g": _linear("MPa-g", 10.0, P_ATM_BAR),
    "psi-a": _linear("psi-a", 1.0 / 14.503773773, 0.0),
    "psi-g": _linear("psi-g", 1.0 / 14.503773773, P_ATM_BAR),
    "kg/cm²": _linear("kg/cm²", 0.980665, 0.0),
    "atm": _linear("atm", P_ATM_BAR, 0.0),
}

# --- Çap / uzunluk -----------------------------------------------------------
_DIAMETER: dict[str, UnitDef] = {
    "mm": _linear("mm", 1.0, 0.0),
    "cm": _linear("cm", 10.0, 0.0),
    "m": _linear("m", 1000.0, 0.0),
    "in": _linear("in", 25.4, 0.0),
    "ft": _linear("ft", 304.8, 0.0),
}

_LENGTH: dict[str, UnitDef] = {
    "m": _linear("m", 1.0, 0.0),
    "km": _linear("km", 1000.0, 0.0),
    "ft": _linear("ft", 0.3048, 0.0),
    "in": _linear("in", 0.0254, 0.0),
}

# --- Kütlesel + hacimsel debi (kanonik: ton/saat) ----------------------------
def _m3h_to_ton_h(value: float, ctx: dict) -> float:
    return value * ctx.get("rho_kgm3", LNG_DENSITY_FALLBACK_KGM3) / 1000.0


def _ton_h_to_m3h(value: float, ctx: dict) -> float:
    rho = ctx.get("rho_kgm3", LNG_DENSITY_FALLBACK_KGM3)
    return value * 1000.0 / rho if rho > 0 else float("nan")


def _lmin_to_ton_h(value: float, ctx: dict) -> float:
    return _m3h_to_ton_h(value * 60.0, ctx)


def _ton_h_to_lmin(value: float, ctx: dict) -> float:
    return _ton_h_to_m3h(value, ctx) / 60.0


def _gpm_to_ton_h(value: float, ctx: dict) -> float:
    return _m3h_to_ton_h(value * 0.227124707, ctx)


def _ton_h_to_gpm(value: float, ctx: dict) -> float:
    return _ton_h_to_m3h(value, ctx) / 0.227124707


def _ft3h_to_ton_h(value: float, ctx: dict) -> float:
    return _m3h_to_ton_h(value * 0.0283168466, ctx)


def _ton_h_to_ft3h(value: float, ctx: dict) -> float:
    return _ton_h_to_m3h(value, ctx) / 0.0283168466


_MASS_FLOW: dict[str, UnitDef] = {
    "t/h": _linear("t/h", 1.0, 0.0),
    "kg/h": _linear("kg/h", 1.0 / 1000.0, 0.0),
    "kg/s": _linear("kg/s", 3.6, 0.0),
    "lb/h": _linear("lb/h", 0.00045359237, 0.0),
    "m³/h (sıvı)": UnitDef("m³/h (sıvı)", "flow_vol", to=_m3h_to_ton_h, from_=_ton_h_to_m3h),
    "L/min": UnitDef("L/min", "flow_vol", to=_lmin_to_ton_h, from_=_ton_h_to_lmin),
    "gpm": UnitDef("gpm", "flow_vol", to=_gpm_to_ton_h, from_=_ton_h_to_gpm),
    "ft³/h": UnitDef("ft³/h", "flow_vol", to=_ft3h_to_ton_h, from_=_ton_h_to_ft3h),
}

# --- Enerji akışı (kanonik: MW) ----------------------------------------------
def _mw_to_ton_h(value: float, ctx: dict) -> float:
    gcv = ctx.get("gcv_mj_kg", LNG_GCV_FALLBACK_MJ_KG)
    if gcv <= 0:
        return float("nan")
    return value * 3600.0 / gcv / 1000.0


def _ton_h_to_mw(value: float, ctx: dict) -> float:
    return value * 1000.0 * ctx.get("gcv_mj_kg", LNG_GCV_FALLBACK_MJ_KG) / 3600.0


def _mmbtu_h_to_mw(value: float, ctx: dict) -> float:
    return value * 0.2930710702


def _mw_to_mmbtu_h(value: float, ctx: dict) -> float:
    return value / 0.2930710702


_ENERGY_FLOW: dict[str, UnitDef] = {
    "MW": UnitDef("MW", "energy", to=lambda v, c: v, from_=lambda v, c: v),
    "kW": _linear("kW", 1.0 / 1000.0, 0.0),
    "GJ/h": _linear("GJ/h", 1000.0 / 3600.0, 0.0),
    "MMBtu/h": UnitDef("MMBtu/h", "energy", to=_mmbtu_h_to_mw, from_=_mw_to_mmbtu_h),
    "t/h (GCV)": UnitDef("t/h (GCV)", "energy", to=_ton_h_to_mw, from_=_mw_to_ton_h),
}

# --- Deb girişi: kütle + enerji akışı (kanonik: ton/saat) --------------------
def _kw_to_ton_h(value: float, ctx: dict) -> float:
    return _mw_to_ton_h(value / 1000.0, ctx)


def _ton_h_to_kw(value: float, ctx: dict) -> float:
    return _ton_h_to_mw(value, ctx) * 1000.0


def _gjh_to_ton_h(value: float, ctx: dict) -> float:
    return _mw_to_ton_h(value * 1000.0 / 3600.0, ctx)


def _ton_h_to_gjh(value: float, ctx: dict) -> float:
    return _ton_h_to_mw(value, ctx) * 3600.0 / 1000.0


_FLOW: dict[str, UnitDef] = dict(_MASS_FLOW)
_FLOW.update({
    "MW": UnitDef("MW", "flow_energy", to=_mw_to_ton_h, from_=_ton_h_to_mw),
    "kW": UnitDef("kW", "flow_energy", to=_kw_to_ton_h, from_=_ton_h_to_kw),
    "GJ/h": UnitDef("GJ/h", "flow_energy", to=_gjh_to_ton_h, from_=_ton_h_to_gjh),
    "MMBtu/h": UnitDef("MMBtu/h", "flow_energy", to=lambda v, c: _mw_to_ton_h(_mmbtu_h_to_mw(v, c), c),
                       from_=lambda v, c: _mw_to_mmbtu_h(_ton_h_to_mw(v, c), c)),
    "t/h (GCV)": UnitDef("t/h (GCV)", "flow_energy", to=_ton_h_to_mw, from_=_mw_to_ton_h),
})

# --- Diferansiyel basınç (kanonik: mbar) -------------------------------------
_DP: dict[str, UnitDef] = {
    "mbar": _linear("mbar", 1.0, 0.0),
    "bar": _linear("bar", 1000.0, 0.0),
    "kPa": _linear("kPa", 10.0, 0.0),
    "Pa": _linear("Pa", 0.01, 0.0),
    "psi": _linear("psi", 68.947572932, 0.0),
    "mmH₂O": _linear("mmH₂O", 0.0980665, 0.0),
    "inH₂O": _linear("inH₂O", 2.49082, 0.0),
    "kgf/cm²": _linear("kgf/cm²", 980.665, 0.0),
}

# --- Yoğunluk (kanonik: kg/m³) ----------------------------------------------
_DENSITY: dict[str, UnitDef] = {
    "kg/m³": _linear("kg/m³", 1.0, 0.0),
    "kg/L": _linear("kg/L", 1000.0, 0.0),
    "g/cm³": _linear("g/cm³", 1000.0, 0.0),
    "lb/ft³": _linear("lb/ft³", 16.01846337, 0.0),
}

# --- Hız (kanonik: m/s) ------------------------------------------------------
_VELOCITY: dict[str, UnitDef] = {
    "m/s": _linear("m/s", 1.0, 0.0),
    "ft/s": _linear("ft/s", 0.3048, 0.0),
    "km/h": _linear("km/h", 1.0 / 3.6, 0.0),
}

# --- Isıl değer (kanonik: MJ/kg) ---------------------------------------------
def _mj_kg_to_mj_kmol(value: float, ctx: dict) -> float:
    m = ctx.get("M_mix_kg_kmol", 17.0)
    return value * m


def _mj_kmol_to_mj_kg(value: float, ctx: dict) -> float:
    m = ctx.get("M_mix_kg_kmol", 17.0)
    return value / m if m > 0 else float("nan")


def _mj_kg_to_mj_nm3(value: float, ctx: dict) -> float:
    m = ctx.get("M_mix_kg_kmol", 17.0)
    return value * m / MOLAR_VOLUME_NM3_PER_KMOL


def _mj_nm3_to_mj_kg(value: float, ctx: dict) -> float:
    m = ctx.get("M_mix_kg_kmol", 17.0)
    return value * MOLAR_VOLUME_NM3_PER_KMOL / m if m > 0 else float("nan")


_HEATING_VALUE: dict[str, UnitDef] = {
    "MJ/kg": _linear("MJ/kg", 1.0, 0.0),
    "kWh/kg": _linear("kWh/kg", 3.6, 0.0),
    "MJ/kmol": UnitDef("MJ/kmol", "hv", to=_mj_kmol_to_mj_kg, from_=_mj_kg_to_mj_kmol),
    "MJ/Nm³": UnitDef("MJ/Nm³", "hv", to=_mj_nm3_to_mj_kg, from_=_mj_kg_to_mj_nm3),
    "Btu/lb": _linear("Btu/lb", 0.002326, 0.0),
}

# --- Molar kütle (kanonik: kg/kmol) -------------------------------------------
_MOLAR_MASS: dict[str, UnitDef] = {
    "kg/kmol": _linear("kg/kmol", 1.0, 0.0),
    "g/mol": _linear("g/mol", 1.0, 0.0),
    "lb/lbmol": _linear("lb/lbmol", 1.0, 0.0),
}

# --- Güç / pompa kaybı (kanonik: kW) ----------------------------------------
_POWER: dict[str, UnitDef] = {
    "kW": _linear("kW", 1.0, 0.0),
    "W": _linear("W", 1.0 / 1000.0, 0.0),
    "MW": _linear("MW", 1000.0, 0.0),
    "hp": _linear("hp", 0.745699872, 0.0),
}

# --- Yüzde / kesir (kanonik: kesir) -------------------------------------------
_PERCENT: dict[str, UnitDef] = {
    "%": _linear("%", 1.0 / 100.0, 0.0),
}

# --- Boyutsuz sayı ------------------------------------------------------------
_NUMBER: dict[str, UnitDef] = {
    "": _linear("", 1.0, 0.0),
}

CATALOG: dict[str, dict[str, UnitDef]] = {
    "temperature": _TEMPERATURE,
    "pressure": _PRESSURE,
    "diameter": _DIAMETER,
    "length": _LENGTH,
    "mass_flow": _MASS_FLOW,
    "flow": _FLOW,
    "energy_flow": _ENERGY_FLOW,
    "power": _POWER,
    "dp": _DP,
    "density": _DENSITY,
    "velocity": _VELOCITY,
    "heating_value": _HEATING_VALUE,
    "molar_mass": _MOLAR_MASS,
    "percent": _PERCENT,
    "number": _NUMBER,
}

# Kategorilerin doğal (kanonik) sembolü
CANONICAL_UNIT: dict[str, str] = {
    "temperature": "°C",
    "pressure": "bar-a",
    "diameter": "mm",
    "length": "m",
    "mass_flow": "t/h",
    "flow": "t/h",
    "energy_flow": "MW",
    "power": "kW",
    "dp": "mbar",
    "density": "kg/m³",
    "velocity": "m/s",
    "heating_value": "MJ/kg",
    "molar_mass": "kg/kmol",
    "percent": "%",
    "number": "",
}

# Kanonik birimden bağımsız olarak kullanıcıya sunulacak girdi birimleri
PRESETS: dict[str, dict[str, str]] = {
    "SI": {
        "temperature": "°C",
        "pressure": "bar-g",
        "diameter": "mm",
        "length": "m",
        "flow": "t/h",
        "mass_flow": "t/h",
        "energy_flow": "MW",
        "power": "kW",
        "dp": "mbar",
        "density": "kg/m³",
        "velocity": "m/s",
        "heating_value": "MJ/kg",
        "molar_mass": "kg/kmol",
    },
    "US": {
        "temperature": "°F",
        "pressure": "psi-g",
        "diameter": "in",
        "length": "ft",
        "flow": "lb/h",
        "mass_flow": "lb/h",
        "energy_flow": "MMBtu/h",
        "power": "hp",
        "dp": "psi",
        "density": "lb/ft³",
        "velocity": "ft/s",
        "heating_value": "Btu/lb",
        "molar_mass": "lb/lbmol",
    },
}
PRESETS["Karışık"] = dict(PRESETS["SI"])

PRESET_NAMES: tuple[str, ...] = ("SI", "US", "Karışık")


def unit_options(category: str) -> list[str]:
    return list(CATALOG.get(category, {}).keys())


def default_unit(category: str, preset: str = "SI") -> str:
    if category == "mass_flow":
        return "t/h" if preset == "SI" else "lb/h"
    if category == "flow":
        return "t/h" if preset == "SI" else "lb/h"
    if category == "number":
        return ""
    return PRESETS.get(preset, PRESETS["SI"]).get(category, CANONICAL_UNIT.get(category, ""))


def to_canonical(value: float, unit: str, category: str, ctx: dict | None = None) -> float:
    u = CATALOG[category].get(unit)
    if u is None:
        raise ValueError(f"Bilinmeyen birim '{unit}' için kategori '{category}'")
    return u.to_canonical(value, ctx)


def from_canonical(value: float, unit: str, category: str, ctx: dict | None = None) -> float:
    u = CATALOG[category].get(unit)
    if u is None:
        raise ValueError(f"Bilinmeyen birim '{unit}' için kategori '{category}'")
    return u.from_canonical(value, ctx)


def convert(value: float, from_unit: str, to_unit: str, category: str, ctx: dict | None = None) -> float:
    return from_canonical(to_canonical(value, from_unit, category, ctx), to_unit, category, ctx)


# Formatlama
DIGITS: dict[str, int] = {
    "temperature": 1,
    "pressure": 2,
    "diameter": 3,
    "length": 2,
    "mass_flow": 2,
    "energy_flow": 3,
    "power": 2,
    "dp": 1,
    "density": 2,
    "velocity": 3,
    "heating_value": 3,
    "molar_mass": 3,
    "percent": 0,
    "number": 4,
}


def format_number(value: float, category: str, unit: str = "", digits: int | None = None) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "–"
    nd = DIGITS.get(category, 4) if digits is None else digits
    if category == "number":
        if unit == "" and abs(value) >= 1000:
            return f"{value:,.0f}"
        return f"{value:.{nd}f}"
    txt = f"{value:.{nd}f}"
    if unit:
        txt = f"{txt} {unit}"
    return txt


def format_canonical(value: float, category: str, unit: str | None = None, ctx: dict | None = None,
                     digits: int | None = None) -> str:
    """Kanonik değeri seçilen (ya da kategori kanonik) birimde biçimlendirir."""
    u = unit or CANONICAL_UNIT.get(category, "")
    disp = from_canonical(value, u, category, ctx) if category != "number" else value
    nd = DIGITS.get(category, 4) if digits is None else digits
    if category == "number":
        if u == "" and abs(disp) >= 1000:
            return f"{disp:,.0f}"
        return f"{disp:.{nd}f}"
    txt = f"{disp:.{nd}f}"
    return f"{txt} {u}"


# --- Otomatik doğrulama -------------------------------------------------------
def _ref_check(name: str, got: float, expected: float, tol_rel: float = 1e-6) -> list[str]:
    if math.isnan(got) or math.isnan(expected):
        return [f"{name}: NaN üretildi"]
    if abs(got) < 1e-12:
        ok = abs(got - expected) < 1e-9
    else:
        ok = abs(got - expected) / max(abs(expected), 1e-12) < tol_rel
    return [] if ok else [f"{name}: beklenen {expected:.8g}, alınan {got:.8g}"]


def verify_conversions(ctx: dict | None = None) -> list[str]:
    """Tüm birimler için dönüşüm doğrulaması. Hata listesi döner (boş = sorun yok)."""
    c = ctx or {}
    errs: list[str] = []

    for category, table in CATALOG.items():
        for unit, ud in table.items():
            for v in (0.0, 1.0, 25.0, 100.0, 1234.5):
                try:
                    back = ud.from_canonical(ud.to_canonical(v, c), c)
                    errs += _ref_check(f"roundtrip {category}/{unit} (v={v})", back, v, 1e-9)
                except (ZeroDivisionError, OverflowError, ValueError) as e:  # noqa: BLE001
                    errs.append(f"roundtrip {category}/{unit} (v={v}): {e}")

    # Referans sabitler (to_canonical: kullanıcı birimi -> kanonik)
    errs += _ref_check("32 °F -> °C", to_canonical(32.0, "°F", "temperature"), 0.0)
    errs += _ref_check("212 °F -> °C", to_canonical(212.0, "°F", "temperature"), 100.0)
    errs += _ref_check("-40 °F -> °C", to_canonical(-40.0, "°F", "temperature"), -40.0)
    errs += _ref_check("273.15 K -> °C", to_canonical(273.15, "K", "temperature"), 0.0)
    errs += _ref_check("1 in -> mm", to_canonical(1.0, "in", "diameter"), 25.4)
    errs += _ref_check("100 kPa-a -> bar-a", to_canonical(100.0, "kPa-a", "pressure"), 1.0)
    errs += _ref_check("1 bar-g -> bar-a", to_canonical(1.0, "bar-g", "pressure"), 2.01325)
    errs += _ref_check("14.5038 psi-a -> bar-a", to_canonical(14.5038, "psi-a", "pressure"), 1.0, 1e-5)
    errs += _ref_check("2.5 kPa -> mbar", to_canonical(2.5, "kPa", "dp"), 25.0)
    errs += _ref_check("1 MPa-a -> bar-a", to_canonical(1.0, "MPa-a", "pressure"), 10.0)
    errs += _ref_check("310.93 K -> °F", to_canonical(310.9277777, "K", "temperature"), 37.7777777, 1e-5)
    errs += _ref_check("1000 kg/h -> t/h", to_canonical(1000.0, "kg/h", "mass_flow"), 1.0)
    errs += _ref_check("2204.6 lb/h -> t/h", to_canonical(2204.62262185, "lb/h", "mass_flow"), 1.0)
    errs += _ref_check("1 ft -> m", to_canonical(1.0, "ft", "length"), 0.3048)
    errs += _ref_check("1 lb/ft³ -> kg/m³", to_canonical(1.0, "lb/ft³", "density"), 16.01846337, 1e-5)
    errs += _ref_check("3.6 km/h -> m/s", to_canonical(3.6, "km/h", "velocity"), 1.0)
    errs += _ref_check("1 Btu/lb -> MJ/kg", to_canonical(1.0, "Btu/lb", "heating_value"), 0.002326)
    errs += _ref_check("1 kWh/kg -> MJ/kg", to_canonical(1.0, "kWh/kg", "heating_value"), 3.6)
    errs += _ref_check("1 MMBtu/h -> MW", to_canonical(1.0, "MMBtu/h", "energy_flow"), 0.2930710702, 1e-4)
    errs += _ref_check("1 hp -> kW", to_canonical(1.0, "hp", "power"), 0.745699872, 1e-6)
    errs += _ref_check("1 atm -> bar-a", to_canonical(1.0, "atm", "pressure"), 1.01325)

    # Çapraz yol tutarlılığı: 250 mbar -> Pa -> psi -> mbar aynı değere dönmeli
    try:
        via = convert(convert(convert(250.0, "mbar", "Pa", "dp"), "Pa", "psi", "dp"), "psi", "mbar", "dp")
        errs += _ref_check("dp zinciri 250 mbar -> psi -> mbar", via, 250.0, 1e-9)
    except Exception as e:  # noqa: BLE001
        errs.append(f"dp zinciri: {e}")

    # Hacimsel debi: yoğunluk bağımlılığı
    c1 = {"rho_kgm3": 450.0}
    m3h = to_canonical(10.0, "m³/h (sıvı)", "mass_flow", c1)
    errs += _ref_check("10 m³/h @450 -> t/h", m3h, 4.5)
    back = from_canonical(m3h, "m³/h (sıvı)", "mass_flow", c1)
    errs += _ref_check("hacimsel debi roundtrip", back, 10.0, 1e-9)

    # Enerji akışı: GCV bağımlılığı
    c2 = {"gcv_mj_kg": 50.0}
    mw = to_canonical(10.0, "t/h (GCV)", "energy_flow", c2)
    errs += _ref_check("10 t/h @GCV50 -> MW", mw, 10.0 * 1000.0 * 50.0 / 3600.0, 1e-9)

    # Isıl değer: molar kütle bağımlılığı
    c3 = {"M_mix_kg_kmol": 17.0}
    mj_kmol = from_canonical(50.0, "MJ/kmol", "heating_value", c3)
    errs += _ref_check("50 MJ/kg @M17 -> MJ/kmol", mj_kmol, 850.0)
    mj_nm3 = from_canonical(50.0, "MJ/Nm³", "heating_value", c3)
    errs += _ref_check("50 MJ/kg @M17 -> MJ/Nm³", mj_nm3, 850.0 / MOLAR_VOLUME_NM3_PER_KMOL, 1e-9)

    return errs
