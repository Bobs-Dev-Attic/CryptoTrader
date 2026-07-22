/** Global slide-in navigation menu (hamburger) shown on every page header. */
import { useRouter } from "expo-router";
import React, { createContext, useContext, useMemo, useState } from "react";
import { Modal, Pressable, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "./auth";
import { colors, radius, spacing } from "./theme";

interface MenuState {
  open: boolean;
  openMenu: () => void;
  closeMenu: () => void;
}
const MenuContext = createContext<MenuState | undefined>(undefined);

export function MenuProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const value = useMemo(
    () => ({ open, openMenu: () => setOpen(true), closeMenu: () => setOpen(false) }),
    [open]
  );
  return <MenuContext.Provider value={value}>{children}</MenuContext.Provider>;
}

export function useMenu(): MenuState {
  const ctx = useContext(MenuContext);
  if (!ctx) throw new Error("useMenu must be used within MenuProvider");
  return ctx;
}

/** The hamburger button — place in a screen header's headerLeft. */
export function MenuButton() {
  const { openMenu } = useMenu();
  return (
    <Pressable
      onPress={openMenu}
      hitSlop={12}
      accessibilityRole="button"
      accessibilityLabel="Open menu"
      style={{ paddingHorizontal: spacing.md, paddingVertical: spacing.xs }}
    >
      <Text style={{ color: colors.text, fontSize: 22, lineHeight: 24 }}>☰</Text>
    </Pressable>
  );
}

const ITEMS: { icon: string; label: string; path: string }[] = [
  { icon: "📊", label: "Dashboard", path: "/" },
  { icon: "🤖", label: "Agents", path: "/agents" },
  { icon: "🔑", label: "Exchanges", path: "/accounts" },
  { icon: "⚙️", label: "Account settings", path: "/settings" },
];

/** The overlay panel. Render once near the app root, inside MenuProvider. */
export function AppMenu() {
  const { open, closeMenu } = useMenu();
  const router = useRouter();
  const { user, logout } = useAuth();
  const insets = useSafeAreaInsets();

  const go = (path: string) => {
    closeMenu();
    router.push(path as any);
  };

  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={closeMenu}>
      <Pressable style={{ flex: 1, flexDirection: "row" }} onPress={closeMenu}>
        <Pressable
          onPress={() => {}}
          style={{
            width: "78%",
            maxWidth: 320,
            backgroundColor: colors.surface,
            borderRightWidth: 1,
            borderRightColor: colors.border,
            paddingTop: insets.top + spacing.lg,
            paddingHorizontal: spacing.lg,
            flex: 1,
          }}
        >
          <Text style={{ color: colors.text, fontSize: 22, fontWeight: "800" }}>CryptoTrader</Text>
          {user ? (
            <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2, marginBottom: spacing.xl }}>
              {user.email}
            </Text>
          ) : (
            <View style={{ height: spacing.xl }} />
          )}

          {ITEMS.map((it) => (
            <Pressable
              key={it.path}
              onPress={() => go(it.path)}
              style={({ pressed }) => ({
                flexDirection: "row",
                alignItems: "center",
                paddingVertical: spacing.md,
                paddingHorizontal: spacing.sm,
                borderRadius: radius.sm,
                backgroundColor: pressed ? colors.surfaceAlt : "transparent",
              })}
            >
              <Text style={{ fontSize: 18, width: 30 }}>{it.icon}</Text>
              <Text style={{ color: colors.text, fontSize: 16 }}>{it.label}</Text>
            </Pressable>
          ))}

          <View style={{ flex: 1 }} />
          <Pressable
            onPress={() => {
              closeMenu();
              logout();
            }}
            style={{
              flexDirection: "row",
              alignItems: "center",
              paddingVertical: spacing.md,
              paddingHorizontal: spacing.sm,
              marginBottom: insets.bottom + spacing.lg,
            }}
          >
            <Text style={{ fontSize: 18, width: 30 }}>🚪</Text>
            <Text style={{ color: colors.red, fontSize: 16 }}>Log out</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}
