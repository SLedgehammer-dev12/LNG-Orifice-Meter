"""Açıklayıcı raporlama: konsol özeti ve kendi kendine yeten HTML raporu."""

from __future__ import annotations

import html as _html
from datetime import datetime

from engine import RunResult
from schematic import build_svg

REFERENCE_NOTES: list[str] = [
    "ISO 5167-2: Orifis plakaları ile akış ölçümü — flange taps konfigürasyonu (Table 3 düz boru gereksinimleri yaklaşıktır; sahaya özel streak/enjektör yerleşimi ayrıca değerlendirilmelidir).",
    "Reader-Harris / Gallagher (R-H/G) deşarj katsayısı denklemi, flange taps bağıntıları dahil tam form.",
    "Peng-Robinson (PR) durum denklemi: kriyojenik bileşim için bubble point (doymuş buhar basıncı) ve birinci buhar bileşimi.",
    "Revised Klosek-Zander (K-Z) yoğunluk modeli: sıcaklığa bağlı doymuş molar hacimler (Rackett) + MW bağımlı düzeltme sabitleri.",
    "ISA S75.01.01 kavitasyon/flashing kriterleri (F_L sıvı basınç toparlanma faktörü yaklaşımı).",
    "Isıl değerler bileşen standart molar yanma ısılarından (HHV/NCV, 25 °C / 1 atm) hesaplanır; ön tasarım içindir.",
    "ASME B31.3: minimum et kalınlığı, korozyon payı ve değirmen toleransı kontrolü.",
    "Bu motor ön tasarım ve fizibilite içindir; resmî ölçüm noktası tasarımı, kalibre edilmiş birim ve legal metroloji belirsizlik hesabı gerektirir.",
]


def _esc(s: object) -> str:
    return _html.escape(str(s))


def _badge_class(ok: bool, level: str = "ok") -> str:
    if not ok:
        return "badge bad"
    return "badge good" if level == "ok" else "badge warn"


