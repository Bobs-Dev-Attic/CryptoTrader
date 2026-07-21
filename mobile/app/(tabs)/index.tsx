import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useState } from "react";
import { RefreshControl, ScrollView, Text, View } from "react-native";

import { Agent, api } from "@/api";
import { useAuth } from "@/auth";
import { Donut, LineChart, Sparkline } from "@/charts";
import { Badge, Button, Card } from "@/components";
import { PriceTicker } from "@/PriceTicker";
import { colors, pnlColor, radius, spacing } from "@/theme";

const TICKER_SYMBOLS = [
  "BTC/USD",
  "ETH/USD",
  "SOL/USD",
  "XRP/USD",
  "ADA/USD",
  "DOGE/USD",
  "LTC/USD",
  "DOT/USD",
];

export default function Dashboard() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [history, setHistory] = useState<{ t: string; equity: number }[]>([]);
  const [allocation, setAllocation] = useState<{ label: string; value: number; symbol: string }[]>([]);
  const [stats, setStats] = useState<Record<string, number | null> | null>(null);
  const [chartW, setChartW] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const [ag, hist, alloc, st] = await Promise.all([
        api.listAgents(),
        api.portfolioHistory().catch(() => []),
        api.portfolioAllocation().catch(() => []),
        api.portfolioStats().catch(() => null),
      ]);
      setAgents(ag);
      setHistory(hist);
      setAllocation(alloc);
      setStats(st);
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
      <PriceTicker symbols={TICKER_SYMBOLS} />

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

      {stats && (stats.closed_trades ?? 0) > 0 && (
        <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.md }}>
          <Stat
            label="Win rate"
            value={stats.win_rate != null ? `${Math.round((stats.win_rate as number) * 100)}%` : "—"}
            valueColor={
              (stats.win_rate ?? 0) >= 0.5 ? colors.green : colors.red
            }
          />
          <Stat
            label="Trades (W/L)"
            value={`${stats.wins ?? 0}/${stats.losses ?? 0}`}
          />
        </View>
      )}

      {history.length >= 2 && (
        <>
          <View style={{ height: spacing.lg }} />
          <Card>
            <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
              <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700" }}>Portfolio equity</Text>
              <Text style={{ color: pnlColor(history[history.length - 1].equity - history[0].equity), fontSize: 13, fontWeight: "600" }}>
                ${history[history.length - 1].equity.toFixed(2)}
              </Text>
            </View>
            <View style={{ height: spacing.sm }} />
            <View onLayout={(e) => setChartW(e.nativeEvent.layout.width)}>
              <LineChart values={history.map((h) => h.equity)} width={chartW} height={130} />
            </View>
          </Card>
        </>
      )}

      {allocation.length > 0 && (
        <Card>
          <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: spacing.md }}>
            Allocation
          </Text>
          <Donut slices={allocation} />
        </Card>
      )}

      {agents.length > 0 && (
        <>
          <View style={{ height: spacing.sm }} />
          <PnlChart agents={agents} />
        </>
      )}

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
              <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
                <Sparkline exchange={a.exchange} symbol={a.symbol} timeframe={a.timeframe} />
                <Badge
                  label={a.status}
                  color={a.status === "running" ? colors.green : a.status === "error" ? colors.red : colors.textDim}
                />
              </View>
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

/** Horizontal bar chart of each agent's realized P&L (dependency-free). */
function PnlChart({ agents }: { agents: Agent[] }) {
  const rows = agents.map((a) => ({
    name: a.name,
    pnl: a.position?.realized_pnl ?? 0,
  }));
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.pnl)));
  const anyNonZero = rows.some((r) => r.pnl !== 0);

  return (
    <Card>
      <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: spacing.md }}>
        Realized P&L by agent
      </Text>
      {!anyNonZero ? (
        <Text style={{ color: colors.textDim, fontSize: 13 }}>
          No closed trades yet — each agent's profit/loss will chart here once it buys and sells.
        </Text>
      ) : (
        rows.map((r, i) => {
          const pct = Math.min(1, Math.abs(r.pnl) / maxAbs);
          const positive = r.pnl >= 0;
          return (
            <View key={i} style={{ marginBottom: spacing.sm }}>
              <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: 3 }}>
                <Text style={{ color: colors.textDim, fontSize: 12 }} numberOfLines={1}>
                  {r.name}
                </Text>
                <Text style={{ color: pnlColor(r.pnl), fontSize: 12, fontWeight: "600" }}>
                  {r.pnl >= 0 ? "+" : ""}${r.pnl.toFixed(2)}
                </Text>
              </View>
              <View style={{ height: 8, backgroundColor: colors.surfaceAlt, borderRadius: 4, overflow: "hidden" }}>
                <View
                  style={{
                    height: 8,
                    width: `${Math.max(pct * 100, 2)}%`,
                    backgroundColor: positive ? colors.green : colors.red,
                    borderRadius: 4,
                  }}
                />
              </View>
            </View>
          );
        })
      )}
    </Card>
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
