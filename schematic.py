"""Şematik gösterim: boru + orifis plakası ölçüm noktası çizimi (Tk Canvas).

`draw(canvas, inp, r, pal, units)`: girdi ve hesaplanan sonuçlara göre ölçüm
noktasını çizer. Tema paleti parametreyle verilir; headless smoke test için
çizim mantığı GUI'den ayrık tutulmuştur.
"""

from __future__ import annotations

import math

from units import CANONICAL_UNIT, DIGITS, from_canonical
from theme import palette

FONT = ("Helvetica", 10, "bold")
FONT_SM = ("Helvetica", 8)


def _fmt(value: float, category: str, unit: str | None, pal: dict | None = None) -> str:
    pal = pal or palette()
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "–"
    u = unit or CANONICAL_UNIT.get(category, "")
    if category == "number":
        if abs(value) >= 1000:
            return f"{value:,.0f}"
        nd = DIGITS.get(category, 4)
        return f"{value:.{nd}f}"
    disp = from_canonical(value, u, category) if category != "number" else value
    nd = DIGITS.get(category, 4)
    return f"{disp:.{nd}f} {u}"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_svg(inp, r, pal: dict | None = None) -> str:
    """HTML rapor için gömülebilir, tema bağımsız (aydınlık) SVG şema."""
    pal = pal or LIGHT_SVG
    W, H = 680, 300
    py = H / 2.0 - 4
    ph = 42.0
    y0, y1 = py - ph, py + ph
    x0, x1, px = 40.0, W - 30.0, 40.0 + (W - 40.0 - 30.0) * 0.50

    el: list[str] = []
    el.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{pal["bg"]}"/>')
    # boru
    el.append(f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" rx="3" '
              f'fill="{pal["pipe_fill"]}" stroke="{pal["pipe"]}" stroke-width="2"/>')
    for fx in (x0, x1):
        el.append(f'<line x1="{fx}" y1="{y0+3}" x2="{fx}" y2="{y1-3}" stroke="{pal["plate"]}" stroke-width="3"/>')
    # akış
    for ax in (x0 + 14, x0 + 38, x0 + 62):
        el.append(f'<polygon points="{ax},{py-4} {ax},{py+4} {ax+10},{py}" fill="{pal["flow"]}"/>')
    el.append(f'<text x="{x0+58}" y="{y0-12}" font-size="10" font-style="italic" '
              f'fill="{pal["flow"]}">Akış →</text>')
    # plaka
    bore = max(0.10, min(0.95, 1.0 if r is None else r.sizing.beta))
    bore_h = 2.0 * ph * bore
    bc = (y0 + y1) / 2.0
    el.append(f'<rect x="{px-3}" y="{y0}" width="6" height="{bc-bore_h/2-y0}" fill="{pal["plate"]}"/>')
    el.append(f'<rect x="{px-3}" y="{bc+bore_h/2}" width="6" height="{y1-(bc+bore_h/2)}" fill="{pal["plate"]}"/>')
    for side, sx in ((-1, px - 5), (1, px + 5)):
        el.append(f'<line x1="{sx}" y1="{bc-bore_h/2}" x2="{sx+side*13}" y2="{y0}" '
                  f'stroke="{pal["dimension"]}" stroke-width="1"/>')
        el.append(f'<line x1="{sx}" y1="{bc+bore_h/2}" x2="{sx+side*13}" y2="{y1}" '
                  f'stroke="{pal["dimension"]}" stroke-width="1"/>')
    # flange taps
    for sx in (px - 10, px + 10):
        el.append(f'<line x1="{sx}" y1="{y0-8}" x2="{sx}" y2="{y0}" stroke="{pal["dimension"]}" stroke-width="2"/>')
    # düz boru
    el.append(f'<line x1="{x0+4}" y1="{y1+14}" x2="{px-8}" y2="{y1+14}" stroke="{pal["dimension"]}" '
              f'stroke-dasharray="3,3"/>')
    el.append(f'<line x1="{px+8}" y1="{y1+14}" x2="{x1-4}" y2="{y1+14}" stroke="{pal["dimension"]}" '
              f'stroke-dasharray="3,3"/>')
    el.append(f'<text x="{(x0+px)/2}" y="{y1+22}" font-size="9" fill="{pal["text_muted"]}" '
              f'text-anchor="middle">≥20D</text>')
    el.append(f'<text x="{(px+x1)/2}" y="{y1+22}" font-size="9" fill="{pal["text_muted"]}" '
              f'text-anchor="middle">≥5D</text>')

    if inp is not None:
        uP, uT, uD, uQ = "bar-g", "°C", "mm", "t/h"
        p1 = f"{inp.P1_barg:.2f} {uP}"
        lx = x0 + 8
        for name, val in (("P₁", p1), ("T₁", f"{inp.T1_C:.1f} {uT}"),
                          ("D", f"{inp.D20_mm:.1f} {uD}"), ("Qₙₒₘ", f"{inp.qm_nom_ton_h:.1f} {uQ}")):
            el.append(f'<text x="{lx}" y="{y0-30}" font-size="9" fill="{pal["text_muted"]}">{_esc(name)}</text>')
            el.append(f'<text x="{lx}" y="{y0-18}" font-size="10" fill="{pal["text"]}">{_esc(val)}</text>')
            lx += 90

    if r is not None:
        s, sf, t, e = r.sizing, r.safety, r.thermo, r.energy
        rx = px + 16
        for name, val in (("P₂", f"{sf.phase.P2_barA:.3f} bar-a"),
                          ("Pvc", f"{sf.phase.Pvc_barA:.3f} bar-a"),
                          ("ΔPₘₐₓ", f"{s.dP_max_mbar:.0f} mbar"),
                          ("v", f"{s.velocity_m_s:.2f} m/s"),
                          ("ρ", f"{t.rho_oper_kgm3:.1f} kg/m³")):
            el.append(f'<text x="{rx}" y="{y1-34}" font-size="9" fill="{pal["text_muted"]}">{_esc(name)}</text>')
            el.append(f'<text x="{rx}" y="{y1-22}" font-size="10" fill="{pal["text"]}">{_esc(val)}</text>')
            rx += 84
        # durum
        if sf.phase.flashing:
            status, scol = "FLASHING", pal["error"]
        elif sf.phase.cavitation:
            status, scol = "KAVİTASYON", pal["warn"]
        else:
            status, scol = "GÜVENLİ", pal["success"]
        cw = 14 + len(status) * 6.5
        cx = x1 - 10 - cw
        el.append(f'<rect x="{cx}" y="{y0-38}" width="{cw}" height="18" rx="9" fill="{scol}"/>')
        el.append(f'<text x="{cx+cw/2}" y="{y0-25}" font-size="9" font-weight="bold" '
                  f'fill="#ffffff" text-anchor="middle">{status}</text>')
        el.append(f'<text x="{x0}" y="{H-16}" font-size="9" fill="{pal["dimension"]}">'
                  f'β={s.beta:.3f}  C={s.C:.4f}  Re={s.Re_D:,.0f}  d₂₀={s.d20_mm:.1f} mm  '
                  f'ΔPₙₒₘ={s.dP_nom_pa/100:.0f} mbar</text>')
        if e is not None:
            el.append(f'<text x="{x0}" y="{H-5}" font-size="9" fill="{pal["dimension"]}">'
                      f'GCV={e.GCV_mj_kg:.2f} MJ/kg   Q×GCV={e.MW_mj_s:.1f} MW</text>')

    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
            'width="100%" height="auto" role="img" aria-label="LNG orifis ölçüm noktası şeması">'
            "{body}</svg>").format(W=W, H=H, body="\n".join(el))


