import { useFocusEffect } from "expo-router";
import React, { useCallback, useRef, useState } from "react";
import { Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { api, Watch } from "@/api";
import { Badge, Button, Card, Field } from "@/components";
import { colors, radius, spacing, screenContent } from "@/theme";

const EXCHANGES = ["kraken", "binance", "coinbase"];
const METRICS = [
  { key: "range_24h", label: "Range 24h", unit: "%" },
  { key: "change_24h", label: "Move 24h", unit: "%" },
  { key: "ret_vol", label: "Return vol", unit: "%" },
  { key: "atr_pct", label: "ATR", unit: "%" },
  { key: "volume", label: "Volume", unit: "$" },
];
const metricLabel = (k: string) => METRICS.find((m) => m.key === k)?.label ?? k;
const isPct = (k: string) => k !== "volume";

function fmt(v: number | null, metric: string): string {
  if (v == null) return "—";
  return isPct(metric) ? `${v.toFixed(1)}%` : `$${v >= 1e6 ? (v / 1e6).toFixed(1) + "M" : v.toFixed(0)}`;
}

function Chips({
  options,
  value,
  onChange,
}: {
  options: { key: string; label: string }[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md }}>
      {options.map((o) => (
        <Pressable
          key={o.key}
          onPress={() => onChange(o.key)}
          style={{
            paddingHorizontal: spacing.md,
            paddingVertical: spacing.xs,
            borderRadius: radius.sm,
            borderWidth: 1,
            borderColor: value === o.key ? colors.primary : colors.border,
            backgroundColor: value === o.key ? colors.primaryDim : colors.surfaceAlt,
          }}
        >
          <Text style={{ color: colors.text, fontSize: 13 }}>{o.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

export default function Alerts() {
  const [watches, setWatches] = useState<Watch[]>([]);
  const [refreshing, setRefreshing] = useState(false);
  const timer = useRef<any>(null);

  // Add-form state
  const [exchange, setExchange] = useState("kraken");
  const [symbol, setSymbol] = useState("BTC/USD");
  const [metric, setMetric] = useState("range_24h");
  const [threshold, setThreshold] = useState("5");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setWatches(await api.listWatches());
    } catch {
      /* ignore */
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
      timer.current = setInterval(load, 30_000);
      return () => timer.current && clearInterval(timer.current);
    }, [load])
  );

  const onRefresh = async () => {
    setRefreshing(true);
    await load();
    setRefreshing(false);
  };

  const add = async () => {
    setError("");
    const t = Number(threshold);
    if (!symbol.trim() || !isFinite(t)) {
      setError("Enter a symbol and a numeric threshold.");
      return;
    }
    setBusy(true);
    try {
      await api.createWatch({ exchange, symbol: symbol.trim().toUpperCase(), metric, threshold: t });
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Could not create alert");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    try {
      await api.deleteWatch(id);
      await load();
    } catch {
      /* ignore */
    }
  };

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={screenContent}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={{ color: colors.textDim, marginBottom: spacing.md, fontSize: 13 }}>
        Volatility alerts. Each is checked about once a minute; when a coin's metric crosses your
        threshold it's flagged <Text style={{ color: colors.yellow, fontWeight: "700" }}>TRIGGERED</Text> here.
      </Text>

      {/* Existing watches */}
      {watches.length === 0 ? (
        <Text style={{ color: colors.textDim, marginBottom: spacing.lg }}>
          No alerts yet. Add one below, or use 👁 Watch on the Volatile markets screen.
        </Text>
      ) : (
        watches.map((w) => (
          <Card key={w.id}>
            <View style={{ flexDirection: "row", alignItems: "center" }}>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", gap: spacing.sm }}>
                  <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700" }}>{w.symbol}</Text>
                  {w.triggered ? <Badge label="triggered" color={colors.yellow} /> : null}
                </View>
                <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2 }}>
                  {w.exchange.toUpperCase()} · {metricLabel(w.metric)} ≥ {fmt(w.threshold, w.metric)}
                </Text>
                <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2 }}>
                  Now: <Text style={{ color: w.triggered ? colors.yellow : colors.text }}>{fmt(w.last_value, w.metric)}</Text>
                  {w.last_triggered_at
                    ? ` · last hit ${new Date(w.last_triggered_at).toLocaleString()}`
                    : ""}
                </Text>
              </View>
              <Pressable
                onPress={() => remove(w.id)}
                style={{
                  paddingHorizontal: spacing.md,
                  paddingVertical: spacing.sm,
                  borderRadius: radius.sm,
                  borderWidth: 1,
                  borderColor: colors.red,
                  backgroundColor: colors.surfaceAlt,
                }}
              >
                <Text style={{ color: colors.red, fontWeight: "600", fontSize: 13 }}>Delete</Text>
              </Pressable>
            </View>
          </Card>
        ))
      )}

      {/* Add form */}
      <View style={{ height: spacing.md }} />
      <Card>
        <Text style={{ color: colors.text, fontWeight: "700", fontSize: 16, marginBottom: spacing.md }}>
          Add an alert
        </Text>
        <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: spacing.xs }}>Exchange</Text>
        <Chips options={EXCHANGES.map((e) => ({ key: e, label: e.toUpperCase() }))} value={exchange} onChange={setExchange} />
        <Field label="Symbol" value={symbol} onChangeText={setSymbol} autoCapitalize="characters" placeholder="BTC/USD" />
        <Text style={{ color: colors.textDim, fontSize: 12, marginBottom: spacing.xs }}>Metric</Text>
        <Chips options={METRICS.map((m) => ({ key: m.key, label: m.label }))} value={metric} onChange={setMetric} />
        <Field
          label={`Threshold (${isPct(metric) ? "%" : "$"})`}
          value={threshold}
          onChangeText={setThreshold}
          keyboardType="numeric"
          help="You'll be alerted when the metric is at or above this value."
        />
        {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}
        <Button title="Add alert" onPress={add} loading={busy} />
      </Card>
      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}
