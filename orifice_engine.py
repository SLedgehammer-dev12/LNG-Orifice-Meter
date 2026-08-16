"""ISO 5167-2 orifis hidrolik motoru: tam R-H/G (flange taps), NR grubu çözücü, belirsizlik."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

BETA_MIN_VALID = 0.10
BETA_MAX_VALID = 0.75
BETA_RECOMMENDED_MIN = 0.30
NR_BETA0 = 0.50
NR_MAX_ITER = 80
NR_TOL = 1e-10


def rhg_flange_C(beta: float, Re_D: float, D_mm: float) -> float:
    if not (0.0 < beta < 0.999):
        raise ValueError(f"beta geçersiz: {beta}")
    if D_mm <= 0.0:
        raise ValueError("D_mm pozitif olmalıdır")
    L1 = L2 = 25.4 / D_mm
    A = (19000.0 * beta / Re_D) ** 0.8
    M2 = 2.0 * L2 / (1.0 - beta)
    term4 = (0.0188 + 0.0063 * A) * beta ** 3.5 * (1e6 / Re_D) ** 0.3
    term5 = (
        0.043
        + 0.080 * math.exp(-10.0 * L1)
        - 0.123 * math.exp(-7.0 * L1)
    ) * (1.0 - 0.11 * A) * beta ** 4 / (1.0 - beta ** 4)
    small_D_term = 0.0
    if D_mm < 71.12:
        small_D_term = 0.011 * (0.75 - beta) * (2.8 - D_mm / 25.4)
    term6 = -0.031 * (M2 - 0.8 * M2 ** 1.1) * beta ** 1.3
    return (
        0.5961
        + 0.0261 * beta ** 2
        - 0.216 * beta ** 8
        + 0.000521 * (1e6 * beta / Re_D) ** 0.7
        + term4
        + term5
        + term6
        + small_D_term
    )


def dC_dbeta_num(beta: float, Re_D: float, D_mm: float) -> float:
    h = 1e-6
    return (rhg_flange_C(beta + h, Re_D, D_mm) - rhg_flange_C(beta - h, Re_D, D_mm)) / (2.0 * h)


def g_beta(beta: float, E: float, Re_D: float, D_mm: float) -> float:
    C = rhg_flange_C(beta, Re_D, D_mm)
    return beta ** 2 / math.sqrt(1.0 - beta ** 4) * C - E


@dataclass
class BetaSolution:
    beta: float
    C: float
    dC_dbeta: float
    method: str
    converged: bool
    iter_count: int
    violations: list[str] = field(default_factory=list)


def solve_beta(E: float, Re_D: float, D_mm: float) -> BetaSolution:
    if not (0.0 < E < 10.0):
        raise ValueError(f"Akış faktörü E fiziksel aralık dışında: {E}")
    beta = NR_BETA0
    conv = False
    it = 0
    for _ in range(NR_MAX_ITER):
        it += 1
        g = g_beta(beta, E, Re_D, D_mm)
        gp = dC_dbeta_num(beta, Re_D, D_mm) * beta ** 2 / math.sqrt(1.0 - beta ** 4) + (
            (2.0 * beta / math.sqrt(1.0 - beta ** 4)) + (2.0 * beta ** 5 / (1.0 - beta ** 4) ** 1.5)
        ) * rhg_flange_C(beta, Re_D, D_mm)
        if abs(gp) < 1e-12:
            break
        b_next = beta - g / gp
        if not (0.02 <= b_next <= 0.98):
            break
        if abs(b_next - beta) < NR_TOL:
            beta = b_next
            conv = True
            break
        beta = b_next
    method = "Newton-Raphson"

    if not conv or not (BETA_MIN_VALID <= beta <= BETA_MAX_VALID + 1e-9):
        lo, hi = 0.10, 0.75
        glo = g_beta(lo, E, Re_D, D_mm)
        ghi = g_beta(hi, E, Re_D, D_mm)
        for _ in range(200):
            mid = 0.5 * (lo + hi)
            gmid = g_beta(mid, E, Re_D, D_mm)
            if abs(gmid) < 1e-11 or (hi - lo) < 1e-12:
                beta = mid
                break
            if glo * gmid <= 0.0:
                hi = mid
                ghi = gmid
            else:
                lo = mid
                glo = gmid
        method = "Bisection (NR yedek)"
        conv = True

    C = rhg_flange_C(beta, Re_D, D_mm)
    dCdb = dC_dbeta_num(beta, Re_D, D_mm)

    violations: list[str] = []
    if beta < BETA_MIN_VALID or beta > BETA_MAX_VALID:
        violations.append(
            f"β={beta:.4f} ISO 5167-2 geçerlilik aralığının ({BETA_MIN_VALID:.2f}–{BETA_MAX_VALID:.2f}) dışında."
        )
    if beta < BETA_RECOMMENDED_MIN:
        violations.append(
            f"β={beta:.4f} çok düşük; tespit duyarlılığı ve turndown için β≥{BETA_RECOMMENDED_MIN:.2f} önerilir "
            "(daha yüksek dP hedefini veya daha küçük boru çapını değerlendirin)."
        )
    if beta > 0.60:
        violations.append(
            "β>0.60: deşarj katsayısı belirsizliği ve ölçüm belirsizliği artar; mümkünse kaçınılmalıdır."
        )
    if Re_D < 1e5:
        violations.append("Re_D<10⁵: R-H/G C() belirsizliği artar ve akış türbülanslı güven aralığından ayrılır.")
    return BetaSolution(beta=beta, C=C, dC_dbeta=dCdb, method=method, converged=conv, iter_count=it,
                        violations=violations)


def rhg_C_uncertainty(beta: float, Re_D: float) -> float:
    base = 0.005
    if beta > 0.60:
        base += (beta - 0.60) / 0.15 * 0.003
    if Re_D < 1e5:
        base += 0.002
    return base


def flow_uncertainty(
    beta: float,
    C: float,
    uC_C: float,
    uD_D: float,
    ud_d: float,
    udP_dP: float,
    urho_rho: float,
) -> float:
    b4 = beta ** 4
    term_c = uC_C ** 2
    term_d = (2.0 * b4 / (1.0 - b4)) ** 2 * uD_D ** 2
    term_dd = (2.0 / (1.0 - b4)) ** 2 * ud_d ** 2
    term_dp = 0.25 * udP_dP ** 2
    term_rho = 0.25 * urho_rho ** 2
    return math.sqrt(term_c + term_d + term_dd + term_dp + term_rho)


def iso5167_permanent_pressure_loss_ratio(beta: float, C: float) -> float:
    """ISO 5167-2:2003 Clause 5.4 kalıcı basınç kaybı oranı Delta_p_loss / Delta_p."""
    b4 = beta ** 4
    c2 = C ** 2
    term = 1.0 - b4 * (1.0 - c2)
    sq = math.sqrt(max(term, 0.0))
    cb2 = C * (beta ** 2)
    num = sq - cb2
    den = sq + cb2
    if den <= 0:
        return max(0.0, min(1.0, (1.0 - beta ** 1.9) / (1.0 + beta ** 1.9)))
    return max(0.0, min(1.0, num / den))


@dataclass
class SizingResult:
    rho: float
    Pv_bara: float
    qm_kg_s: float
    D20_mm: float
    DT_mm: float
    D_m: float
    dT_mm: float
    d20_mm: float
    beta: float
    C: float
    Re_D: float
    velocity_m_s: float
    E: float
    dP_nom_pa: float
    dP_max_mbar: float
    dP_min_mbar: float
    dP_perm_loss_mbar: float
    pump_power_loss_kw: float
    viscosity_pa_s: float
    alpha_1K: float
    u_flow_pct: float
    uC_C_pct: float
    beta_violations: list[str]
    solver: str


def size_orifice(
    comp: dict[str, float],
    T1_C: float,
    P1_barg: float,
    D20_mm: float,
    qm_nom_ton_h: float,
    dP_target_mbar: float,
    q_min_ratio: float = 0.30,
    q_max_ratio: float = 1.20,
    viscosity_pa_s: float = 0.00012,
    alpha_1K: float = 16.0e-6,
    uC_C: float = 0.005,
    uD_D: float = 0.001,
    ud_d: float = 0.0005,
    udP_dP: float = 0.005,
    urho_rho: float = 0.001,
    thermo: "ThermoResult | None" = None,
) -> tuple[SizingResult, "ThermoResult"]:
    from thermo_engine import ThermoResult, compute_thermo

    if thermo is None:
        P_abs = (P1_barg + 1.01325)
        thermo = compute_thermo(comp, T1_C, P_abs, viscosity_pa_s)

    rho = thermo.rho_oper_kgm3
    qm_kg_s = qm_nom_ton_h * 1000.0 / 3600.0
    DT_mm = D20_mm * (1.0 + alpha_1K * (T1_C - 20.0))
    D_m = DT_mm / 1000.0
    A_pipe = math.pi / 4.0 * D_m ** 2
    velocity = qm_kg_s / (rho * A_pipe)
    Re_D = rho * velocity * D_m / viscosity_pa_s
    dP_nom_pa = dP_target_mbar * 100.0
    E = qm_kg_s / (A_pipe * math.sqrt(2.0 * rho * dP_nom_pa))

    sol = solve_beta(E, Re_D, D_mm=DT_mm)
    dT_mm = sol.beta * DT_mm
    d20_mm = dT_mm / (1.0 + alpha_1K * (T1_C - 20.0))

    dP_max_mbar = dP_target_mbar * q_max_ratio ** 2
    dP_min_mbar = dP_target_mbar * q_min_ratio ** 2

    loss_ratio = iso5167_permanent_pressure_loss_ratio(sol.beta, sol.C)
    dP_perm_loss_mbar = dP_target_mbar * loss_ratio
    dP_perm_loss_pa = dP_perm_loss_mbar * 100.0
    # Pompalama güç kaybı: Q_vol (m3/s) * Delta_P_loss (Pa) / 1000 (kW)
    qv_m3_s = qm_kg_s / rho if rho > 0 else 0.0
    pump_power_loss_kw = (qv_m3_s * dP_perm_loss_pa) / 1000.0

    uC_eff = max(rhg_C_uncertainty(sol.beta, Re_D), uC_C)
    u_flow = flow_uncertainty(sol.beta, sol.C, uC_eff, uD_D, ud_d, udP_dP, urho_rho)

    return (
        SizingResult(
            rho=rho,
            Pv_bara=thermo.Pv_final_bara,
            qm_kg_s=qm_kg_s,
            D20_mm=D20_mm,
            DT_mm=DT_mm,
            D_m=D_m,
            dT_mm=dT_mm,
            d20_mm=d20_mm,
            beta=sol.beta,
            C=sol.C,
            Re_D=Re_D,
            velocity_m_s=velocity,
            E=E,
            dP_nom_pa=dP_nom_pa,
            dP_max_mbar=dP_max_mbar,
            dP_min_mbar=dP_min_mbar,
            dP_perm_loss_mbar=dP_perm_loss_mbar,
            pump_power_loss_kw=pump_power_loss_kw,
            viscosity_pa_s=viscosity_pa_s,
            alpha_1K=alpha_1K,
            u_flow_pct=u_flow * 100.0,
            uC_C_pct=uC_eff * 100.0,
            beta_violations=sol.violations,
            solver=sol.method,
        ),
        thermo,
    )