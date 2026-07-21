alter table public.sessions
drop constraint if exists sessions_status_check;

alter table public.sessions
add constraint sessions_status_check
check (status in ('active', 'submitted', 'completed', 'escalated', 'abandoned'));

drop index if exists public.sessions_one_active_per_patient_idx;

create unique index if not exists sessions_one_open_per_patient_idx
on public.sessions (patient_id)
where status in ('active', 'submitted');
