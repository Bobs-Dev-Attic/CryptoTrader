import {
  useFocusEffect,
  useLocalSearchParams,
  useNavigation,
  useRouter,
} from "expo-router";
import React, { useCallback, useState } from "react";
import { Alert, Platform, RefreshControl, ScrollView, Text, View } from "react-native";

import { AgentDetail, api } from "@/api";
import { LineChart } from "@/charts";
import { Badge, Button, Card } from "@/components";
import { colors, pnlColor, spacing } from "@/theme";

function confirm(message: string, onYes: () => void) {
  if (Platform.OS === "web") {
    // eslint-disable-next-line no-alert
    if (window.confirm(message)) onYes();
  } else {
    Alert.alert("Confirm", message, [
      { text: "Cancel", style: "cancel" },
      { text: "OK", onPress: onYes },
    ]);
  }
}

export default function AgentDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const agentId = Number(id);
  const router = useRouter();
  const navigation = useNavigation();
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [equity, setEquity] = useState<{ t: string; equity: number }[]>([]);
  const [chartW, setChartW] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const [a, eq] = await Promise.all([
        api.getAgent(agentId),
        api.agentEquity(agentId).catch(() => []),
      ]);
      setAgent(a);
      setEquity(eq);
      navigation.setOptions({ title: a.name });
    } catch {
      /* ignore */
    }
  }, [agentId, navigation]);

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

  const act = async (fn: () => Promise<any>) => {
    setBusy(true);
    try {
      await fn();
      await load();
    } catch (e: any) {
      Alert.alert("Error", e?.message ?? "Action failed");
    } finally {
      setBusy(false);
    }
  };

  if (!agent) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Text style={{ color: colors.textDim }}>Loading…</Text>
      </View>
    );
  }

  const pos = agent.position;
  const running = agent.status === "running";

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md }}>
        <Badge label={agent.status} color={running ? colors.green : agent.status === "error" ? colors.red : colors.textDim} />
        <Badge label={agent.trade_mode} color={agent.trade_mode === "live" ? colors.yellow : colors.primary} />
        <Badge label={agent.strategy_type} color={colors.textDim} />
      </View>
      <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
        {agent.exchange.toUpperCase()} · {agent.symbol} · {agent.timeframe} · every {agent.interval_seconds}s
      </Text>

      {agent.last_error ? (
        <Card style={{ borderColor: colors.red }}>
          <Text style={{ color: colors.red }}>{agent.last_error}</Text>
        </Card>
      ) : null}

      {/* Position + P&L */}
      <Card>
        <Text style={{ color: colors.text, fontWeight: "700", marginBottom: spacing.md }}>Position</Text>
        <Line label="Quantity" value={pos ? pos.quantity.toFixed(6) : "0"} />
        <Line label="Avg entry" value={pos ? `$${pos.avg_entry_price.toFixed(2)}` : "—"} />
        <Line label="Cash" value={pos ? `$${pos.cash_quote.toFixed(2)}` : "—"} />
        <Line
          label="Realized P&L"
          value={pos ? `${pos.realized_pnl >= 0 ? "+" : ""}$${pos.realized_pnl.toFixed(2)}` : "—"}
          color={pos ? pnlColor(pos.realized_pnl) : undefined}
        />
        {agent.unrealized_pnl != null && (
          <Line
            label="Unrealized P&L"
            value={`${agent.unrealized_pnl >= 0 ? "+" : ""}$${agent.unrealized_pnl.toFixed(2)}`}
            color={pnlColor(agent.unrealized_pnl)}
          />
        )}
        {agent.equity != null && <Line label="Equity" value={`$${agent.equity.toFixed(2)}`} />}
      </Card>

      {equity.length >= 2 && (
        <Card>
          <Text style={{ color: colors.text, fontWeight: "700", marginBottom: spacing.sm }}>Equity curve</Text>
          <View onLayout={(e) => setChartW(e.nativeEvent.layout.width)}>
            <LineChart values={equity.map((p) => p.equity)} width={chartW} height={120} />
          </View>
        </Card>
      )}

      {/* Controls */}
      <Card>
        <View style={{ flexDirection: "row", gap: spacing.md }}>
          <View style={{ flex: 1 }}>
            {running ? (
              <Button title="Stop" variant="secondary" loading={busy} onPress={() => act(() => api.stopAgent(agentId))} />
            ) : (
              <Button title="Start" loading={busy} onPress={() => act(() => api.startAgent(agentId))} />
            )}
          </View>
          <View style={{ flex: 1 }}>
            <Button title="Run once" variant="secondary" loading={busy} onPress={() => act(() => api.runAgent(agentId))} />
          </View>
        </View>
        <View style={{ height: spacing.md }} />
        <Button
          title="Save as new agent"
          variant="secondary"
          onPress={() => {
            const cfg: any = agent.strategy_config || {};
            const prefill = {
              name: `${agent.name} (copy)`,
              exchange: agent.exchange,
              symbol: agent.symbol,
              timeframe: agent.timeframe,
              strategyType: agent.strategy_type,
              // Raw configs so single-method strategies and risk overlays copy too.
              strategy_config: cfg,
              risk_config: agent.risk_config || {},
              useRsi: cfg.use_rsi ?? true,
              useMacd: cfg.use_macd ?? true,
              useMaCross: cfg.use_ma_cross ?? true,
              maFast: String(cfg.ma_fast ?? 20),
              maSlow: String(cfg.ma_slow ?? 50),
              guidance: cfg.guidance ?? "",
              // Copies default to paper so a duplicate never trades real money by surprise.
              tradeMode: "paper",
              orderSize: String(agent.order_size_quote),
              interval: String(agent.interval_seconds),
              paperBalance: String(agent.paper_balance_quote),
              accountId: agent.account_id,
            };
            router.push({ pathname: "/agent/new", params: { prefill: JSON.stringify(prefill) } });
          }}
        />
        <Text style={{ color: colors.textDim, fontSize: 12, marginTop: spacing.xs }}>
          Opens the new-agent form pre-filled with this agent's settings (as a fresh paper agent).
        </Text>
        <View style={{ height: spacing.md }} />
        <Button
          title="Delete agent"
          variant="danger"
          onPress={() =>
            confirm("Delete this agent and all its history?", () =>
              act(async () => {
                await api.deleteAgent(agentId);
                router.back();
              })
            )
          }
        />
      </Card>

      {/* Recent signals */}
      <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginVertical: spacing.md }}>
        Recent signals
      </Text>
      {agent.recent_signals.length > 0 && (
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 4, marginBottom: spacing.md }}>
          {[...agent.recent_signals].reverse().map((s) => (
            <View
              key={`hs-${s.id}`}
              style={{
                width: 14,
                height: 14,
                borderRadius: 3,
                backgroundColor:
                  s.action === "buy" ? colors.green : s.action === "sell" ? colors.red : colors.surfaceAlt,
              }}
            />
          ))}
        </View>
      )}
      {agent.recent_signals.length === 0 ? (
        <Text style={{ color: colors.textDim }}>No evaluations yet. Try “Run once”.</Text>
      ) : (
        agent.recent_signals.map((s) => (
          <Card key={s.id}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Badge
                label={s.action}
                color={s.action === "buy" ? colors.green : s.action === "sell" ? colors.red : colors.textDim}
              />
              <Text style={{ color: colors.textDim }}>{new Date(s.created_at).toLocaleString()}</Text>
            </View>
            <Text style={{ color: colors.text, marginTop: spacing.sm }}>{s.rationale}</Text>
            <Text style={{ color: colors.textDim, marginTop: spacing.xs, fontSize: 12 }}>
              @ ${s.price.toFixed(2)} · confidence {(s.confidence * 100).toFixed(0)}%
            </Text>
          </Card>
        ))
      )}

      {/* Recent trades */}
      <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginVertical: spacing.md }}>
        Recent trades
      </Text>
      {agent.recent_trades.length === 0 ? (
        <Text style={{ color: colors.textDim }}>No trades yet.</Text>
      ) : (
        agent.recent_trades.map((t) => (
          <Card key={t.id}>
            <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
              <Badge label={t.side} color={t.side === "buy" ? colors.green : colors.red} />
              <Text style={{ color: colors.textDim }}>{new Date(t.created_at).toLocaleString()}</Text>
            </View>
            <Text style={{ color: colors.text, marginTop: spacing.sm }}>
              {t.quantity.toFixed(6)} @ ${t.price.toFixed(2)} = ${t.cost_quote.toFixed(2)}
            </Text>
            {t.note ? <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2 }}>{t.note}</Text> : null}
          </Card>
        ))
      )}
      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

function Line({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", marginBottom: spacing.sm }}>
      <Text style={{ color: colors.textDim }}>{label}</Text>
      <Text style={{ color: color ?? colors.text, fontWeight: "600" }}>{value}</Text>
    </View>
  );
}
