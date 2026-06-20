-- ===========================================================================
-- Personal AI OS — Voice Notes subsystem
-- Migration 0001: schema, pgvector, RLS, storage, transcript view
-- ---------------------------------------------------------------------------
-- Run with:  supabase db push     (or paste into the Supabase SQL editor)
-- Requires:  Supabase project with auth enabled.
-- Embedding dim 192 == SpeechBrain ECAPA-TDNN voiceprint (see voice-worker).
-- ===========================================================================

create extension if not exists vector;
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- SPEAKERS — the persisted, self-evolving voice identities.
-- A speaker may exist with no name yet (status='provisional'); the worker
-- assigns/upgrades names through continuous learning, the user confirms.
-- ---------------------------------------------------------------------------
create table if not exists public.speakers (
  id              uuid primary key default gen_random_uuid(),
  user_id         uuid not null references auth.users(id) on delete cascade,
  name            text,                                   -- null until identified
  is_self         boolean not null default false,         -- the owner's own voice
  status          text not null default 'provisional'     -- provisional | named | confirmed
                    check (status in ('provisional','named','confirmed')),
  -- running mean of all this speaker's voiceprints; used for fast matching
  centroid        vector(192),
  voiceprint_count integer not null default 0,
  -- name the worker most recently *guessed* but the user hasn't confirmed
  suggested_name   text,
  suggestion_confidence real,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);
create index if not exists speakers_user_idx on public.speakers(user_id);

-- ---------------------------------------------------------------------------
-- NOTES — one recording == one note (the user-facing object).
-- ---------------------------------------------------------------------------
create table if not exists public.notes (
  id               uuid primary key default gen_random_uuid(),
  user_id          uuid not null references auth.users(id) on delete cascade,
  title            text,                                  -- auto from first line / editable
  recorded_at      timestamptz not null default now(),
  duration_sec     integer,
  audio_path       text,                                  -- storage object path
  status           text not null default 'recording'
                     check (status in (
                       'recording','uploaded','transcribing','transcribed',
                       'diarized','matching','matched','failed')),
  transcript_text  text,                                  -- flat fallback text
  summary          text,
  language         text,
  -- post-note "whose voices were there" answer:
  participant_mode text check (participant_mode in ('self','others')),
  participant_count integer,                              -- when mode='others'
  participant_names text[],                               -- names the user typed, if any
  error            text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now()
);
create index if not exists notes_user_idx on public.notes(user_id, recorded_at desc);
create index if not exists notes_status_idx on public.notes(status);

-- ---------------------------------------------------------------------------
-- SEGMENTS — turn-by-turn dialogue. Each row is ONE speaker's turn.
-- Consecutive utterances by the same speaker are merged into one segment
-- by the transcription function, so the sequence reads naturally:
--   [Speaker A turn] -> [Speaker B turn] -> [Speaker A turn] ...
-- `seq` preserves true chronological order of the conversation.
-- ---------------------------------------------------------------------------
create table if not exists public.segments (
  id            uuid primary key default gen_random_uuid(),
  note_id       uuid not null references public.notes(id) on delete cascade,
  user_id       uuid not null references auth.users(id) on delete cascade,
  seq           integer not null,                         -- 0-based order in the call
  speaker_label text not null,                            -- AssemblyAI per-file label: 'A','B'..
  speaker_id    uuid references public.speakers(id) on delete set null,
  start_ms      integer,
  end_ms        integer,
  text          text not null,
  created_at    timestamptz not null default now(),
  unique (note_id, seq)
);
create index if not exists segments_note_idx on public.segments(note_id, seq);

