# Deploy the web / mobile-web app (free tier)

The same Expo codebase renders on the web via **react-native-web**. `output:
"single"` produces a static SPA, so any free static host works.

## One-time
```bash
cd voice-notes/mobile
npm install                      # pulls react-native-web, react-dom, @expo/metro-runtime
npm run web                      # local dev at http://localhost:8081
```

## Build
```bash
npm run build:web                # -> mobile/dist/  (static SPA)
```

## Host (pick one — all have free tiers)

### Vercel (config already in `mobile/vercel.json`)
```bash
npm i -g vercel
cd voice-notes/mobile
vercel            # preview
vercel --prod     # production
```

### Cloudflare Pages
- New Pages project → connect the repo → set **root directory** `voice-notes/mobile`,
  **build command** `npx expo export -p web`, **output directory** `dist`.

### GitHub Pages / Netlify
- Build locally (`npm run build:web`) and publish `mobile/dist/`.

## Required env (set in the host's dashboard, not committed)
```
EXPO_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=...
```

## After deploy
1. In **Supabase ▸ Auth ▸ URL Configuration**, add your web origin (e.g.
   `https://your-app.vercel.app`) to **Site URL** and **Redirect URLs** so magic
   links land back on the site.
2. The web build is a **PWA** (manifest "Personal AI OS") — users can "Add to
   Home Screen" on mobile browsers for an app-like icon, and a home-screen
   shortcut to `/record?minutes=30` starts a recording.

## Web platform notes (honest limits)
- **Recording** uses the browser MediaRecorder via expo-av. It works, but the
  browser has **no mic metering**, so the live waveform and *meeting
  auto-extend* are disabled on web (the time cap still applies). Full
  meeting-aware capture is an iOS/Android-only capability.
- Background/lock-screen capture is not possible in a browser tab — that's what
  the native apps are for. Web is ideal for reviewing, searching, tagging,
  uploading media, and quick foreground recordings.
