import React, { useEffect, useRef, useState } from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";
import { RecordingEngine, Tick } from "../lib/recording";
import { loadConfig } from "../lib/settings";
import { createVoiceNote } from "../lib/api";
import { T } from "../theme";

function fmt(ms: number) {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function RecordScreen({ navigation, route }: any) {
  const engineRef = useRef<RecordingEngine | null>(null);
  const [tick, setTick] = useState<Tick | null>(null);
  const [busy, setBusy] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    (async () => {
      if (started.current) return;
      started.current = true;
      const cfg = await loadConfig();
      const minutes = route.params?.minutes;
      const engine = new RecordingEngine(
        minutes ? { ...cfg, capMs: minutes * 60 * 1000 } : cfg);
      engineRef.current = engine;
      try {
        await engine.start({
          onTick: setTick,
          onAutoStop: (r) => finalize(r),
        });
      } catch (e: any) {
        Alert.alert("Mic error", String(e?.message ?? e));
        navigation.goBack();
      }
    })();
    return () => { engineRef.current?.stop().catch(() => {}); };
  }, []);

  async function finalize(r: { uri: string; durationMs: number; isMeeting: boolean; autoExtended: boolean }) {
    if (busy) return;
    setBusy(true);
    try {
      const noteId = await createVoiceNote(r);
      navigation.replace("SpeakerPrompt", { noteId });
    } catch (e: any) {
      Alert.alert("Save error", String(e?.message ?? e));
      navigation.goBack();
    }
  }

  async function stopNow() {
    const r = await engineRef.current?.stop();
    if (r) finalize(r);
  }

  const level = tick?.level ?? 0;
  const meeting = tick?.meetingLikely;
  const extended = tick?.extended;

  return (
    <View style={{ flex: 1, backgroundColor: T.bg, alignItems: "center", justifyContent: "center", padding: 24 }}>
      <Text style={{ color: T.text, fontSize: 56, fontVariant: ["tabular-nums"], fontWeight: "200" }}>
        {fmt(tick?.elapsedMs ?? 0)}
      </Text>

      {/* simple live level bar */}
      <View style={{ width: "80%", height: 10, backgroundColor: T.card, borderRadius: 6, marginTop: 22, overflow: "hidden" }}>
        <View style={{ width: `${Math.round(level * 100)}%`, height: "100%",
          backgroundColor: tick?.isSilent ? T.dim : T.green }} />
      </View>

      {extended ? (
        <Text style={{ color: T.blue, marginTop: 22, textAlign: "center" }}>
          Meeting detected — still recording.{"\n"}Will stop after 10 min of continuous silence
          {tick ? `  (${fmt(tick.continuousSilenceMs)} so far)` : ""}.
        </Text>
      ) : meeting ? (
        <Text style={{ color: T.dim, marginTop: 22 }}>Sounds like a meeting · auto-extend armed</Text>
      ) : (
        <Text style={{ color: T.dim, marginTop: 22 }}>Recording…</Text>
      )}

      <TouchableOpacity onPress={stopNow} disabled={busy}
        style={{ marginTop: 44, backgroundColor: T.red, width: 92, height: 92, borderRadius: 46,
          alignItems: "center", justifyContent: "center", opacity: busy ? 0.5 : 1 }}>
        <Text style={{ color: "#fff", fontSize: 20, fontWeight: "700" }}>{busy ? "…" : "STOP"}</Text>
      </TouchableOpacity>
    </View>
  );
}
