"""
context_builder.py
===================
This file is the "brain glue" between raw Supabase data and the LLM.

It takes:
  1. The user's profile (name, age, city...)
  2. Their recent health check-ins (physical/mental scores, journal text)
  3. Their previous chat messages in this session

...and turns it all into a clean list of chat "messages" in the format
Hugging Face chat models expect:
    [
        {"role": "system", "content": "..."},
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."},
        ...
    ]
"""

from datetime import date


def _format_checkins_as_text(checkins: list[dict]) -> str:
    """
    Turn a list of raw check-in rows into a readable bullet-point summary
    that we can drop straight into the system prompt.

    Example output:
        - 2026-07-10: feeling_score=6/10. Journal: "Felt tired and anxious
          today, had headache." Recommendation given: "Try sleeping earlier."
        - 2026-07-09: feeling_score=8/10. Journal: "Good day overall."
    """
    if not checkins:
        return "No recent health check-in data is available for this user."

    lines = []
    for c in checkins:
        checkin_date = c.get("date", "unknown date")
        score = c.get("feeling_score", "N/A")
        journal = (c.get("free_text") or "").strip()
        recommendation = (c.get("recommendation") or "").strip()

        line = f"- {checkin_date}: feeling_score={score}/10."
        if journal:
            line += f' Journal: "{journal}"'
        if recommendation:
            line += f' Previous recommendation given: "{recommendation}"'
        lines.append(line)

    return "\n".join(lines)


def build_system_prompt(user_profile: dict | None, checkins: list[dict]) -> str:
    """
    Build the SYSTEM message: this is the instruction + context that
    tells the LLM who it's talking to, how to behave, and what health
    data it should ground its answers in.

    Customize the persona/instructions here freely - this is the main
    "prompt engineering" lever for the whole chatbot.
    """
    name = user_profile.get("name") if user_profile else "the user"
    age = user_profile.get("age") if user_profile else "unknown"
    city = user_profile.get("city") if user_profile else "unknown"

    checkins_summary = _format_checkins_as_text(checkins)

    system_prompt = f"""You are a supportive AI health & wellness assistant embedded in a
health-tracking app. You are talking to {name}, age {age}, based in {city}.

Today's date is {date.today().isoformat()}.

Below is a summary of this user's recent daily health check-ins
(physical/mental wellbeing scores and journal notes), most recent first.
Use this as context to personalize your responses, notice trends
(e.g. declining mood/energy, recurring symptoms), and give relevant,
empathetic, and practical suggestions.

RECENT HEALTH CHECK-INS:
{checkins_summary}

GUIDELINES:
- Be warm, empathetic, and conversational - not clinical or robotic.
- Reference specific patterns from their check-ins when relevant
  (e.g. "I noticed your energy has been low the last few days...").
- You are a supportive companion, NOT a doctor. For anything that sounds
  like a serious medical concern, gently encourage the user to consult
  a real healthcare professional.
- Keep replies concise and easy to read (a few short paragraphs max),
  unless the user asks for more detail.
- Never fabricate health data that wasn't provided above.
"""
    return system_prompt.strip()


def build_llm_messages(
    user_profile: dict | None,
    checkins: list[dict],
    chat_history: list[dict],
    new_user_message: str,
) -> list[dict]:
    """
    Assemble the FULL message list to send to the LLM for one turn:

        [system prompt with health context]
        [...prior turns from chat_history...]
        [new user message]

    `chat_history` is expected to already be sorted oldest -> newest
    (see database.get_session_messages, which handles that ordering).
    """
    messages = [
        {"role": "system", "content": build_system_prompt(user_profile, checkins)}
    ]

    # Re-attach prior conversation turns so the model has full memory
    # of what's already been said in this session.
    for msg in chat_history:
        role = msg.get("role")
        content = msg.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    # Finally, append the brand-new message the user just sent.
    messages.append({"role": "user", "content": new_user_message})

    return messages
