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


# --- ASME B36.19M / ASME B36.10M Standart Boru Veritabanı ---
@dataclass(frozen=True)
class PipeSpec:
    nps: str
    dn: int
    od_mm: float
    schedules: dict[str, float]  # sch -> wall_mm


ASME_PIPE_CATALOG: list[PipeSpec] = [
    PipeSpec("1/8\"", 6, 10.29, {"10S": 1.24, "40S": 1.73, "STD": 1.73, "80S": 2.41, "XS": 2.41}),
    PipeSpec("1/4\"", 8, 13.72, {"10S": 1.65, "40S": 2.24, "STD": 2.24, "80S": 3.02, "XS": 3.02}),
    PipeSpec("3/8\"", 10, 17.15, {"10S": 1.65, "40S": 2.31, "STD": 2.31, "80S": 3.20, "XS": 3.20}),
    PipeSpec("1/2\"", 15, 21.34, {"5S": 1.65, "10S": 2.11, "40S": 2.77, "STD": 2.77, "80S": 3.73, "XS": 3.73, "160": 4.78, "XXS": 7.47}),
    PipeSpec("3/4\"", 20, 26.67, {"5S": 1.65, "10S": 2.11, "40S": 2.87, "STD": 2.87, "80S": 3.91, "XS": 3.91, "160": 5.56, "XXS": 7.82}),
    PipeSpec("1\"", 25, 33.40, {"5S": 1.65, "10S": 2.77, "40S": 3.38, "STD": 3.38, "80S": 4.55, "XS": 4.55, "160": 6.35, "XXS": 9.09}),
    PipeSpec("1-1/4\"", 32, 42.16, {"5S": 1.65, "10S": 2.77, "40S": 3.56, "STD": 3.56, "80S": 4.85, "XS": 4.85, "160": 6.35, "XXS": 9.70}),
    PipeSpec("1-1/2\"", 40, 48.26, {"5S": 1.65, "10S": 2.77, "40S": 3.68, "STD": 3.68, "80S": 5.08, "XS": 5.08, "160": 7.14, "XXS": 10.16}),
    PipeSpec("2\"", 50, 60.33, {"5S": 1.65, "10S": 2.77, "40S": 3.91, "STD": 3.91, "80S": 5.54, "XS": 5.54, "160": 8.74, "XXS": 11.07}),
    PipeSpec("2-1/2\"", 65, 73.03, {"5S": 2.11, "10S": 3.05, "40S": 5.16, "STD": 5.16, "80S": 7.01, "XS": 7.01, "160": 9.53, "XXS": 14.02}),
    PipeSpec("3\"", 80, 88.90, {"5S": 2.11, "10S": 3.05, "40S": 5.49, "STD": 5.49, "80S": 7.62, "XS": 7.62, "160": 11.13, "XXS": 15.24}),
    PipeSpec("3-1/2\"", 90, 101.60, {"5S": 2.11, "10S": 3.05, "40S": 5.74, "STD": 5.74, "80S": 8.08, "XS": 8.08}),
    PipeSpec("4\"", 100, 114.30, {"5S": 2.11, "10S": 3.05, "40S": 6.02, "STD": 6.02, "80S": 8.56, "XS": 8.56, "120": 11.13, "160": 13.49, "XXS": 17.12}),
    PipeSpec("5\"", 125, 141.30, {"5S": 2.77, "10S": 3.40, "40S": 6.55, "STD": 6.55, "80S": 9.53, "XS": 9.53, "120": 12.70, "160": 15.88, "XXS": 19.05}),
    PipeSpec("6\"", 150, 168.28, {"5S": 2.77, "10S": 3.40, "40S": 7.11, "STD": 7.11, "80S": 10.97, "XS": 10.97, "120": 14.27, "160": 18.26, "XXS": 21.95}),
    PipeSpec("8\"", 200, 219.08, {"5S": 2.77, "10S": 3.76, "20": 6.35, "30": 7.04, "40S": 8.18, "STD": 8.18, "60": 10.31, "80S": 12.70, "XS": 12.70, "100": 15.09, "120": 18.26, "140": 20.62, "160": 23.01, "XXS": 22.22}),
    PipeSpec("10\"", 250, 273.05, {"5S": 3.40, "10S": 4.19, "20": 6.35, "30": 7.80, "40S": 9.27, "STD": 9.27, "60": 12.70, "80S": 15.09, "XS": 15.09, "100": 18.26, "120": 21.44, "140": 25.40, "160": 28.58, "XXS": 25.40}),
    PipeSpec("12\"", 300, 323.85, {"5S": 3.96, "10S": 4.57, "20": 6.35, "30": 8.38, "40S": 9.53, "STD": 9.53, "60": 14.27, "80S": 17.48, "XS": 12.70, "100": 21.44, "120": 25.40, "140": 28.58, "160": 33.32, "XXS": 25.40}),
    PipeSpec("14\"", 350, 355.60, {"5S": 3.96, "10S": 4.78, "10": 6.35, "20": 7.92, "30": 9.53, "40S": 9.53, "STD": 9.53, "40": 11.13, "XS": 12.70, "60": 15.09, "80S": 19.05, "80": 19.05, "100": 23.83, "120": 27.79, "140": 31.75, "160": 35.71, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70}),
    PipeSpec("16\"", 400, 406.40, {"5S": 4.19, "10S": 4.78, "10": 6.35, "20": 7.92, "30": 9.53, "40S": 9.53, "STD": 9.53, "40": 12.70, "XS": 12.70, "60": 16.66, "80S": 21.44, "80": 21.44, "100": 26.19, "120": 30.96, "140": 36.53, "160": 40.49, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70}),
    PipeSpec("18\"", 450, 457.20, {"5S": 4.19, "10S": 4.78, "10": 6.35, "20": 7.92, "STD": 9.53, "40S": 9.53, "30": 11.13, "XS": 12.70, "40": 14.27, "60": 19.05, "80S": 23.83, "80": 23.83, "100": 29.36, "120": 34.93, "140": 39.67, "160": 45.24, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70}),
    PipeSpec("20\"", 500, 508.00, {"5S": 4.78, "10S": 5.54, "10": 6.35, "20": 9.53, "STD": 9.53, "40S": 9.53, "30": 12.70, "XS": 12.70, "40": 15.09, "60": 20.62, "80S": 26.19, "80": 26.19, "100": 32.54, "120": 38.10, "140": 44.45, "160": 50.01, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70}),
    PipeSpec("22\"", 550, 558.80, {"5S": 4.78, "10S": 5.54, "10": 6.35, "STD": 9.53, "20": 9.53, "30": 12.70, "XS": 12.70, "60": 22.22, "80": 28.58, "100": 34.93, "120": 41.28, "140": 47.62, "160": 53.98, "6.35mm": 6.35, "9.53mm": 9.53, "12.70mm": 12.70}),
    PipeSpec("24\"", 600, 609.60, {"5S": 5.54, "10S": 6.35, "10": 6.35, "20": 9.53, "STD": 9.53, "40S": 9.53, "XS": 12.70, "30": 14.27, "40": 17.48, "60": 24.61, "80S": 30.96, "80": 30.96, "100": 38.89, "120": 46.02, "140": 52.37, "160": 59.54, "6.35mm": 6.35, "9.53mm": 9.53, "12.70mm": 12.70}),
    PipeSpec("26\"", 650, 660.40, {"10": 7.92, "STD": 9.53, "20": 12.70, "XS": 12.70, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70, "15.88mm": 15.88, "19.05mm": 19.05, "22.22mm": 22.22, "25.40mm": 25.40, "31.75mm": 31.75}),
    PipeSpec("28\"", 700, 711.20, {"10": 7.92, "STD": 9.53, "20": 12.70, "XS": 12.70, "30": 15.88, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70, "15.88mm": 15.88, "19.05mm": 19.05, "22.22mm": 22.22, "25.40mm": 25.40, "31.75mm": 31.75}),
    PipeSpec("30\"", 750, 762.00, {"10": 7.92, "STD": 9.53, "20": 12.70, "XS": 12.70, "30": 15.88, "40": 19.05, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70, "15.88mm": 15.88, "19.05mm": 19.05, "22.22mm": 22.22, "25.40mm": 25.40, "31.75mm": 31.75}),
    PipeSpec("32\"", 800, 812.80, {"10": 7.92, "STD": 9.53, "20": 12.70, "XS": 12.70, "30": 15.88, "40": 17.48, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "22.22mm": 22.22, "25.40mm": 25.40, "31.75mm": 31.75}),
    PipeSpec("34\"", 850, 863.60, {"10": 7.92, "STD": 9.53, "20": 12.70, "XS": 12.70, "30": 15.88, "40": 17.48, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70, "15.88mm": 15.88, "17.48mm": 17.48, "19.05mm": 19.05, "22.22mm": 22.22, "25.40mm": 25.40, "31.75mm": 31.75}),
    PipeSpec("36\"", 900, 914.40, {"10": 7.92, "STD": 9.53, "20": 12.70, "XS": 12.70, "30": 15.88, "40": 19.05, "6.35mm": 6.35, "7.92mm": 7.92, "9.53mm": 9.53, "12.70mm": 12.70, "15.88mm": 15.88, "19.05mm": 19.05, "22.22mm": 22.22, "25.40mm": 25.40, "31.75mm": 31.75}),
]


