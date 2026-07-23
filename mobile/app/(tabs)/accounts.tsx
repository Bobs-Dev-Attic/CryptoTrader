import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { Alert, Platform, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { api, ExchangeAccount } from "@/api";
import { Badge, Button, Card } from "@/components";
import { colors, radius, spacing, screenContent } from "@/theme";

function confirm(message: string, onYes: () => void) {
  if (Platform.OS === "web") {
    // eslint-disable-next-line no-alert
    if (window.confirm(message)) onYes();
  } else {
    Alert.alert("Confirm", message, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: onYes },
    ]);
  }
}

/** A compact inline button used for per-row actions (Edit / Delete). */
function MiniButton({
  title,
  onPress,
  danger,
}: {
  title: string;
  onPress: () => void;
  danger?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        borderRadius: radius.sm,
        borderWidth: 1,
        borderColor: danger ? colors.red : colors.border,
        backgroundColor: colors.surfaceAlt,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <Text style={{ color: danger ? colors.red : colors.text, fontWeight: "600", fontSize: 13 }}>
        {title}
      </Text>
    </Pressable>
  );
}

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

  const remove = (a: ExchangeAccount) =>
    confirm(
      `Remove "${a.label}"? Agents using it will need a new connection for live trading.`,
      async () => {
        try {
          await api.deleteAccount(a.id);
          await load();
        } catch (e: any) {
          Alert.alert("Error", e?.message ?? "Failed to remove connection");
        }
      }
    );

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={screenContent}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      {/* Top button row */}
      <View style={{ flexDirection: "row", justifyContent: "flex-end", marginBottom: spacing.md }}>
        <Button title="Add" onPress={() => router.push("/connect")} />
      </View>

      <Text style={{ color: colors.textDim, marginBottom: spacing.lg }}>
        Link exchange API keys to enable live trading. Keys are encrypted at rest and never
        returned to the app. Paper agents don't need keys.
      </Text>

      {accounts.map((a) => (
        <Card key={a.id}>
          <View style={{ flexDirection: "row", alignItems: "center" }}>
            <View style={{ flex: 1, paddingRight: spacing.md }}>
              <Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>{a.label}</Text>
              <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 4 }}>
                <Text style={{ color: colors.textDim }}>
                  {a.exchange.toUpperCase()}
                  {!a.is_active ? " · disabled" : ""}
                </Text>
                <Badge
                  label={a.has_credentials ? "keyed" : "paper only"}
                  color={a.has_credentials ? colors.green : colors.textDim}
                />
              </View>
            </View>
            <View style={{ flexDirection: "row", gap: spacing.sm }}>
              <MiniButton title="Open / Edit" onPress={() => router.push(`/account/${a.id}`)} />
              <MiniButton title="Delete" danger onPress={() => remove(a)} />
            </View>
          </View>
        </Card>
      ))}

      {accounts.length === 0 && (
        <Text style={{ color: colors.textDim, textAlign: "center", marginTop: spacing.xl }}>
          No exchanges linked yet. Tap “Add” to run the setup wizard.
        </Text>
      )}
    </ScrollView>
  );
}