def build_html(r: RunResult, title: str = "LNG Orifis Ölçüm Noktası Tasarım Raporu") -> str:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    inp, t, s, sf = r.inputs, r.thermo, r.sizing, r.safety
    e = r.energy
    svg = build_svg(inp, r)

    comp_rows = "".join(
        f"<tr><td>{_esc(k)}</td><td>{inp.comp.get(k, 0.0)*100:.2f} %</td></tr>"
        for k in ("CH4", "C2H6", "C3H8", "iC4", "nC4", "iC5", "nC5", "N2")
    )

    ph = sf.phase
    if ph.flashing:
        ph_badge = '<span class="badge bad">KRİTİK: FLASHING</span>'
    elif ph.cavitation:
        ph_badge = '<span class="badge warn">UYARI: KAVİTASYON RİSKİ</span>'
    else:
        ph_badge = '<span class="badge good">GÜVENLİ</span>'
    wall_badge = (
        '<span class="badge good">UYGUN</span>'
        if sf.wall.ok
        else '<span class="badge bad">YETERSİZ</span>'
        if not str(sf.wall.t_actual_mm) == "nan"
        else '<span class="badge warn">GİRİLMEDİ</span>'
    )

    sens_rows = "".join(
        "<tr>"
        f"<td>{row.n2_pct:.2f}</td>"
        f"<td>{row.pv_bara:.4f}</td>"
        f"<td>{row.rho_kgm3:.1f}</td>"
        f"<td>{row.margin_p2:.2f}</td>"
        f"<td><span class='badge {'good' if row.safe else 'bad'}'>"
        f"{'Güvenli' if row.safe else 'Flashing riski'}</span></td>"
        "</tr>"
        for row in r.sensitivity
    )

    note_list = "".join(f"<li>{_esc(n)}</li>" for n in REFERENCE_NOTES)
    warn_list = "".join(f"<li>{_esc(w)}</li>" for w in r.warnings) if r.warnings else "<li>Yok.</li>"

    material = inp.material
    wall_rows = (
        f"<tr><td>Hesap kalınlığı t_hesap (B31.3)</td><td>{sf.wall.t_calc_mm:.2f} mm</td></tr>"
        f"<tr><td>Gerekli kalınlık (t+korozyon {inp.c_mm:.1f})</td><td>{sf.wall.t_required_mm:.2f} mm</td></tr>"
        f"<tr><td>Mevcut (değirmen toleransı sonrası)</td><td>{sf.wall.t_available_mm:.2f} mm</td></tr>"
        f"<tr><td>Durum</td><td>{wall_badge} {'– '.join(sf.wall.notes)}</td></tr>"
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<title>{_esc(title)}</title>
<style>
 body {{ font-family: 'Segoe UI', Helvetica, Arial, sans-serif; margin: 24px; color: #1c2733; background:#f5f7fa; }}
 .wrap {{ max-width: 980px; margin: 0 auto; }}
 h1 {{ font-size: 20px; margin: 4px 0 2px; }}
 .sub {{ color:#5a6b7a; font-size: 13px; margin-bottom: 18px; }}
 h2 {{ font-size: 15px; border-left: 4px solid #0b6ea8; padding-left: 8px; margin-top: 28px; }}
 table {{ border-collapse: collapse; width: 100%; background:#fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
 th,td {{ border: 1px solid #dde3ea; padding: 6px 10px; font-size: 13px; text-align: left; }}
 th {{ background: #eef3f8; }}
 td:last-child {{ text-align: right; font-variant-numeric: tabular-nums; }}
 .meta td:last-child {{ text-align: left; }}
 .badge {{ display:inline-block; padding: 2px 10px; border-radius: 10px; font-size: 12px; font-weight:600; }}
 .good {{ background:#d6f5e0; color:#0a6b2e; }}
 .warn {{ background:#fff3cd; color:#856404; }}
 .bad {{ background:#f8d7da; color:#a02b2b; }}
 .note {{ background:#fff; border:1px solid #dde3ea; padding: 12px 16px; font-size:13px; }}
 ul {{ margin: 6px 0 0 18px; }}
 .summary {{ display:flex; gap:16px; flex-wrap:wrap; margin: 10px 0; }}
 .card {{ flex:1; min-width:180px; background:#fff; border:1px solid #dde3ea; border-radius:8px; padding:12px 16px; }}
 .card .v {{ font-size: 22px; font-weight:700; }}
 .card .l {{ font-size: 12px; color:#5a6b7a; }}
 .foot {{ margin-top: 24px; font-size: 11px; color:#8a97a5; }}
 .svgbox {{ background:#fff; border:1px solid #dde3ea; border-radius:8px; padding:8px; }}
</style></head><body><div class="wrap">
<h1>🔧 {_esc(title)}</h1>
<div class="sub">Üretim: {now} &nbsp;|&nbsp; Malzeme: {_esc(material)} &nbsp;|&nbsp; Pv modeli: {_esc(t.pv_model)}</div>

<div class="summary">
 <div class="card"><div class="v">{s.beta:.3f}</div><div class="l">Beta (β = d/D)</div></div>
 <div class="card"><div class="v">{s.d20_mm:.1f} mm</div><div class="l">İmalat orifis çapı d₂₀</div></div>
 <div class="card"><div class="v">{s.u_flow_pct:.2f} %</div><div class="l">Tahmini akış belirsizliği (±)</div></div>
 <div class="card"><div class="v">{s.rho:.1f} kg/m³</div><div class="l">Çalışma yoğunluğu</div></div>
</div>

<h2>0. Şematik Gösterim</h2>
<div class="svgbox">{svg}</div>

<h2>1. Girdi Parametreleri</h2>
<table class="meta">
<tr><th>Proses</th><th>Değer</th></tr>
<tr><td>Sıcaklık T₁</td><td>{inp.T1_C:.2f} °C</td></tr>
<tr><td>Hat emiş basıncı P₁</td><td>{inp.P1_barg:.2f} bar-g ({inp.P1_barg+1.01325:.2f} bar-a)</td></tr>
<tr><td>Boru iç çapı D₂₀</td><td>{inp.D20_mm:.1f} mm</td></tr>
<tr><td>Nominal kütlesel debi Qm</td><td>{inp.qm_nom_ton_h:.2f} t/h</td></tr>
<tr><td>Hedef ΔP (nominal)</td><td>{inp.dP_target_mbar:.0f} mbar</td></tr>
<tr><td>Turndown (min/max)</td><td>%{inp.q_min_ratio*100:.0f} / %{inp.q_max_ratio*100:.0f}</td></tr>
<tr><td>Hat uzunluğu / pürüzlülük</td><td>{inp.L_pipe_m:.0f} m / {inp.eps_mm:.4f} mm</td></tr>
<tr><td>Darbe hattı F_L</td><td>{inp.FL:.2f}</td></tr>
</table>
<table class="meta" style="margin-top:10px">
<tr><th>Bileşen</th><th>Mol kesri</th></tr>{comp_rows}</table>

<h2>2. Termofiziksel Özellikler</h2>
<table>
<tr><th>Parametre</th><th>Değer</th></tr>
<tr><td>Ortalama molar kütle (M_mix)</td><td>{t.M_mix:.3f} kg/kmol</td></tr>
<tr><td>Doymuş sıvı yoğunluğu (Klosek-Zander)</td><td>{t.rho_sat_kgm3:.2f} kg/m³</td></tr>
<tr><td>Çalışma (subcooled) yoğunluğu</td><td>{t.rho_oper_kgm3:.2f} kg/m³</td></tr>
<tr><td>Bubble point — Peng-Robinson</td><td>{t.Pv_pr_bara:.4f} bar-a</td></tr>
<tr><td>Bubble point — Antoine/Raoult (karşılaştırma)</td><td>{t.Pv_raoult_bara:.4f} bar-a</td></tr>
<tr><td>Kullanılan Pv (model)</td><td>{t.Pv_final_bara:.4f} bar-a ({_esc(t.pv_model)})</td></tr>
</table>
<p class="note"><b>İlk buhar bileşimi (PR):</b>
{", ".join(f"{_esc(k)} %{v*100:.1f}" for k, v in sorted(t.first_vapor_y.items(), key=lambda kv: -kv[1]) if v > 1e-4)} —
azot, sıvıdaki oranına göre buhar fazında belirgin şekilde zenginleşir; bu yüzden yerel faz dengesi kritiktir.</p>

<h2>3. ISO 5167-2 Hidrolik Boyutlandırma</h2>
<table>
<tr><th>Parametre</th><th>Değer</th></tr>
<tr><td>β = d/D (soğuk)</td><td>{s.beta:.5f} ({'UYGUN' if 0.20<=s.beta<=0.75 else 'ARALIK DIŞI'})</td></tr>
<tr><td>Deşarj katsayısı C (R-H/G flange taps)</td><td>{s.C:.5f}</td></tr>
<tr><td>Reynolds sayısı Re_D</td><td>{s.Re_D:,.0f}</td></tr>
<tr><td>Ortalama hat hızı</td><td>{s.velocity_m_s:.3f} m/s</td></tr>
<tr><td>Soğuk boru iç çapı D_T</td><td>{s.DT_mm:.3f} mm</td></tr>
<tr><td>Soğuk orifis çapı d_T</td><td>{s.dT_mm:.3f} mm</td></tr>
<tr><td><b>İmalat çapı d₂₀ (@20°C)</b></td><td><b>{s.d20_mm:.3f} mm</b></td></tr>
<tr><td>Çözücü / yakınsama</td><td>{_esc(s.solver)}</td></tr>
</table>

<h2>4. Akış Aralığı ve Belirsizlik</h2>
<table>
<tr><th>Parametre</th><th>Değer</th></tr>
<tr><td>ΔP nominal</td><td>{inp.dP_target_mbar:.0f} mbar ({s.dP_nom_pa:.0f} Pa)</td></tr>
<tr><td>ΔP @ Qmax (%{inp.q_max_ratio*100:.0f})</td><td>{s.dP_max_mbar:.1f} mbar</td></tr>
<tr><td>ΔP @ Qmin (%{inp.q_min_ratio*100:.0f})</td><td>{s.dP_min_mbar:.1f} mbar</td></tr>
<tr><td>Akış belirsizliği u(q)/q (k=2 tahmini)</td><td>± {s.u_flow_pct:.2f} %</td></tr>
<tr><td>Deşarj katsayısı belirsizliği u(C)/C</td><td>± {s.uC_C_pct:.2f} %</td></tr>
</table>

<h2>5. Enerji (Isıl Değer)</h2>
<table>
<tr><th>Parametre</th><th>Değer</th></tr>
<tr><td>Isıl değer GCV</td><td>{e.GCV_mj_kg:.3f} MJ/kg</td></tr>
<tr><td>Isıl değer NCV</td><td>{e.NCV_mj_kg:.3f} MJ/kg</td></tr>
<tr><td>GCV (molar)</td><td>{e.GCV_mj_kmol:.1f} MJ/kmol</td></tr>
<tr><td>GCV (gaz, ideal Nm³)</td><td>{e.GCV_mj_Nm3:.2f} MJ/Nm³</td></tr>
<tr><td>NCV (gaz, ideal Nm³)</td><td>{e.NCV_mj_Nm3:.2f} MJ/Nm³</td></tr>
<tr><td>Termal güç Q×GCV</td><td>{e.MW_mj_s:.1f} MW</td></tr>
<tr><td>Termal güç Q×NCV</td><td>{e.MW_lv_mj_s:.1f} MW</td></tr>
</table>

<h2>6. Emniyet Denetim Matrisi</h2>
<table>
<tr><th>Parametre</th><th>Değer</th></tr>
<tr><td>Faz değişimi durumu</td><td>{ph_badge}</td></tr>
<tr><td>P₂ (plaka sonrası, boru kaybı dahil)</td><td>{ph.P2_barA:.3f} bar-a</td></tr>
<tr><td>P_vc (vena contracta)</td><td>{ph.Pvc_barA:.3f} bar-a</td></tr>
<tr><td>Pv (bubble point)</td><td>{ph.Pv_barA:.4f} bar-a</td></tr>
<tr><td>Plaka ΔP (Qmax)</td><td>{ph.dP_plate_max_bar*1000:.0f} mbar</td></tr>
<tr><td>Boru sürtünme ΔP</td><td>{ph.dP_pipe_bar*1000:.1f} mbar</td></tr>
<tr><td>Marj P₂/Pv</td><td>{ph.margin_P2_over_Pv:.2f} x</td></tr>
<tr><td>Marj Pvc/Pv</td><td>{ph.margin_Pvc_over_Pv:.2f} x</td></tr>
<tr><td>B31.3 et kalınlığı (malzeme {_esc(material)})</td><td>{wall_badge}</td></tr>{wall_rows}
<tr><td>Upstream düz boru</td><td>≥ 20D → {sf.straight_up_m:.2f} m</td></tr>
<tr><td>Downstream düz boru</td><td>≥ 5D → {sf.straight_down_m:.2f} m</td></tr>
</table>

<h2>7. N₂ Duyarlılık Analizi</h2>
<p class="note">Bubble point başta olmak üzere sonuçlar azot oranına duyarlıdır. Belirlenen P₂ basıncında
(boru kaybı dahil) N₂ oranı değişiminin etkisi:</p>
<table>
<tr><th>N₂ (mol%)</th><th>Pv (bar-a)</th><th>ρ (kg/m³)</th><th>Marj P₂/Pv</th><th>Durum</th></tr>
{sens_rows}
</table>

<h2>8. Uyarılar ve Dikkat Notları</h2>
<ul>{warn_list}</ul>

<h2>9. Varsayımlar ve Referanslar</h2>
<ul>{note_list}</ul>

<div class="foot">Bu rapor bir ön tasarım hesaplamasıdır; kalibrasyon, montaj ve legal metroloji onayı tasarım paketine dahil edilir.</div>
</div></body></html>
"""
    return html_doc


def print_console_summary(r: RunResult) -> None:
    line = "=" * 62
    print(f"\n{line}")
    print("  LNG ORİFİS ÖLÇÜM NOKTASI — HESAP ÖZETİ")
    print(line)
    t, s, sf = r.thermo, r.sizing, r.safety
    print(f"  M_mix            : {t.M_mix:9.3f} kg/kmol")
    print(f"  ρ_doğru          : {t.rho_oper_kgm3:9.2f} kg/m³  (doymuş {t.rho_sat_kgm3:.2f})")
    print(f"  Pv (PR)          : {t.Pv_pr_bara:9.4f} bar-a  (Raoult {t.Pv_raoult_bara:.4f})")
    print(f"  β                : {s.beta:9.5f}   C = {s.C:.5f}")
    print(f"  Re_D             : {s.Re_D:9,.0f}")
    print(f"  d₂₀ (imalat)     : {s.d20_mm:9.3f} mm   (soğuk dT = {s.dT_mm:.3f} mm)")
    print(f"  ΔP max/min       : {s.dP_max_mbar:9.1f} / {s.dP_min_mbar:6.1f} mbar")
    print(f"  u(q)/q           : {s.u_flow_pct:9.2f} %  (uC/C = {s.uC_C_pct:.2f} %)")
    print(f"  Faz durumu       : {sf.phase.status}")
    print(f"  B31.3            : " + ("UYGUN" if sf.wall.ok else "YETERSİZ / GİRİLMEDİ"))
    print(line)
    for w in r.warnings:
        print(f"  [!] {w}")
    print(line)


def write_html(r: RunResult, path: str, title: str = "LNG Orifis Ölçüm Noktası Tasarım Raporu") -> str:
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(build_html(r, title))
    return path