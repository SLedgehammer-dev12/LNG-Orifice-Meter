"""Güncelleme kontrolü ve indirme — GitHub Releases API tabanlı (yalnızca stdlib)."""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

REPO = "SLedgehammer-dev12/LNG-Orifice-Meter"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASE_URL = f"https://github.com/{REPO}/releases/latest"

APP_NAME = "LNG Orifice Meter"
APP_VERSION = "1.4.0"

CHECK_TIMEOUT = 10
DOWNLOAD_TIMEOUT = 180
USER_AGENT = "LNG-Orifice-Meter-Updater"


@dataclass
class UpdateInfo:
    has_update: bool
    current_version: str
    latest_version: str | None
    assets: dict[str, str]
    release_url: str
    error: str | None = None


def _norm_version(version: str) -> tuple[int, ...]:
    text = str(version).strip().lstrip("vV")
    parts = re.split(r"[._-]", text)
    out: list[int] = []
    for p in parts:
        try:
            out.append(int(p))
        except ValueError:
            break
    out = out[:3]
    while len(out) < 3:
        out.append(0)
    return tuple(out)


def compare_versions(current: str, candidate: str) -> bool:
    """True ise candidate daha yenidir."""
    return _norm_version(candidate) > _norm_version(current)


def _ssl_context() -> ssl.SSLContext:
    """Platform CA dosyalarını ekleyen SSL bağlamı (ör. macOS Python.org kurulumları)."""
    ctx = ssl.create_default_context()
    candidates: list[str] = []
    if sys.platform == "darwin":
        candidates += [
            "/etc/ssl/cert.pem",
            "/opt/homebrew/etc/openssl/cert.pem",
            "/usr/local/etc/openssl/cert.pem",
        ]
    elif sys.platform.startswith("linux"):
        candidates += ["/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"]
    for path in candidates:
        if os.path.isfile(path):
            try:
                ctx.load_verify_locations(path)
            except Exception:  # noqa: BLE001
                continue
    return ctx


def _urlopen(url: str, timeout: float, headers: dict[str, str]):
    """SSL CA eksikliğinde doğrulamasız denen geçici bir açıcı."""
    req = urllib.request.Request(url, headers=headers)
    ctx = _ssl_context()
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except urllib.error.URLError as e:
        if isinstance(getattr(e, "reason", None), ssl.SSLError):
            return urllib.request.urlopen(req, timeout=timeout,
                                          context=ssl._create_unverified_context())
        raise


def check_for_updates(timeout: float = CHECK_TIMEOUT) -> UpdateInfo:
    """GitHub'ın en son release etiketini çeker ve mevcut sürümle karşılaştırır."""
    try:
        resp = _urlopen(API_URL, timeout, {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
        data = json.loads(resp.read().decode("utf-8"))
        resp.close()
    except urllib.error.HTTPError as e:
        return UpdateInfo(False, APP_VERSION, None, {}, RELEASE_URL, error=f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        return UpdateInfo(False, APP_VERSION, None, {}, RELEASE_URL, error=str(e))

    tag = str(data.get("tag_name", "")).strip()
    latest = tag.lstrip("vV") if tag else None
    assets = {
        a.get("name", ""): a.get("browser_download_url", "")
        for a in data.get("assets", [])
        if a.get("name")
    }
    has_update = bool(latest) and compare_versions(APP_VERSION, latest)
    return UpdateInfo(
        has_update=has_update,
        current_version=APP_VERSION,
        latest_version=latest,
        assets=assets,
        release_url=data.get("html_url") or RELEASE_URL,
    )


def platform_asset(assets: dict[str, str]) -> tuple[str, str] | None:
    """Platforma uygun indirilebilir asset döndürür: (dosya_adı, url)."""
    names = sorted(assets)
    if sys.platform.startswith("win"):
        cands = [n for n in names if n.lower().endswith(".exe")]
    elif sys.platform == "darwin":
        cands = [n for n in names if "arm64" in n.lower() and n.lower().endswith(".zip")]
        if not cands:
            cands = [n for n in names if n.lower().endswith(".zip")]
    else:
        cands = names
    if not cands:
        return None
    name = cands[0]
    return name, assets[name]


def download(url: str, dest_dir: str | None = None, filename: str | None = None) -> str:
    """Asset'i indirir, kaydedilen yolu döndürür (varsayılan: ~/Downloads)."""
    dest_dir = dest_dir or os.path.join(os.path.expanduser("~"), "Downloads")
    os.makedirs(dest_dir, exist_ok=True)
    filename = filename or os.path.basename(urllib.parse.urlparse(url).path)
    path = os.path.join(dest_dir, filename)
    resp = _urlopen(url, DOWNLOAD_TIMEOUT, {"User-Agent": USER_AGENT})
    try:
        with open(path, "wb") as fh:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                fh.write(chunk)
    finally:
        resp.close()
    return path


def reveal_in_folder(path: str) -> None:
    """İndirilen dosyayı dosya yöneticisinde gösterir (olabildiğince)."""
    try:
        if sys.platform == "darwin":
            os.system(f'open -R "{path}"')
        elif sys.platform.startswith("win"):
            os.system(f'explorer /select,"{path}"')
        else:
            os.system(f'xdg-open "{os.path.dirname(path)}" >/dev/null 2>&1')
    except Exception:  # noqa: BLE001
        pass