def find_closest_pipe(od_mm: float) -> PipeSpec | None:
    if od_mm <= 0:
        return None
    best_pipe = None
    best_diff = float("inf")
    for p in ASME_PIPE_CATALOG:
        diff = abs(p.od_mm - od_mm)
        if diff < best_diff:
            best_diff = diff
            best_pipe = p
    if best_pipe and (best_diff / best_pipe.od_mm) < 0.05:
        return best_pipe
    return None


def identify_pipe(od_mm: float, t_actual_mm: float) -> tuple[str, str | None]:
    pipe = find_closest_pipe(od_mm)
    if pipe is None:
        return f"Özel Çap ({od_mm:.1f} mm)", None
    best_sch = None
    best_diff = float("inf")
    # Harfli / standart schedule öncelikli arama
    priority_order = ["5S", "10S", "40S", "STD", "80S", "XS", "160", "XXS", "10", "20", "30", "40", "60", "80", "100", "120", "140"]
    for sch in priority_order:
        if sch in pipe.schedules:
            diff = abs(pipe.schedules[sch] - t_actual_mm)
            if diff < best_diff:
                best_diff = diff
                best_sch = sch
    for sch, t in pipe.schedules.items():
        diff = abs(t - t_actual_mm)
        if diff < best_diff:
            best_diff = diff
            best_sch = sch
    if best_sch and best_diff <= 0.35:
        if best_sch.endswith("mm"):
            label = f"NPS {pipe.nps} (DN {pipe.dn}) t={pipe.schedules[best_sch]:.2f} mm"
        elif best_sch in ("STD", "XS", "XXS"):
            label = f"NPS {pipe.nps} (DN {pipe.dn}) {best_sch}"
        else:
            label = f"NPS {pipe.nps} (DN {pipe.dn}) Sch {best_sch}"
        return label, best_sch
    if best_sch:
        label = f"NPS {pipe.nps} (DN {pipe.dn}) Özel Kalınlık (En yakın: {best_sch})"
    else:
        label = f"NPS {pipe.nps} (DN {pipe.dn}) Özel Kalınlık"
    return label, best_sch


