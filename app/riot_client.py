"""Riot TFT API client — adapted from pull_matches.py (do not break that script)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Americas routing for NA accounts
ACCOUNT_HOST = "https://americas.api.riotgames.com"
MATCH_HOST = "https://americas.api.riotgames.com"

DOUBLE_UP_QUEUE_IDS = {1160, 1161}
QUEUE_NAMES = {
    1090: "NORMAL",
    1100: "RANKED",
    1130: "HYPER_ROLL",
    1160: "RANKED_DOUBLE_UP",
    1161: "RANKED_DOUBLE_UP",
}

# Adjacent placement pairs for Double Up partner inference
_PARTNER_PAIRS = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7}

USER_AGENT = "TFTDoubleUpCoachPOC/0.1 (personal)"


def api_get(url: str, key: str) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={
            "X-Riot-Token": key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code} for {url}: {body[:500]}") from e


def resolve_puuid(game_name: str, tag_line: str, key: str) -> tuple[str, dict]:
    encoded_name = urllib.parse.quote(game_name)
    encoded_tag = urllib.parse.quote(tag_line)
    account = api_get(
        f"{ACCOUNT_HOST}/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}",
        key,
    )
    return account["puuid"], account


def fetch_match_ids(puuid: str, key: str, count: int = 20) -> list[str]:
    return api_get(
        f"{MATCH_HOST}/tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count={count}",
        key,
    )


def fetch_match(match_id: str, key: str) -> dict:
    return api_get(f"{MATCH_HOST}/tft/match/v1/matches/{match_id}", key)


def _clean_unit_name(raw: str | None) -> str:
    if not raw:
        return "?"
    name = raw
    for prefix in ("TFT18_", "TFT17_", "TFT16_", "TFT15_", "TFT14_", "TFT13_", "TFT12_", "TFT11_", "TFT10_", "TFT9_", "TFT8_", "TFT7_", "TFT6_", "TFT5_", "TFT4_", "TFT3_", "TFT"):
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break
    return name


def _clean_item(raw: Any) -> str:
    if isinstance(raw, int):
        return str(raw)
    s = str(raw)
    for prefix in ("TFT_Item_", "TFT18_Item_", "TFT5_Item_", "Item_"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
            break
    return s


def _format_board_unit(u: dict) -> str:
    name = _clean_unit_name(u.get("character_id") or u.get("name"))
    tier = u.get("tier") or 1
    items_raw = u.get("itemNames") or u.get("items") or []
    items = [_clean_item(i) for i in items_raw if i]
    star = "★" * int(tier)
    if items:
        return f"{name}{star}[{','.join(items)}]"
    return f"{name}{star}"


def _infer_partner(participants: list[dict], me: dict, puuid: str) -> dict | None:
    """Infer Double Up partner via partner_group_id or adjacent placements."""
    pgid = me.get("partner_group_id")
    if pgid is not None:
        partner = next(
            (
                p
                for p in participants
                if p.get("partner_group_id") == pgid and p.get("puuid") != puuid
            ),
            None,
        )
        if partner:
            return partner

    my_place = me.get("placement")
    if my_place is None:
        return None
    target = _PARTNER_PAIRS.get(int(my_place))
    if target is None:
        return None
    return next((p for p in participants if p.get("placement") == target), None)


def _riot_name(p: dict | None) -> str | None:
    if not p:
        return None
    gn = p.get("riotIdGameName") or p.get("gameName")
    tl = p.get("riotIdTagline") or p.get("tagLine")
    if gn and tl:
        return f"{gn}#{tl}"
    if gn:
        return gn
    return None


def summarize_match(match: dict, puuid: str) -> dict[str, Any]:
    """Build a coach-friendly summary from a raw match payload."""
    info = match.get("info", {})
    metadata = match.get("metadata", {})
    match_id = metadata.get("match_id") or info.get("game_id")
    queue_id = info.get("queue_id") or info.get("queueId")
    participants = info.get("participants", [])
    me = next((p for p in participants if p.get("puuid") == puuid), None)
    partner = _infer_partner(participants, me, puuid) if me else None

    traits = []
    if me:
        for t in me.get("traits") or []:
            if t.get("style", 0) >= 1:
                traits.append(f"{_clean_unit_name(t.get('name'))}:{t.get('num_units', 0)}")

    board = [_format_board_unit(u) for u in (me.get("units") if me else []) or []]
    partner_board = [
        _format_board_unit(u) for u in (partner.get("units") if partner else []) or []
    ]

    game_dt = info.get("game_datetime")
    when = None
    if game_dt:
        try:
            # Riot returns ms epoch
            from datetime import datetime, timezone, timedelta

            ct = timezone(timedelta(hours=-5))  # America/Chicago approx (CST label)
            when = datetime.fromtimestamp(game_dt / 1000, tz=ct).strftime("%Y-%m-%d %H:%M")
        except Exception:
            when = str(game_dt)

    placement = me.get("placement") if me else None
    is_du = (
        queue_id in DOUBLE_UP_QUEUE_IDS
        or "DOUBLE" in str(info.get("tft_game_type", "")).upper()
        or bool(me and me.get("partner_group_id") is not None)
        or (placement is not None and partner is not None)
    )

    return {
        "when": when,
        "match_id": match_id,
        "queue_id": queue_id,
        "queue": "DOUBLE_UP" if is_du else QUEUE_NAMES.get(queue_id, str(queue_id)),
        "is_double_up": is_du,
        "set": info.get("tft_set_core_name") or info.get("tft_set_number"),
        "placement": placement,
        "level": me.get("level") if me else None,
        "last_round": me.get("last_round") if me else None,
        "gold_left": me.get("gold_left") if me else None,
        "damage": me.get("total_damage_to_players") if me else None,
        "augments": me.get("augments") if me else None,
        "win": bool(placement and placement <= 4) if placement else False,
        "traits": traits,
        "board": board,
        "partner_name": _riot_name(partner),
        "partner_placement": partner.get("placement") if partner else None,
        "partner_level": partner.get("level") if partner else None,
        "partner_board": partner_board,
    }


def pull_recent_summaries(
    game_name: str,
    tag_line: str,
    key: str,
    count: int = 20,
    double_up_only: bool = True,
) -> list[dict]:
    """Pull recent matches and return summaries (mirrors pull_matches.py logic)."""
    puuid, _ = resolve_puuid(game_name, tag_line, key)
    match_ids = fetch_match_ids(puuid, key, count=count)
    summaries = []
    for i, mid in enumerate(match_ids):
        match = fetch_match(mid, key)
        summary = summarize_match(match, puuid)
        summaries.append(summary)
        if i < len(match_ids) - 1:
            time.sleep(0.05)
    if double_up_only:
        du = [s for s in summaries if s.get("is_double_up") or s.get("queue") == "DOUBLE_UP"]
        if du:
            return du
    return summaries
