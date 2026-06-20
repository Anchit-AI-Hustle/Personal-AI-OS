/**
 * RecordingEngine — meeting-aware voice capture.
 *
 * Behaviour (per spec):
 *  - Records for a configurable cap (default 30 min).
 *  - While recording it watches the mic level (metering) to track speech vs
 *    silence and to sense whether this is a *meeting* (sustained, varied,
 *    multi-party-like activity) rather than a short solo memo.
 *  - When the cap is hit:
 *      - if it looks like a meeting AND someone is still talking, it KEEPS
 *        recording and only stops after `silenceStopMs` of CONTINUOUS silence
 *        (default 10 min).
 *      - otherwise it stops at the cap.
 *  - Emits live ticks (elapsed, level, isSilent, meetingLikely) so the UI can
 *    show a waveform + "meeting detected, still recording…" banner.
 *
 * Real silence detection uses expo-av metering (dBFS). A streaming-STT hook
 * (`onPartialTranscript`) is exposed for those who wire AssemblyAI/Deepgram
 * realtime; it's optional and the meeting heuristic works without it.
 */
import { Audio } from "expo-av";

export type RecorderConfig = {
  capMs: number;            // default 30 min
  silenceStopMs: number;    // continuous silence that ends an extended meeting (default 10 min)
  silenceDbThreshold: number; // metering dBFS below which we call it silence
  autoExtendMeetings: boolean;
};

export const DEFAULT_CONFIG: RecorderConfig = {
  capMs: 30 * 60 * 1000,
  silenceStopMs: 10 * 60 * 1000,
  silenceDbThreshold: -45,
  autoExtendMeetings: true,
};

export type Tick = {
  elapsedMs: number;
  level: number;          // 0..1 normalised
  isSilent: boolean;
  extended: boolean;      // past the cap, in meeting auto-extend mode
  meetingLikely: boolean;
  continuousSilenceMs: number;
};

export type RecordingResult = {
  uri: string;
  durationMs: number;
  isMeeting: boolean;
  autoExtended: boolean;
};

const TICK_MS = 500;

export class RecordingEngine {
  private rec: Audio.Recording | null = null;
  private cfg: RecorderConfig;
  private timer: ReturnType<typeof setInterval> | null = null;
  private startedAt = 0;
  private continuousSilence = 0;
  private speechSamples = 0;
  private levelChanges = 0;
  private lastLoud = false;
  private extended = false;
  private onTick?: (t: Tick) => void;
  private onAutoStop?: (r: RecordingResult) => void;
  public onPartialTranscript?: (text: string) => void; // optional realtime STT sink

  constructor(cfg: Partial<RecorderConfig> = {}) {
    this.cfg = { ...DEFAULT_CONFIG, ...cfg };
  }

  async start(opts: { onTick?: (t: Tick) => void; onAutoStop?: (r: RecordingResult) => void } = {}) {
    this.onTick = opts.onTick;
    this.onAutoStop = opts.onAutoStop;

    await Audio.requestPermissionsAsync();
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: true,
      playsInSilentModeIOS: true,
      staysActiveInBackground: true, // Android foreground service / iOS background audio
      shouldDuckAndroid: true,
    });

    const rec = new Audio.Recording();
    await rec.prepareToRecordAsync({
      ...Audio.RecordingOptionsPresets.HIGH_QUALITY,
      isMeteringEnabled: true,
    });
    await rec.startAsync();
    this.rec = rec;
    this.startedAt = Date.now();
    this.continuousSilence = 0;
    this.speechSamples = 0;
    this.levelChanges = 0;
    this.extended = false;

    this.timer = setInterval(() => this.poll(), TICK_MS);
  }

  private meetingLikely(elapsedMs: number): boolean {
    // proxy for a multi-party discussion: enough speech, enough back-and-forth
    // level variation, and not a tiny clip.
    const minutes = elapsedMs / 60000;
    const speechRatio = this.speechSamples / Math.max(1, elapsedMs / TICK_MS);
    return minutes >= 2 && speechRatio > 0.35 && this.levelChanges >= 8;
  }

  private async poll() {
    if (!this.rec) return;
    const status = await this.rec.getStatusAsync();
    if (!status.isRecording) return;

    const elapsed = Date.now() - this.startedAt;
    // Metering (dBFS) is available on iOS/Android but NOT on web. Without it we
    // can't measure silence, so on web we don't claim silence and we don't
    // arm meeting auto-extend (the recording still respects the time cap).
    const meteringAvailable = typeof status.metering === "number";
    const db = meteringAvailable ? (status.metering as number) : 0;
    const isSilent = meteringAvailable ? db < this.cfg.silenceDbThreshold : false;
    const level = meteringAvailable ? Math.max(0, Math.min(1, (db + 60) / 60)) : 0;

    if (isSilent) {
      this.continuousSilence += TICK_MS;
    } else {
      this.continuousSilence = 0;
      this.speechSamples += 1;
      if (this.lastLoud === false) this.levelChanges += 1;
    }
    this.lastLoud = !isSilent;

    const meeting = meteringAvailable && this.meetingLikely(elapsed);

    this.onTick?.({
      elapsedMs: elapsed,
      level,
      isSilent,
      extended: this.extended,
      meetingLikely: meeting,
      continuousSilenceMs: this.continuousSilence,
    });

    // --- cap & auto-extend logic -------------------------------------------
    if (!this.extended && elapsed >= this.cfg.capMs) {
      if (this.cfg.autoExtendMeetings && meeting) {
        this.extended = true; // keep going; stop on sustained silence
      } else {
        await this.finishAuto();
        return;
      }
    }
    if (this.extended && this.continuousSilence >= this.cfg.silenceStopMs) {
      await this.finishAuto();
    }
  }

  private async finishAuto() {
    const r = await this.stop();
    if (r) this.onAutoStop?.(r);
  }

  /** Manual stop (or internal auto-stop). Returns the file + meeting verdict. */
  async stop(): Promise<RecordingResult | null> {
    if (this.timer) { clearInterval(this.timer); this.timer = null; }
    if (!this.rec) return null;
    const elapsed = Date.now() - this.startedAt;
    try {
      await this.rec.stopAndUnloadAsync();
    } catch { /* already stopped */ }
    const uri = this.rec.getURI() ?? "";
    const meeting = this.meetingLikely(elapsed);
    this.rec = null;
    await Audio.setAudioModeAsync({ allowsRecordingIOS: false });
    return { uri, durationMs: elapsed, isMeeting: meeting, autoExtended: this.extended };
  }

  get isRecording() { return this.rec !== null; }
}
