/** Shared color + spacing tokens for a dark, finance-app aesthetic. */
export const colors = {
  bg: "#0b0f1a",
  surface: "#141a2a",
  surfaceAlt: "#1c2438",
  border: "#26304a",
  text: "#e8ecf5",
  textDim: "#8a94ad",
  primary: "#4f7cff",
  primaryDim: "#2d3f7a",
  green: "#2ecc71",
  red: "#ff5c6c",
  yellow: "#f5b942",
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
};

/** Color for a signed number (green up / red down). */
export function pnlColor(value: number): string {
  if (value > 0) return colors.green;
  if (value < 0) return colors.red;
  return colors.textDim;
}

/**
 * Centered, max-width content container. Keeps pages from stretching edge-to-edge
 * on wide (desktop web) screens while staying full-width on phones. Use as a
 * ScrollView's contentContainerStyle.
 */
export const screenContent = {
  padding: spacing.lg,
  width: "100%",
  maxWidth: 980,
  alignSelf: "center",
} as const;
