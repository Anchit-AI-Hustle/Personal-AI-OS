import React, { useEffect, useState } from "react";
import { View, Text, TextInput, Switch, TouchableOpacity } from "react-native";
import { loadConfig, saveConfig } from "../lib/settings";
import { RecorderConfig } from "../lib/recording";
import { supabase } from "../lib/supabase";
import { T } from "../theme";

export default function SettingsScreen() {
  const [cfg, setCfg] = useState<RecorderConfig | null>(null);
  useEffect(() => { loadConfig().then(setCfg); }, []);
  if (!cfg) return null;

  const set = (patch: Partial<RecorderConfig>) => {
    const next = { ...cfg, ...patch }; setCfg(next); saveConfig(next);
  };

  return (
    <View style={{ flex: 1, backgroundColor: T.bg, padding: 20 }}>
      <Row label="Default recording length (minutes)">
        <TextInput keyboardType="number-pad" style={mini}
          value={String(Math.round(cfg.capMs / 60000))}
          onChangeText={(v) => set({ capMs: (Number(v) || 30) * 60000 })} />
      </Row>
      <Row label="Auto-extend when a meeting is detected">
        <Switch value={cfg.autoExtendMeetings} onValueChange={(v) => set({ autoExtendMeetings: v })}
          trackColor={{ true: T.accent }} />
      </Row>
      <Row label="Stop extended meeting after silence (minutes)">
        <TextInput keyboardType="number-pad" style={mini}
          value={String(Math.round(cfg.silenceStopMs / 60000))}
          onChangeText={(v) => set({ silenceStopMs: (Number(v) || 10) * 60000 })} />
      </Row>
      <Text style={{ color: T.dim, marginTop: 8, fontSize: 13 }}>
        Silence threshold {cfg.silenceDbThreshold} dB. Recording continues past the
        default length only if it sounds like an ongoing meeting, then stops after the
        silence window above.
      </Text>

      <TouchableOpacity onPress={() => supabase.auth.signOut()}
        style={{ marginTop: 40, backgroundColor: T.card, padding: 14, borderRadius: T.radius }}>
        <Text style={{ color: T.red, textAlign: "center", fontWeight: "700" }}>Sign out</Text>
      </TouchableOpacity>
    </View>
  );
}

const mini = { backgroundColor: T.card, color: T.text, padding: 8, borderRadius: 10,
  width: 70, textAlign: "center" } as const;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between",
      paddingVertical: 14, borderBottomWidth: 1, borderBottomColor: T.card }}>
      <Text style={{ color: T.text, flex: 1, paddingRight: 12 }}>{label}</Text>
      {children}
    </View>
  );
}
