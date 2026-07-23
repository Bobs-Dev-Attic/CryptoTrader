import { useFocusEffect, useRouter } from "expo-router";
import React, { useCallback, useRef, useState } from "react";
import { Platform, Pressable, RefreshControl, ScrollView, Text, View } from "react-native";

import { api, VolRow } from "@/api";
import { Card } from "@/components";
import { colors, pnlColor, radius, spacing } from "@/theme";

const EXCHANGES = ["kraken", "binance", "coinbase"];
const METRICS = [
  { key: "range_24h", label: "Range 24h", unit: "%" },
  { key: "change_24h", label: "Move 24h", unit: "%" },
  { key: "ret_vol", label: "Return vol", unit: "%" },
  { key: "atr_pct", label: "ATR", unit: "%" },
  { key: "volume", label: "Volume", unit: "$" },
];

function abbrev(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e9) return (n / 1e9).toFixed(1) + "B";
  if (a >= 1e6) return (n / 1e6).toFixed(1) + "M";
  if (a >= 1e3) return (n / 1e3).toFixed(1) + "k";
  return n.toFixed(0);
}

function metricValue(row: VolRow, metric: string): number | null {
  return (row as any)[metric] ?? null;
}
function fmtMetric(row: VolRow, metric: string): string {
  const v = metricValue(row, metric);
  if (v == null) return "—";
  if (metric === "volume") return "$" + abbrev(v);
  return `${v >= 0 ? "" : ""}${v.toFixed(1)}%`;
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
    <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.sm }}>
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

export default function Movers() {
  const router = useRouter();
  const [exchange, setExchange] = useState("kraken");
  const [metric, setMetric] = useState("range_24h");
  const [rows, setRows] = useState<VolRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [msg, setMsg] = useState("");
  const timer = useRef<any>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.volatility(exchange, metric, 25);
      setRows(data.rows);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [exchange, metric]);

  // Reload on focus + when exchange/metric change, and auto-refresh every 30s.
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

  const metricMeta = METRICS.find((m) => m.key === metric)!;

  const makeAgent = (row: VolRow) => {
    router.push({
      pathname: "/agent/new",
      params: { prefill: JSON.stringify({ symbol: row.symbol, exchange }) },
    });
  };

  const watch = async (row: VolRow) => {
    const cur = metricValue(row, metric) ?? 5;
    const suggested = metric === "volume" ? Math.round(cur) : Math.max(1, Math.ceil(cur));
    let threshold = suggested;
    if (Platform.OS === "web") {
      // eslint-disable-next-line no-alert
      const input = window.prompt(
        `Alert when ${metricMeta.label} for ${row.base} reaches (${metricMeta.unit}):`,
        String(suggested)
      );
      if (input == null) return;
      const n = Number(input);
      if (!isFinite(n)) return;
      threshold = n;
    }
    try {
      await api.createWatch({ exchange, symbol: row.symbol, metric, threshold });
      setMsg(`Watching ${row.base} — alerts in Alerts.`);
    } catch (e: any) {
      setMsg(e?.message ?? "Could not create alert");
    }
  };

  return (
    <ScrollView
      style={{ backgroundColor: colors.bg }}
      contentContainerStyle={{ padding: spacing.lg }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary} />}
    >
      <Text style={{ color: colors.textDim, marginBottom: spacing.md, fontSize: 13 }}>
        The most volatile coins from a curated list, refreshed automatically. Tap ＋ to build an agent
        for one, or 👁 to get an alert when it crosses a level.
      </Text>

      <Chips options={EXCHANGES.map((e) => ({ key: e, label: e.toUpperCase() }))} value={exchange} onChange={setExchange} />
      <Chips options={METRICS.map((m) => ({ key: m.key, label: m.label }))} value={metric} onChange={setMetric} />

      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm }}>
        <Text style={{ color: colors.textDim, fontSize: 12 }}>
          Ranked by {metricMeta.label}
          {loading ? " · updating…" : ""}
        </Text>
        <Pressable onPress={() => router.push("/alerts")}>
          <Text style={{ color: colors.primary, fontSize: 13, fontWeight: "600" }}>Alerts →</Text>
        </Pressable>
      </View>

      {msg ? <Text style={{ color: colors.green, marginBottom: spacing.sm, fontSize: 12 }}>{msg}</Text> : null}

      {rows.length === 0 && !loading ? (
        <Text style={{ color: colors.textDim, textAlign: "center", marginTop: spacing.xl }}>
          Couldn't load market data. Pull to refresh.
        </Text>
      ) : (
        rows.map((row, i) => {
          const v = metricValue(row, metric);
          const signed = metric === "change_24h" && v != null;
          return (
            <Card key={row.symbol}>
              <View style={{ flexDirection: "row", alignItems: "center" }}>
                <Text style={{ color: colors.textDim, width: 26, fontSize: 13 }}>{i + 1}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700" }}>{row.base}</Text>
                  <Text style={{ color: colors.textDim, fontSize: 12 }}>
                    {row.last != null ? `$${row.last < 1 ? row.last.toFixed(5) : row.last.toFixed(2)}` : "—"}
                  </Text>
                </View>
                <Text
                  style={{
                    color: signed ? pnlColor(v as number) : colors.text,
                    fontSize: 18,
                    fontWeight: "800",
                    marginRight: spacing.md,
                  }}
                >
                  {fmtMetric(row, metric)}
                </Text>
                <View style={{ flexDirection: "row", gap: spacing.sm }}>
                  <MiniAction label="＋ Agent" onPress={() => makeAgent(row)} />
                  <MiniAction label="👁 Watch" onPress={() => watch(row)} />
                </View>
              </View>
            </Card>
          );
        })
      )}
      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}

function MiniAction({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => ({
        paddingHorizontal: spacing.sm,
        paddingVertical: spacing.xs,
        borderRadius: radius.sm,
        borderWidth: 1,
        borderColor: colors.border,
        backgroundColor: colors.surfaceAlt,
        opacity: pressed ? 0.7 : 1,
      })}
    >
      <Text style={{ color: colors.text, fontSize: 12, fontWeight: "600" }}>{label}</Text>
    </Pressable>
  );
}
