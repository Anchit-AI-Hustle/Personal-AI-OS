/**
 * Data layer: notes, assets, transcript, speaker resolution.
 * All reads/writes go through Supabase with the signed-in user's JWT, so RLS
 * keeps everything private to the owner.
 */
import { Platform } from "react-native";
import * as FileSystem from "expo-file-system";
import { decode as decodeBase64 } from "base64-arraybuffer";
import { supabase, currentUserId } from "./supabase";

const BUCKET = "voice-notes";

export type NoteKind = "voice" | "text" | "link" | "file" | "image" | "video" | "music" | "mixed";
export type AssetType = "audio" | "video" | "image" | "document" | "music" | "link" | "other";

export type Note = {
  id: string; kind: NoteKind; title: string | null; summary: string | null;
  body: string | null; url: string | null; tags: string[]; status: string;
  is_meeting: boolean; pinned: boolean; recorded_at: string; duration_sec: number | null;
};

// ---- feed / detail ---------------------------------------------------------
export async function listFeed(): Promise<Note[]> {
  const { data, error } = await supabase.from("note_feed").select("*");
  if (error) throw error;
  return (data ?? []) as unknown as Note[];
}

export async function getNote(id: string): Promise<Note> {
  const { data, error } = await supabase.from("notes").select("*").eq("id", id).single();
  if (error) throw error;
  return data as unknown as Note;
}

export type TranscriptRow = {
  seq: number; speaker_label: string; speaker_display: string; is_self: boolean;
  text: string; start_ms: number | null; end_ms: number | null;
  match_status: string | null; confidence: number | null;
};

export async function getTranscript(noteId: string): Promise<TranscriptRow[]> {
  const { data, error } = await supabase
    .from("note_transcript").select("*").eq("note_id", noteId).order("seq");
  if (error) throw error;
  return (data ?? []) as unknown as TranscriptRow[];
}

export async function getAssets(noteId: string) {
  const { data, error } = await supabase
    .from("assets").select("*").eq("note_id", noteId).order("created_at");
  if (error) throw error;
  return data ?? [];
}

// ---- creating notes --------------------------------------------------------
async function uploadFile(localUri: string, ext: string, mime: string): Promise<string> {
  const uid = await currentUserId();
  const path = `${uid}/${Date.now()}-${Math.random().toString(36).slice(2)}.${ext}`;

  // Cross-platform binary read:
  //  - web: the recorder/picker gives a blob: or data: URL -> fetch().arrayBuffer()
  //  - native: `atob` does NOT exist in the RN runtime, so read base64 via
  //    expo-file-system and decode with base64-arraybuffer.
  let body: ArrayBuffer;
  if (Platform.OS === "web") {
    body = await (await fetch(localUri)).arrayBuffer();
  } else {
    const b64 = await FileSystem.readAsStringAsync(localUri, {
      encoding: FileSystem.EncodingType.Base64,
    });
    body = decodeBase64(b64);
  }

  const { error } = await supabase.storage.from(BUCKET).upload(path, body, {
    contentType: mime, upsert: false,
  });
  if (error) throw error;
  return path;
}

/** Create a voice note from a finished recording and kick off transcription. */
export async function createVoiceNote(rec: {
  uri: string; durationMs: number; isMeeting: boolean; autoExtended: boolean;
}): Promise<string> {
  const uid = await currentUserId();
  const path = await uploadFile(rec.uri, "m4a", "audio/m4a");
  const { data, error } = await supabase.from("notes").insert({
    user_id: uid, kind: "voice", status: "uploaded", audio_path: path,
    duration_sec: Math.round(rec.durationMs / 1000),
    is_meeting: rec.isMeeting, auto_extended: rec.autoExtended,
  }).select("id").single();
  if (error) throw error;
  const noteId = data.id as string;
  await supabase.from("assets").insert({
    user_id: uid, note_id: noteId, type: "audio", storage_path: path,
    mime_type: "audio/m4a", duration_sec: Math.round(rec.durationMs / 1000),
  });
  await triggerTranscribe(noteId);
  return noteId;
}

