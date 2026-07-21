alter table public.sessions
add column if not exists status text not null default 'active';

alter table public.sessions
drop constraint if exists sessions_status_check;

alter table public.sessions
add constraint sessions_status_check
check (status in ('active', 'completed', 'escalated', 'abandoned'));

-- The Phase 3 ownership check is NOT VALID so legacy NULL-owner sessions may
-- remain, but PostgreSQL still enforces it whenever one of those rows is
-- updated. Temporarily remove it so those inaccessible legacy rows can be
-- classified as abandoned, then restore the same protection for new writes.
alter table public.sessions
drop constraint if exists sessions_patient_id_required;

-- Preserve emergency closures even if a summary was generated afterward.
with last_assistant_message as (
    select distinct on (message.session_id)
        message.session_id,
        message.content
    from public.messages as message
    where message.role = 'assistant'
    order by message.session_id, message.created_at desc, message.id desc
)
update public.sessions as session
set status = case
    when last_message.content =
        'Your message may describe a medical emergency. Please call emergency services now or go to the nearest emergency department. If you are in the U.S. or Canada, call 911. Do not wait for this chat. If possible, have someone stay with you.'
        then 'escalated'
    when exists (
        select 1 from public.summaries as summary
        where summary.session_id = session.id
    ) then 'completed'
    else 'abandoned'
end
from (select session_row.id from public.sessions as session_row) as all_sessions
left join last_assistant_message as last_message
    on last_message.session_id = all_sessions.id
where session.id = all_sessions.id;

alter table public.sessions
add constraint sessions_patient_id_required
check (patient_id is not null) not valid;

-- Keep the stronger NOT NULL form on databases that have no legacy NULL-owner
-- rows, matching the behavior of the Phase 3 migration.
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

create unique index if not exists sessions_one_active_per_patient_idx
on public.sessions (patient_id)
where status = 'active';
