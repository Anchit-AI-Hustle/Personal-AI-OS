import React, { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, Alert } from "react-native";
import * as Linking from "expo-linking";
import { supabase } from "../lib/supabase";
import { T } from "../theme";

export default function AuthScreen() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  async function sendLink() {
    // resolves to the web origin in the browser, or the personalaios:// scheme
    // on device — so the magic link returns the user to the right place.
    const emailRedirectTo = Linking.createURL("/");
    const { error } = await supabase.auth.signInWithOtp({ email, options: { emailRedirectTo } });
    if (error) Alert.alert("Sign-in error", error.message);
    else setSent(true);
  }

  return (
    <View style={{ flex: 1, backgroundColor: T.bg, justifyContent: "center", padding: 28 }}>
      <Text style={{ color: T.accent, fontSize: 30, fontWeight: "700" }}>Personal AI OS</Text>
      <Text style={{ color: T.dim, fontSize: 15, marginTop: 6, marginBottom: 28 }}>
        Your voice notes, transcribed and organised — privately.
      </Text>
      <TextInput
        placeholder="you@email.com" placeholderTextColor={T.dim}
        autoCapitalize="none" keyboardType="email-address" value={email}
        onChangeText={setEmail}
        style={{ backgroundColor: T.card, color: T.text, padding: 14,
          borderRadius: T.radius, fontSize: 16 }}
      />
      <TouchableOpacity onPress={sendLink}
        style={{ backgroundColor: T.accent, padding: 15, borderRadius: T.radius, marginTop: 14 }}>
        <Text style={{ textAlign: "center", color: "#0E0F12", fontWeight: "700", fontSize: 16 }}>
          {sent ? "Link sent — check your email" : "Send magic link"}
        </Text>
      </TouchableOpacity>
      <Text style={{ color: T.dim, fontSize: 12, marginTop: 18, textAlign: "center" }}>
        Tip: enable Google OAuth in Supabase Auth for one-tap sign-in.
      </Text>
    </View>
  );
}