/** Generic note: typed text, pasted link, or one+ uploaded media assets. */
export async function createNote(input: {
  kind: NoteKind; title?: string; body?: string; url?: string; tags?: string[];
  files?: { uri: string; ext: string; mime: string; type: AssetType; title?: string }[];
}): Promise<string> {
  const uid = await currentUserId();
  const { data, error } = await supabase.from("notes").insert({
    user_id: uid, kind: input.kind, status: "transcribed",
    title: input.title ?? null, body: input.body ?? null,
    url: input.url ?? null, tags: input.tags ?? [],
  }).select("id").single();
  if (error) throw error;
  const noteId = data.id as string;

  if (input.url) {
    await supabase.from("assets").insert({
      user_id: uid, note_id: noteId, type: "link", url: input.url, title: input.title,
    });
  }
  for (const f of input.files ?? []) {
    const path = await uploadFile(f.uri, f.ext, f.mime);
    await supabase.from("assets").insert({
      user_id: uid, note_id: noteId, type: f.type, storage_path: path,
      mime_type: f.mime, title: f.title,
    });
    // if an uploaded media file is audio/video, transcribe it too
    if (f.type === "audio" || f.type === "video") {
      await supabase.from("notes").update({ audio_path: path, status: "uploaded" }).eq("id", noteId);
      await triggerTranscribe(noteId);
    }
  }
  return noteId;
}

export async function triggerTranscribe(noteId: string) {
  const { data: { session } } = await supabase.auth.getSession();
  const { error } = await supabase.functions.invoke("transcribe", {
    body: { note_id: noteId },
    headers: session ? { Authorization: `Bearer ${session.access_token}` } : undefined,
  });
  if (error) console.warn("transcribe invoke", error);
}

export async function signedUrl(path: string, seconds = 3600): Promise<string> {
  const { data, error } = await supabase.storage.from(BUCKET).createSignedUrl(path, seconds);
  if (error) throw error;
  return data.signedUrl;
}

// ---- "whose voices" prompt -------------------------------------------------
export async function setParticipants(noteId: string, p: {
  mode: "self" | "others"; count?: number; names?: string[];
}) {
  const { error } = await supabase.from("notes").update({
    participant_mode: p.mode,
    participant_count: p.mode === "others" ? p.count ?? null : 1,
    participant_names: p.names ?? null,
  }).eq("id", noteId);
  if (error) throw error;
}

// ---- speaker resolution (the confirmation contract) ------------------------
export type SpeakerCard = {
  speaker_label: string; speaker_id: string | null; suggested_name: string | null;
  confidence: number | null; match_status: string;
};

export async function getSpeakerCards(noteId: string): Promise<SpeakerCard[]> {
  const { data, error } = await supabase
    .from("note_speakers").select("*").eq("note_id", noteId).order("speaker_label");
  if (error) throw error;
  return (data ?? []) as unknown as SpeakerCard[];
}

/** User confirms the system's guess: lock the name onto the speaker identity. */
export async function confirmSpeaker(noteId: string, label: string, speakerId: string, name: string) {
  await supabase.from("speakers").update({ name, status: "confirmed", suggested_name: null })
    .eq("id", speakerId);
  await supabase.from("note_speakers").update({ match_status: "confirmed", suggested_name: name })
    .eq("note_id", noteId).eq("speaker_label", label);
}

/** User corrects/sets a name (also used when the guess was wrong). */
export async function renameSpeaker(noteId: string, label: string, speakerId: string, name: string) {
  await supabase.from("speakers").update({ name, status: "confirmed", suggested_name: null })
    .eq("id", speakerId);
  await supabase.from("note_speakers").update({ match_status: "confirmed", suggested_name: name })
    .eq("note_id", noteId).eq("speaker_label", label);
}

export async function updateNote(id: string, patch: Partial<Note>) {
  const { error } = await supabase.from("notes").update(patch).eq("id", id);
  if (error) throw error;
}