LIGHT_SVG = {
    "bg": "#f5f7fa",
    "pipe_fill": "#dce6ef",
    "pipe": "#9fb3c6",
    "flow": "#0b6ea8",
    "plate": "#7a8ea3",
    "dimension": "#5a6b7a",
    "text": "#1c2733",
    "text_muted": "#5a6b7a",
    "success": "#1f9d55",
    "warn": "#b8891c",
    "error": "#c0392b",
}


def _darrow(cv, x: float, y0: float, y1: float, color: str) -> None:
    cv.create_line(x, y0, x, y1, fill=color, width=1)
    a = 6.0
    cv.create_line(x, y0, x - a, y0 + a, fill=color)
    cv.create_line(x, y0, x + a, y0 + a, fill=color)
    cv.create_line(x, y1, x - a, y1 - a, fill=color)
    cv.create_line(x, y1, x + a, y1 - a, fill=color)


def _chip(cv, x: float, y: float, text: str, bg: str, fg: str) -> float:
    w = 8.0 + len(text) * 6.1
    h = 18.0
    cv.create_rectangle(x, y, x + w, y + h, fill=bg, outline="", width=0)
    cv.create_text(x + w / 2.0, y + h / 2.0, text=text, fill=fg,
                   font=("Helvetica", 8, "bold"))
    return x + w


