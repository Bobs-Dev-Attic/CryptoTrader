import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import React, { useEffect } from "react";
import { ActivityIndicator, View } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import { AuthProvider, useAuth } from "@/auth";
import { colors } from "@/theme";

function AuthGate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;
    const inAuthScreen = segments[0] === "login";
    if (!user && !inAuthScreen) {
      router.replace("/login");
    } else if (user && inAuthScreen) {
      router.replace("/");
    }
  }, [user, loading, segments]);

  if (loading) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, justifyContent: "center" }}>
        <ActivityIndicator color={colors.primary} size="large" />
      </View>
    );
  }
  return <>{children}</>;
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <AuthGate>
          <StatusBar style="light" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: colors.surface },
              headerTintColor: colors.text,
              contentStyle: { backgroundColor: colors.bg },
            }}
          >
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen name="login" options={{ headerShown: false }} />
            <Stack.Screen name="agent/new" options={{ title: "New Agent", presentation: "modal" }} />
            <Stack.Screen name="agent/[id]" options={{ title: "Agent" }} />
            <Stack.Screen name="connect" options={{ title: "Connect an exchange", presentation: "modal" }} />
            <Stack.Screen name="account/[id]" options={{ title: "Edit connection" }} />
          </Stack>
        </AuthGate>
      </AuthProvider>
    </SafeAreaProvider>
  );
}
