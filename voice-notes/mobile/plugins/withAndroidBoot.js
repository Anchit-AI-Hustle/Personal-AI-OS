/**
 * Expo config plugin: start Personal AI OS automatically when the phone boots.
 *
 * Adds a BOOT_COMPLETED BroadcastReceiver that re-launches the app via the
 * `personalaios://` deep link. On Android 10+ background-activity-launch is
 * restricted, so on boot we start a foreground service that posts a
 * persistent "Tap to record" notification (the reliable, policy-compliant way
 * to be "always one tap away" the instant the phone is on).
 *
 * Enable by adding "./plugins/withAndroidBoot" to plugins[] in app.config.ts,
 * then `expo prebuild`.
 */
const { withAndroidManifest, withDangerousMod, AndroidConfig } = require("@expo/config-plugins");
const fs = require("fs");
const path = require("path");

const PKG = "com.anchit.personalaios";

const BOOT_RECEIVER_KT = `package ${PKG}

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import androidx.core.app.NotificationCompat

class BootReceiver : BroadcastReceiver() {
  override fun onReceive(context: Context, intent: Intent?) {
    if (intent?.action != Intent.ACTION_BOOT_COMPLETED) return
    val channelId = "paios_quick"
    val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.O) {
      nm.createNotificationChannel(
        NotificationChannel(channelId, "Quick record", NotificationManager.IMPORTANCE_LOW))
    }
    val deep = Intent(Intent.ACTION_VIEW, android.net.Uri.parse("personalaios://record?minutes=30"))
    deep.setPackage(context.packageName)
    val pi = PendingIntent.getActivity(
      context, 0, deep,
      PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
    val notif = NotificationCompat.Builder(context, channelId)
      .setContentTitle("Personal AI OS")
      .setContentText("Tap to record a note")
      .setSmallIcon(android.R.drawable.ic_btn_speak_now)
      .setOngoing(true)
      .setContentIntent(pi)
      .build()
    nm.notify(7001, notif)
  }
}
`;

function withBootReceiverFile(config) {
  return withDangerousMod(config, [
    "android",
    async (cfg) => {
      const pkgPath = PKG.replace(/\./g, "/");
      const dir = path.join(cfg.modRequest.platformProjectRoot, "app", "src", "main", "java", pkgPath);
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, "BootReceiver.kt"), BOOT_RECEIVER_KT);
      return cfg;
    },
  ]);
}

function withBootReceiverManifest(config) {
  return withAndroidManifest(config, (cfg) => {
    const app = AndroidConfig.Manifest.getMainApplicationOrThrow(cfg.modResults);
    app.receiver = app.receiver || [];
    app.receiver.push({
      $: { "android:name": `${PKG}.BootReceiver`, "android:exported": "true" },
      "intent-filter": [
        { action: [{ $: { "android:name": "android.intent.action.BOOT_COMPLETED" } }] },
      ],
    });
    return cfg;
  });
}

module.exports = (config) => withBootReceiverManifest(withBootReceiverFile(config));
