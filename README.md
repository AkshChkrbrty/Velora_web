# ✦ Velora — AI Study Companion

Full-stack AI tutoring app powered by **OpenRouter**. Runs entirely on ONE Render
service — the backend serves the web page AND the API. No Vercel needed.

## Files (keep them all in ONE folder / repo root)
```
main.py            FastAPI server — serves the website + AI API
index.html         the web page (served by main.py at "/")
requirements.txt
.env               your API key (NOT pushed to GitHub)
.env.example
.gitignore
```

## Run locally
1. `pip install -r requirements.txt`
2. Put your key in `.env`:  `OPENROUTER_API_KEY=sk-or-v1-...`  (https://openrouter.ai/keys)
3. `uvicorn main:app --reload --port 8000`
4. Open http://localhost:8000  ← the whole app loads here (login: demo@velora.ai / demo123)

## Deploy — Render only (one service, one URL)
1. Push all files to GitHub (in the repo root, all together).
2. Render → New → Web Service → connect repo.
   - Language: **Python 3**
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - Root Directory: leave **blank** (all files are in the root)
   - Environment variable: `OPENROUTER_API_KEY` = your key
     (Optional `OPENROUTER_MODEL`; defaults to `openrouter/auto`)
3. Wait for **Live**, then open your `https://YOUR-URL.onrender.com` — the website loads directly.
4. Sanity check: `https://YOUR-URL.onrender.com/api/health` should show `"model":"openrouter/auto"`.

That's it — the site and all AI features run from that single URL.

## Model
Defaults to `openrouter/auto`, which always routes to a valid available model
(avoids "no endpoints found for <model>" errors). Set `OPENROUTER_MODEL=openrouter/free`
for free-only models, or pin any slug from https://openrouter.ai/models.

## Endpoints
GET / (the website) · GET /api/health · POST /api/study-plan · /api/summarize ·
/api/generate-quiz · /api/chat · /api/flashcards · /api/difficulty-hint
