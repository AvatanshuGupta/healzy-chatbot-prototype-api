-- =========================================================================
-- SUPABASE SCHEMA ADDITIONS FOR THE CHATBOT
-- =========================================================================
-- Your existing tables (from your ER diagram) are assumed to be:
--
--   users(id uuid PK, created_at timestamptz, name text, phone text,
--         age int4, city text)
--
--   checkins(id uuid PK, created_at timestamptz, user_id uuid FK -> users.id,
--            date date, feeling_score int8, free_text text, recommendation text)
--
-- Run the statements below in the Supabase SQL Editor to add the two
-- tables the chatbot needs in order to remember conversations.
-- =========================================================================

-- 1) CHAT SESSIONS
-- A "session" groups a sequence of messages together (like one chat thread).
-- A user can have many sessions (e.g. one per day, or one per topic).
create table if not exists chat_sessions (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references users(id) on delete cascade,
    title       text default 'New Chat',
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

-- Index to quickly fetch "all sessions for a given user"
create index if not exists idx_chat_sessions_user_id
    on chat_sessions(user_id);


-- 2) CHAT MESSAGES
-- Every single message (from the user OR the assistant) is a row here.
-- This is what gives the bot "memory" of a conversation.
create table if not exists chat_messages (
    id          uuid primary key default gen_random_uuid(),
    session_id  uuid not null references chat_sessions(id) on delete cascade,
    user_id     uuid not null references users(id) on delete cascade,
    role        text not null check (role in ('user', 'assistant', 'system')),
    content     text not null,
    created_at  timestamptz not null default now()
);

-- Index to quickly fetch "all messages for a given session, in order"
create index if not exists idx_chat_messages_session_id
    on chat_messages(session_id, created_at);

-- Index to quickly fetch "all messages for a given user" (across sessions)
create index if not exists idx_chat_messages_user_id
    on chat_messages(user_id, created_at);


-- 3) OPTIONAL: keep chat_sessions.updated_at fresh whenever a new message
--    is inserted, so you can sort "recent chats" in your React sidebar.
create or replace function touch_chat_session()
returns trigger as $$
begin
    update chat_sessions
    set updated_at = now()
    where id = new.session_id;
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_touch_chat_session on chat_messages;
create trigger trg_touch_chat_session
after insert on chat_messages
for each row execute function touch_chat_session();


-- =========================================================================
-- Row Level Security (RLS) - recommended for production.
-- Since this FastAPI backend uses the SERVICE ROLE key, it bypasses RLS,
-- so these policies mainly protect against direct frontend access to
-- Supabase (e.g. if you ever call Supabase directly from React too).
-- Safe to skip for a local prototype, but included for completeness.
-- =========================================================================
alter table chat_sessions enable row level security;
alter table chat_messages enable row level security;

create policy "Users can view their own sessions"
    on chat_sessions for select
    using (auth.uid() = user_id);

create policy "Users can view their own messages"
    on chat_messages for select
    using (auth.uid() = user_id);
