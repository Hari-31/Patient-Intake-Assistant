create table if not exists public.sessions (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

create table if not exists public.messages (
    id bigint generated always as identity primary key,
    session_id uuid not null references public.sessions(id) on delete cascade,
    role text not null check (role in ('patient', 'assistant', 'system')),
    content text not null check (length(content) > 0),
    created_at timestamptz not null default now()
);

create index if not exists messages_session_order_idx
    on public.messages (session_id, created_at, id);

create table if not exists public.summaries (
    id bigint generated always as identity primary key,
    session_id uuid not null unique references public.sessions(id) on delete cascade,
    summary jsonb not null check (jsonb_typeof(summary) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.audit_log (
    id bigint generated always as identity primary key,
    session_id uuid not null references public.sessions(id) on delete cascade,
    event_type text not null,
    content jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists audit_log_session_order_idx
    on public.audit_log (session_id, created_at, id);

-- Keep direct client access closed until patient/doctor RLS policies are added.
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.summaries enable row level security;
alter table public.audit_log enable row level security;
