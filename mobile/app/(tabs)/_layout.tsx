import { Tabs } from "expo-router";
import React from "react";
import { Text } from "react-native";

import { MenuButton } from "@/menu";
import { colors } from "@/theme";

function TabIcon({ icon, color }: { icon: string; color: string }) {
  return <Text style={{ fontSize: 20, color }}>{icon}</Text>;
}

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerStyle: { backgroundColor: colors.surface },
        headerTintColor: colors.text,
        headerLeft: () => <MenuButton />,
        // Navigation is handled by the global hamburger menu, so the bottom tab
        // bar is hidden. These screens remain a Tabs navigator only for routing.
        tabBarStyle: { display: "none" },
        sceneStyle: { backgroundColor: colors.bg },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "Dashboard",
          tabBarIcon: ({ color }) => <TabIcon icon="📊" color={color} />,
        }}
      />
      <Tabs.Screen
        name="agents"
        options={{
          title: "Agents",
          tabBarIcon: ({ color }) => <TabIcon icon="🤖" color={color} />,
        }}
      />
      <Tabs.Screen
        name="accounts"
        options={{
          title: "Exchanges",
          tabBarIcon: ({ color }) => <TabIcon icon="🔑" color={color} />,
        }}
      />
    </Tabs>
  );
}
