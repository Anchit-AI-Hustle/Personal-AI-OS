-- ===========================================================================
-- Migration 0003: universal note-taker
-- ---------------------------------------------------------------------------
-- Notes become more than voice recordings: a note may be a typed note, a
-- pasted link, an uploaded file/image/video/music, a voice memo, or an
-- audio-transcribed note. Each note can carry MANY attachments (assets) and
-- gets smart auto-tags. Adds a meeting flag for the auto-extend recording mode.
-- ===========================================================================

-- what kind of thing the note primarily is (UI grouping / icons)
alter table public.notes
  add column if not exists kind text not null default 'voice'
    check (kind in ('voice','text','link','file','image','video','music','mixed')),
  add column if not exists body text,                 -- typed note body / pasted text
  add column if not exists url text,                  -- when kind='link'
  add column if not exists tags text[] default '{}',  -- smart auto-tags + user tags
  add column if not exists is_meeting boolean not null default false,
  add column if not exists auto_extended boolean not null default false,
  add column if not exists pinned boolean not null default false;

-- ---------------------------------------------------------------------------
-- ASSETS — arbitrary media attached to a note. Files live in storage; links
-- store only the URL. type is a coarse bucket for choosing a player/viewer.
-- ---------------------------------------------------------------------------
create table if not exists public.assets (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  note_id     uuid not null references public.notes(id) on delete cascade,
  type        text not null
                check (type in ('audio','video','image','document','music','link','other')),
  title       text,
  storage_path text,        -- object path in the 'voice-notes' bucket (null for links)
  url         text,         -- external link (null for stored files)
  mime_type   text,
  size_bytes  bigint,
  duration_sec integer,     -- for audio/video
  width       integer,
  height      integer,
  created_at  timestamptz not null default now()
);
create index if not exists assets_note_idx on public.assets(note_id);
create index if not exists assets_user_idx on public.assets(user_id);

alter table public.assets enable row level security;
drop policy if exists assets_owner on public.assets;
create policy assets_owner on public.assets
  for all using (user_id = auth.uid()) with check (user_id = auth.uid());

-- A flat feed the home/lock-screen widgets read: most-recent notes with a
-- light summary + a primary asset hint. Keeps the widget query trivial.
create or replace view public.note_feed as
select
  n.id,
  n.user_id,
  n.kind,
  n.title,
  n.summary,
  n.tags,
  n.is_meeting,
  n.pinned,
  n.recorded_at,
  n.duration_sec,
  n.status,
  (select count(*) from public.assets a where a.note_id = n.id) as asset_count,
  (select a.type from public.assets a where a.note_id = n.id
     order by a.created_at limit 1) as primary_asset_type
from public.notes n
order by n.pinned desc, n.recorded_at desc;
