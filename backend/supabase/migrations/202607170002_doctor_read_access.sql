create table if not exists public.patient_doctor (
    patient_id uuid not null references auth.users(id) on delete cascade,
    doctor_id uuid not null references auth.users(id) on delete cascade,
    created_at timestamptz not null default now(),
    primary key (patient_id, doctor_id),
    constraint patient_doctor_distinct_users check (patient_id <> doctor_id)
);

create index if not exists patient_doctor_doctor_id_idx
    on public.patient_doctor (doctor_id, patient_id);

alter table public.patient_doctor enable row level security;

revoke all on table public.patient_doctor from anon;
revoke insert, update, delete, truncate, references, trigger
    on table public.patient_doctor from authenticated;
grant select on table public.patient_doctor to authenticated;

drop policy if exists patient_doctor_doctor_select_assigned
    on public.patient_doctor;
create policy patient_doctor_doctor_select_assigned
    on public.patient_doctor
    for select
    to authenticated
    using (
        doctor_id = (select auth.uid())
        and (select auth.jwt() -> 'app_metadata' ->> 'role') = 'doctor'
    );

drop policy if exists profiles_doctor_select_assigned on public.profiles;
create policy profiles_doctor_select_assigned
    on public.profiles
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'doctor'
        and exists (
            select 1
            from public.patient_doctor as assignment
            where assignment.patient_id = profiles.id
              and assignment.doctor_id = (select auth.uid())
        )
    );

drop policy if exists sessions_doctor_select_assigned on public.sessions;
create policy sessions_doctor_select_assigned
    on public.sessions
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'doctor'
        and exists (
            select 1
            from public.patient_doctor as assignment
            where assignment.patient_id = sessions.patient_id
              and assignment.doctor_id = (select auth.uid())
        )
    );

drop policy if exists messages_doctor_select_assigned on public.messages;
create policy messages_doctor_select_assigned
    on public.messages
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'doctor'
        and exists (
            select 1
            from public.sessions as session
            join public.patient_doctor as assignment
              on assignment.patient_id = session.patient_id
            where session.id = messages.session_id
              and assignment.doctor_id = (select auth.uid())
        )
    );

drop policy if exists summaries_doctor_select_assigned on public.summaries;
create policy summaries_doctor_select_assigned
    on public.summaries
    for select
    to authenticated
    using (
        (select auth.jwt() -> 'app_metadata' ->> 'role') = 'doctor'
        and exists (
            select 1
            from public.sessions as session
            join public.patient_doctor as assignment
              on assignment.patient_id = session.patient_id
            where session.id = summaries.session_id
              and assignment.doctor_id = (select auth.uid())
        )
    );
