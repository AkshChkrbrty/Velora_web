import os
import json
import re

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Load variables from a local .env file (if present). On Render you set the
# same variables in the dashboard instead; this line is harmless there.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter configuration
# ─────────────────────────────────────────────────────────────────────────────
# API key comes from the environment variable OPENROUTER_API_KEY (never hard-coded).
# Get a key at: https://openrouter.ai/keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Model is OPTIONAL. If OPENROUTER_MODEL is unset/blank, we use "openrouter/auto",
# which lets OpenRouter automatically pick a valid, available model for every
# request. This avoids the "no endpoints found for <model>" error that happens
# when a hard-coded model name gets retired.
#   • openrouter/auto  → best model auto-picked (no markup; pays chosen model's rate)
#   • openrouter/free  → only free models (zero cost; may be slower / rate-limited)
#   • any slug from https://openrouter.ai/models → pin one exact model
MODEL = os.getenv("OPENROUTER_MODEL") or "openrouter/auto"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

app = FastAPI(title="Velora EduAI")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Request models  (field names must match what the frontend sends)
# ─────────────────────────────────────────────────────────────────────────────
class PlanRequest(BaseModel):
    subject: str
    exam_date: str
    hours_per_day: int
    level: str = "intermediate"


class TextRequest(BaseModel):
    text: str


class QuizRequest(BaseModel):
    text: str
    count: int = 5


class ChatRequest(BaseModel):
    history: list
    question: str


# ─────────────────────────────────────────────────────────────────────────────
# Core AI call (OpenRouter, OpenAI-compatible chat completions)
# ─────────────────────────────────────────────────────────────────────────────
def chat_completion(messages):
    """Send a list of {role, content} messages to OpenRouter; return the text."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            500,
            "OPENROUTER_API_KEY is not set. Add your OpenRouter key as an "
            "environment variable (or in a .env file) and restart the server.",
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Velora EduAI",
    }
    payload = {"model": MODEL, "messages": messages}

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach OpenRouter: {e}")

    if resp.status_code != 200:
        # Surface OpenRouter's own error so problems are obvious (bad model,
        # no credits, invalid key, etc.).
        raise HTTPException(resp.status_code, f"OpenRouter error: {resp.text[:300]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(502, f"Unexpected OpenRouter response: {str(data)[:300]}")


def gen(prompt):
    """Convenience wrapper: single user message -> text."""
    return chat_completion([{"role": "user", "content": prompt}])


def extract_json(raw):
    """Extract the first complete JSON array/object from an LLM reply.

    Robust against ```json fences and any leading/trailing prose around the JSON.
    """
    text = re.sub(r"```(?:json)?", "", raw).strip().strip("`")

    start = -1
    opener = None
    for ch in ("[", "{"):
        idx = text.find(ch)
        if idx != -1 and (start == -1 or idx < start):
            start = idx
            opener = ch
    if start == -1:
        raise ValueError("No JSON found: " + text[:100])

    closer = "]" if opener == "[" else "}"
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == opener:
            depth += 1
        elif ch == closer:
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])

    return json.loads(text[start:])


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the Velora web page itself, so the whole app runs on one Render URL.

    Looks for index.html in a few likely spots so it works regardless of whether
    the frontend sits next to main.py or in a separate frontend/ folder.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "index.html"),
        os.path.join(here, "frontend", "index.html"),
        os.path.join(here, "..", "frontend", "index.html"),
        os.path.join(here, "static", "index.html"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                return HTMLResponse(f.read())
    # Frontend file not found — still return something useful instead of 404.
    return HTMLResponse(
        "<h2>Velora backend is running.</h2>"
        "<p>index.html was not found next to main.py. Place index.html in the "
        "same folder as main.py (or in a frontend/ folder) so the site can load.</p>"
        "<p>API docs: <a href='/docs'>/docs</a></p>",
        status_code=200,
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.post("/api/study-plan")
def study_plan(req: PlanRequest):
    from datetime import date
    try:
        days = max(3, (date.fromisoformat(req.exam_date) - date.today()).days)
    except Exception:
        days = 7
    prompt = f"""Create a {days}-day study plan for a {req.level} student studying "{req.subject}".
{req.hours_per_day} hours/day. Exam: {req.exam_date}.
Return ONLY valid JSON array, no markdown:
[{{"day":1,"title":"Title","topics":["Topic 1","Topic 2","Topic 3"],"tip":"Helpful tip"}}]
Be specific to {req.subject}. Cover all major topics."""
    raw = gen(prompt)
    try:
        return {"ok": True, "plan": extract_json(raw)}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": raw}


@app.post("/api/summarize")
def summarize(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "Empty text")
    prompt = f"""Summarize these study notes for exam prep. Use markdown:
## Key Concepts
- bullet each concept

## Important Points  
- critical facts

## Quick Revision
- 1-line points

Bold key terms. Max 350 words.

Notes:
{req.text[:3000]}"""
    return {"ok": True, "summary": gen(prompt)}


@app.post("/api/generate-quiz")
def generate_quiz(req: QuizRequest):
    if not req.text.strip():
        raise HTTPException(400, "Empty text")
    prompt = f"""Generate exactly {req.count} MCQs from these notes. Test real understanding.
Return ONLY valid JSON array, no markdown:
[{{"q":"Question?","options":["A. opt","B. opt","C. opt","D. opt"],"answer":"A","explanation":"Why A is correct"}}]

Notes:
{req.text[:2500]}"""
    raw = gen(prompt)
    try:
        return {"ok": True, "questions": extract_json(raw)}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": raw}


@app.post("/api/chat")
def chat(req: ChatRequest):
    messages = [{
        "role": "system",
        "content": (
            "You are Velora, a friendly AI tutor for students. Explain clearly "
            "with examples. Show step-by-step for math/science. Be encouraging. "
            "Max 250 words."
        ),
    }]
    for m in req.history[-8:]:
        role = "user" if m.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": m.get("content", "")})

    last = messages[-1] if len(messages) > 1 else None
    if not (last and last["role"] == "user" and last["content"] == req.question):
        messages.append({"role": "user", "content": req.question})

    return {"ok": True, "reply": chat_completion(messages)}


@app.post("/api/flashcards")
def flashcards(req: TextRequest):
    if not req.text.strip():
        raise HTTPException(400, "Empty text")
    prompt = f"""Create 8 flashcards from these notes. Each tests one concept.
Return ONLY valid JSON array, no markdown:
[{{"front":"Short question/term (max 12 words)","back":"Clear answer (max 25 words)"}}]

Notes:
{req.text[:2000]}"""
    raw = gen(prompt)
    try:
        return {"ok": True, "flashcards": extract_json(raw)}
    except Exception as e:
        return {"ok": False, "error": str(e), "raw": raw}


@app.post("/api/difficulty-hint")
def difficulty_hint(req: TextRequest):
    try:
        score = int(req.text.strip())
    except Exception:
        raise HTTPException(400, "Send score as number")
    if score < 50:
        return {"hint": "Below 50% — revisit the basics and retry. You've got this! 💪", "level": "easy"}
    elif score < 80:
        return {"hint": "Good effort! Review your wrong answers and challenge yourself next. 👍", "level": "medium"}
    else:
        return {"hint": "Excellent! 🌟 You're mastering this. Move on to the next topic!", "level": "hard"}
