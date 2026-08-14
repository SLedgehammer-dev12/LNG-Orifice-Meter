"""Kullanıcı tercihleri (tema + birimler) kalıcılığı.

Config: ~/.lng_orifice_meter/config.json (JSON, UTF-8).
"""

from __future__ import annotations

import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".lng_orifice_meter")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS: dict = {
    "theme": "light",
    "preset": "SI",
    "input_units": {},
    "output_units": {},
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            cfg.update({k: data[k] for k in DEFAULTS if k in data})
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
            json.dump({k: cfg.get(k, v) for k, v in DEFAULTS.items()}, fh,
                      ensure_ascii=False, indent=2)
    except OSError:
        pass
