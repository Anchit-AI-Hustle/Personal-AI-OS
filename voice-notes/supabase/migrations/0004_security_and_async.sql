-- ===========================================================================
-- Migration 0004: SECURITY FIX + async transcription support
-- ---------------------------------------------------------------------------
-- CRITICAL: views are created by the migration role (postgres), which BYPASSES
-- row level security. A plain view therefore leaks EVERY user's rows to any
-- authenticated caller. Postgres 15+ / Supabase fix: security_invoker=on, so
-- the view runs with the *querying* user's privileges and RLS is enforced.
-- ===========================================================================

alter view public.note_transcript set (security_invoker = on);
alter view public.note_feed       set (security_invoker = on);

-- async transcription: the edge function now only SUBMITs the job (returns
-- fast); the always-on worker polls AssemblyAI for completion. Store the job id.
alter table public.notes
  add column if not exists transcript_job_id text;

create index if not exists notes_jobid_idx on public.notes(status)
  where status = 'transcribing';
