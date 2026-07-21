import { useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, Switch, Text, View } from "react-native";

import { api, ExchangeAccount, ExchangeMeta, StrategyMeta } from "@/api";
import { Button, Card, Field } from "@/components";
import { colors, radius, spacing } from "@/theme";

/** A pill-style single-select control. */
function Pills<T extends string>({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (v: T) => void;
}) {
  return (
    <View style={{ marginBottom: spacing.md }}>
      <Text style={{ color: colors.textDim, fontSize: 13, marginBottom: spacing.xs }}>{label}</Text>
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm }}>
        {options.map((o) => (
          <Pressable
            key={o.value}
            onPress={() => onChange(o.value)}
            style={{
              paddingHorizontal: spacing.md,
              paddingVertical: spacing.sm,
              borderRadius: radius.sm,
              borderWidth: 1,
              borderColor: value === o.value ? colors.primary : colors.border,
              backgroundColor: value === o.value ? colors.primaryDim : colors.surfaceAlt,
            }}
          >
            <Text style={{ color: colors.text }}>{o.label}</Text>
          </Pressable>
        ))}
      </View>
    </View>
  );
}

function Toggle({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: spacing.sm }}>
      <Text style={{ color: colors.text }}>{label}</Text>
      <Switch value={value} onValueChange={onChange} trackColor={{ true: colors.primary }} />
    </View>
  );
}

export default function NewAgent() {
  const router = useRouter();
  const [exchanges, setExchanges] = useState<ExchangeMeta[]>([]);
  const [strategies, setStrategies] = useState<StrategyMeta[]>([]);
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);

  const [name, setName] = useState("My BTC agent");
  const [exchange, setExchange] = useState("kraken");
  const [symbol, setSymbol] = useState("BTC/USD");
  const [timeframe, setTimeframe] = useState("1h");
  const [strategyType, setStrategyType] = useState<"rule_based" | "llm">("rule_based");
  const [tradeMode, setTradeMode] = useState<"paper" | "live">("paper");
  const [orderSize, setOrderSize] = useState("100");
  const [paperBalance, setPaperBalance] = useState("10000");
  const [interval, setIntervalSec] = useState("300");
  const [accountId, setAccountId] = useState<number | null>(null);

  // Rule-based config
  const [useRsi, setUseRsi] = useState(true);
  const [useMacd, setUseMacd] = useState(true);
  const [useMaCross, setUseMaCross] = useState(true);
  const [maFast, setMaFast] = useState("20");
  const [maSlow, setMaSlow] = useState("50");
  // LLM config
  const [guidance, setGuidance] = useState("");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [ex, st, acc] = await Promise.all([api.exchanges(), api.strategies(), api.listAccounts()]);
        setExchanges(ex);
        setStrategies(st);
        setAccounts(acc);
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const strategyConfig = () =>
    strategyType === "rule_based"
      ? {
          use_rsi: useRsi,
          use_macd: useMacd,
          use_ma_cross: useMaCross,
          ma_fast: Number(maFast) || 20,
          ma_slow: Number(maSlow) || 50,
        }
      : { guidance };

  const matchingAccounts = accounts.filter((a) => a.exchange === exchange);

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      await api.createAgent({
        name,
        exchange,
        symbol: symbol.trim().toUpperCase(),
        timeframe,
        strategy_type: strategyType,
        strategy_config: strategyConfig(),
        trade_mode: tradeMode,
        order_size_quote: Number(orderSize) || 100,
        paper_balance_quote: Number(paperBalance) || 10000,
        interval_seconds: Number(interval) || 300,
        account_id: tradeMode === "live" ? accountId : null,
      } as any);
      router.back();
    } catch (e: any) {
      setError(e?.message ?? "Failed to create agent");
    } finally {
      setBusy(false);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
      <Card>
        <Field label="Name" value={name} onChangeText={setName} />
        <Pills
          label="Exchange"
          value={exchange}
          onChange={setExchange}
          options={exchanges.map((e) => ({ value: e.id, label: e.name }))}
        />
        <Field label="Symbol" value={symbol} onChangeText={setSymbol} autoCapitalize="characters" placeholder="BTC/USD" />
        <Pills
          label="Timeframe"
          value={timeframe}
          onChange={setTimeframe}
          options={[
            { value: "15m", label: "15m" },
            { value: "1h", label: "1h" },
            { value: "4h", label: "4h" },
            { value: "1d", label: "1d" },
          ]}
        />
      </Card>

      <Card>
        <Pills
          label="Strategy"
          value={strategyType}
          onChange={setStrategyType}
          options={strategies.map((s) => ({ value: s.type as any, label: s.name }))}
        />
        {strategyType === "rule_based" ? (
          <View>
            <Toggle label="RSI mean-reversion" value={useRsi} onChange={setUseRsi} />
            <Toggle label="MACD crossover" value={useMacd} onChange={setUseMacd} />
            <Toggle label="MA crossover" value={useMaCross} onChange={setUseMaCross} />
            {useMaCross && (
              <View style={{ flexDirection: "row", gap: spacing.md }}>
                <View style={{ flex: 1 }}>
                  <Field label="Fast MA" value={maFast} onChangeText={setMaFast} keyboardType="numeric" />
                </View>
                <View style={{ flex: 1 }}>
                  <Field label="Slow MA" value={maSlow} onChangeText={setMaSlow} keyboardType="numeric" />
                </View>
              </View>
            )}
          </View>
        ) : (
          <Field
            label="LLM guidance (optional)"
            value={guidance}
            onChangeText={setGuidance}
            placeholder="e.g. Be conservative; avoid trading in high volatility."
            multiline
          />
        )}
      </Card>

      <Card>
        <Pills
          label="Trade mode"
          value={tradeMode}
          onChange={setTradeMode}
          options={[
            { value: "paper", label: "Paper (simulated)" },
            { value: "live", label: "Live (real money)" },
          ]}
        />
        {tradeMode === "live" && (
          <>
            <Text style={{ color: colors.yellow, marginBottom: spacing.md }}>
              ⚠ Live mode executes real orders. Link a keyed account for {exchange.toUpperCase()}.
            </Text>
            <Pills
              label="Account"
              value={accountId ? String(accountId) : ""}
              onChange={(v) => setAccountId(Number(v))}
              options={matchingAccounts.map((a) => ({ value: String(a.id), label: a.label }))}
            />
            {matchingAccounts.length === 0 && (
              <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
                No {exchange.toUpperCase()} account linked. Add one under Exchanges.
              </Text>
            )}
          </>
        )}
        <View style={{ flexDirection: "row", gap: spacing.md }}>
          <View style={{ flex: 1 }}>
            <Field label="Order size (quote)" value={orderSize} onChangeText={setOrderSize} keyboardType="numeric" />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Interval (sec)" value={interval} onChangeText={setIntervalSec} keyboardType="numeric" />
          </View>
        </View>
        {tradeMode === "paper" && (
          <Field label="Paper balance (quote)" value={paperBalance} onChangeText={setPaperBalance} keyboardType="numeric" />
        )}
      </Card>

      {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}
      <Button title="Create agent" onPress={submit} loading={busy} />
      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}
