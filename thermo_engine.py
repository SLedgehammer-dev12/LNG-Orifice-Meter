"""Kriyojenik termofiziksel hesap motoru (Peng-Robinson EOS, Klosek-Zander, Antoine/Raoult)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

COMPONENTS: tuple[str, ...] = ("CH4", "C2H6", "C3H8", "iC4", "nC4", "iC5", "nC5", "N2")

MOLAR_MASS: dict[str, float] = {
    "CH4": 16.043,
    "C2H6": 30.070,
    "C3H8": 44.097,
    "iC4": 58.123,
    "nC4": 58.123,
    "iC5": 72.150,
    "nC5": 72.150,
    "N2": 28.013,
}

TCRIT_K: dict[str, float] = {
    "CH4": 190.564,
    "C2H6": 305.320,
    "C3H8": 369.830,
    "iC4": 407.800,
    "nC4": 425.120,
    "iC5": 460.430,
    "nC5": 469.700,
    "N2": 126.190,
}

PCRIT_BAR: dict[str, float] = {
    "CH4": 45.990,
    "C2H6": 48.720,
    "C3H8": 42.480,
    "iC4": 36.400,
    "nC4": 37.960,
    "iC5": 33.800,
    "nC5": 33.700,
    "N2": 33.980,
}

ACENTRIC: dict[str, float] = {
    "CH4": 0.011,
    "C2H6": 0.099,
    "C3H8": 0.152,
    "iC4": 0.181,
    "nC4": 0.200,
    "iC5": 0.227,
    "nC5": 0.251,
    "N2": 0.037,
}

VCRIT_M3_KMOL: dict[str, float] = {
    "CH4": 0.0991,
    "C2H6": 0.1457,
    "C3H8": 0.2002,
    "iC4": 0.2627,
    "nC4": 0.2554,
    "iC5": 0.3060,
    "nC5": 0.3135,
    "N2": 0.0894,
}

ANTONIE: dict[str, tuple[float, float, float]] = {
    "CH4": (3.9895, 443.013, -0.49),
    "C2H6": (4.0932, 687.165, -12.11),
    "C3H8": (4.0583, 808.921, -25.26),
    "iC4": (4.0087, 882.800, -30.00),
    "nC4": (4.0026, 935.860, -23.86),
    "iC5": (3.9766, 1024.70, -32.84),
    "nC5": (3.9893, 1064.84, -33.30),
    "N2": (3.7362, 255.680, -6.47),
}

K_IJ: dict[tuple[str, str], float] = {
    ("N2", "CH4"): 0.031,
    ("N2", "C2H6"): 0.051,
    ("N2", "C3H8"): 0.085,
    ("N2", "iC4"): 0.103,
    ("N2", "nC4"): 0.080,
    ("N2", "iC5"): 0.092,
    ("N2", "nC5"): 0.090,
    ("CH4", "C2H6"): 0.003,
    ("CH4", "C3H8"): 0.011,
    ("CH4", "nC4"): 0.019,
    ("CH4", "nC5"): 0.028,
    ("C2H6", "C3H8"): 0.001,
    ("C3H8", "nC4"): 0.002,
}

KZ_TABLE: list[tuple[float, float, float]] = [
    (16.03, 0.000170, 0.000210),
    (17.00, 0.000180, 0.000220),
    (18.00, 0.000195, 0.000240),
    (19.00, 0.000210, 0.000260),
    (20.60, 0.000230, 0.000280),
]

R_GAS: float = 0.08314466
LIQUID_COMPRESS_1_PER_BAR: float = 2.2e-4
VISCOSITY_DEFAULT_PA_S: float = 0.00012
ANTONIE_NBP_WARNING_BELOW_K: float = 160.0


class ThermoError(ValueError):
    pass


def normalize_composition(comp: dict[str, float]) -> tuple[dict[str, float], list[str]]:
    missing = [c for c in COMPONENTS if c not in comp]
    if missing:
        raise ThermoError("Eksik bileşen: " + ", ".join(missing))
    total = sum(comp[c] for c in COMPONENTS)
    if total <= 0.0:
        raise ThermoError("Bileşim toplamı pozitif olmalıdır.")
    warnings: list[str] = []
    if abs(total - 1.0) > 1e-3:
        warnings.append(
            f"Bileşim toplamı {total:.4f}; 1.0000'e normalize edildi "
            "(kromatograf verisi tutarsız olabilir)."
        )
    return {c: comp[c] / total for c in COMPONENTS}, warnings


def molar_mass(comp: dict[str, float]) -> float:
    return sum(x * MOLAR_MASS[c] for c, x in comp.items())


def antoine_psat(c: str, T_K: float) -> float:
    a, b, cc = ANTONIE[c]
    return 10.0 ** (a - b / (T_K + cc))


def raoult_bubble(comp: dict[str, float], T_K: float) -> float:
    return sum(x * antoine_psat(c, T_K) for c, x in comp.items())


def kz_constants(M_mix: float) -> tuple[float, float]:
    if M_mix <= KZ_TABLE[0][0]:
        return KZ_TABLE[0][1], KZ_TABLE[0][2]
    if M_mix >= KZ_TABLE[-1][0]:
        return KZ_TABLE[-1][1], KZ_TABLE[-1][2]
    for (m0, k0a, k0b), (m1, k1a, k1b) in zip(KZ_TABLE, KZ_TABLE[1:]):
        if m0 <= M_mix <= m1:
            f = (M_mix - m0) / (m1 - m0)
            return k0a + f * (k1a - k0a), k0b + f * (k1b - k0b)
    return KZ_TABLE[-1][1], KZ_TABLE[-1][2]


def rackett_vsat(c: str, T_K: float) -> float:
    Tr = T_K / TCRIT_K[c]
    if Tr >= 1.0:
        return VCRIT_M3_KMOL[c]
    zc = 0.29056 - 0.08775 * ACENTRIC[c]
    return VCRIT_M3_KMOL[c] * zc ** ((1.0 - Tr) ** (2.0 / 7.0))


def klosek_zander_rho(comp: dict[str, float], T_K: float) -> float:
    M_mix = molar_mass(comp)
    v_ideal = sum(x * rackett_vsat(c, T_K) for c, x in comp.items())
    x_n2 = comp["N2"]
    x_ch4 = comp["CH4"]
    k1, k2 = kz_constants(M_mix)
    if x_n2 > 0.0:
        v_corr = (k1 + (k2 - k1) * (x_n2 / 0.0425)) * x_ch4
    else:
        v_corr = k1 * x_ch4
    v_m = v_ideal - v_corr
    return M_mix / v_m


def _cbrt(x: float) -> float:
    return math.copysign(abs(x) ** (1.0 / 3.0), x)


def cubic_roots(p: float, q: float, r: float) -> list[float]:
    qq = (3.0 * q - p * p) / 9.0
    rr = (9.0 * p * q - 27.0 * r - 2.0 * p ** 3) / 54.0
    dd = qq ** 3 + rr ** 2
    if dd > 1e-12:
        sq = math.sqrt(dd)
        s = _cbrt(rr + sq)
        t = _cbrt(rr - sq)
        return [s + t - p / 3.0]
    arg = rr / math.sqrt(max(-qq ** 3, 1e-300))
    theta = math.acos(max(-1.0, min(1.0, arg)))
    m = 2.0 * math.sqrt(-qq)
    return sorted(
        [
            m * math.cos(theta / 3.0) - p / 3.0,
            m * math.cos((theta + 2.0 * math.pi) / 3.0) - p / 3.0,
            m * math.cos((theta + 4.0 * math.pi) / 3.0) - p / 3.0,
        ]
    )


def _kij(a: str, b: str) -> float:
    if a == b:
        return 0.0
    return K_IJ.get((a, b), K_IJ.get((b, a), 0.0))


def _pr_a_b(T_K: float) -> tuple[dict[str, float], dict[str, float]]:
    a: dict[str, float] = {}
    b: dict[str, float] = {}
    for i in COMPONENTS:
        tc, pc, w = TCRIT_K[i], PCRIT_BAR[i], ACENTRIC[i]
        a[i] = (
            0.45724
            * R_GAS ** 2
            * tc ** 2
            / pc
            * (1.0 + (0.37464 + 1.54226 * w - 0.26992 * w ** 2) * (1.0 - math.sqrt(T_K / tc))) ** 2
        )
        b[i] = 0.07780 * R_GAS * tc / pc
    return a, b


def _mixing(a: dict[str, float], b: dict[str, float], z: dict[str, float]) -> tuple[float, float]:
    a_m = 0.0
    for i in COMPONENTS:
        for j in COMPONENTS:
            a_m += z[i] * z[j] * (1.0 - _kij(i, j)) * math.sqrt(a[i] * a[j])
    b_m = sum(z[i] * b[i] for i in COMPONENTS)
    return a_m, b_m


def pr_compressibility(T_K: float, P_bar: float, z: dict[str, float]):
    a, b = _pr_a_b(T_K)
    a_m, b_m = _mixing(a, b, z)
    A = a_m * P_bar / (R_GAS ** 2 * T_K ** 2)
    B = b_m * P_bar / (R_GAS * T_K)
    roots = cubic_roots(
        -(1.0 - B), A - 3.0 * B * B - 2.0 * B, -(A * B - B * B - B ** 3)
    )
    return roots, a, b, a_m, b_m, A, B


def pr_fugacity(T_K: float, P_bar: float, z: dict[str, float], phase: str) -> dict[str, float]:
    roots, a, b, a_m, b_m, A, B = pr_compressibility(T_K, P_bar, z)
    if len(roots) >= 2:
        Z = min(roots) if phase == "liquid" else max(roots)
    else:
        Z = roots[0]
    phi: dict[str, float] = {}
    bi_ratio = {i: b[i] / b_m for i in COMPONENTS}
    s_a: dict[str, float] = {}
    for i in COMPONENTS:
        s_a[i] = sum(
            z[j] * (1.0 - _kij(i, j)) * math.sqrt(a[i] * a[j]) for j in COMPONENTS
        )
    ln_den = math.log((Z + (1.0 + math.sqrt(2.0)) * B) / (Z + (1.0 - math.sqrt(2.0)) * B))
    for i in COMPONENTS:
        ln_phi = (
            bi_ratio[i] * (Z - 1.0)
            - math.log(Z - B)
            - (A / (2.0 * math.sqrt(2.0) * B))
            * (2.0 * s_a[i] / a_m - bi_ratio[i])
            * ln_den
        )
        phi[i] = math.exp(ln_phi)
    return phi


def pr_bubble_point(T_K: float, x: dict[str, float]) -> tuple[float, dict[str, float], bool]:
    psat = {c: antoine_psat(c, T_K) for c in COMPONENTS}
    P = max(sum(x[c] * psat[c] for c in COMPONENTS), 1e-6)
    y = {c: x[c] * psat[c] / P for c in COMPONENTS}
    converged = False
    for _ in range(100):
        phi_v = pr_fugacity(T_K, P, y, "vapor")
        phi_l = pr_fugacity(T_K, P, x, "liquid")
        K = {c: phi_l[c] / phi_v[c] for c in COMPONENTS}
        s = sum(x[c] * K[c] for c in COMPONENTS)
        if abs(s - 1.0) < 5e-8:
            converged = True
            break
        P_new = P * s
        y_new = {c: x[c] * K[c] / s for c in COMPONENTS}
        P = 0.5 * (P + P_new)
        y = {c: 0.5 * (y[c] + y_new[c]) for c in COMPONENTS}
    return P, y, converged


@dataclass
class ThermoResult:
    M_mix: float
    rho_sat_kgm3: float
    rho_oper_kgm3: float
    Pv_pr_bara: float
    Pv_raoult_bara: float
    Pv_final_bara: float
    pv_model: str
    first_vapor_y: dict[str, float]
    pr_converged: bool
    T_K: float
    warnings: list[str] = field(default_factory=list)


def compute_thermo(
    comp: dict[str, float], T1_C: float, P_abs_bara: float, viscosity_pa_s: float = VISCOSITY_DEFAULT_PA_S
) -> ThermoResult:
    comp_n, warn = normalize_composition(comp)
    T_K = T1_C + 273.15
    M_mix = molar_mass(comp_n)
    rho_sat = klosek_zander_rho(comp_n, T_K)

    pv_pr, y_pr, conv = pr_bubble_point(T_K, comp_n)
    pv_ra = raoult_bubble(comp_n, T_K)

    warnings = list(warn)
    if T_K < ANTONIE_NBP_WARNING_BELOW_K:
        warnings.append(
            f"Çalışma sıcaklığı ({T1_C:.1f} °C) bileşenlerin normal kaynama noktalarının çok altında; "
            "Antoine/Raoult değerleri ekstrapolasyon içerir, birincil sonuç Peng-Robinson modelidir."
        )
    if not conv:
        warnings.append(
            "Peng-Robinson bubble point iterasyonu yakınsamadı; Raoult sonucu kullanıldı."
        )

    subcool = max(P_abs_bara - pv_pr, 0.0)
    rho_oper = rho_sat * (1.0 + LIQUID_COMPRESS_1_PER_BAR * subcool)

    if conv:
        pv_final, pv_model = pv_pr, "Peng-Robinson EOS"
    else:
        pv_final, pv_model = pv_ra, "Raoult (yedeği)"

    return ThermoResult(
        M_mix=M_mix,
        rho_sat_kgm3=rho_sat,
        rho_oper_kgm3=rho_oper,
        Pv_pr_bara=pv_pr,
        Pv_raoult_bara=pv_ra,
        Pv_final_bara=pv_final,
        pv_model=pv_model,
        first_vapor_y=y_pr if conv else {},
        pr_converged=conv,
        T_K=T_K,
        warnings=warnings,
    )