def draw(cv, inp, r, pal: dict | None = None, units: dict[str, str] | None = None) -> None:
    pal = pal or palette()
    units = units or {}
    cv.delete("all")
    cv.configure(bg=pal["bg"])

    W = max(cv.winfo_width() or 640, 640)
    H = max(cv.winfo_height() or 300, 300)
    py = H / 2.0 - 6
    ph = min(46.0, H / 5.0)
    y0 = py - ph
    y1 = py + ph
    x0 = 46.0
    x1 = W - 34.0
    px = x0 + (x1 - x0) * 0.50

    # Boru gövdesi
    cv.create_rectangle(x0, y0, x1, y1, fill=pal["pipe_fill"], outline=pal["pipe"], width=2)
    # Flanş halkaları
    for fx in (x0, x1):
        cv.create_line(fx, y0 + 3, fx, y1 - 3, fill=pal["plate"], width=3)
    # Akış yönü okları (upstream)
    for ax in (x0 + 16, x0 + 40, x0 + 64):
        cv.create_polygon(ax, py - 4, ax, py + 4, ax + 10, py, fill=pal["flow"],
                          outline="", width=0)
    # akış yönü etiketi
    cv.create_text(x0 + 58, y0 - 10, text="Akış →", font=("Helvetica", 8, "italic"),
                   fill=pal["flow"])

    # Orifis plakası + boğaz
    bore_frac = max(0.10, min(0.95, 1.0 if r is None else r.sizing.beta))
    bore_h = 2.0 * ph * bore_frac
    bore_c = (y0 + y1) / 2.0
    cv.create_rectangle(px - 3, y0, px + 3, bore_c - bore_h / 2.0, fill=pal["plate"], outline="")
    cv.create_rectangle(px - 3, bore_c + bore_h / 2.0, px + 3, y1, fill=pal["plate"], outline="")
    # vena contracta
    for side, sx in ((-1, px - 4), (1, px + 4)):
        cv.create_line(sx, bore_c - bore_h / 2.0, sx + side * 14, y0, fill=pal["dimension"], width=1)
        cv.create_line(sx, bore_c + bore_h / 2.0, sx + side * 14, y1, fill=pal["dimension"], width=1)

    # Flange taps izleri (D/2 ~ 25.4 mm sembolik)
    ft = 10.0
    cv.create_line(px - ft, y0 - 8, px - ft, y0, fill=pal["dimension"], width=2)
    cv.create_line(px + ft, y0 - 8, px + ft, y0, fill=pal["dimension"], width=2)
    cv.create_text(px - ft, y0 - 14, text="P⁺", font=FONT_SM, fill=pal["dimension"])
    cv.create_text(px + ft, y0 - 14, text="P⁻", font=FONT_SM, fill=pal["dimension"])

    # Düz boru göstergeleri
    dash = (3, 3)
    cv.create_line(x0 + 4, y1 + 14, px - 6, y1 + 14, fill=pal["dimension"], dash=dash)
    cv.create_line(px + 6, y1 + 14, x1 - 4, y1 + 14, fill=pal["dimension"], dash=dash)
    cv.create_text((x0 + px) / 2.0, y1 + 20, text="≥20D", font=FONT_SM, fill=pal["text_muted"])
    cv.create_text((px + x1) / 2.0, y1 + 20, text="≥5D", font=FONT_SM, fill=pal["text_muted"])

    # D dimension (sol)
    dim_x = x0 - 16
    cv.create_line(dim_x - 6, y0, dim_x + 6, y0, fill=pal["dimension"])
    cv.create_line(dim_x - 6, y1, dim_x + 6, y1, fill=pal["dimension"])
    _darrow(cv, dim_x + 8, y0, y1, pal["dimension"])
    D20 = inp.D20_mm if inp is not None else 0.0
    cv.create_text(dim_x + 26, py, text="D", font=FONT, fill=pal["dimension"], anchor="w")

    # d dimension (plaaka)
    if r is not None:
        _darrow(cv, px, bore_c - bore_h / 2.0 - 10, bore_c + bore_h / 2.0 + 10, pal["dimension"])
        cv.create_text(px, y1 + 30, text="d", font=FONT, fill=pal["dimension"])

    # ---- Etiketler: girdi (üst/upstream) ----
    uT = units.get("temperature", "°C")
    uP = units.get("pressure", "bar-g")
    uQ = units.get("mass_flow", "t/h")
    uD = units.get("diameter", "mm")
    uL = units.get("dp", "mbar")
    P1_bara = (inp.P1_barg + 1.01325) if inp is not None else float("nan")
    lbl = [
        ("P₁", _fmt(P1_bara, "pressure", uP), pal["text"]),
        ("T₁", _fmt(inp.T1_C, "temperature", uT) if inp is not None else "–", pal["text"]),
        ("D", _fmt(inp.D20_mm, "diameter", uD) if inp is not None else "–", pal["text"]),
        ("Qₙₒₘ", _fmt(inp.qm_nom_ton_h, "mass_flow", uQ) if inp is not None else "–", pal["text"]),
    ]
    lx = x0 + 8
    for name, val, col in lbl:
        cv.create_text(lx, y0 - 30, text=name, font=FONT_SM, fill=pal["text_muted"], anchor="w")
        cv.create_text(lx, y0 - 18, text=val, font=FONT_SM, fill=col, anchor="w")
        lx += 78

    # ---- Etiketler: sonuç (alt/downstream) ----
    if r is not None:
        s, t, sf, e = r.sizing, r.thermo, r.safety, r.energy
        rx = px + 16
        rows = [
            ("P₂", _fmt(sf.phase.P2_barA, "pressure", uP)),
            ("Pvc", _fmt(sf.phase.Pvc_barA, "pressure", uP)),
            ("ΔPₘₐₓ", _fmt(s.dP_max_mbar, "dp", uL)),
            ("v", _fmt(s.velocity_m_s, "velocity", units.get("velocity", "m/s"))),
            ("ρ", _fmt(t.rho_oper_kgm3, "density", units.get("density", "kg/m³"))),
        ]
        rxx = rx
        for name, val in rows:
            cv.create_text(rxx, y1 - 34, text=name, font=FONT_SM, fill=pal["text_muted"], anchor="w")
            cv.create_text(rxx, y1 - 22, text=val, font=FONT_SM, fill=pal["text"], anchor="w")
            rxx += 78

        # Durum çipleri (üst sağ)
        cx, cy = x1, y0 - 40
        if sf.phase.flashing:
            cx = _chip(cv, cx - 30, cy, "FLASHING", pal["error"], "#ffffff") - 8
        elif sf.phase.cavitation:
            cx = _chip(cv, cx - 30, cy, "KAVİTASYON", pal["warn"], "#1a1a1a") - 8
        else:
            cx = _chip(cv, cx - 30, cy, "GÜVENLİ", pal["success"], "#ffffff") - 8
        if sf.wall.ok and not str(sf.wall.t_actual_mm) == "nan":
            colors = (pal["success"], "#ffffff") if sf.wall.ok else (pal["error"], "#ffffff")
            cx = _chip(cv, cx - 10, cy, "B31.3", *colors) - 8
        elif str(sf.wall.t_actual_mm) == "nan":
            cx = _chip(cv, cx - 10, cy, "B31.3≠", pal["surface_alt"], pal["text_muted"]) - 8
        else:
            cx = _chip(cv, cx - 10, cy, "B31.3", pal["error"], "#ffffff") - 8

        # Alt bilgi satırı
        line1 = (f"β={s.beta:.3f}  C={s.C:.4f}  Re={s.Re_D:,.0f}  "
                 f"d₂₀={_fmt(s.d20_mm, 'diameter', uD)}  ΔPₙₒₘ={_fmt(s.dP_nom_pa / 100.0, 'dp', uL)}")
        cv.create_text(x0, H - 18, text=line1, font=FONT_SM, fill=pal["dimension"], anchor="w")
        if e is not None:
            line2 = (f"GCV={_fmt(e.GCV_mj_kg, 'heating_value', units.get('heating_value', 'MJ/kg'))}  "
                     f"Q×GCV={_fmt(e.MW_mj_s, 'energy_flow', units.get('energy_flow', 'MW'))}")
            cv.create_text(x0, H - 6, text=line2, font=FONT_SM, fill=pal["dimension"], anchor="w")
    else:
        cv.create_text(px, y1 + 42, text="Sonuç yok — 'Hesapla' düğmesiyle hesap çalıştırın.",
                       font=FONT_SM, fill=pal["text_muted"])