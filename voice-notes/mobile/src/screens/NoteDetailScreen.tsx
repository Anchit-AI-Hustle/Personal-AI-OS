import React, { useCallback, useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity, TextInput, Alert, Linking, Image,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { Audio, Video, ResizeMode } from "expo-av";
import {
  getNote, getTranscript, getAssets, getSpeakerCards, confirmSpeaker, renameSpeaker,
  signedUrl, Note, TranscriptRow, SpeakerCard,
} from "../lib/api";
import { T, KIND_ICON } from "../theme";

export default function NoteDetailScreen({ route }: any) {
  const { noteId } = route.params;
  const [note, setNote] = useState<Note | null>(null);
  const [rows, setRows] = useState<TranscriptRow[]>([]);
  const [assets, setAssets] = useState<any[]>([]);
  const [cards, setCards] = useState<SpeakerCard[]>([]);
  const soundRef = React.useRef<Audio.Sound | null>(null);

  const load = useCallback(async () => {
    const [n, t, a, c] = await Promise.all([
      getNote(noteId), getTranscript(noteId), getAssets(noteId), getSpeakerCards(noteId),
    ]);
    setNote(n); setRows(t); setAssets(a); setCards(c);
  }, [noteId]);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  async function playAudio(path: string) {
    try {
      const url = await signedUrl(path);
      await soundRef.current?.unloadAsync();
      const { sound } = await Audio.Sound.createAsync({ uri: url }, { shouldPlay: true });
      soundRef.current = sound;
    } catch (e: any) { Alert.alert("Playback", String(e?.message ?? e)); }
  }

  if (!note) return null;
  const processing = !["matched", "transcribed", "failed"].includes(note.status);

  return (
    <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: T.pad, paddingBottom: 60 }}>
      <Text style={{ color: T.text, fontSize: 22, fontWeight: "700" }}>
        {KIND_ICON[note.kind] ?? "•"} {note.title ?? "Untitled note"}
      </Text>
      {!!note.summary && <Text style={{ color: T.dim, marginTop: 6 }}>{note.summary}</Text>}
      <View style={{ flexDirection: "row", flexWrap: "wrap", marginTop: 8 }}>
        {note.is_meeting && <Pill text="MEETING" color={T.blue} />}
        {(note.tags ?? []).map((t) => <Pill key={t} text={`#${t}`} color={T.accent} />)}
      </View>
      {processing && <Text style={{ color: T.dim, marginTop: 10 }}>⏳ {note.status}… pull-to-refresh.</Text>}

      {/* typed body / link */}
      {!!note.body && <Text style={{ color: T.text, marginTop: 14, lineHeight: 22 }}>{note.body}</Text>}
      {!!note.url && (
        <TouchableOpacity onPress={() => Linking.openURL(note.url!)}>
          <Text style={{ color: T.blue, marginTop: 12 }}>{note.url}</Text>
        </TouchableOpacity>
      )}

      {/* media assets */}
      {assets.map((a) => (
        <View key={a.id} style={{ marginTop: 14 }}>
          {a.type === "audio" && (
            <TouchableOpacity onPress={() => playAudio(a.storage_path)}
              style={{ backgroundColor: T.card, padding: 14, borderRadius: T.radius }}>
              <Text style={{ color: T.text }}>▶︎ Play audio {a.duration_sec ? `· ${a.duration_sec}s` : ""}</Text>
            </TouchableOpacity>
          )}
          {a.type === "image" && <RemoteImage path={a.storage_path} />}
          {a.type === "video" && <RemoteVideo path={a.storage_path} />}
          {(a.type === "document" || a.type === "music" || a.type === "other") && (
            <OpenFile path={a.storage_path} title={a.title ?? a.type} />
          )}
          {a.type === "link" && (
            <TouchableOpacity onPress={() => a.url && Linking.openURL(a.url)}>
              <Text style={{ color: T.blue }}>🔗 {a.title ?? a.url}</Text>
            </TouchableOpacity>
          )}
        </View>
      ))}

      {/* speaker confirmation cards (smart-evolution surfacing) */}
      {cards.filter((c) => c.suggested_name && c.match_status !== "confirmed").map((c) => (
        <ConfirmCard key={c.speaker_label} card={c} noteId={noteId} onDone={load} />
      ))}

      {/* turn-by-turn transcript */}
      {rows.length > 0 && (
        <Text style={{ color: T.dim, marginTop: 22, marginBottom: 6, fontWeight: "700" }}>TRANSCRIPT</Text>
      )}
      {rows.map((r) => (
        <View key={r.seq} style={{ marginTop: 12,
          alignItems: r.is_self ? "flex-end" : "flex-start" }}>
          <Text style={{ color: r.is_self ? T.green : T.accent, fontSize: 12, fontWeight: "700", marginBottom: 2 }}>
            {r.speaker_display}
            {r.match_status === "confirmed" ? " ✓" : (r.confidence ? `  (${Math.round(r.confidence * 100)}%)` : "")}
          </Text>
          <Text style={{ color: T.text, backgroundColor: r.is_self ? T.card2 : T.card,
            padding: 12, borderRadius: T.radius, maxWidth: "92%", lineHeight: 21 }}>
            {r.text}
          </Text>
        </View>
      ))}
    </ScrollView>
  );
}

