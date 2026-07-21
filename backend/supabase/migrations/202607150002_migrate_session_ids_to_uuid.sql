do $migration$
declare
    current_id_type text;
begin
    select data_type
    into current_id_type
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'sessions'
      and column_name = 'id';

    -- Fresh databases already use UUIDs from the initial migration.
    if current_id_type in ('text', 'character varying') then
        alter table public.sessions
            add column migrated_id uuid not null default gen_random_uuid();
        alter table public.messages
            add column migrated_session_id uuid;
        alter table public.summaries
            add column migrated_session_id uuid;
        alter table public.audit_log
            add column migrated_session_id uuid;

        update public.messages as child
        set migrated_session_id = parent.migrated_id
        from public.sessions as parent
        where child.session_id = parent.id;

        update public.summaries as child
        set migrated_session_id = parent.migrated_id
        from public.sessions as parent
        where child.session_id = parent.id;

        update public.audit_log as child
        set migrated_session_id = parent.migrated_id
        from public.sessions as parent
        where child.session_id = parent.id;

        alter table public.messages
            alter column migrated_session_id set not null;
        alter table public.summaries
            alter column migrated_session_id set not null;
        alter table public.audit_log
            alter column migrated_session_id set not null;

        alter table public.messages
            drop constraint if exists messages_session_id_fkey;
        alter table public.summaries
            drop constraint if exists summaries_session_id_fkey,
            drop constraint if exists summaries_session_id_key;
        alter table public.audit_log
            drop constraint if exists audit_log_session_id_fkey;
        alter table public.sessions
            drop constraint if exists sessions_pkey;

        drop index if exists public.messages_session_order_idx;
        drop index if exists public.audit_log_session_order_idx;

        alter table public.messages drop column session_id;
        alter table public.summaries drop column session_id;
        alter table public.audit_log drop column session_id;
        alter table public.sessions drop column id;

        alter table public.sessions rename column migrated_id to id;
        alter table public.messages rename column migrated_session_id to session_id;
        alter table public.summaries rename column migrated_session_id to session_id;
        alter table public.audit_log rename column migrated_session_id to session_id;

        alter table public.sessions
            add constraint sessions_pkey primary key (id);
        alter table public.messages
            add constraint messages_session_id_fkey
            foreign key (session_id) references public.sessions(id) on delete cascade;
        alter table public.summaries
            add constraint summaries_session_id_fkey
            foreign key (session_id) references public.sessions(id) on delete cascade,
            add constraint summaries_session_id_key unique (session_id);
        alter table public.audit_log
            add constraint audit_log_session_id_fkey
            foreign key (session_id) references public.sessions(id) on delete cascade;

        create index messages_session_order_idx
            on public.messages (session_id, created_at, id);
        create index audit_log_session_order_idx
            on public.audit_log (session_id, created_at, id);
    end if;
end
$migration$;
