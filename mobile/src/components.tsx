/** Small reusable UI primitives shared across screens. */
import React, { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  TextInputProps,
  useWindowDimensions,
  View,
  ViewStyle,
} from "react-native";

import { colors, radius, spacing } from "./theme";

/** Number of columns to tile cards into, based on the viewport width. */
export function useColumns(breakpoint = 860): number {
  const { width } = useWindowDimensions();
  return width >= breakpoint ? 2 : 1;
}

/**
 * Lays children out in a responsive grid (2 columns on wide screens, 1 on
 * phones). Each child is wrapped so it takes an equal column width.
 */
export function CardGrid({ children, columns }: { children: React.ReactNode; columns?: number }) {
  const auto = useColumns();
  const cols = columns ?? auto;
  const items = React.Children.toArray(children);
  if (cols === 1) return <>{children}</>;
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", justifyContent: "space-between" }}>
      {items.map((child, i) => (
        <View key={i} style={{ width: "49%" }}>
          {child}
        </View>
      ))}
    </View>
  );
}

/**
 * A field label with an optional tap-to-reveal help hint (ⓘ). Works on web and
 * mobile (hover tooltips don't exist on touch devices), so tapping the icon
 * toggles an inline explanation beneath the label.
 */
export function InfoLabel({ label, help }: { label: string; help?: string }) {
  const [open, setOpen] = useState(false);
  if (!help) {
    return <Text style={styles.label}>{label}</Text>;
  }
  return (
    <View style={{ marginBottom: spacing.xs }}>
      <Pressable
        onPress={() => setOpen((o) => !o)}
        hitSlop={8}
        style={{ flexDirection: "row", alignItems: "center" }}
        accessibilityRole="button"
        accessibilityLabel={`${label} — tap for help`}
      >
        <Text style={styles.label}>{label}</Text>
        <View style={styles.infoBadge}>
          <Text style={styles.infoBadgeText}>{open ? "×" : "i"}</Text>
        </View>
      </Pressable>
      {open && <Text style={styles.helpText}>{help}</Text>}
    </View>
  );
}

/** A standalone explanatory paragraph (e.g. a section intro for lay users). */
export function HelpNote({ children }: { children: React.ReactNode }) {
  return (
    <View style={styles.helpNote}>
      <Text style={styles.helpNoteText}>{children}</Text>
    </View>
  );
}

export function Card({
  children,
  style,
}: {
  children: React.ReactNode;
  style?: ViewStyle;
}) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Button({
  title,
  onPress,
  variant = "primary",
  loading,
  disabled,
}: {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "danger";
  loading?: boolean;
  disabled?: boolean;
}) {
  const bg =
    variant === "primary"
      ? colors.primary
      : variant === "danger"
      ? colors.red
      : colors.surfaceAlt;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.button,
        { backgroundColor: bg, opacity: disabled ? 0.5 : pressed ? 0.8 : 1 },
      ]}
    >
      {loading ? (
        <ActivityIndicator color="#fff" />
      ) : (
        <Text style={styles.buttonText}>{title}</Text>
      )}
    </Pressable>
  );
}

export function Field({
  label,
  help,
  style,
  ...props
}: { label: string; help?: string } & TextInputProps) {
  return (
    <View style={{ marginBottom: spacing.md }}>
      <InfoLabel label={label} help={help} />
      <TextInput
        placeholderTextColor={colors.textDim}
        style={[styles.input, style]}
        {...props}
      />
    </View>
  );
}

export function Badge({
  label,
  color,
}: {
  label: string;
  color: string;
}) {
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

export function Row({
  left,
  right,
}: {
  left: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <View style={styles.row}>
      <View style={{ flex: 1 }}>{left}</View>
      {right}
    </View>
  );
}

export const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.lg,
    marginBottom: spacing.md,
  },
  button: {
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
    minHeight: 46,
  },
  buttonText: { color: "#fff", fontWeight: "600", fontSize: 15 },
  label: { color: colors.textDim, fontSize: 13 },
  infoBadge: {
    marginLeft: 6,
    width: 15,
    height: 15,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  infoBadgeText: {
    color: colors.primary,
    fontSize: 10,
    fontWeight: "700",
    lineHeight: 12,
  },
  helpText: {
    color: colors.textDim,
    fontSize: 12,
    lineHeight: 17,
    marginTop: spacing.xs,
    paddingLeft: 2,
  },
  helpNote: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    borderLeftWidth: 3,
    borderLeftColor: colors.primary,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  helpNoteText: { color: colors.text, fontSize: 13, lineHeight: 19 },
  input: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    color: colors.text,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: 15,
  },
  badge: {
    borderWidth: 1,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    alignSelf: "flex-start",
  },
  badgeText: { fontSize: 12, fontWeight: "600", textTransform: "uppercase" },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
});
