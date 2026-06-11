# ✦ Velora — AI Study Companion

Full-stack AI tutoring app powered by **OpenRouter** (use any model — Gemini, GPT, Claude, Llama…).

## Project Structure
```
velora/
├── backend/
│   ├── main.py           ← FastAPI server (OpenRouter AI)
│   └── requirements.txt
└── frontend/
    └── index.html        ← Complete frontend (open in browser)
```

## ⚡ Quick Start (run locally)

### Step 1 — Install Python dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2 — Set your OpenRouter API key
Get a key at: https://openrouter.ai/keys

macOS / Linux:
```bash
export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
```
Windows (PowerShell):
```powershell
setx OPENROUTER_API_KEY "sk-or-v1-your-key-here"
```
(Optional) pick a different model — defaults to `google/gemini-2.0-flash-001`:
```bash
export OPENROUTER_MODEL="openai/gpt-4o-mini"
```
Browse models at https://openrouter.ai/models

### Step 3 — Start the backend
```bash
uvicorn main:app --reload --port 8000
```
You'll see: `Uvicorn running on http://127.0.0.1:8000`

### Step 4 — Open the frontend
Just open `frontend/index.html` in your browser.
(Or use VS Code Live Server)

Demo login: `demo@velora.ai` / `demo123`

---

## 🌐 Deploy to Production

### Backend → Render.com (free)
1. Push `backend/` folder to GitHub
2. Go to render.com → New Web Service
3. Connect your repo, set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment variable:** `OPENROUTER_API_KEY` = your key
     (and optionally `OPENROUTER_MODEL`)
4. Copy your Render URL (e.g. `https://velora-api.onrender.com`)

### Frontend → Vercel (free)
1. In `frontend/index.html`, change line:
   ```js
   const API = "http://localhost:8000";
   ```
   to:
   ```js
   const API = "https://velora-api.onrender.com"; // your Render URL
   ```
2. Push `frontend/` to GitHub
3. Import to vercel.com → deploy

---

## 🤖 AI Features
| Feature | Endpoint | What it does |
|---------|----------|-------------|
| Study Planner | POST /api/study-plan | Day-by-day exam schedule |
| Summarizer | POST /api/summarize | Bullet-point summary of notes |
| Quiz Generator | POST /api/generate-quiz | MCQs with explanations |
| Doubt Chatbot | POST /api/chat | Multi-turn tutoring conversation |
| Flashcards | POST /api/flashcards | Flip-card Q&A pairs |
| Difficulty Hint | POST /api/difficulty-hint | Adaptive feedback on score |

## API Key
The Gemini key is gone. The backend now reads your **OpenRouter** key from the
`OPENROUTER_API_KEY` environment variable (never hard-coded in source).
Get one at: https://openrouter.ai/keys
