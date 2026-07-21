import { Tabs } from "expo-router";
import React from "react";
import { Text } from "react-native";

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
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.textDim,
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
