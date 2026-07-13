"""
models.py
=========
Pydantic "schemas" that define the exact shape of data going IN and OUT
of our API endpoints. FastAPI uses these to:
  - Validate incoming request bodies automatically (bad requests get a
    clean 422 error instead of crashing our code)
  - Auto-generate interactive API docs at /docs
  - Serialize our responses consistently for the React frontend
"""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------------------
# REQUEST SCHEMAS (what the React app sends TO this API)
# -------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Body for POST /chat - sending a new message to the bot."""

    user_id: str = Field(..., description="Supabase UUID of the user (from `users` table)")
    message: str = Field(..., min_length=1, description="The user's chat message")
    session_id: Optional[str] = Field(
        default=None,
        description=(
            "UUID of an existing chat session to continue. "
            "If omitted, a brand new session is created automatically."
        ),
    )


# -------------------------------------------------------------------------
# RESPONSE SCHEMAS (what this API sends BACK to the React app)
# -------------------------------------------------------------------------

class ChatMessageOut(BaseModel):
    """A single message as returned to the frontend (for history views)."""

    id: str
    role: Literal["user", "assistant", "system"]
    content: str
    created_at: datetime


class ChatResponse(BaseModel):
    """Response for POST /chat."""

    session_id: str
    reply: str
    created_at: datetime


class ChatSessionOut(BaseModel):
    """A single chat session summary, used for a 'chat history sidebar'."""

    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatHistoryResponse(BaseModel):
    """Response for GET /chat/history/{user_id}/{session_id}."""

    session_id: str
    messages: list[ChatMessageOut]


class ChatSessionsResponse(BaseModel):
    """Response for GET /chat/sessions/{user_id}."""

    sessions: list[ChatSessionOut]
