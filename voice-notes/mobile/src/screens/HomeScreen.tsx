import React, { useCallback, useState } from "react";
import { View, Text, FlatList, TouchableOpacity, RefreshControl } from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { listFeed, Note } from "../lib/api";
import { T, KIND_ICON } from "../theme";

export default function HomeScreen({ navigation }: any) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setNotes(await listFeed()); } finally { setLoading(false); }
  }, []);
  useFocusEffect(useCallback(() => { load(); }, [load]));

  return (
    <View style={{ flex: 1, backgroundColor: T.bg }}>
      <FlatList
        data={notes}
        keyExtractor={(n) => n.id}
        contentContainerStyle={{ padding: T.pad, paddingBottom: 160 }}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={T.accent} />}
        ListHeaderComponent={
          <TouchableOpacity onPress={() => navigation.navigate("Settings")}>
            <Text style={{ color: T.dim, textAlign: "right", marginBottom: 8 }}>⚙︎ Settings</Text>
          </TouchableOpacity>
        }
        ListEmptyComponent={
          <Text style={{ color: T.dim, textAlign: "center", marginTop: 60 }}>
            No notes yet. Tap ⏺ to record, or + to add media.
          </Text>}
        renderItem={({ item }) => (
          <TouchableOpacity
            onPress={() => navigation.navigate("NoteDetail", { noteId: item.id })}
            style={{ backgroundColor: T.card, borderRadius: T.radius, padding: 14, marginBottom: 10 }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Text style={{ color: T.text, fontSize: 16, fontWeight: "600", flex: 1 }} numberOfLines={1}>
                {KIND_ICON[item.kind] ?? "•"} {item.title ?? "Untitled note"}
              </Text>
              {item.is_meeting && (
                <Text style={{ color: T.blue, fontSize: 11, fontWeight: "700" }}>MEETING</Text>
              )}
            </View>
            {!!item.summary && (
              <Text style={{ color: T.dim, marginTop: 4 }} numberOfLines={2}>{item.summary}</Text>
            )}
            <View style={{ flexDirection: "row", flexWrap: "wrap", marginTop: 8 }}>
              {(item.tags ?? []).slice(0, 5).map((t) => (
                <Text key={t} style={{ color: T.accent, backgroundColor: T.card2,
                  paddingHorizontal: 8, paddingVertical: 3, borderRadius: 10,
                  marginRight: 6, marginBottom: 4, fontSize: 12 }}>#{t}</Text>
              ))}
            </View>
            <Text style={{ color: T.dim, fontSize: 11, marginTop: 6 }}>
              {new Date(item.recorded_at).toLocaleString()}
              {item.status !== "matched" && item.status !== "transcribed"
                ? `  ·  ${item.status}…` : ""}
            </Text>
          </TouchableOpacity>
        )}
      />
      {/* floating actions */}
      <View style={{ position: "absolute", right: 20, bottom: 34, alignItems: "center" }}>
        <TouchableOpacity onPress={() => navigation.navigate("AddNote")}
          style={{ backgroundColor: T.card2, width: 56, height: 56, borderRadius: 28,
            alignItems: "center", justifyContent: "center", marginBottom: 14 }}>
          <Text style={{ color: T.text, fontSize: 28, marginTop: -2 }}>＋</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => navigation.navigate("Record", { auto: false })}
          style={{ backgroundColor: T.red, width: 72, height: 72, borderRadius: 36,
            alignItems: "center", justifyContent: "center" }}>
          <Text style={{ color: "#fff", fontSize: 30 }}>⏺</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
