// ===========================================================================
// Supabase Edge Function: transcribe  (SUBMIT-ONLY)
// ---------------------------------------------------------------------------
// Why submit-only: edge functions have a short wall-clock budget on the free
// tier, and AssemblyAI jobs can take minutes. Synchronously polling here was
// unreliable. So this function ONLY:
//   1. verifies the caller's JWT and that the note is theirs
//   2. signs the audio object
//   3. submits the AssemblyAI diarization job
//   4. stores transcript_job_id and sets status='transcribing', returns fast
// The always-on voice-worker polls AssemblyAI, writes turn-by-turn segments +
// tags, then does voiceprint matching. See voice-worker/transcribe.py.
//
// Secrets:  ASSEMBLYAI_API_KEY  (SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY auto)
// ===========================================================================

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const AAI_KEY = Deno.env.get("ASSEMBLYAI_API_KEY")!;
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const AAI = "https://api.assemblyai.com/v2";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { ...cors, "Content-Type": "application/json" },
  });
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  const admin = createClient(SUPABASE_URL, SERVICE_ROLE);
  try {
    const token = (req.headers.get("Authorization") ?? "").replace("Bearer ", "");
    if (!token) return json({ error: "missing token" }, 401);
    const { data: userData, error: userErr } = await admin.auth.getUser(token);
    if (userErr || !userData?.user) return json({ error: "invalid token" }, 401);
    const userId = userData.user.id;

    const { note_id } = await req.json();
    if (!note_id) return json({ error: "note_id required" }, 400);

    const { data: note, error: noteErr } = await admin
      .from("notes").select("id, user_id, audio_path").eq("id", note_id).single();
    if (noteErr || !note) return json({ error: "note not found" }, 404);
    if (note.user_id !== userId) return json({ error: "forbidden" }, 403);
    if (!note.audio_path) return json({ error: "note has no audio" }, 400);

    // signed URL valid long enough for the worker to fetch via AssemblyAI
    const { data: signed, error: signErr } = await admin.storage
      .from("voice-notes").createSignedUrl(note.audio_path, 60 * 60 * 6); // 6h
    if (signErr || !signed?.signedUrl) {
      await fail(admin, note_id, "could not sign audio url");
      return json({ error: "sign failed" }, 500);
    }

    const submit = await fetch(`${AAI}/transcript`, {
      method: "POST",
      headers: { authorization: AAI_KEY, "content-type": "application/json" },
      body: JSON.stringify({
        audio_url: signed.signedUrl,
        speaker_labels: true,
        punctuate: true,
        format_text: true,
        language_detection: true,
      }),
    });
    const submitJson = await submit.json();
    if (!submit.ok || !submitJson?.id) {
      await fail(admin, note_id, `assemblyai submit: ${JSON.stringify(submitJson)}`);
      return json({ error: "submit failed", detail: submitJson }, 502);
    }

    await admin.from("notes").update({
      status: "transcribing",
      transcript_job_id: submitJson.id,
      error: null,
    }).eq("id", note_id);

    return json({ ok: true, job_id: submitJson.id });
  } catch (e) {
    return json({ error: String(e) }, 500);
  }
});

async function fail(admin: any, noteId: string, msg: string) {
  await admin.from("notes").update({ status: "failed", error: msg }).eq("id", noteId);
}
