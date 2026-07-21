import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { Agent, api } from "@/api";
import { useAuth } from "@/auth";
import { Badge, Button, Card } from "@/components";
import { colors, pnlColor, spacing } from "@/theme";

export default function Dashboard() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      setAgents(await api.listAgents());
    } catch {
      /* handled by empty state */
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

  const running = agents.filter((a) => a.status === "running").length;
  const realized = agents.reduce((s, a) => s + (a.position?.realized_pnl ?? 0), 0);
  const deployed = agents.reduce(
    (s, a) => s + (a.position ? a.position.quantity * a.position.avg_entry_price : 0),
    0
  );

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={{ color: colors.textDim, marginBottom: spacing.lg }}>
        Signed in as {user?.email}
      </Text>

      <View style={{ flexDirection: "row", gap: spacing.md, marginBottom: spacing.md }}>
        <Stat label="Agents" value={String(agents.length)} />
        <Stat label="Running" value={String(running)} valueColor={running ? colors.green : colors.textDim} />
      </View>
      <View style={{ flexDirection: "row", gap: spacing.md }}>
        <Stat label="Deployed" value={`$${deployed.toFixed(0)}`} />
        <Stat
          label="Realized P&L"
          value={`${realized >= 0 ? "+" : ""}$${realized.toFixed(2)}`}
          valueColor={pnlColor(realized)}
        />
      </View>

      <View style={{ height: spacing.lg }} />
      <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginBottom: spacing.md }}>
        Your agents
      </Text>

      {agents.length === 0 ? (
        <Card>
          <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
            No agents yet. Create one to start paper trading.
          </Text>
          <Button title="Create an agent" onPress={() => router.push("/agent/new")} />
        </Card>
      ) : (
        agents.map((a) => (
          <Card key={a.id}>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>{a.name}</Text>
              <Badge
                label={a.status}
                color={a.status === "running" ? colors.green : a.status === "error" ? colors.red : colors.textDim}
              />
            </View>
            <Text style={{ color: colors.textDim, marginTop: spacing.xs }}>
              {a.exchange.toUpperCase()} · {a.symbol} · {a.trade_mode} · {a.strategy_type}
            </Text>
            <View style={{ height: spacing.md }} />
            <Button title="Open" variant="secondary" onPress={() => router.push(`/agent/${a.id}`)} />
          </Card>
        ))
      )}

      <View style={{ height: spacing.xl }} />
      <Button title="Log out" variant="secondary" onPress={logout} />
    </ScrollView>
  );
}

function Stat({ label, value, valueColor }: { label: string; value: string; valueColor?: string }) {
  return (
    <View
      style={{
        flex: 1,
        backgroundColor: colors.surface,
        borderRadius: 12,
        borderWidth: 1,
        borderColor: colors.border,
        padding: spacing.lg,
      }}
    >
      <Text style={{ color: colors.textDim, fontSize: 13 }}>{label}</Text>
      <Text style={{ color: valueColor ?? colors.text, fontSize: 22, fontWeight: "800", marginTop: 4 }}>
        {value}
      </Text>
    </View>
  );
}
