import AsyncStorage from "@react-native-async-storage/async-storage";
import { DEFAULT_CONFIG, RecorderConfig } from "./recording";

const KEY = "voicenotes.recorder.cfg";

export async function loadConfig(): Promise<RecorderConfig> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? { ...DEFAULT_CONFIG, ...JSON.parse(raw) } : DEFAULT_CONFIG;
  } catch {
    return DEFAULT_CONFIG;
  }
}

export async function saveConfig(cfg: RecorderConfig) {
  await AsyncStorage.setItem(KEY, JSON.stringify(cfg));
}
