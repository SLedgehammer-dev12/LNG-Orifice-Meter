"""Orkestratör motor: girdileri alır, tüm hesaplamaları zincirler, rapor yapısını kurar."""

from __future__ import annotations

from dataclasses import dataclass, field

from thermo_engine import ThermoResult, compute_thermo
from orifice_engine import SizingResult, size_orifice
from safety_engine import SafetyResult, check_safety
from energy_engine import EnergyResult, compute_energy


@dataclass
class RunInputs:
    comp: dict[str, float]
    T1_C: float
    P1_barg: float
    qm_nom_ton_h: float
    dP_target_mbar: float
    D20_mm: float = 0.0
    q_min_ratio: float = 0.30
    q_max_ratio: float = 1.20
    viscosity_pa_s: float = 0.00012
    alpha_1K: float = 16.0e-6
    L_pipe_m: float = 0.0
    eps_mm: float = 0.0457
    FL: float = 0.85
    Do_mm: float | None = None
    t_actual_mm: float | None = None
    S_mpa: float = 138.0
    c_mm: float = 1.6
    material: str = "AISI 304"
    uC_C: float = 0.005
    uD_D: float = 0.001
    ud_d: float = 0.0005
    udP_dP: float = 0.005
    urho_rho: float = 0.001

    def __post_init__(self) -> None:
        """[MÜHENDİSLİK DÜZELTMESİ v1.3.0]: Geometrik Tutarlılık İlkesi.
        
        Kullanıcının iç çapı ayrıca elle girmesine gerek kalmadan;
        Boru Dış Çapı (Do_mm / OD) ve Boru Et Kalınlığı (t_actual_mm / t) girildiğinde,
        iç çap doğrudan geometrik kural olan D₂₀ = OD - 2×t formülüyle otomatik türetilir.
        Eğer yalnızca D20_mm verilmişse (eski uyumluluk), D20_mm korunur.
        """
        if self.Do_mm is not None and self.t_actual_mm is not None and self.Do_mm > 0:
            calc_d20 = self.Do_mm - 2.0 * self.t_actual_mm
            if calc_d20 > 0:
                self.D20_mm = calc_d20
            else:
                raise ValueError(f"Geçersiz boru geometrisi: Dış çap ({self.Do_mm:.1f} mm) et kalınlığının 2 katından ({2.0*self.t_actual_mm:.1f} mm) küçük veya eşit olamaz.")
        elif self.D20_mm <= 0:
            raise ValueError("Boru geometrisi eksik: ya Dış Çap (OD) ve Et Kalınlığı (t) ya da geçerli bir İç Çap (D₂₀) girilmelidir.")


@dataclass
class SensitivityRow:
    n2_pct: float
    pv_bara: float
    rho_kgm3: float
    margin_p2: float
    safe: bool


@dataclass
class RunResult:
    inputs: RunInputs
    thermo: ThermoResult
    sizing: SizingResult
    safety: SafetyResult
    sensitivity: list[SensitivityRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    energy: EnergyResult | None = None


def n2_sensitivity(
    comp: dict[str, float],
    T1_C: float,
    P_abs_bara: float,
    P2_barA: float,
    Pv_base: float,
    factors: tuple[float, ...] = (0.0, 0.5, 1.0, 1.5, 2.0),
) -> list[SensitivityRow]:
    base_n2 = comp.get("N2", 0.0)
    others = sum(v for k, v in comp.items() if k not in ("N2", "CH4"))
    rows: list[SensitivityRow] = []
    for f in factors:
        n2 = base_n2 * f
        ch4 = max(1.0 - others - n2, 0.0)
        variant = dict(comp)
        variant["N2"] = n2
        variant["CH4"] = ch4
        thermo = compute_thermo(variant, T1_C, P_abs_bara)
        safe = P2_barA > thermo.Pv_final_bara
        rows.append(
            SensitivityRow(
                n2_pct=n2 * 100.0,
                pv_bara=thermo.Pv_final_bara,
                rho_kgm3=thermo.rho_oper_kgm3,
                margin_p2=P2_barA / thermo.Pv_final_bara if thermo.Pv_final_bara > 0 else float("inf"),
                safe=safe,
            )
        )
    return rows


def run_engineering(inp: RunInputs) -> RunResult:
    P_abs = inp.P1_barg + 1.01325
    sizing, thermo = size_orifice(
        comp=inp.comp,
        T1_C=inp.T1_C,
        P1_barg=inp.P1_barg,
        D20_mm=inp.D20_mm,
        qm_nom_ton_h=inp.qm_nom_ton_h,
        dP_target_mbar=inp.dP_target_mbar,
        q_min_ratio=inp.q_min_ratio,
        q_max_ratio=inp.q_max_ratio,
        viscosity_pa_s=inp.viscosity_pa_s,
        alpha_1K=inp.alpha_1K,
        uC_C=inp.uC_C,
        uD_D=inp.uD_D,
        ud_d=inp.ud_d,
        udP_dP=inp.udP_dP,
        urho_rho=inp.urho_rho,
    )
    safety = check_safety(
        P1_barg=inp.P1_barg,
        Pv_bara=thermo.Pv_final_bara,
        dP_max_mbar=sizing.dP_max_mbar,
        qm_kg_s=sizing.qm_kg_s,
        rho_kgm3=sizing.rho,
        D20_mm=inp.D20_mm,
        L_pipe_m=inp.L_pipe_m,
        mu_pa_s=inp.viscosity_pa_s,
        eps_mm=inp.eps_mm,
        FL=inp.FL,
        Do_mm=inp.Do_mm,
        t_actual_mm=inp.t_actual_mm,
        S_mpa=inp.S_mpa,
        c_mm=inp.c_mm,
        beta=sizing.beta,
        alpha_1K=inp.alpha_1K,
        T1_C=inp.T1_C,
    )
    sens = n2_sensitivity(inp.comp, inp.T1_C, P_abs, safety.phase.P2_barA, thermo.Pv_final_bara)
    energy = compute_energy(inp.comp, thermo.M_mix, sizing.qm_kg_s)

    warnings = list(thermo.warnings) + list(sizing.beta_violations) + list(safety.warnings)
    return RunResult(
        inputs=inp,
        thermo=thermo,
        sizing=sizing,
        safety=safety,
        sensitivity=sens,
        warnings=warnings,
        energy=energy,
    )