def recommend_schedule(od_mm: float, t_required_mm: float, mill_tol: float = MILL_TOLERANCE_DEFAULT) -> tuple[str, float]:
    pipe = find_closest_pipe(od_mm)
    if pipe is None:
        return "Bilinmeyen Çap", float("nan")
    t_min_nom = t_required_mm / (1.0 - mill_tol) if (1.0 - mill_tol) > 0 else t_required_mm
    # schedules kalınlığa göre artan sıralanır
    sorted_sch = sorted(pipe.schedules.items(), key=lambda kv: kv[1])
    for sch, t in sorted_sch:
        if t >= t_min_nom:
            if sch.endswith("mm"):
                return f"NPS {pipe.nps} (t={t:.2f} mm)", t
            if sch in ("STD", "XS", "XXS"):
                return f"NPS {pipe.nps} {sch} (t={t:.2f} mm)", t
            return f"NPS {pipe.nps} Sch {sch} (t={t:.2f} mm)", t
    heaviest_sch, heaviest_t = sorted_sch[-1]
    return f"NPS {pipe.nps} {heaviest_sch} (t={heaviest_t:.2f} mm, Özel takviye gerekebilir)", heaviest_t


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
    identified_pipe: str
    recommended_schedule: str
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
            identified_pipe="–",
            recommended_schedule="–",
            ok=True,
            notes=["Boru dış çapı / et kalınlığı girilmedi; B31.3 kontrolü atlandı."],
        )
    else:
        t_calc = b31_3_min_wall_mm(max(P1_barg, 0.0), Do_mm, S_mpa, E_JOINT_DEFAULT, Y_AUSTENITIC_DEFAULT)
        t_required = t_calc + c_mm
        t_available = t_actual_mm * (1.0 - mill_tol)
        ok = t_available >= t_required

        ident_label, _ = identify_pipe(Do_mm, t_actual_mm)
        rec_label, _ = recommend_schedule(Do_mm, t_required, mill_tol)

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
            identified_pipe=ident_label,
            recommended_schedule=rec_label,
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
