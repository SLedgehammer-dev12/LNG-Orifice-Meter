"""Emniyet denetim motoru: flashing/kavitasyon (boru kayıplı), ASME B31.3 et kalınlığı."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

FL_DEFAULT = 0.85
PIPE_ROUGHNESS_DEFAULT_MM = 0.0457
CORROSION_ALLOWANCE_DEFAULT_MM = 1.6
MILL_TOLERANCE_DEFAULT = 0.125
S_304_MPA_DEFAULT = 138.0
S_316_MPA_DEFAULT = 138.0
E_JOINT_DEFAULT = 1.0
Y_AUSTENITIC_DEFAULT = 0.4


def haaland_friction(Re_D: float, eps_mm: float, D_mm: float) -> float:
    if Re_D < 2300.0:
        return 64.0 / Re_D
    eD = eps_mm / D_mm
    f = 1.0 / (-1.8 * math.log10((eD / 3.7) ** 1.11 + 6.9 / Re_D)) ** 2
    return max(f, 64.0 / Re_D)


def pipe_dp_mbar(qm_kg_s: float, rho_kgm3: float, D_mm: float, L_m: float, mu_pa_s: float, eps_mm: float) -> float:
    if L_m <= 0.0:
        return 0.0
    D_m = D_mm / 1000.0
    A = math.pi / 4.0 * D_m ** 2
    v = qm_kg_s / (rho_kgm3 * A)
    Re = rho_kgm3 * v * D_m / mu_pa_s
    f = haaland_friction(Re, eps_mm, D_mm)
    return (f * L_m / D_m * rho_kgm3 * v ** 2 / 2.0) * 0.01


def b31_3_min_wall_mm(P_gauge_bara: float, Do_mm: float, S_mpa: float, E_joint: float, Y: float) -> float:
    P_mpa = P_gauge_bara * 0.1
    if (S_mpa * E_joint + P_mpa * Y) <= 0.0:
        return float("inf")
    return P_mpa * Do_mm / (2.0 * (S_mpa * E_joint + P_mpa * Y))


@dataclass
class PhaseSafety:
    flashing: bool
    cavitation: bool
    status: str
    P2_barA: float
    P2_plaka_only_barA: float
    Pvc_barA: float
    Pv_barA: float
    dP_plate_max_bar: float
    dP_pipe_bar: float
    FL: float
    margin_P2_over_Pv: float
    margin_Pvc_over_Pv: float


@dataclass
class WallCheck:
    t_calc_mm: float
    t_required_mm: float
    t_available_mm: float
    t_actual_mm: float
    ok: bool
    notes: list[str] = field(default_factory=list)


@dataclass
class SafetyResult:
    phase: PhaseSafety
    wall: WallCheck
    straight_up_m: float
    straight_down_m: float
    beta_in_range: bool
    warnings: list[str] = field(default_factory=list)


def check_safety(
    P1_barg: float,
    Pv_bara: float,
    dP_max_mbar: float,
    qm_kg_s: float,
    rho_kgm3: float,
    D20_mm: float,
    L_pipe_m: float,
    mu_pa_s: float,
    eps_mm: float = PIPE_ROUGHNESS_DEFAULT_MM,
    FL: float = FL_DEFAULT,
    Do_mm: float | None = None,
    t_actual_mm: float | None = None,
    S_mpa: float = S_304_MPA_DEFAULT,
    c_mm: float = CORROSION_ALLOWANCE_DEFAULT_MM,
    mill_tol: float = MILL_TOLERANCE_DEFAULT,
    beta: float | None = None,
    alpha_1K: float = 16.0e-6,
    T1_C: float = -163.0,
) -> SafetyResult:
    warnings: list[str] = []

    DT_mm = D20_mm * (1.0 + alpha_1K * (T1_C - 20.0))
    P1_abs = P1_barg + 1.01325
    dP_plate_max_bar = dP_max_mbar / 1000.0
    dP_pipe_bar = pipe_dp_mbar(qm_kg_s, rho_kgm3, DT_mm, L_pipe_m, mu_pa_s, eps_mm) / 1000.0

    P2_plaka = P1_abs - dP_plate_max_bar
    P2_total = P1_abs - dP_plate_max_bar - dP_pipe_bar
    Pvc = P1_abs - dP_plate_max_bar / (FL * FL)

    flashing = P2_total <= Pv_bara
    cavitation = Pvc <= Pv_bara

    if flashing:
        status = "KRİTİK: FLASHING! (P2 <= Pv)"
    elif cavitation:
        status = "UYARI: VENA CONTRACTA'DA KAVİTASYON RİSKİ"
    else:
        status = "GÜVENLİ: Faz değişimi yok (Pvc > Pv)"

    margin_p2 = P2_total / Pv_bara if Pv_bara > 0 else float("inf")
    margin_pvc = Pvc / Pv_bara if Pv_bara > 0 else float("inf")

    if dP_pipe_bar > 0.05:
        warnings.append(
            f"Boru sürtünme kaybı {dP_pipe_bar*1000:.0f} mbar; plaka dP'si {dP_plate_max_bar*1000:.0f} mbar. "
            "Basınç profili hesabına dahil edildi."
        )

    phase = PhaseSafety(
        flashing=flashing,
        cavitation=cavitation,
        status=status,
        P2_barA=P2_total,
        P2_plaka_only_barA=P2_plaka,
        Pvc_barA=Pvc,
        Pv_barA=Pv_bara,
        dP_plate_max_bar=dP_plate_max_bar,
        dP_pipe_bar=dP_pipe_bar,
        FL=FL,
        margin_P2_over_Pv=margin_p2,
        margin_Pvc_over_Pv=margin_pvc,
    )

    wall: WallCheck
    if Do_mm is None or t_actual_mm is None:
        wall = WallCheck(
            t_calc_mm=float("nan"),
            t_required_mm=float("nan"),
            t_available_mm=float("nan"),
            t_actual_mm=float("nan"),
            ok=True,
            notes=["Boru dış çapı / et kalınlığı girilmedi; B31.3 kontrolü atlandı."],
        )
    else:
        t_calc = b31_3_min_wall_mm(max(P1_barg, 0.0), Do_mm, S_mpa, E_JOINT_DEFAULT, Y_AUSTENITIC_DEFAULT)
        t_required = t_calc + c_mm
        t_available = t_actual_mm * (1.0 - mill_tol)
        ok = t_available >= t_required
        notes: list[str] = []
        if ok:
            notes.append(
                f"t_mevcut={t_available:.2f} mm ≥ t_gerekli={t_required:.2f} mm (hesap {t_calc:.2f} + korozyon {c_mm:.1f})"
            )
        else:
            notes.append(
                f"YETERSİZ: t_mevcut={t_available:.2f} mm < t_gerekli={t_required:.2f} mm."
            )
        wall = WallCheck(
            t_calc_mm=t_calc,
            t_required_mm=t_required,
            t_available_mm=t_available,
            t_actual_mm=t_actual_mm,
            ok=ok,
            notes=notes,
        )

    beta_in_range = True
    if beta is not None:
        beta_in_range = 0.20 <= beta <= 0.75
        if not beta_in_range:
            warnings.append(f"β={beta:.4f} ISO 5167-2 tasarım aralığı (0.20–0.75) dışında.")

    return SafetyResult(
        phase=phase,
        wall=wall,
        straight_up_m=20.0 * D20_mm / 1000.0,
        straight_down_m=5.0 * D20_mm / 1000.0,
        beta_in_range=beta_in_range,
        warnings=warnings,
    )
