import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, ScrollView } from "react-native";
import { setParticipants } from "../lib/api";
import { T } from "../theme";

/**
 * Post-note prompt: "Whose voices were in the last recording?"
 *   - Only you            -> mode='self'
 *   - Others              -> ask count, then optional names
 * Names typed here feed the worker's smart identification. The user is NOT
 * asked to confirm each voice now — confirmation surfaces later as cards on
 * the note once the system has a confident guess.
 */
export default function SpeakerPromptScreen({ navigation, route }: any) {
  const { noteId } = route.params;
  const [count, setCount] = useState("2");
  const [names, setNames] = useState("");
  const [stage, setStage] = useState<"who" | "others">("who");

  async function onlyMe() {
    await setParticipants(noteId, { mode: "self" });
    navigation.replace("NoteDetail", { noteId });
  }
  async function saveOthers() {
    const list = names.split(",").map((s) => s.trim()).filter(Boolean);
    await setParticipants(noteId, { mode: "others", count: Number(count) || list.length || 2, names: list });
    navigation.replace("NoteDetail", { noteId });
  }

  return (
    <ScrollView style={{ flex: 1, backgroundColor: T.bg }} contentContainerStyle={{ padding: 24 }}>
      <Text style={{ color: T.text, fontSize: 22, fontWeight: "700", marginBottom: 6 }}>
        Who was in this discussion?
      </Text>
      <Text style={{ color: T.dim, marginBottom: 24 }}>
        This helps me learn voices. I’ll match them automatically next time and only
        ask you to confirm once I’m confident.
      </Text>

      {stage === "who" ? (
        <>
          <Big label="🙋 Only me" onPress={onlyMe} />
          <Big label="👥 Me + others" onPress={() => setStage("others")} subtle />
        </>
      ) : (
        <>
          <Text style={{ color: T.dim, marginBottom: 6 }}>How many other people?</Text>
          <TextInput value={count} onChangeText={setCount} keyboardType="number-pad"
            style={inputStyle} placeholder="2" placeholderTextColor={T.dim} />
          <Text style={{ color: T.dim, marginTop: 16, marginBottom: 6 }}>
            Their names (optional, comma-separated)
          </Text>
          <TextInput value={names} onChangeText={setNames}
            style={inputStyle} placeholder="Aman, Manisha" placeholderTextColor={T.dim} />
          <Big label="Save" onPress={saveOthers} />
          <TouchableOpacity onPress={() => navigation.replace("NoteDetail", { noteId })}>
            <Text style={{ color: T.dim, textAlign: "center", marginTop: 14 }}>Skip for now</Text>
          </TouchableOpacity>
        </>
      )}
    </ScrollView>
  );
}

const inputStyle = { backgroundColor: T.card, color: T.text, padding: 14,
  borderRadius: T.radius, fontSize: 16 } as const;

function Big({ label, onPress, subtle }: { label: string; onPress: () => void; subtle?: boolean }) {
  return (
    <TouchableOpacity onPress={onPress}
      style={{ backgroundColor: subtle ? T.card2 : T.accent, padding: 18,
        borderRadius: T.radius, marginTop: 14 }}>
      <Text style={{ textAlign: "center", color: subtle ? T.text : "#0E0F12",
        fontWeight: "700", fontSize: 17 }}>{label}</Text>
    </TouchableOpacity>
  );
}
