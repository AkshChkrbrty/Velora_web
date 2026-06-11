import os
import json
import re

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Load variables from a local .env file (if present) into the environment.
# On hosts like Render you set real env vars in the dashboard instead — this
# line is harmless there because no .env file exists.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# OpenRouter configuration
# ─────────────────────────────────────────────────────────────────────────────
# Your key is read from OPENROUTER_API_KEY — either from the .env file next to
# this script, or from a real environment variable. Never hard-code real keys.
# Get a key at: https://openrouter.ai/keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# You do NOT have to pick a model. If OPENROUTER_MODEL is unset or blank,
# this defaults to "openrouter/auto" — OpenRouter analyses each prompt and
# picks the best model automatically (no extra fee; you pay the chosen
# model's normal rate). Set "openrouter/free" to only use free models, or
# any specific slug from https://openrouter.ai/models to pin one.
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
# Request models  (unchanged — the frontend depends on these field names)
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
    """Send a list of {role, content} messages to OpenRouter and return the text."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            500,
            "OPENROUTER_API_KEY is not set. Add your OpenRouter key as an "
            "environment variable and restart the server.",
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # Optional attribution headers (safe to leave as-is):
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "Velora EduAI",
    }
    payload = {"model": MODEL, "messages": messages}

    try:
        resp = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach OpenRouter: {e}")

    if resp.status_code != 200:
        # Surface OpenRouter's own error message so problems are obvious.
        raise HTTPException(resp.status_code, f"OpenRouter error: {resp.text[:300]}")

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise HTTPException(502, f"Unexpected OpenRouter response: {str(data)[:300]}")


def gen(prompt):
    """Convenience wrapper for a single-prompt (one user message) generation."""
    return chat_completion([{"role": "user", "content": prompt}])


def extract_json(raw):
    """Extract the first complete JSON array/object from an LLM reply.

    Robust against ```json fences and any leading/trailing prose the model
    may add around the JSON.
    """
    text = re.sub(r"```(?:json)?", "", raw).strip().strip("`")

    # Find the earliest opening bracket of either type.
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

    # Walk forward tracking bracket depth (ignoring brackets inside strings)
    # to find the matching close bracket, so trailing text is ignored.
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

    # Fallback: try parsing from the first bracket to the end.
    return json.loads(text[start:])


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints  (paths + response shapes identical to the original)
# ─────────────────────────────────────────────────────────────────────────────
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
    # Map the conversation history into OpenRouter message roles.
    for m in req.history[-8:]:
        role = "user" if m.get("role") == "user" else "assistant"
        messages.append({"role": role, "content": m.get("content", "")})

    # The frontend already appends the question to history before calling,
    # so only add it again if it isn't already the last user message.
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
