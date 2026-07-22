import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { api, ExchangeAccount } from "@/api";
import { Badge, Button, Card } from "@/components";
import { colors, spacing } from "@/theme";

export default function AccountsScreen() {
  const router = useRouter();
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setAccounts(await api.listAccounts());
    } catch {
      /* ignore */
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
        Link exchange API keys to enable live trading. Keys are encrypted at rest and never
        returned to the app. Paper agents don't need keys.
      </Text>

      <Button title="+ Connect an exchange" onPress={() => router.push("/connect")} />
      <View style={{ height: spacing.lg }} />

      {accounts.map((a) => (
        <Pressable key={a.id} onPress={() => router.push(`/account/${a.id}`)}>
          <Card>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <View style={{ flex: 1 }}>
                <Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>{a.label}</Text>
                <Text style={{ color: colors.textDim, marginTop: 2 }}>
                  {a.exchange.toUpperCase()}
                  {!a.is_active ? " · disabled" : ""}
                </Text>
              </View>
              <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
                <Badge
                  label={a.has_credentials ? "keyed" : "paper only"}
                  color={a.has_credentials ? colors.green : colors.textDim}
                />
                <Text style={{ color: colors.textDim, fontSize: 20 }}>›</Text>
              </View>
            </View>
          </Card>
        </Pressable>
      ))}

      {accounts.length === 0 && (
        <Text style={{ color: colors.textDim, textAlign: "center", marginTop: spacing.xl }}>
          No exchanges linked yet. Tap “Connect an exchange” to run the setup wizard.
        </Text>
      )}
    </ScrollView>
  );
}
