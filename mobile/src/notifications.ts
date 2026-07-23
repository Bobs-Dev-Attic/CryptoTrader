/** Web push + foreground notifications for triggered volatility alerts (web only). */
import { useEffect } from "react";
import { Platform } from "react-native";

import { api } from "./api";

export function pushSupported(): boolean {
  return (
    Platform.OS === "web" &&
    typeof window !== "undefined" &&
    "Notification" in window &&
    "serviceWorker" in navigator &&
    "PushManager" in window
  );
}

export function notificationPermission(): "default" | "granted" | "denied" | "unsupported" {
  if (Platform.OS !== "web" || typeof window === "undefined" || !("Notification" in window)) {
    return "unsupported";
  }
  return Notification.permission as "default" | "granted" | "denied";
}

function urlB64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(b64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/**
 * Request permission and register a Web Push subscription so alerts arrive even
 * when the app is closed. Returns a human-readable status.
 */
export async function enablePush(): Promise<{ ok: boolean; message: string }> {
  if (!pushSupported()) {
    return { ok: false, message: "Notifications aren't supported in this browser." };
  }
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      return { ok: false, message: "Notification permission was not granted." };
    }
    const reg = await navigator.serviceWorker.register("/sw.js");
    await navigator.serviceWorker.ready;
    const { key } = await api.pushPublicKey();
    let sub = await reg.pushManager.getSubscription();
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(key),
      });
    }
    const json: any = sub.toJSON();
    await api.pushSubscribe({ endpoint: json.endpoint, keys: json.keys });
    return { ok: true, message: "Push notifications enabled for this browser." };
  } catch (e: any) {
    return { ok: false, message: e?.message ?? "Could not enable notifications." };
  }
}

export async function disablePush(): Promise<void> {
  if (!pushSupported()) return;
  try {
    const reg = await navigator.serviceWorker.getRegistration();
    const sub = reg && (await reg.pushManager.getSubscription());
    if (sub) {
      await api.pushUnsubscribe(sub.endpoint).catch(() => {});
      await sub.unsubscribe().catch(() => {});
    }
  } catch {
    /* ignore */
  }
}

/**
 * Foreground fallback: while the app is open, poll for newly-triggered alerts
 * and raise a browser notification. Complements Web Push (covers users who
 * haven't enabled push, and gives immediate feedback while browsing). Web only.
 */
export function useAlertNotifications(enabled: boolean) {
  useEffect(() => {
    if (!enabled || Platform.OS !== "web" || typeof window === "undefined" || !("Notification" in window)) {
      return;
    }
    const KEY = "cryptotrader.notified";
    let seen: Record<string, string> = {};
    try {
      seen = JSON.parse(window.localStorage.getItem(KEY) || "{}");
    } catch {
      seen = {};
    }
    let alive = true;

    const poll = async () => {
      if (Notification.permission !== "granted") return;
      try {
        const watches = await api.listWatches();
        let changed = false;
        for (const w of watches) {
          if (w.triggered && w.last_triggered_at && seen[w.id] !== w.last_triggered_at) {
            seen[w.id] = w.last_triggered_at;
            changed = true;
            // eslint-disable-next-line no-new
            new Notification(`${w.symbol} volatility alert`, {
              body: `${w.metric} crossed ${w.threshold}`,
            });
          }
        }
        if (changed) window.localStorage.setItem(KEY, JSON.stringify(seen));
      } catch {
        /* ignore (e.g. logged out) */
      }
    };

    poll();
    const t = setInterval(() => alive && poll(), 45_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [enabled]);
}
