import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { Agent, api } from "@/api";
import { Badge, Button, Card } from "@/components";
import { colors, pnlColor, spacing } from "@/theme";

export default function AgentsScreen() {
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setAgents(await api.listAgents());
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
      <Button title="+ New agent" onPress={() => router.push("/agent/new")} />
      <View style={{ height: spacing.lg }} />

      {agents.map((a) => {
        const pnl = a.position?.realized_pnl ?? 0;
        return (
          <Card key={a.id} style={{ marginBottom: spacing.md }}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>{a.name}</Text>
              <Badge
                label={a.trade_mode}
                color={a.trade_mode === "live" ? colors.yellow : colors.primary}
              />
            </View>
            <Text style={{ color: colors.textDim, marginTop: spacing.xs }}>
              {a.exchange.toUpperCase()} · {a.symbol} · {a.strategy_type}
            </Text>
            <View style={{ flexDirection: "row", justifyContent: "space-between", marginTop: spacing.md }}>
              <Text style={{ color: colors.textDim }}>
                Status: <Text style={{ color: a.status === "running" ? colors.green : colors.textDim }}>{a.status}</Text>
              </Text>
              <Text style={{ color: pnlColor(pnl) }}>
                P&L {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
              </Text>
            </View>
            <View style={{ height: spacing.md }} />
            <Button title="Open" variant="secondary" onPress={() => router.push(`/agent/${a.id}`)} />
          </Card>
        );
      })}

      {agents.length === 0 && (
        <Text style={{ color: colors.textDim, textAlign: "center", marginTop: spacing.xl }}>
          No agents yet.
        </Text>
      )}
    </ScrollView>
  );
}
