"""LNG Orifis Ölçüm Noktası Tasarım Aracı — giriş noktası.

Kullanım:
    python3 main.py                    # Tkinter masaüstü arayüzünü başlatır
    python3 main.py --cli              # Komut satırı hesabı (BOTAŞ varsayılanları)
    python3 main.py --cli --qm 200 --dp 300 --out rapor.html
    python3 main.py --check-updates    # En son sürümü kontrol eder
    python3 main.py --update           # En son sürümü indirir
    python3 test_engine.py             # Motor doğrulama testlerini çalıştırır
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from engine import RunInputs, run_engineering
from report import print_console_summary, write_html
from updater import APP_VERSION, check_for_updates, download, platform_asset, reveal_in_folder

BOTAŞ_DEFAULT_COMP = {
    "CH4": 0.915,
    "C2H6": 0.055,
    "C3H8": 0.018,
    "iC4": 0.004,
    "nC4": 0.004,
    "iC5": 0.001,
    "nC5": 0.001,
    "N2": 0.002,
}


def parse_comp(spec: str) -> dict[str, float]:
    comp: dict[str, float] = {}
    for item in spec.split(","):
        if not item.strip():
            continue
        if ":" not in item and "=" not in item:
            raise ValueError(f"Bileşim öğesi geçersiz: {item!r} (CH4:0.915 biçiminde olmalı)")
        k, _, v = item.replace("=", ":").partition(":")
        k = k.strip()
        comp[k] = float(v)
    missing = [c for c in ("CH4", "C2H6", "C3H8", "iC4", "nC4", "iC5", "nC5", "N2") if c not in comp]
    if missing:
        raise ValueError("Eksik bileşenler: " + ", ".join(missing))
    return comp


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="LNG Orifis Ölçüm Noktası Tasarım Aracı — ISO 5167-2 / PR EOS / Klosek-Zander",
    )
    p.add_argument("--cli", action="store_true", help="GUI yerine komut satırı modunda çalıştır.")
    p.add_argument("--comp", type=str, default=None,
                   help='Bileşim "CH4:0.915,C2H6:0.055,..." (varsayılan BOTAŞ örneği).')
    p.add_argument("--t1", type=float, default=-163.0, help="Çalışma sıcaklığı (°C).")
    p.add_argument("--p1", type=float, default=8.5, help="Emiş basıncı (bar-g).")
    p.add_argument("--d20", type=float, default=300.0, help="Boru iç çapı @20°C (mm).")
    p.add_argument("--qm", type=float, default=150.0, help="Nominal debi (ton/saat).")
    p.add_argument("--dp", type=float, default=250.0, help="Hedef ΔP (mbar).")
    p.add_argument("--qmin", type=float, default=30.0, help="Min turndown (%).")
    p.add_argument("--qmax", type=float, default=120.0, help="Max turndown (%).")
    p.add_argument("--L", type=float, default=50.0, help="Hat uzunluğu (m).")
    p.add_argument("--od", type=float, default=323.9, help="Boru dış çapı (mm).")
    p.add_argument("--t", type=float, default=9.53, help="Et kalınlığı (mm).")
    p.add_argument("--out", type=str, default=None, help="HTML rapor yolu (varsayılan: lng_orifice_rapor.html).")
    p.add_argument("--no-html", action="store_true", help="HTML raporu üretme.")
    p.add_argument("--json", type=str, default=None, help="Sonuçları JSON dosyasına yaz.")
    p.add_argument("--check-updates", action="store_true",
                   help="GitHub Releases'tan en son sürümü kontrol et (GUI başlatmaz).")
    p.add_argument("--update", action="store_true",
                   help="En son sürümü indir (varsayılan: ~/Downloads) ve klasörde göster.")
    return p


def build_inputs(args: argparse.Namespace) -> RunInputs:
    comp = BOTAŞ_DEFAULT_COMP if args.comp is None else parse_comp(args.comp)
    return RunInputs(
        comp=comp,
        T1_C=args.t1,
        P1_barg=args.p1,
        D20_mm=args.d20,
        qm_nom_ton_h=args.qm,
        dP_target_mbar=args.dp,
        q_min_ratio=args.qmin / 100.0,
        q_max_ratio=args.qmax / 100.0,
        L_pipe_m=args.L,
        Do_mm=args.od,
        t_actual_mm=args.t,
    )


def result_to_dict(r) -> dict:
    t, s, sf = r.thermo, r.sizing, r.safety
    return {
        "uretim": datetime.now().isoformat(timespec="seconds"),
        "termofiziksel": {
            "M_mix_kg_kmol": round(t.M_mix, 3),
            "rho_doymus_kg_m3": round(t.rho_sat_kgm3, 2),
            "rho_calisma_kg_m3": round(t.rho_oper_kgm3, 2),
            "Pv_PR_barA": round(t.Pv_pr_bara, 4),
            "Pv_Raoult_barA": round(t.Pv_raoult_bara, 4),
            "Pv_final_barA": round(t.Pv_final_bara, 4),
            "Pv_model": t.pv_model,
            "ilk_buhar": {k: round(v, 4) for k, v in t.first_vapor_y.items()},
        },
        "hidrolik": {
            "beta": round(s.beta, 5),
            "C": round(s.C, 5),
            "Re_D": round(s.Re_D, 0),
            "hiz_m_s": round(s.velocity_m_s, 3),
            "d20_imalat_mm": round(s.d20_mm, 3),
            "dT_soguk_mm": round(s.dT_mm, 3),
            "DT_soguk_mm": round(s.DT_mm, 3),
            "cozucu": s.solver,
        },
        "akis_araligi": {
            "dP_nom_Pa": round(s.dP_nom_pa, 0),
            "dP_max_mbar": round(s.dP_max_mbar, 1),
            "dP_min_mbar": round(s.dP_min_mbar, 1),
            "dP_perm_loss_mbar": round(s.dP_perm_loss_mbar, 1),
            "pompa_guc_kaybi_kW": round(s.pump_power_loss_kw, 2),
            "u_q_q_pct": round(s.u_flow_pct, 2),
        },
        "emniyet": {
            "durum": sf.phase.status,
            "P2_barA": round(sf.phase.P2_barA, 3),
            "Pvc_barA": round(sf.phase.Pvc_barA, 3),
            "Pv_barA": round(sf.phase.Pv_barA, 4),
            "boru_kaybi_mbar": round(sf.phase.dP_pipe_bar * 1000, 1),
            "marj_P2_Pv": round(sf.phase.margin_P2_over_Pv, 2),
            "tanimlanan_boru_B36_19M": sf.wall.identified_pipe,
            "onerilen_schedule": sf.wall.recommended_schedule,
            "b31_3_uygun": sf.wall.ok,
            "beta_aralik": sf.beta_in_range,
        },
        "enerji": (
            {
                "GCV_MJ_kg": round(e.GCV_mj_kg, 3),
                "NCV_MJ_kg": round(e.NCV_mj_kg, 3),
                "GCV_MJ_kmol": round(e.GCV_mj_kmol, 1),
                "GCV_MJ_Nm3": round(e.GCV_mj_Nm3, 2),
                "NCV_MJ_Nm3": round(e.NCV_mj_Nm3, 2),
                "termal_guc_MW_GCV": round(e.MW_mj_s, 2),
                "termal_guc_MW_NCV": round(e.MW_lv_mj_s, 2),
            }
            if (e := r.energy) is not None
            else None
        ),
        "uyarilar": r.warnings,
        "n2_duyarlilik": [
            {"n2_pct": row.n2_pct, "pv_barA": round(row.pv_bara, 4), "rho_kg_m3": round(row.rho_kgm3, 1),
             "marj": round(row.margin_p2, 2), "guvenli": row.safe}
            for row in r.sensitivity
        ],
    }


def _ensure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def run_cli(args: argparse.Namespace) -> int:
    _ensure_utf8_stdio()
    try:
        inp = build_inputs(args)
        result = run_engineering(inp)
    except Exception as e:  # noqa: BLE001
        print(f"HATA: {e}", file=sys.stderr)
        return 1

    print_console_summary(result)

    if not args.no_html:
        out = args.out or "lng_orifice_rapor.html"
        write_html(result, out)
        print(f"HTML raporu yazıldı: {out}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(result_to_dict(result), fh, ensure_ascii=False, indent=2)
        print(f"JSON sonucu yazıldı: {args.json}")

    return 0


def run_updates(args: argparse.Namespace) -> int:
    _ensure_utf8_stdio()
    info = check_for_updates()
    print(f"Şu anki sürüm : v{info.current_version}")
    if info.error:
        print(f"Sürüm kontrolü yapılamadı: {info.error}")
        return 1
    print(f"En son sürüm  : v{info.latest_version}")
    if not info.has_update:
        print("Durum         : Güncel — güncelleme gerekmiyor.")
        return 0

    print("Durum         : GÜNCELLEME MEVCUT")
    if not args.update:
        print(f"Sayfa         : {info.release_url}")
        return 0

    name_url = platform_asset(info.assets)
    if name_url is None:
        print(f"Bu platform için indirilebilir dosya bulunamadı.\nSayfa: {info.release_url}")
        return 1
    name, url = name_url
    try:
        path = download(url, filename=name)
    except Exception as e:  # noqa: BLE001
        print(f"İndirme hatası: {e}", file=sys.stderr)
        return 1
    reveal_in_folder(path)
    print(f"İndirildi      : {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check_updates or args.update:
        return run_updates(args)
    if args.cli:
        return run_cli(args)
    try:
        import tkinter  # noqa: F401
    except Exception:  # noqa: BLE001
        print("Tkinter kullanılamıyor. GUI için python3-tk gerekir veya --cli kullanın.", file=sys.stderr)
        return 2
    from app import main as gui_main

    gui_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
