"""
database.py
============
Everything that talks to Supabase lives in this ONE file.

WHY: keeping all raw table/column names and Supabase-specific query
syntax in a single module means:
  - If you rename a column later, you fix it in exactly one place.
  - Other files (chat_service.py, main.py) never see raw SQL/queries -
    they just call clean Python functions like `get_user_profile(...)`.

This uses the official `supabase-py` client, which is a Python wrapper
around Supabase's REST API (PostgREST) - no need for raw SQL or a
Postgres driver.
"""

from datetime import datetime, timezone
from typing import Optional

from supabase import create_client, Client

from app.config import settings


# ---------------------------------------------------------------------
# Client setup
# ---------------------------------------------------------------------
# Created once at import time and reused for every request (the
# supabase-py client is safe to share across requests in a simple
# single-process prototype like this).
supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)


# =======================================================================
# USER PROFILE
# =======================================================================

def get_user_profile(user_id: str) -> Optional[dict]:
    """
    Fetch a single user's profile info from the `users` table.

    Returns a dict like:
        {"id": ..., "name": "Alice", "age": 29, "city": "Lucknow", ...}
    or None if the user_id doesn't exist.
    """
    response = (
        supabase.table("users")
        .select("id, name, age, city, phone, created_at")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    return rows[0] if rows else None


# =======================================================================
# HEALTH CHECK-INS (the daily physical/mental health logs)
# =======================================================================

def get_recent_checkins(user_id: str, limit: int = None) -> list[dict]:
    """
    Fetch the most recent daily check-ins for a user, newest first.

    Each row looks like:
        {
            "date": "2026-07-10",
            "feeling_score": 6,
            "free_text": "Felt tired and anxious today",
            "recommendation": "Try to sleep earlier"
        }

    These are exactly the "health score and all" data points you wanted
    the chatbot to have as context.
    """
    limit = limit or settings.CHECKIN_HISTORY_WINDOW

    response = (
        supabase.table("checkins")
        .select("date, feeling_score, free_text, recommendation, created_at")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


# =======================================================================
# CHAT SESSIONS
# =======================================================================

def create_chat_session(user_id: str, title: str = "New Chat") -> dict:
    """Create a brand-new chat session row and return it (including its new id)."""
    response = (
        supabase.table("chat_sessions")
        .insert({"user_id": user_id, "title": title})
        .execute()
    )
    return response.data[0]


def get_chat_session(session_id: str, user_id: str) -> Optional[dict]:
    """
    Fetch a single chat session, making sure it actually belongs to
    this user_id (basic ownership check so one user can't read another
    user's session just by guessing/passing a different session_id).
    """
    response = (
        supabase.table("chat_sessions")
        .select("*")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data
    return rows[0] if rows else None


def get_or_create_session(user_id: str, session_id: Optional[str]) -> dict:
    """
    Core helper used by the chat endpoint:
      - If `session_id` was provided AND belongs to this user -> reuse it.
      - Otherwise -> create a brand new session for this user.

    This is what lets the frontend either continue an existing
    conversation or start a fresh one, just by including/omitting
    `session_id` in the request.
    """
    if session_id:
        existing = get_chat_session(session_id, user_id)
        if existing:
            return existing
        # If a session_id was given but doesn't exist / isn't theirs,
        # we fail safe by creating a new session rather than erroring,
        # so the chat UI never gets stuck.
    return create_chat_session(user_id)


def list_chat_sessions(user_id: str) -> list[dict]:
    """Fetch all chat sessions for a user, most recently updated first.
    Used to render a 'chat history' sidebar in the React app."""
    response = (
        supabase.table("chat_sessions")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .execute()
    )
    return response.data or []


# =======================================================================
# CHAT MESSAGES
# =======================================================================

def get_session_messages(session_id: str, limit: int = None) -> list[dict]:
    """
    Fetch messages belonging to one session, OLDEST first (so they can
    be fed directly into the LLM in correct chronological order).

    `limit` here refers to "how many of the most recent messages" -
    we fetch the newest N and then re-reverse them to chronological
    order, so long conversations don't blow up the LLM's context window.
    """
    limit = limit or settings.CHAT_HISTORY_WINDOW

    response = (
        supabase.table("chat_messages")
        .select("id, role, content, created_at")
        .eq("session_id", session_id)
        .order("created_at", desc=True)   # newest first from DB...
        .limit(limit)
        .execute()
    )
    messages = response.data or []
    messages.reverse()  # ...then flip to oldest-first for the LLM/UI
    return messages


def save_message(user_id: str, session_id: str, role: str, content: str) -> dict:
    """
    Insert one chat message (either role="user" or role="assistant").
    This is what gives the bot persistent memory - every turn of the
    conversation is written to Supabase immediately.
    """
    response = (
        supabase.table("chat_messages")
        .insert(
            {
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "content": content,
            }
        )
        .execute()
    )
    return response.data[0]
