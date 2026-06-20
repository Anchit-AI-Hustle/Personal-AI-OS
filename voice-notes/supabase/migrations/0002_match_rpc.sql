-- ===========================================================================
-- Migration 0002: speaker-matching RPCs used by the voice-worker.
-- ===========================================================================

-- Nearest known speaker to a candidate voiceprint, by cosine similarity to
-- the speaker's running centroid. Returns 1 - cosine_distance as similarity.
create or replace function public.match_speaker(
  p_user_id uuid,
  p_embedding vector(192),
  p_limit int default 3
)
returns table (
  speaker_id uuid,
  name text,
  is_self boolean,
  status text,
  voiceprint_count int,
  similarity real
)
language sql stable as $$
  select
    sp.id,
    sp.name,
    sp.is_self,
    sp.status,
    sp.voiceprint_count,
    (1 - (sp.centroid <=> p_embedding))::real as similarity
  from public.speakers sp
  where sp.user_id = p_user_id
    and sp.centroid is not null
  order by sp.centroid <=> p_embedding asc
  limit p_limit;
$$;

-- NOTE: the running-mean centroid update is done client-side in the
-- voice-worker (matcher._fold_centroid) to stay independent of pgvector's
-- scalar-arithmetic operator availability across versions.
