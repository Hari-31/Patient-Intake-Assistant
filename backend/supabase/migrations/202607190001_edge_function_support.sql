-- Report embeddings are retrieved only by the service-role Edge Function after
-- it has verified the requesting patient and session ownership.
create or replace function public.match_report_chunks(
    p_patient_id uuid,
    p_session_id uuid,
    query_embedding extensions.vector(1536),
    match_count integer default 4
)
returns table (chunk_text text)
language sql
security definer
set search_path = public, extensions
as $$
    select chunk.chunk_text
    from public.report_chunks as chunk
    join public.reports as report
      on report.id = chunk.report_id
    where chunk.patient_id = p_patient_id
      and report.patient_id = p_patient_id
      and report.session_id = p_session_id
    order by chunk.embedding <=> query_embedding
    limit greatest(least(match_count, 10), 1);
$$;

revoke all on function public.match_report_chunks(uuid, uuid, extensions.vector, integer)
from public, anon, authenticated;
grant execute on function public.match_report_chunks(uuid, uuid, extensions.vector, integer)
to service_role;
