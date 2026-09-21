#!/usr/bin/env python3
"""POC: pull TFT match history (Double Up focused) for a Riot ID."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

# Americas routing for NA accounts
ACCOUNT_HOST = "https://americas.api.riotgames.com"
MATCH_HOST = "https://americas.api.riotgames.com"

# Common TFT queue IDs
DOUBLE_UP_QUEUE_IDS = {1160, 1161}  # ranked double up variants
QUEUE_NAMES = {
    1090: "NORMAL",
    1100: "RANKED",
    1130: "HYPER_ROLL",
    1160: "RANKED_DOUBLE_UP",
    1161: "RANKED_DOUBLE_UP",
}


def load_key() -> str:
    if os.environ.get("RIOT_API_KEY"):
        return os.environ["RIOT_API_KEY"]
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith("RIOT_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("RIOT_API_KEY not found")


def api_get(url: str, key: str) -> dict | list:
    req = urllib.request.Request(
        url,
        headers={
            "X-Riot-Token": key,
            "User-Agent": "TFTDoubleUpCoachPOC/0.1 (personal)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise SystemExit(f"HTTP {e.code} for {url}: {body[:500]}") from e


def main() -> None:
    game_name = "ScrewedviaSonic"
    tag_line = "NA1"
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    key = load_key()
    encoded_name = urllib.parse.quote(game_name)
    encoded_tag = urllib.parse.quote(tag_line)

    account = api_get(
        f"{ACCOUNT_HOST}/riot/account/v1/accounts/by-riot-id/{encoded_name}/{encoded_tag}",
        key,
    )
    puuid = account["puuid"]
    print(f"Account: {account.get('gameName')}#{account.get('tagLine')}")
    print(f"PUUID: {puuid[:8]}…")

    match_ids = api_get(
        f"{MATCH_HOST}/tft/match/v1/matches/by-puuid/{puuid}/ids?start=0&count={count}",
        key,
    )
    print(f"Fetched {len(match_ids)} recent match IDs\n")

    out_dir = ROOT / "data"
    out_dir.mkdir(exist_ok=True)
    summaries = []

    for i, mid in enumerate(match_ids):
        match = api_get(f"{MATCH_HOST}/tft/match/v1/matches/{mid}", key)
        info = match.get("info", {})
        queue_id = info.get("queue_id") or info.get("queueId")
        participants = info.get("participants", [])
        me = next((p for p in participants if p.get("puuid") == puuid), None)
        partner = None
        if me and me.get("partner_group_id") is not None:
            partner = next(
                (
                    p
                    for p in participants
                    if p.get("partner_group_id") == me.get("partner_group_id")
                    and p.get("puuid") != puuid
                ),
                None,
            )

        units = []
        if me:
            for u in me.get("units", []):
                name = u.get("character_id") or u.get("name") or "?"
                items = u.get("itemNames") or u.get("items") or []
                units.append({"unit": name, "tier": u.get("tier"), "items": items})

        summary = {
            "match_id": mid,
            "queue_id": queue_id,
            "queue": QUEUE_NAMES.get(queue_id, str(queue_id)),
            "is_double_up": queue_id in DOUBLE_UP_QUEUE_IDS
            or "DOUBLE" in str(info.get("tft_game_type", "")).upper()
            or bool(me and me.get("partner_group_id") is not None),
            "set": info.get("tft_set_core_name") or info.get("tft_set_number"),
            "game_datetime": info.get("game_datetime"),
            "placement": me.get("placement") if me else None,
            "level": me.get("level") if me else None,
            "last_round": me.get("last_round") if me else None,
            "gold_left": me.get("gold_left") if me else None,
            "damage": me.get("total_damage_to_players") if me else None,
            "augments": me.get("augments") if me else None,
            "traits": [
                {"name": t.get("name"), "style": t.get("style"), "num_units": t.get("num_units")}
                for t in (me.get("traits") if me else [])
                if t.get("style", 0) >= 1
            ],
            "units": units,
            "partner_placement": partner.get("placement") if partner else None,
            "partner_level": partner.get("level") if partner else None,
            "partner_units": [
                u.get("character_id") or u.get("name")
                for u in (partner.get("units") if partner else [])
            ],
        }
        summaries.append(summary)

        # light rate-limit cushion
        if i < len(match_ids) - 1:
            time.sleep(0.05)

        q = summary["queue"]
        place = summary["placement"]
        print(
            f"{i+1:2d}. {mid}  queue={q:<18} place={place}  "
            f"lvl={summary['level']}  dmg={summary['damage']}  "
            f"partner_place={summary['partner_placement']}"
        )

    (out_dir / "summaries.json").write_text(json.dumps(summaries, indent=2))
    (out_dir / "raw_last.json").write_text(json.dumps(match, indent=2))

    du = [s for s in summaries if s["is_double_up"]]
    print(f"\nDouble Up matches in this batch: {len(du)} / {len(summaries)}")
    if du:
        places = [s["placement"] for s in du if s["placement"] is not None]
        if places:
            avg = sum(places) / len(places)
            print(f"Double Up avg placement: {avg:.2f} (n={len(places)})")
    print(f"\nWrote {out_dir / 'summaries.json'}")


if __name__ == "__main__":
    main()
