"""
main.py
=======
The FastAPI application entrypoint. This file is intentionally "thin" -
it only handles HTTP concerns (routes, status codes, request/response
validation) and delegates all real logic to chat_service.py.

RUN LOCALLY:
    uvicorn app.main:app --reload --port 8000

Then visit http://localhost:8000/docs for interactive Swagger docs.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app import chat_service
from app.llm_service import LLMServiceError
from app.models import (
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatSessionsResponse,
)


app = FastAPI(
    title="AI Health Chatbot API",
    description=(
        "A FastAPI backend that powers a health-aware chatbot. "
        "It combines a user's Supabase health check-in data with "
        "full chat history and an open-source LLM from Hugging Face."
    ),
    version="1.0.0",
)

# ---------------------------------------------------------------------
# CORS: allows your React app (running on a different port/domain) to
# call this API from the browser. Without this, the browser blocks the
# requests with a CORS error even if the API itself works fine.
# ---------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =======================================================================
# HEALTH CHECK
# =======================================================================

@app.get("/", tags=["Health"])
def root():
    """Simple endpoint to confirm the API is up and reachable."""
    return {"status": "ok", "message": "AI Health Chatbot API is running."}


# =======================================================================
# MAIN CHAT ENDPOINT
# =======================================================================

@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(request: ChatRequest):
    """
    Send a new message to the chatbot.

    - Requires `user_id` so the bot can pull that user's health data
      (from `checkins`/`users` tables) and use it as context.
    - Optionally include `session_id` to continue a previous
      conversation with full memory; omit it to start a new session.

    Example request body:
        {
            "user_id": "1c2d3e4f-...-uuid",
            "message": "Why have I been feeling so tired lately?",
            "session_id": null
        }
    """
    try:
        result = chat_service.handle_chat_turn(
            user_id=request.user_id,
            message=request.message,
            session_id=request.session_id,
        )
        return ChatResponse(**result)

    except LLMServiceError as e:
        # The LLM call itself failed (bad token, model down, etc.)
        raise HTTPException(status_code=502, detail=str(e))

    except Exception as e:  # noqa: BLE001 - fail safe for a prototype
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


# =======================================================================
# CHAT HISTORY ENDPOINTS (so the React app can show past conversations)
# =======================================================================

@app.get(
    "/chat/sessions/{user_id}",
    response_model=ChatSessionsResponse,
    tags=["Chat History"],
)
def list_sessions(user_id: str):
    """
    Get all chat sessions (conversation threads) belonging to a user,
    most recently active first. Use this to render a sidebar of past
    chats, similar to ChatGPT's conversation list.
    """
    sessions = chat_service.get_user_sessions(user_id)
    return ChatSessionsResponse(sessions=sessions)


@app.get(
    "/chat/history/{user_id}/{session_id}",
    response_model=ChatHistoryResponse,
    tags=["Chat History"],
)
def get_history(user_id: str, session_id: str):
    """
    Get the full message history for one specific chat session.
    Used when the user re-opens a previous conversation.
    """
    messages = chat_service.get_chat_history(user_id, session_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Session not found for this user.")
    return ChatHistoryResponse(session_id=session_id, messages=messages)
