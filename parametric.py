"""Parametrik tarama motoru: tek değişken (ΔP / Qm / D₂₀) duyarlılık taraması.

v1.4.0'da eklendi. GUI'den bağımsız; verilen taban girdilerin bir alanını tarar ve
her nokta için ana boyutlandırma çıktılarını toplar. Bozuk/geçersiz girdiler satırı
düşürmez, hata notu ile işaretlenir.

Örnek: ``sweep(base_inp, "dP", [100.0, 250.0, 500.0])`` → ΔP hedefi taraması.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from engine import RunInputs, run_engineering

SWEEP_KEYS = {
    "dP": ("ΔP hedefi", "mbar"),
    "Qm": ("Nominal debi", "t/h"),
    "D": ("İç çap D₂₀", "mm"),
}

FIELD_MAP = {
    "dP": "dP_target_mbar",
    "Qm": "qm_nom_ton_h",
    "D": "D20_mm",
}


@dataclass
class ParamRow:
    value: float
    beta: float
    d20_mm: float
    velocity_m_s: float
    u_flow_pct: float
    dP_max_mbar: float
    ok: bool
    note: str


def linspace(start: float, stop: float, steps: int) -> list[float]:
    if steps < 2:
        return [start]
    step = (stop - start) / (steps - 1)
    return [start + step * i for i in range(steps)]


def sweep(base: RunInputs, key: str, values: list[float]) -> list[ParamRow]:
    """`key` alanını (SWEEP_KEYS anahtarlarından) verilen değerlerde tarar."""
    if key == "D":
        # RunInputs.__post_init__, Do_mm verildiğinde D20_mm'yi ezerek OD-2t hesaplar;
        # çap taramasında D20_mm'yi doğrudan kontrol etmek için geometri bilgisi boşaltılır.
        base = replace(base, Do_mm=None, t_actual_mm=None)

    rows: list[ParamRow] = []
    field = FIELD_MAP[key]
    for v in values:
        inp = replace(base, **{field: v})
        try:
            r = run_engineering(inp)
            s = r.sizing
            rows.append(
                ParamRow(
                    value=v,
                    beta=s.beta,
                    d20_mm=s.d20_mm,
                    velocity_m_s=s.velocity_m_s,
                    u_flow_pct=s.u_flow_pct,
                    dP_max_mbar=s.dP_max_mbar,
                    ok=not r.safety.phase.flashing and not r.safety.phase.cavitation,
                    note="; ".join(r.warnings),
                )
            )
        except Exception as e:  # noqa: BLE001
            rows.append(
                ParamRow(
                    value=v,
                    beta=float("nan"),
                    d20_mm=float("nan"),
                    velocity_m_s=float("nan"),
                    u_flow_pct=float("nan"),
                    dP_max_mbar=float("nan"),
                    ok=False,
                    note=str(e),
                )
            )
    return rows
