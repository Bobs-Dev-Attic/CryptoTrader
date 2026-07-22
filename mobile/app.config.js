// Extends the static app.json config and injects build-time metadata so the
// on-screen version badge can show the exact deployed commit. Vercel sets
// VERCEL_GIT_COMMIT_SHA automatically during the build; locally it falls back
// to "dev".
const base = require("./app.json").expo;

const sha = process.env.VERCEL_GIT_COMMIT_SHA || process.env.EXPO_PUBLIC_COMMIT || "";
const commit = sha ? sha.slice(0, 7) : "dev";

module.exports = {
  ...base,
  extra: {
    ...(base.extra || {}),
    appVersion: base.version,
    commit,
  },
};
