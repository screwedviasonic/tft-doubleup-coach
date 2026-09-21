"""TFT Double Up post-game coach — FastAPI local web app."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from autopsy import generate_autopsy, update_patterns_ledger
from riot_client import pull_recent_summaries, fetch_match, resolve_puuid, summarize_match
from settings_store import (
    DATA_DIR,
    PATTERNS_PATH,
    REVIEWS_DIR,
    ensure_dirs,
    list_saved_reviews,
    load_api_key,
    load_sample_summaries,
    load_settings,
    parse_riot_id,
    save_settings,
)

APP_ROOT = Path(__file__).resolve().parent

app = FastAPI(title="TFT Double Up Coach", version="0.1.0")
ensure_dirs()

static_dir = APP_ROOT / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# In-memory cache of latest live pull (cleared on restart)
_live_cache: list[dict[str, Any]] = []


class SettingsIn(BaseModel):
    riot_id: str | None = None
    region: str | None = None
    partner_hint: str | None = None
    riot_api_key: str | None = None


class ReviewIn(BaseModel):
    match_id: str | None = None
    force_live: bool = False
    force_dry: bool = False


def _get_summaries(force_live: bool = False, force_dry: bool = False) -> tuple[list[dict], bool]:
    """Return (summaries, dry_run). Prefer live if key present unless dry forced."""
    global _live_cache
    if force_dry:
        samples = load_sample_summaries()
        if not samples:
            raise HTTPException(status_code=404, detail="No sample summaries for dry-run")
        return samples, True
    key = load_api_key()
    settings = load_settings()
    if key and (force_live or not _live_cache):
        try:
            name, tag = parse_riot_id(settings["riot_id"])
            summaries = pull_recent_summaries(name, tag, key, count=20, double_up_only=True)
            _live_cache = summaries
            return summaries, False
        except Exception as e:
            # Fall back to sample if live fails
            samples = load_sample_summaries()
            if samples:
                return samples, True
            raise HTTPException(status_code=502, detail=f"Riot API error: {e}") from e
    if key and _live_cache:
        return _live_cache, False
    samples = load_sample_summaries()
    if not samples:
        raise HTTPException(status_code=404, detail="No sample summaries and no API key")
    return samples, True


def _find_summary(match_id: str | None, summaries: list[dict]) -> dict:
    if not summaries:
        raise HTTPException(status_code=404, detail="No matches available")
    if not match_id:
        return summaries[0]
    for s in summaries:
        if s.get("match_id") == match_id:
            return s
    raise HTTPException(status_code=404, detail=f"Match {match_id} not found in recent list")


def _persist_review(autopsy: dict) -> dict:
    ensure_dirs()
    mid = autopsy["match_id"]
    place = autopsy.get("placement")
    md_path = REVIEWS_DIR / f"{mid}.md"
    md_path.write_text(autopsy["markdown"])
    meta_path = REVIEWS_DIR / f"{mid}.json"
    meta = {k: v for k, v in autopsy.items() if k != "markdown"}
    meta_path.write_text(json.dumps(meta, indent=2))
    update_patterns_ledger(PATTERNS_PATH, autopsy)
    return {"review_path": str(md_path.name), "patterns_path": str(PATTERNS_PATH.name)}


@app.get("/api/health")
def health():
    settings = load_settings()
    samples = load_sample_summaries()
    return {
        "ok": True,
        "dry_run": settings["dry_run"],
        "has_api_key": settings["has_api_key"],
        "riot_id": settings["riot_id"],
        "sample_count": len(samples),
        "saved_reviews": len(list_saved_reviews()),
    }


@app.get("/api/settings")
def get_settings():
    return load_settings()


@app.post("/api/settings")
def post_settings(body: SettingsIn):
    return save_settings(
        riot_id=body.riot_id,
        region=body.region,
        partner_hint=body.partner_hint,
        riot_api_key=body.riot_api_key,
    )


@app.get("/api/matches")
def list_matches(refresh: bool = False, dry_run: bool = False):
    summaries, dry_run = _get_summaries(force_live=refresh, force_dry=dry_run)
    # lightweight list for UI
    items = []
    for s in summaries:
        items.append({
            "match_id": s.get("match_id"),
            "when": s.get("when"),
            "placement": s.get("placement"),
            "partner_placement": s.get("partner_placement"),
            "partner_name": s.get("partner_name"),
            "level": s.get("level"),
            "last_round": s.get("last_round"),
            "queue": s.get("queue"),
            "set": s.get("set"),
            "traits": (s.get("traits") or [])[:4],
        })
    return {"dry_run": dry_run, "matches": items}


@app.post("/api/review")
def review_match(body: ReviewIn | None = None):
    body = body or ReviewIn()
    settings = load_settings()
    summaries, dry_run = _get_summaries(force_live=body.force_live, force_dry=body.force_dry)

    # If live key and specific match not in cache, try fetch single match
    key = None if body.force_dry else load_api_key()
    summary = None
    if body.match_id:
        try:
            summary = _find_summary(body.match_id, summaries)
        except HTTPException:
            summary = None
        if summary is None and key and not dry_run:
            try:
                name, tag = parse_riot_id(settings["riot_id"])
                puuid, _ = resolve_puuid(name, tag, key)
                match = fetch_match(body.match_id, key)
                summary = summarize_match(match, puuid)
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Failed to fetch match: {e}") from e
        if summary is None:
            raise HTTPException(status_code=404, detail=f"Match {body.match_id} not found")
    else:
        summary = _find_summary(None, summaries)

    summary = dict(summary)
    summary["_dry_run"] = dry_run
    autopsy = generate_autopsy(summary, partner_hint=settings.get("partner_hint") or "Tudon")
    autopsy["dry_run"] = dry_run
    persisted = _persist_review(autopsy)
    return {**autopsy, **persisted}


@app.get("/api/review/last")
def review_last():
    return review_match(ReviewIn(match_id=None, force_live=False))


@app.get("/api/patterns")
def get_patterns():
    ensure_dirs()
    return {"markdown": PATTERNS_PATH.read_text() if PATTERNS_PATH.exists() else ""}


@app.get("/api/reviews")
def get_reviews():
    return {"reviews": list_saved_reviews()}


@app.get("/", response_class=HTMLResponse)
def index():
    html_path = static_dir / "index.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="index.html missing")
    return HTMLResponse(html_path.read_text())
