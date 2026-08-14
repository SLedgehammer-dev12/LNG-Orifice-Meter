"""Isıl değer (GCV/NCV) ve enerji akışı motoru.

Bileşen molar yanma ısıları (MJ/kmol, 25 °C / 1 atm standart durum) — NIST/z26
kaynakların yaygın yaklaşıklıklarıdır. N₂ yanmaz (0). Ön tasarım içindir.

Kanonik çıktılar:
  GCV/NCV  -> MJ/kg ve türevleri (MJ/kmol, MJ/Nm³ ideal gaz)
  Enerji akışı -> MW (kütlesel debi kg/s × GCV MJ/kg)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# (HHV, LHV) MJ/kmol @ 25 °C / 1 atm
COMBUSTION_MJ_KMOL: dict[str, tuple[float, float]] = {
    "CH4": (890.8, 802.6),
    "C2H6": (1560.7, 1428.7),
    "C3H8": (2219.2, 2043.2),
    "iC4": (2868.0, 2648.3),
    "nC4": (2877.4, 2658.0),
    "iC5": (3529.9, 3271.3),
    "nC5": (3536.7, 3278.2),
    "N2": (0.0, 0.0),
}

MOLAR_VOLUME_NM3_PER_KMOL = 22.414


@dataclass
class EnergyResult:
    GCV_mj_kg: float
    GCV_mj_kmol: float
    GCV_mj_Nm3: float
    NCV_mj_kg: float
    NCV_mj_kmol: float
    NCV_mj_Nm3: float
    MW_mj_s: float          # termal güç, MWh kütle bazlı GCV
    MW_lv_mj_s: float       # NCV bazlı termal güç


def compute_energy(
    comp: dict[str, float],
    M_mix_kg_kmol: float,
    qm_kg_s: float,
    molar_volume_m3_kmol: float = MOLAR_VOLUME_NM3_PER_KMOL,
) -> EnergyResult:
    M_mix_kg_kmol = M_mix_kg_kmol or 17.0
    gcv_kmol = sum(x * (COMBUSTION_MJ_KMOL[c][0]) for c, x in comp.items())
    ncv_kmol = sum(x * (COMBUSTION_MJ_KMOL[c][1]) for c, x in comp.items())
    return EnergyResult(
        GCV_mj_kg=gcv_kmol / M_mix_kg_kmol,
        GCV_mj_kmol=gcv_kmol,
        GCV_mj_Nm3=gcv_kmol / molar_volume_m3_kmol,
        NCV_mj_kg=ncv_kmol / M_mix_kg_kmol,
        NCV_mj_kmol=ncv_kmol,
        NCV_mj_Nm3=ncv_kmol / molar_volume_m3_kmol,
        MW_mj_s=qm_kg_s * gcv_kmol / M_mix_kg_kmol,
        MW_lv_mj_s=qm_kg_s * ncv_kmol / M_mix_kg_kmol,
    )


def gcv_points(comp: dict[str, float]) -> list[tuple[str, float]]:
    """Isıl değerin bileşen dağılımı: görselleştirmede kullanılır."""
    return [(c, x * COMBUSTION_MJ_KMOL[c][0]) for c, x in comp.items() if COMBUSTION_MJ_KMOL[c][0] > 0]


def has_energy_support(comp: dict[str, float]) -> bool:
    return all(c in COMBUSTION_MJ_KMOL for c in comp)