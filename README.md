# AI Health Chatbot API (FastAPI + Supabase + Hugging Face)

A working prototype backend for a health-aware chatbot:
- Uses your existing Supabase `users` + `checkins` tables as **context**
- Remembers full conversation history per session (**memory**)
- Calls an **open-source LLM** hosted on Hugging Face (no local GPU needed)
- Built to be called from a **React** frontend

No Kafka / Airflow / batch pipelines — just a simple, robust prototype.

---

## 1. Project structure

```
chatbot_api/
├── app/
│   ├── __init__.py
│   ├── config.py           # loads & validates all environment variables
│   ├── models.py            # Pydantic request/response schemas
│   ├── database.py          # ALL Supabase queries live here
│   ├── context_builder.py   # turns health data + history into an LLM prompt
│   ├── llm_service.py       # wraps the Hugging Face Inference API call
│   ├── chat_service.py      # orchestrates one full chat turn
│   └── main.py               # FastAPI app + routes (the HTTP layer)
├── requirements.txt
├── .env.example              # copy to .env and fill in your keys
├── supabase_schema.sql        # SQL to create the 2 new tables needed
└── README.md
```

Each file has ONE job (see the docstring at the top of each file for
details) — this keeps things easy to extend later (e.g. swap the LLM
provider by only touching `llm_service.py`).

---

## 2. Supabase setup

Your existing tables (from your schema) are:
- `users(id, created_at, name, phone, age, city)`
- `checkins(id, created_at, user_id, date, feeling_score, free_text, recommendation)`

The chatbot needs **two additional tables** to store conversations:
- `chat_sessions` — one row per conversation thread
- `chat_messages` — one row per individual message (user or assistant)

**Run `supabase_schema.sql` in your Supabase SQL Editor** (Dashboard →
SQL Editor → New query → paste the file → Run). It creates both
tables, indexes, a trigger to auto-update `updated_at`, and basic RLS
policies.

---

## 3. Environment setup

```bash
cd chatbot_api
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# now edit .env and fill in:
#   SUPABASE_URL, SUPABASE_SERVICE_KEY  -> from Supabase Dashboard > Settings > API
#   HF_TOKEN                             -> from https://huggingface.co/settings/tokens
```

**Important:** use the Supabase **service_role** key (not the `anon`
key) in `SUPABASE_SERVICE_KEY`. This backend runs server-side and needs
to read/write data across all users, and must never be exposed to the
browser/React app.

### Choosing your Hugging Face model
`HF_MODEL` in `.env` can be any open-source instruction-tuned chat
model available via HF's Inference API/Providers, e.g.:
- `mistralai/Mistral-7B-Instruct-v0.3` (default, good balance)
- `meta-llama/Llama-3.1-8B-Instruct`
- `HuggingFaceH4/zephyr-7b-beta`

If a model returns an error, it may require a specific inference
provider to be enabled on your HF account — check the model page's
"Deploy" tab, or just try a different model name.

---

## 4. Run the API

```bash
uvicorn app.main:app --reload --port 8000
```

Open **http://localhost:8000/docs** for interactive Swagger docs where
you can test every endpoint directly in the browser.

---

## 5. API Endpoints

### `POST /chat`
Send a message, get a reply. Include `session_id` to continue a past
conversation, or omit it to start a new one.

```json
// Request
{
  "user_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
  "message": "Why have I been feeling so tired this week?",
  "session_id": null
}

// Response
{
  "session_id": "a1b2c3d4-...",
  "reply": "Looking at your last few check-ins, I noticed...",
  "created_at": "2026-07-13T10:15:00Z"
}
```

### `GET /chat/sessions/{user_id}`
List all past conversation threads for a user (for a "chat history"
sidebar in React).

### `GET /chat/history/{user_id}/{session_id}`
Get every message in one specific session, oldest first.

---

## 6. Calling it from React

```javascript
async function sendMessage(userId, message, sessionId = null) {
  const res = await fetch("http://localhost:8000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message, session_id: sessionId }),
  });
  if (!res.ok) throw new Error(`Chat request failed: ${res.status}`);
  return res.json(); // { session_id, reply, created_at }
}
```

Store the returned `session_id` in React state (or localStorage) and
pass it back on every subsequent message in the same conversation to
keep memory intact. Omit it (or pass `null`) whenever the user clicks
"New Chat".

---

## 7. How context + memory actually work

1. **Health context**: on every request, `database.py` fetches the
   user's profile and their last `CHECKIN_HISTORY_WINDOW` check-ins
   (default 14). `context_builder.py` formats these into a readable
   summary and injects it into the LLM's **system prompt**.
2. **Conversation memory**: `database.py` fetches the last
   `CHAT_HISTORY_WINDOW` messages (default 12) for the current
   `session_id` and replays them back to the model as prior turns,
   before appending the new message.
3. Every turn (both the user's message and the assistant's reply) is
   immediately saved to `chat_messages`, so memory persists across
   server restarts and works correctly even with multiple concurrent
   users (memory is scoped per `session_id`, not stored in server RAM).

You can tune the two window sizes in `.env` — larger windows = more
context but slower/pricier LLM calls.

---

## 8. Notes on scaling later (not needed for the prototype)

- **Swap the LLM backend**: only `llm_service.py` needs to change —
  e.g. to call a self-hosted model via `vllm` or `text-generation-inference`.
- **Streaming responses**: `chat_completion(..., stream=True)` is
  supported by `huggingface_hub` if you want token-by-token streaming
  to the frontend later (would need a small change to `main.py` to
  return a `StreamingResponse`).
- **Auth**: right now any caller can pass any `user_id`. For
  production, add a proper auth dependency (e.g. verify a Supabase JWT
  from the `Authorization` header) instead of trusting `user_id` from
  the request body.
- **Summarization for long chats**: once a session gets very long, you
  may want to periodically summarize older messages instead of
  including them all, to keep prompt size bounded.
