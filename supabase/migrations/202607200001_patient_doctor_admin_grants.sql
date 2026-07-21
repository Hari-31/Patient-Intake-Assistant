-- Trusted backend/admin workflows use service_role to manage assignments.
-- RLS bypass does not replace ordinary table privileges.
grant select, insert, update
    on table public.patient_doctor
    to service_role;
