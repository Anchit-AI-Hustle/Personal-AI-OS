import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView, Alert } from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { createNote, AssetType, NoteKind } from "../lib/api";
import { T } from "../theme";

function classify(mime: string): { type: AssetType; kind: NoteKind } {
  if (mime.startsWith("image/")) return { type: "image", kind: "image" };
  if (mime.startsWith("video/")) return { type: "video", kind: "video" };
  if (mime.startsWith("audio/")) return { type: "audio", kind: "music" };
  if (mime.includes("pdf") || mime.includes("word") || mime.includes("text") || mime.includes("sheet"))
    return { type: "document", kind: "file" };
  return { type: "other", kind: "file" };
}

export default function AddNoteScreen({ navigation }: any) {
  const [tab, setTab] = useState<"text" | "link" | "media">("text");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function saveText() {
    setBusy(true);
    try {
      await createNote({ kind: "text", title: title || undefined, body });
      navigation.goBack();
    } catch (e: any) { Alert.alert("Save", String(e?.message ?? e)); } finally { setBusy(false); }
  }
  async function saveLink() {
    setBusy(true);
    try {
      await createNote({ kind: "link", title: title || url, url });
      navigation.goBack();
    } catch (e: any) { Alert.alert("Save", String(e?.message ?? e)); } finally { setBusy(false); }
  }
  async function pickAndSave() {
    const res = await DocumentPicker.getDocumentAsync({ type: "*/*", copyToCacheDirectory: true, multiple: true });
    if (res.canceled) return;
    setBusy(true);
    try {
      const files = res.assets.map((a) => {
        const mime = a.mimeType ?? "application/octet-stream";
        const { type } = classify(mime);
        const ext = (a.name?.split(".").pop() ?? "bin").toLowerCase();
        return { uri: a.uri, ext, mime, type, title: a.name };
      });
      const kind: NoteKind = files.length > 1 ? "mixed" : classify(files[0].mime).kind;
      await createNote({ kind, title: title || files[0].title, files });
      navigation.goBack();
    } catch (e: any) { Alert.alert("Upload", String(e?.message ?? e)); } finally { setBusy(false); }
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: 20 }}>
      <View style={{ flexDirection: "row", marginBottom: 18 }}>
        {(["text", "link", "media"] as const).map((t) => (
          <TouchableOpacity key={t} onPress={() => setTab(t)}
            style={{ flex: 1, padding: 10, borderRadius: 10, marginRight: t !== "media" ? 8 : 0,
              backgroundColor: tab === t ? T.accent : T.card }}>
            <Text style={{ textAlign: "center", color: tab === t ? "#0E0F12" : T.text, fontWeight: "700" }}>
              {t === "text" ? "📝 Note" : t === "link" ? "🔗 Link" : "📎 Media"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput value={title} onChangeText={setTitle} placeholder="Title (optional)"
        placeholderTextColor={T.dim} style={input} />

      {tab === "text" && (
        <>
          <TextInput value={body} onChangeText={setBody} placeholder="Type your note…"
            placeholderTextColor={T.dim} multiline style={[input, { height: 200, textAlignVertical: "top", marginTop: 12 }]} />
          <Save label="Save note" onPress={saveText} busy={busy} />
          <TouchableOpacity onPress={() => navigation.replace("Record", { auto: false })}>
            <Text style={{ color: T.dim, textAlign: "center", marginTop: 16 }}>🎙️ …or record a voice note instead</Text>
          </TouchableOpacity>
        </>
      )}
      {tab === "link" && (
        <>
          <TextInput value={url} onChangeText={setUrl} placeholder="https://…" autoCapitalize="none"
            keyboardType="url" placeholderTextColor={T.dim} style={[input, { marginTop: 12 }]} />
          <Save label="Save link" onPress={saveLink} busy={busy} />
        </>
      )}
      {tab === "media" && (
        <>
          <Text style={{ color: T.dim, marginTop: 12 }}>
            Attach any files — images, videos, music, audio, PDFs, documents. Audio/video
            files are auto-transcribed.
          </Text>
          <Save label="📎 Pick files & save" onPress={pickAndSave} busy={busy} />
        </>
      )}
    </ScrollView>
  );
}

const input = { backgroundColor: T.card, color: T.text, padding: 14, borderRadius: T.radius, fontSize: 16 } as const;

function Save({ label, onPress, busy }: { label: string; onPress: () => void; busy: boolean }) {
  return (
    <TouchableOpacity onPress={onPress} disabled={busy}
      style={{ backgroundColor: T.accent, padding: 16, borderRadius: T.radius, marginTop: 18, opacity: busy ? 0.5 : 1 }}>
      <Text style={{ textAlign: "center", color: "#0E0F12", fontWeight: "700", fontSize: 16 }}>
        {busy ? "Saving…" : label}
      </Text>
    </TouchableOpacity>
  );
}