-- ---------------------------------------------------------------------------
-- VOICEPRINTS — one embedding per (note, per-file speaker label).
-- The worker computes these from the diarized audio and matches them
-- against speakers.centroid. Kept for retraining / drift correction.
-- ---------------------------------------------------------------------------
create table if not exists public.voiceprints (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  note_id       uuid not null references public.notes(id) on delete cascade,
  speaker_label text not null,                            -- which per-file label this came from
  speaker_id    uuid references public.speakers(id) on delete set null,
  embedding     vector(192) not null,
  created_at    timestamptz not null default now(),
  unique (note_id, speaker_label)
);
create index if not exists voiceprints_speaker_idx on public.voiceprints(speaker_id);
-- approximate nearest-neighbour search over voiceprints (cosine)
create index if not exists voiceprints_embedding_idx
  on public.voiceprints using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- ---------------------------------------------------------------------------
-- NOTE_SPEAKERS — per-note resolution of each per-file label to an identity.
-- Drives the "we think Speaker A is <name> — correct?" confirmation UI and
-- the user's name corrections.
-- ---------------------------------------------------------------------------
create table if not exists public.note_speakers (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,
  note_id       uuid not null references public.notes(id) on delete cascade,
  speaker_label text not null,
  speaker_id    uuid references public.speakers(id) on delete set null,
  suggested_name text,                                    -- worker's best guess
  confidence     real,                                    -- cosine similarity 0..1
  match_status   text not null default 'unknown'          -- unknown|auto|confirmed|rejected
                   check (match_status in ('unknown','auto','confirmed','rejected')),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (note_id, speaker_label)
);
create index if not exists note_speakers_note_idx on public.note_speakers(note_id);

-- ---------------------------------------------------------------------------
-- updated_at triggers
-- ---------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end; $$;

drop trigger if exists t_notes_touch on public.notes;
create trigger t_notes_touch before update on public.notes
  for each row execute function public.touch_updated_at();
drop trigger if exists t_speakers_touch on public.speakers;
create trigger t_speakers_touch before update on public.speakers
  for each row execute function public.touch_updated_at();
drop trigger if exists t_note_speakers_touch on public.note_speakers;
create trigger t_note_speakers_touch before update on public.note_speakers
  for each row execute function public.touch_updated_at();

-- ---------------------------------------------------------------------------
-- TRANSCRIPT VIEW — turn-by-turn with the resolved display name.
-- Resolution priority: confirmed speaker name -> suggested name -> label.
-- The mobile app reads this for the transcript screen.
-- ---------------------------------------------------------------------------
create or replace view public.note_transcript as
select
  s.note_id,
  s.seq,
  s.speaker_label,
  s.start_ms,
  s.end_ms,
  s.text,
  s.speaker_id,
  coalesce(
    sp.name,
    ns.suggested_name,
    'Speaker ' || s.speaker_label
  ) as speaker_display,
  case when sp.is_self then true else false end as is_self,
  ns.match_status,
  ns.confidence,
  s.user_id
from public.segments s
left join public.note_speakers ns
  on ns.note_id = s.note_id and ns.speaker_label = s.speaker_label
left join public.speakers sp
  on sp.id = coalesce(s.speaker_id, ns.speaker_id)
order by s.note_id, s.seq;

-- ---------------------------------------------------------------------------
-- ROW LEVEL SECURITY — strict per-user isolation on every table.
-- ---------------------------------------------------------------------------
alter table public.speakers      enable row level security;
alter table public.notes         enable row level security;
alter table public.segments      enable row level security;
alter table public.voiceprints   enable row level security;
alter table public.note_speakers enable row level security;

do $$
declare t text;
begin
  foreach t in array array['speakers','notes','segments','voiceprints','note_speakers']
  loop
    execute format('drop policy if exists %I_owner on public.%I;', t, t);
    execute format($f$
      create policy %I_owner on public.%I
        for all
        using (user_id = auth.uid())
        with check (user_id = auth.uid());
    $f$, t, t);
  end loop;
end $$;

-- ---------------------------------------------------------------------------
-- STORAGE — private bucket for audio. Owner-scoped by path prefix <uid>/...
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('voice-notes', 'voice-notes', false)
on conflict (id) do nothing;

drop policy if exists "voice_notes_rw" on storage.objects;
create policy "voice_notes_rw" on storage.objects
  for all
  using (
    bucket_id = 'voice-notes'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'voice-notes'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