function Pill({ text, color }: { text: string; color: string }) {
  return <Text style={{ color, backgroundColor: T.card2, paddingHorizontal: 8, paddingVertical: 3,
    borderRadius: 10, marginRight: 6, marginBottom: 4, fontSize: 12, fontWeight: "700" }}>{text}</Text>;
}

function ConfirmCard({ card, noteId, onDone }: { card: SpeakerCard; noteId: string; onDone: () => void }) {
  const [name, setName] = useState(card.suggested_name ?? "");
  const [editing, setEditing] = useState(false);
  return (
    <View style={{ backgroundColor: T.card2, borderRadius: T.radius, padding: 14, marginTop: 16,
      borderLeftWidth: 3, borderLeftColor: T.accent }}>
      <Text style={{ color: T.text }}>
        I’ve learned this voice. I think <Text style={{ color: T.accent, fontWeight: "700" }}>Speaker {card.speaker_label}</Text> is{" "}
        <Text style={{ color: T.accent, fontWeight: "700" }}>{card.suggested_name}</Text>
        {card.confidence ? ` (${Math.round(card.confidence * 100)}% sure)` : ""}. Correct?
      </Text>
      {editing && (
        <TextInput value={name} onChangeText={setName}
          style={{ backgroundColor: T.bg, color: T.text, padding: 10, borderRadius: 10, marginTop: 10 }} />
      )}
      <View style={{ flexDirection: "row", marginTop: 12 }}>
        <TouchableOpacity
          onPress={async () => {
            if (!card.speaker_id) return;
            await confirmSpeaker(noteId, card.speaker_label, card.speaker_id, card.suggested_name!);
            onDone();
          }}
          style={{ backgroundColor: T.green, paddingHorizontal: 18, paddingVertical: 9, borderRadius: 10, marginRight: 10 }}>
          <Text style={{ color: "#0E0F12", fontWeight: "700" }}>Yes, correct</Text>
        </TouchableOpacity>
        <TouchableOpacity
          onPress={async () => {
            if (!editing) { setEditing(true); return; }
            if (!card.speaker_id) return;
            await renameSpeaker(noteId, card.speaker_label, card.speaker_id, name.trim());
            onDone();
          }}
          style={{ backgroundColor: T.card, paddingHorizontal: 18, paddingVertical: 9, borderRadius: 10 }}>
          <Text style={{ color: T.text }}>{editing ? "Save name" : "No, fix name"}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function RemoteImage({ path }: { path: string }) {
  const [uri, setUri] = useState<string | null>(null);
  React.useEffect(() => { signedUrl(path).then(setUri).catch(() => {}); }, [path]);
  return uri ? <Image source={{ uri }} style={{ width: "100%", height: 220, borderRadius: T.radius }} resizeMode="cover" /> : null;
}
function RemoteVideo({ path }: { path: string }) {
  const [uri, setUri] = useState<string | null>(null);
  React.useEffect(() => { signedUrl(path).then(setUri).catch(() => {}); }, [path]);
  return uri ? <Video source={{ uri }} useNativeControls resizeMode={ResizeMode.CONTAIN}
    style={{ width: "100%", height: 220, borderRadius: T.radius, backgroundColor: "#000" }} /> : null;
}
function OpenFile({ path, title }: { path: string; title: string }) {
  return (
    <TouchableOpacity onPress={async () => Linking.openURL(await signedUrl(path))}
      style={{ backgroundColor: T.card, padding: 14, borderRadius: T.radius }}>
      <Text style={{ color: T.text }}>📄 Open {title}</Text>
    </TouchableOpacity>
  );
}
