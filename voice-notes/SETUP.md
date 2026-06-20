# Setup — stand up Voice Notes end to end

Five parts: **Supabase → AssemblyAI → edge function → voice-worker → mobile app**.
You'll need: a Supabase project, an AssemblyAI API key, a Gemini key (optional,
for tagging), Node 18+, the Supabase CLI, and (for device builds) an Expo/EAS
account.

---

## 1. Supabase database

```bash
cd voice-notes/supabase
supabase link --project-ref YOUR_PROJECT_REF
supabase db push        # applies migrations 0001, 0002, 0003
```
Or paste the three files in `supabase/migrations/` into the SQL editor in order.

This creates: `speakers`, `notes`, `segments`, `voiceprints`, `note_speakers`,
`assets`; the `note_transcript` + `note_feed` views; the `match_speaker` RPC;
RLS on everything; and the private `voice-notes` storage bucket.

> Enable **Auth ▸ Email** (magic link) and optionally **Google** for one-tap
> sign-in.

## 2. AssemblyAI

Create a key at assemblyai.com. Diarization (`speaker_labels`) is included.

## 3. Transcription edge function

```bash
cd voice-notes/supabase
supabase secrets set ASSEMBLYAI_API_KEY=xxxxx
supabase secrets set GEMINI_API_KEY=xxxxx      # optional, enables smart tagging
supabase functions deploy transcribe
```
`SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are injected automatically in the
edge runtime — don't set them yourself.

## 4. Voice-worker (runs on your machine, beside Personal AI OS)

```bash
cd voice-notes/voice-worker
cp .env.example .env        # fill SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
# reuse the existing Personal-AI-OS venv, or make one:
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# ffmpeg is required:  macOS: brew install ffmpeg   ·   Ubuntu: apt install ffmpeg
python worker.py            # long-running; or `python worker.py --once` for cron
```
First run downloads the ECAPA model (~80 MB) and caches it. The worker watches
for notes the edge function marked `diarized`, builds voiceprints, matches
speakers, and writes back suggestions/confirmations.

> Tip: add it to your existing Personal-AI-OS startup so it's always on. On
> Windows you can add a line to `START.bat`; on macOS a `launchd` plist or a
> line in `START.command`.

## 5. Mobile app

```bash
cd voice-notes/mobile
cp .env.example .env        # EXPO_PUBLIC_SUPABASE_URL + EXPO_PUBLIC_SUPABASE_ANON_KEY
npm install
npx expo prebuild           # generates native projects + applies the boot plugin
# dev build on a connected device (recording/widgets need a dev build, not Expo Go):
npx expo run:ios            # or: npx expo run:android
```
For installable builds:
```bash
npm i -g eas-cli && eas login
eas build -p android --profile development
eas build -p ios --profile development
```

## 6. Gestures & widgets
Follow `WIDGETS_AND_GESTURES.md`:
- iOS **Back Tap** → Shortcut → `personalaios://record?minutes=30`
- Android **Quick Tap** → *Open app* → Personal AI OS
- Optional home/lock-screen widgets (WidgetKit / Glance) that open the same link.

---

## End-to-end smoke test
1. Sign in on the phone.
2. Record ~30s with two people talking. Stop.
3. Answer the **"Who was in this?"** prompt → *Me + others*, names `Aman, Manisha`.
4. Watch the note: status moves `uploaded → transcribing → diarized → matching →
   matched`. Pull-to-refresh.
5. Transcript shows turn-by-turn dialogue. After the worker runs you'll see a
   *"I think Speaker B is Aman — correct?"* card. Confirm it.
6. Record a second conversation with the same people — they should now be matched
   automatically, with the confidence shown next to each turn.

## Troubleshooting
- **Note stuck at `transcribing`** → check `supabase functions logs transcribe`
  (AssemblyAI key / signed-url access).
- **Stuck at `diarized`** → the worker isn't running, or `ffmpeg`/model download
  failed. Run `python worker.py --once` and read the traceback.
- **Everyone matches as one speaker** → lower `SIM_HIGH` toward `0.8`+ or raise
  it if distinct people are being merged; tune `SIM_LOW`/`SIM_HIGH` in `.env`.
- **iOS recording stops when locked** → expected under memory pressure; the
  audio background mode keeps it going in most cases (see WIDGETS_AND_GESTURES).
