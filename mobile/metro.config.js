// Default Expo Metro config. Expo enables tsconfig `paths` (the "@/*" alias)
// automatically, so no extra resolver wiring is needed.
const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

module.exports = config;
