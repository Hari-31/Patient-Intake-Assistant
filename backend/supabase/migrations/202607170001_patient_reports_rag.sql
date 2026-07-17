create extension if not exists vector with schema extensions;

alter table public.sessions
    drop constraint if exists sessions_id_patient_id_key;
alter table public.sessions
    add constraint sessions_id_patient_id_key unique (id, patient_id);

create table if not exists public.reports (
    id uuid primary key default gen_random_uuid(),
    patient_id uuid not null references auth.users(id) on delete cascade,
    session_id uuid not null,
    filename text not null check (length(filename) > 0),
    storage_path text not null unique check (length(storage_path) > 0),
    created_at timestamptz not null default now(),
    constraint reports_session_owner_fkey
        foreign key (session_id, patient_id)
        references public.sessions (id, patient_id)
        on delete cascade,
    constraint reports_id_patient_id_key unique (id, patient_id)
);

create index if not exists reports_patient_session_idx
    on public.reports (patient_id, session_id, created_at);

create table if not exists public.report_chunks (
    id bigint generated always as identity primary key,
    report_id uuid not null,
    patient_id uuid not null references auth.users(id) on delete cascade,
    chunk_index integer not null check (chunk_index >= 0),
    chunk_text text not null check (length(chunk_text) > 0),
    embedding extensions.vector(1536) not null,
    created_at timestamptz not null default now(),
    constraint report_chunks_report_owner_fkey
        foreign key (report_id, patient_id)
        references public.reports (id, patient_id)
        on delete cascade,
    constraint report_chunks_report_index_key unique (report_id, chunk_index)
);

create index if not exists report_chunks_patient_report_idx
    on public.report_chunks (patient_id, report_id);
create index if not exists report_chunks_embedding_hnsw_idx
    on public.report_chunks
    using hnsw (embedding extensions.vector_cosine_ops);

alter table public.reports enable row level security;
alter table public.report_chunks enable row level security;

revoke all on table public.reports from anon;
revoke all on table public.report_chunks from anon;
revoke insert, update, delete, truncate, references, trigger
    on table public.reports, public.report_chunks
    from authenticated;
grant select on table public.reports, public.report_chunks to authenticated;

drop policy if exists reports_patient_select_own on public.reports;
create policy reports_patient_select_own
    on public.reports
    for select
    to authenticated
    using (
        patient_id = (select auth.uid())
        and (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
    );

drop policy if exists report_chunks_patient_select_own on public.report_chunks;
create policy report_chunks_patient_select_own
    on public.report_chunks
    for select
    to authenticated
    using (
        patient_id = (select auth.uid())
        and (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
    );

insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
values (
    'medical-reports',
    'medical-reports',
    false,
    10485760,
    array['application/pdf']::text[]
)
on conflict (id) do update
set public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists medical_reports_patient_select_own on storage.objects;
create policy medical_reports_patient_select_own
    on storage.objects
    for select
    to authenticated
    using (
        bucket_id = 'medical-reports'
        and (storage.foldername(name))[1] = (select auth.uid())::text
        and (select auth.jwt() -> 'app_metadata' ->> 'role') = 'patient'
    );

-- Uploads and deletions intentionally have no authenticated-client policy.
-- The backend uses its service-role key and still enforces patient/session
-- ownership in application SQL before and during every report mutation.
