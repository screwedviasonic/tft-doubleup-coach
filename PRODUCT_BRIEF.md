# TFT Double Up Post-Game Coach — product brief

## User
- Riot ID: ScrewedviaSonic#NA1 (NA / americas routing)
- Duo partner often: Tudon#NA1
- Rank: ends seasons ~Emerald Double Up
- Wants an app to open after every game for coaching

## Already working POC
- `pull_matches.py` pulls last N TFT matches via Riot API
- Must send User-Agent header or Cloudflare returns 1010
- Double Up queue_id 1160; partner_group_id often missing — infer partner from adjacent placements (1-2, 3-4, 5-6, 7-8)
- Augments often missing; total_damage_to_players often 0
- Sample reviews in reviews/ show desired autopsy shape
- sample_summaries.json is real recent match summaries

## Desired app (MVP)
A local web app (or simple desktop-friendly web UI) the user opens after a Double Up game:
1. Configure once: Riot API key, Riot ID, region
2. One big button: "Review last game" (or pick from recent list)
3. Pull match via API, show board + partner board + placement
4. Generate autopsy: lobby story, 3 rights, 3 wrongs, Double Up note, one drill
5. Append to a running patterns.md / pattern ledger
6. Fast and usable the same night — not a huge platform

## Constraints
- Do NOT commit API keys
- Prefer simple stack (e.g. Next.js or plain Python FastAPI + simple HTML) that runs locally with `npm run dev` or `uvicorn`
- Coaching can start as deterministic template + heuristics from end-state; optional LLM hook later via env OPENAI_API_KEY or similar — but MVP must work without LLM using the autopsy template style in reviews/
- README with setup steps

## Done when
- README explains how to run
- User can set Riot key + ID, click review last Double Up game, see autopsy UI
- Patterns persist across sessions
- Basic tests or a dry-run mode using sample_summaries.json if no API key
