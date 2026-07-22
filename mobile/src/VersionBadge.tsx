import React from "react";
import { Platform, Text, View } from "react-native";

import { colors } from "@/theme";
import { VERSION_LABEL } from "@/version";

/**
 * A small, unobtrusive version label pinned to the upper-right corner of the
 * web app. It sits above everything (fixed position on web) so you can confirm
 * which build is loaded regardless of the current screen. Rendered on web only.
 */
export function VersionBadge() {
  if (Platform.OS !== "web") return null;
  return (
    <View
      // `position: fixed` keeps it in the corner as the page scrolls (web only).
      style={{
        position: "fixed" as any,
        top: 6,
        right: 8,
        zIndex: 9999,
        paddingHorizontal: 8,
        paddingVertical: 3,
        borderRadius: 6,
        backgroundColor: "rgba(0,0,0,0.35)",
        pointerEvents: "none" as any,
      }}
    >
      <Text style={{ color: colors.textDim, fontSize: 11, fontWeight: "600" }}>{VERSION_LABEL}</Text>
    </View>
  );
}
