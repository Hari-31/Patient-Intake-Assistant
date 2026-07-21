-- Close any historical intake that already emitted the terminal review message
-- before the chat service started writing a terminal session status.
update public.sessions as session
set status = 'completed'
where session.status in ('active', 'submitted')
  and exists (
      select 1
      from public.messages as message
      where message.session_id = session.id
        and message.role = 'assistant'
        and message.content like
            'Thank you. Your intake request has been sent for doctor review%'
  );

-- The former "submitted" state was writable by patients. Under the closed
-- lifecycle it is a terminal review record, so normalize legacy rows.
update public.sessions
set status = 'completed'
where status = 'submitted';

drop index if exists public.sessions_one_open_per_patient_idx;

create unique index if not exists sessions_one_active_per_patient_idx
on public.sessions (patient_id)
where status = 'active';
