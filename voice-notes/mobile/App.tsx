import React, { useEffect, useRef, useState } from "react";
import { NavigationContainer, useNavigationContainerRef } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import * as Linking from "expo-linking";
import { StatusBar } from "expo-status-bar";

import { supabase } from "./src/lib/supabase";
import { T } from "./src/theme";
import AuthScreen from "./src/screens/AuthScreen";
import HomeScreen from "./src/screens/HomeScreen";
import RecordScreen from "./src/screens/RecordScreen";
import SpeakerPromptScreen from "./src/screens/SpeakerPromptScreen";
import NoteDetailScreen from "./src/screens/NoteDetailScreen";
import AddNoteScreen from "./src/screens/AddNoteScreen";
import SettingsScreen from "./src/screens/SettingsScreen";

export type RootParams = {
  Home: undefined;
  Record: { minutes?: number; auto?: boolean } | undefined;
  SpeakerPrompt: { noteId: string };
  NoteDetail: { noteId: string };
  AddNote: undefined;
  Settings: undefined;
};

const Stack = createNativeStackNavigator<RootParams>();

export default function App() {
  const [session, setSession] = useState<any>(null);
  const [ready, setReady] = useState(false);
  const navRef = useNavigationContainerRef<any>();
  const pending = useRef<{ minutes?: number } | null>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  // gesture / instant-on entry. Works for BOTH:
  //   native deep link  personalaios://record?minutes=30   (Back Tap / Quick Tap)
  //   web URL           https://<site>/record?minutes=30   (PWA shortcut / bookmark)
  useEffect(() => {
    const handle = (url: string | null) => {
      if (!url) return;
      const parsed = Linking.parse(url);
      // on web the route is in `path`; on native it's in `hostname`
      const route = (parsed.hostname || parsed.path || "").replace(/^\//, "");
      if (route === "record") {
        const minutes = parsed.queryParams?.minutes ? Number(parsed.queryParams.minutes) : undefined;
        if (navRef.isReady()) navRef.navigate("Record", { minutes, auto: true });
        else pending.current = { minutes };
      }
    };
    Linking.getInitialURL().then(handle);
    const sub = Linking.addEventListener("url", (e) => handle(e.url));
    return () => sub.remove();
  }, [navRef]);

  if (!ready) return null;

  return (
    <NavigationContainer
      ref={navRef}
      theme={{ dark: true, colors: {
        background: T.bg, card: T.card, text: T.text, border: T.card2,
        primary: T.accent, notification: T.accent } as any }}
      onReady={() => {
        if (pending.current && session) {
          navRef.navigate("Record", { ...pending.current, auto: true });
          pending.current = null;
        }
      }}
    >
      <StatusBar style="light" />
      <Stack.Navigator
        screenOptions={{
          headerStyle: { backgroundColor: T.bg },
          headerTintColor: T.text, contentStyle: { backgroundColor: T.bg },
        }}
      >
        {!session ? (
          <Stack.Screen name="Auth" component={AuthScreen} options={{ headerShown: false }} />
        ) : (
          <>
            <Stack.Screen name="Home" component={HomeScreen} options={{ title: "Notes" }} />
            <Stack.Screen name="Record" component={RecordScreen} options={{ title: "Recording" }} />
            <Stack.Screen name="SpeakerPrompt" component={SpeakerPromptScreen}
              options={{ title: "Who was in this?", presentation: "modal" }} />
            <Stack.Screen name="NoteDetail" component={NoteDetailScreen} options={{ title: "Note" }} />
            <Stack.Screen name="AddNote" component={AddNoteScreen}
              options={{ title: "Add note", presentation: "modal" }} />
            <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: "Settings" }} />
          </>
        )}
      </Stack.Navigator>
    </NavigationContainer>
  );
}
