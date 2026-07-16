create table if not exists public.profiles (
    id uuid primary key references auth.users(id) on delete cascade,
    name text null,
    doctor_id uuid null references auth.users(id) on delete set null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create or replace function public.handle_new_user_profile()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.profiles (id, name)
    values (new.id, new.raw_user_meta_data ->> 'name')
    on conflict (id) do nothing;
    return new;
end;
$$;

drop trigger if exists on_auth_user_created_profile on auth.users;
create trigger on_auth_user_created_profile
    after insert on auth.users
    for each row execute function public.handle_new_user_profile();

-- Backfill profiles for users created before this migration. Authorization
-- remains in auth.users.raw_app_meta_data and the JWT app_metadata claim.
insert into public.profiles (id, name)
select id, raw_user_meta_data ->> 'name'
from auth.users
on conflict (id) do nothing;

create index if not exists sessions_patient_id_idx
    on public.sessions (patient_id);
create index if not exists profiles_doctor_id_idx
    on public.profiles (doctor_id);

-- Reject all new anonymous sessions. Legacy NULL-owner sessions remain in place
-- but are inaccessible through both RLS and application ownership filters.
alter table public.sessions
    drop constraint if exists sessions_patient_id_required;
alter table public.sessions
    add constraint sessions_patient_id_required
    check (patient_id is not null) not valid;

-- Fresh databases, or databases whose legacy sessions were already cleaned up,
-- receive a true NOT NULL column constraint immediately.
do $ownership_constraint$
begin
    if not exists (
        select 1 from public.sessions where patient_id is null
    ) then
        alter table public.sessions
            validate constraint sessions_patient_id_required;
        alter table public.sessions
            alter column patient_id set not null;
        alter table public.sessions
            drop constraint sessions_patient_id_required;
    end if;
end
$ownership_constraint$;

alter table public.profiles enable row level security;
alter table public.sessions enable row level security;
alter table public.messages enable row level security;
alter table public.summaries enable row level security;
alter table public.audit_log enable row level security;

-- The service-role backend performs mutations and bypasses RLS. Authenticated
-- clients receive read-only access, constrained by patient role and ownership.
revoke all on table public.profiles from anon;
revoke all on table public.sessions from anon;
revoke all on table public.messages from anon;
revoke all on table public.summaries from anon;
revoke all on table public.audit_log from anon;

revoke insert, update, delete, truncate, references, trigger
    on table public.profiles, public.sessions, public.messages,
    public.summaries, public.audit_log
    from authenticated;
grant select
    on table public.profiles, public.sessions, public.messages,
    public.summaries, public.audit_log
    to authenticated;

drop policy if exists profiles_patient_select_own on public.profiles;
create policy profiles_patient_select_own
    on public.profiles
    for select
    to authenticated
    using (
        id = (select auth.uid())
        and (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
    );

drop policy if exists sessions_patient_select_own on public.sessions;
create policy sessions_patient_select_own
    on public.sessions
    for select
    to authenticated
    using (
        patient_id = (select auth.uid())
        and (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
    );

drop policy if exists messages_patient_select_own on public.messages;
create policy messages_patient_select_own
    on public.messages
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
        and exists (
            select 1
            from public.sessions
            where sessions.id = messages.session_id
              and sessions.patient_id = (select auth.uid())
        )
    );

drop policy if exists summaries_patient_select_own on public.summaries;
create policy summaries_patient_select_own
    on public.summaries
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
        and exists (
            select 1
            from public.sessions
            where sessions.id = summaries.session_id
              and sessions.patient_id = (select auth.uid())
        )
    );

drop policy if exists audit_log_patient_select_own on public.audit_log;
create policy audit_log_patient_select_own
    on public.audit_log
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
        and exists (
            select 1
            from public.sessions
            where sessions.id = audit_log.session_id
              and sessions.patient_id = (select auth.uid())
        )
    );
