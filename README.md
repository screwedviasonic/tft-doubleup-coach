# TFT Double Up Post-Game Coach

Local web app: after a ranked Double Up game, open the UI, hit **Review last Double Up game**, get an autopsy (rights / wrongs / duo note / one drill) from Riot match data.

## Quick start

See [`app/README.md`](app/README.md).

```bash
cd app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env   # add your Riot API key from developer.riotgames.com
uvicorn main:app --host 127.0.0.1 --port 8765 --reload
```

Open http://127.0.0.1:8765

## Important

- **GitHub Pages cannot host this app** — it needs a Python server and a private Riot API key. Run it locally.
- Never commit `.env` or your Riot API key.
- Default Riot ID in settings is configurable in the UI.

## Layout

- `app/` — FastAPI web UI + Riot client + heuristic autopsy
- `pull_matches.py` — CLI match-history puller
- `samples/` — sample match summaries for dry-run
- `examples/` — example autopsy writeups
