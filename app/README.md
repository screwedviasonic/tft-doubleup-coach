# TFT Double Up Coach (local web app)

Post-game autopsy coach for TFT Double Up. Open after a game → review last lobby → get rights/wrongs/drill. Heuristic end-state coach (no LLM required).

## Setup

```bash
cd /workspace/tft-doubleup-coach/app
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Riot API key: put `RIOT_API_KEY=…` in ``../.env` (repo root) or `app/.env`` (parent) or `app/.env`. **Never commit the key.**

Without a key the app runs in **dry-run** mode using `../data/summaries.json` (or `../export/sample_summaries.json`).

## Run

```bash
cd /workspace/tft-doubleup-coach/app
source .venv/bin/activate   # if you created a venv
uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

Open http://127.0.0.1:8765

## Use after a game

1. Settings (optional): Riot ID (`ScrewedviaSonic#NA1`), region `NA`, partner hint, API key.
2. Home → huge **Review last Double Up game** button.
3. Or click a match in **Recent Double Up matches**.
4. Autopsy saves to `data/reviews/` and appends to `data/patterns.md`.

## API (for curl / smoke tests)

- `GET /api/health`
- `GET /api/matches`
- `POST /api/review` — body optional `{"match_id":"NA1_…"}`
- `GET /api/review/last`
- `GET /api/settings` / `POST /api/settings`
- `GET /api/patterns`

## Notes / API limits

- Riot requests must send `User-Agent: TFTDoubleUpCoachPOC/0.1 (personal)` and `Accept: application/json` (Cloudflare 1010 otherwise).
- Double Up `queue_id` 1160; `partner_group_id` often missing — partner inferred from adjacent placements (1–2, 3–4, 5–6, 7–8).
- Augments often missing; damage often 0 — labeled on every autopsy.
- Existing CLI puller `../pull_matches.py` is unchanged; app reuses the same request headers and summary ideas via `riot_client.py`.

## Defaults

- Riot ID: ScrewedviaSonic#NA1 (americas routing)
- Partner hint: Tudon#NA1
