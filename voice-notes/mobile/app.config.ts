import { ExpoConfig } from "expo/config";

// Secrets come from env at build time (eas.json / .env). Anon key is safe to
// embed in a client; service-role key must NEVER be here.
const config: ExpoConfig = {
  name: "Personal AI OS",
  slug: "personal-ai-os-voice-notes",
  scheme: "personalaios",                 // deep link for Back Tap / Quick Tap entry
  version: "1.0.0",
  orientation: "portrait",
  userInterfaceStyle: "dark",
  splash: { backgroundColor: "#0E0F12", resizeMode: "contain" },
  assetBundlePatterns: ["**/*"],
  web: {
    bundler: "metro",     // react-native-web via Metro
    output: "single",     // SPA — deploy the dist/ folder to any static host
    favicon: "./assets/favicon.png",
  },
  ios: {
    bundleIdentifier: "com.anchit.personalaios",
    supportsTablet: true,
    infoPlist: {
      // continuous + background audio capture
      UIBackgroundModes: ["audio"],
      NSMicrophoneUsageDescription:
        "Personal AI OS records and transcribes your notes and meetings.",
    },
  },
  android: {
    package: "com.anchit.personalaios",
    permissions: [
      "RECORD_AUDIO",
      "FOREGROUND_SERVICE",
      "FOREGROUND_SERVICE_MICROPHONE",
      "RECEIVE_BOOT_COMPLETED",          // auto-start service on boot
      "POST_NOTIFICATIONS",
      "WAKE_LOCK",
    ],
  },
  plugins: [
    [
      "expo-av",
      { microphonePermission: "Personal AI OS records and transcribes your notes and meetings." },
    ],
    "expo-document-picker",
    "./plugins/withAndroidBoot",       // BOOT_COMPLETED -> persistent "tap to record" notification
    // Widgets (home + lock screen) are added via native targets — see
    // WIDGETS_AND_GESTURES.md (iOS expo-apple-targets / Android Glance).
  ],
  extra: {
    supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL,
    supabaseAnonKey: process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY,
    eas: { projectId: process.env.EAS_PROJECT_ID },
  },
};

export default config;
