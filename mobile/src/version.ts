/** App version + build info, surfaced in a small on-screen badge.
 *
 * `appVersion` comes from app.json (`expo.version`); `commit` is injected at
 * build time from Vercel's VERCEL_GIT_COMMIT_SHA (see app.config.js). The badge
 * lets you confirm at a glance that the browser is running the latest build and
 * not a stale cached bundle.
 */
import Constants from "expo-constants";

const extra = (Constants.expoConfig?.extra as Record<string, any>) || {};

export const APP_VERSION: string = extra.appVersion || "0.0.0";
export const BUILD_COMMIT: string = extra.commit || "dev";

/** e.g. "v0.2.0 · a1b2c3d" (or "v0.2.0 · dev" for a local build). */
export const VERSION_LABEL = `v${APP_VERSION} · ${BUILD_COMMIT}`;
