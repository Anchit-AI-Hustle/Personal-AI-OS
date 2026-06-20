# Instant-on, gestures & widgets — what's possible on each OS

The single biggest reality of this feature: **iOS and Android give apps very
different power to "turn on instantly" and run from a gesture.** Here is exactly
what works, and how each piece is wired in this project.

| Capability | Android | iOS |
|---|---|---|
| Auto-start the moment the phone powers on | ✅ `BootReceiver` posts a persistent "Tap to record" notification (`plugins/withAndroidBoot.js`). True silent auto-record on boot is blocked by policy; one tap from the notification starts it. | ❌ Apps cannot launch on boot. Closest: a Lock-Screen widget that's one tap from recording. |
| Double-tap back of phone → start recording | ✅ **Quick Tap** (Settings ▸ System ▸ Gestures ▸ Quick Tap ▸ *Open app* → Personal AI OS). App opens on the record deep link and starts a 30-min capture. | ✅ **Back Tap** (Settings ▸ Accessibility ▸ Touch ▸ Back Tap ▸ Double Tap → run a Shortcut). The Shortcut opens `personalaios://record?minutes=30`. |
| Continuous background recording | ✅ Foreground service (mic) keeps recording with the screen off. | ⚠️ Only while the app holds the audio session (`UIBackgroundModes: ["audio"]`). Survives screen-lock; iOS may reclaim it under pressure. |
| Home-screen widget | ✅ Android App Widget (Glance) | ✅ WidgetKit |
| Lock-screen widget | ✅ (Android 12 clock/widget surfaces vary by OEM) | ✅ WidgetKit accessory widgets |

The app already handles the deep link: `App.tsx` parses `personalaios://record?minutes=N`
and jumps straight into a timed recording, so every gesture path below just needs
to open that URL.

---

## 1. The gesture entry point (no build needed)

### iOS — Back Tap → Shortcut
1. Shortcuts app → **+** → *Add Action* → **Open URL** → `personalaios://record?minutes=30`.
   Name it "Record note".
2. Settings ▸ Accessibility ▸ Touch ▸ **Back Tap** ▸ **Double Tap** → choose the
   "Record note" shortcut.
3. Double-tapping the back of the iPhone now opens the app and starts a 30-minute
   recording (auto-extends if it detects a meeting).

> Want a custom length? Make a second shortcut pointing at
> `personalaios://record?minutes=60` and assign it to **Triple Tap**.

### Android — Quick Tap (Pixel) / equivalent OEM gesture
1. Settings ▸ System ▸ Gestures ▸ **Quick Tap** → toggle on → **Open app** →
   *Personal AI OS*.
2. On boot, the app's `BootReceiver` posts a persistent low-priority notification
   ("Tap to record") so it's always one tap away even before you open it.

---

## 2. Home- and lock-screen widgets

Widgets are native extensions; they ship in a **dev/prod build** (`eas build`),
not in Expo Go. Two supported routes:

### iOS — WidgetKit via `expo-apple-targets`
```bash
npx create-target widget         # from @bacons/apple-targets, after `expo prebuild`
```
- Build a small SwiftUI widget with one button → `Link(destination: "personalaios://record?minutes=30")`.
- Add an **accessory** widget family for the **Lock Screen** (circular/rectangular).
- The widget can also show the latest note title by reading a shared App Group
  value the app writes after each save (see `note_feed`).

### Android — App Widget via Glance
- Add a Glance `GlanceAppWidget` whose root is a button with
  `actionStartActivity` → `Intent(ACTION_VIEW, "personalaios://record?minutes=30")`.
- Register it as a `<receiver android:name=".RecordWidget">` with
  `android.appwidget.action.APPWIDGET_UPDATE` (mirror the pattern in
  `plugins/withAndroidBoot.js`; a `plugins/withWidgets.js` can write the Kotlin +
  `appwidget-provider` XML during prebuild).

Both widgets only need to open the deep link — all recording/meeting logic
already lives in the app.

---

## 3. Always-on foreground service (Android, optional)

For true "mic is always listening, auto-tags meetings" behaviour with the screen
off, run the capture inside a **foreground service** (permissions
`FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MICROPHONE` are already declared). The
`RecordingEngine` keeps `staysActiveInBackground: true`; pair it with
`expo-task-manager` to keep the JS alive, or move capture into a native service if
you need it to survive JS suspension. iOS cannot offer the equivalent — there the
gesture/widget + audio background mode is the ceiling.
