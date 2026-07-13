"""
chat_service.py
================
The "orchestrator" layer. This file ties together database.py,
context_builder.py, and llm_service.py into the single high-level
operation the API actually needs: "handle one chat turn".

Keeping this logic separate from main.py (the HTTP layer) means:
  - You could reuse this exact same logic in a CLI tool, a background
    worker, a websocket handler, etc. - not just a REST endpoint.
  - main.py stays thin and just handles HTTP concerns (status codes,
    request/response models).
"""

from datetime import datetime, timezone

from app import database
from app.context_builder import build_llm_messages
from app.llm_service import llm_service


def handle_chat_turn(user_id: str, message: str, session_id: str | None) -> dict:
    """
    Run one full turn of the conversation:

      1. Get or create the chat session for this user.
      2. Pull the user's profile + recent health check-ins (context).
      3. Pull prior messages in this session (memory).
      4. Build the full message list and call the LLM.
      5. Save BOTH the user's message and the assistant's reply to
         Supabase, so the next turn (and any future session load)
         has full history.
      6. Return the reply + session_id to the API layer.

    Returns:
        {
            "session_id": "...",
            "reply": "...",
            "created_at": datetime
        }
    """
    # --- Step 1: session management ---
    session = database.get_or_create_session(user_id, session_id)
    resolved_session_id = session["id"]

    # --- Step 2: health/profile context ---
    user_profile = database.get_user_profile(user_id)
    checkins = database.get_recent_checkins(user_id)

    # --- Step 3: prior conversation memory ---
    chat_history = database.get_session_messages(resolved_session_id)

    # --- Step 4: build prompt & call the LLM ---
    llm_messages = build_llm_messages(
        user_profile=user_profile,
        checkins=checkins,
        chat_history=chat_history,
        new_user_message=message,
    )
    reply_text = llm_service.generate_reply(llm_messages)

    # --- Step 5: persist this turn ---
    # Save the user's message first, then the assistant's reply, so the
    # ordering in the DB always matches the actual conversation order.
    database.save_message(user_id, resolved_session_id, role="user", content=message)
    saved_reply = database.save_message(
        user_id, resolved_session_id, role="assistant", content=reply_text
    )

    # --- Step 6: return a clean result for the API layer ---
    return {
        "session_id": resolved_session_id,
        "reply": reply_text,
        "created_at": saved_reply.get("created_at", datetime.now(timezone.utc)),
    }


def get_chat_history(user_id: str, session_id: str) -> list[dict]:
    """
    Fetch full message history for one session (used by the
    GET /chat/history endpoint so the React app can render a past
    conversation when the user reopens it).

    Note: we don't apply the CHAT_HISTORY_WINDOW limit here, since this
    is for *displaying* history in the UI, not for feeding the LLM -
    the user should be able to scroll back through everything.
    """
    # Ownership check: make sure this session actually belongs to user_id
    session = database.get_chat_session(session_id, user_id)
    if not session:
        return []

    response = (
        database.supabase.table("chat_messages")
        .select("id, role, content, created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def get_user_sessions(user_id: str) -> list[dict]:
    """Fetch all chat sessions for a user (for a 'past chats' sidebar)."""
    return database.list_chat_sessions(user_id)
