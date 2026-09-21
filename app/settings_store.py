"""Settings + sample data helpers. Never log or return the raw API key in responses."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parent
DATA_DIR = APP_ROOT / "data"
REVIEWS_DIR = DATA_DIR / "reviews"
SETTINGS_PATH = DATA_DIR / "settings.json"
PATTERNS_PATH = DATA_DIR / "patterns.md"
PARENT_ENV = PROJECT_ROOT / ".env"
APP_ENV = APP_ROOT / ".env"

DEFAULTS = {
    "riot_id": "ScrewedviaSonic#NA1",
    "region": "NA",
    "partner_hint": "Tudon#NA1",
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REVIEWS_DIR.mkdir(parents=True, exist_ok=True)
    if not PATTERNS_PATH.exists():
        seed = PROJECT_ROOT / "reviews" / "patterns_seed.md"
        if seed.exists():
            PATTERNS_PATH.write_text(seed.read_text())
        else:
            PATTERNS_PATH.write_text(
                "# Pattern ledger\n\n## Recent autopsies\n\n"
                "## Standing drill\n"
                "Before stage 4: name your win-con, partner's win-con, and the contested pool to avoid.\n"
            )


def _read_key_from_env_file(path: Path) -> str | None:
    if not path.exists():
        return None
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("RIOT_API_KEY="):
            val = line.split("=", 1)[1].strip().strip('"').strip("'")
            return val or None
    return None


def load_api_key() -> str | None:
    """Load Riot API key from env, app .env, or parent ../.env. Never print it."""
    if os.environ.get("TFT_COACH_FORCE_DRY_RUN", "").strip() in ("1", "true", "yes"):
        return None
    if os.environ.get("RIOT_API_KEY"):
        return os.environ["RIOT_API_KEY"].strip() or None
    for path in (APP_ENV, PARENT_ENV):
        key = _read_key_from_env_file(path)
        if key:
            return key
    # settings.json may store key locally (not committed)
    settings = _load_settings_raw()
    key = (settings.get("riot_api_key") or "").strip()
    return key or None


def save_api_key_to_env(key: str) -> None:
    """Write RIOT_API_KEY to app-local .env only (never commit)."""
    key = key.strip()
    lines: list[str] = []
    if APP_ENV.exists():
        for line in APP_ENV.read_text().splitlines():
            if line.startswith("RIOT_API_KEY="):
                continue
            lines.append(line)
    lines.append(f"RIOT_API_KEY={key}")
    APP_ENV.write_text("\n".join(lines) + "\n")
    os.environ["RIOT_API_KEY"] = key


def _load_settings_raw() -> dict[str, Any]:
    ensure_dirs()
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())
        except json.JSONDecodeError:
            return dict(DEFAULTS)
    return dict(DEFAULTS)


def load_settings() -> dict[str, Any]:
    raw = _load_settings_raw()
    has_key = bool(load_api_key())
    return {
        "riot_id": raw.get("riot_id") or DEFAULTS["riot_id"],
        "region": raw.get("region") or DEFAULTS["region"],
        "partner_hint": raw.get("partner_hint") or DEFAULTS["partner_hint"],
        "has_api_key": has_key,
        "dry_run": not has_key,
        "api_key_masked": "••••••••" if has_key else None,
    }


def save_settings(
    riot_id: str | None = None,
    region: str | None = None,
    partner_hint: str | None = None,
    riot_api_key: str | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    raw = _load_settings_raw()
    if riot_id is not None:
        raw["riot_id"] = riot_id.strip()
    if region is not None:
        raw["region"] = region.strip().upper()
    if partner_hint is not None:
        raw["partner_hint"] = partner_hint.strip()
    if riot_api_key is not None and riot_api_key.strip() and riot_api_key.strip() != "••••••••":
        # Prefer .env; also keep a copy flag in settings without writing key into committed files
        save_api_key_to_env(riot_api_key.strip())
        # Do not persist plaintext key into settings.json if we have .env
        raw.pop("riot_api_key", None)
    SETTINGS_PATH.write_text(json.dumps({k: v for k, v in raw.items() if k != "riot_api_key"}, indent=2))
    return load_settings()


def parse_riot_id(riot_id: str) -> tuple[str, str]:
    if "#" not in riot_id:
        raise ValueError("Riot ID must look like Name#TAG")
    name, tag = riot_id.split("#", 1)
    name, tag = name.strip(), tag.strip()
    if not name or not tag:
        raise ValueError("Riot ID must look like Name#TAG")
    return name, tag


def load_sample_summaries() -> list[dict]:
    """Dry-run data: parent data/summaries.json or export/sample_summaries.json."""
    candidates = [
        PROJECT_ROOT / "data" / "summaries.json",
        PROJECT_ROOT / "export" / "sample_summaries.json",
        APP_ROOT / "data" / "sample_summaries.json",
    ]
    for path in candidates:
        if path.exists():
            data = json.loads(path.read_text())
            for s in data:
                s["_dry_run"] = True
                s.setdefault("is_double_up", s.get("queue") == "DOUBLE_UP")
            return data
    return []


def list_saved_reviews() -> list[dict]:
    ensure_dirs()
    out = []
    for p in sorted(REVIEWS_DIR.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        out.append({"match_id": p.stem, "path": str(p.name), "mtime": p.stat().st_mtime})
    return out
