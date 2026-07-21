import { useLocalSearchParams, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Pressable, ScrollView, Switch, Text, View } from "react-native";

import { api, ExchangeAccount, ExchangeMeta, StrategyMeta } from "@/api";
import { Button, Card, Field, HelpNote, InfoLabel } from "@/components";
import { colors, radius, spacing } from "@/theme";

type PillOption<T> = { value: T; label: string; help?: string };

/** A pill-style single-select control. Shows the selected option's help below. */
function Pills<T extends string>({
  label,
  help,
  value,
  options,
  onChange,
}: {
  label: string;
  help?: string;
  value: T;
  options: PillOption<T>[];
  onChange: (v: T) => void;
}) {
  const selected = options.find((o) => o.value === value);
  return (
    <View style={{ marginBottom: spacing.md }}>
      <InfoLabel label={label} help={help} />
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.xs }}>
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
      {selected?.help ? (
        <Text style={{ color: colors.textDim, fontSize: 12, lineHeight: 17, marginTop: spacing.xs }}>
          {selected.help}
        </Text>
      ) : null}
    </View>
  );
}

function Toggle({
  label,
  help,
  value,
  onChange,
}: {
  label: string;
  help?: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <View style={{ marginBottom: spacing.sm }}>
      <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start" }}>
        <View style={{ flex: 1, paddingRight: spacing.md }}>
          <InfoLabel label={label} help={help} />
        </View>
        <Switch value={value} onValueChange={onChange} trackColor={{ true: colors.primary }} />
      </View>
    </View>
  );
}

/** Plain-language help strings for the New Agent form. */
const HELP = {
  name: "A label for you to recognize this agent — e.g. 'BTC swing bot'. It has no effect on trading.",
  exchange:
    "The crypto marketplace this agent watches for prices. In live mode, real orders are placed here (Robinhood is paper-only in this build).",
  symbol:
    "The trading pair to trade. 'BTC/USD' means Bitcoin priced in US dollars; 'ETH/USDT' means Ethereum priced in the USDT stablecoin. The part after the slash is the 'quote' currency you spend.",
  timeframe:
    "How much time each price bar (candle) covers. Shorter bars (15m) react faster but are noisier; longer bars (1d) are slower but steadier.",
  strategy:
    "The logic the agent uses to decide when to buy or sell. Choose one below — tap ⓘ on each option to learn more.",
  strategyRule:
    "Uses classic math indicators on the price chart to make decisions. Predictable, free, and needs no AI. A good place to start.",
  strategyLlm:
    "Uses Claude AI to weigh the market like a human analyst would. More flexible and can follow plain-English guidance, but needs an AI key and each decision costs a little.",
  rsi:
    "RSI (Relative Strength Index) measures whether a coin has recently jumped a lot ('overbought') or dropped a lot ('oversold'). This rule leans buy when oversold and sell when overbought — betting the price snaps back.",
  macd:
    "MACD spots shifts in momentum. It leans buy when momentum turns upward and sell when it turns downward.",
  maCross:
    "Compares a fast and a slow moving average (the average price over N recent candles). Buy when the fast average crosses above the slow one (an uptrend forming) and sell when it crosses below.",
  maFast:
    "How many candles the FAST moving average covers. Smaller reacts quicker to price changes. Typical: 20. Must be smaller than the slow value.",
  maSlow:
    "How many candles the SLOW moving average covers. Larger is steadier and filters out noise. Typical: 50.",
  guidance:
    "Optional plain-English instructions for the AI, e.g. 'be cautious when the market is volatile' or 'favor long-term trends over quick moves'. Leave blank for a balanced default.",
  tradeMode:
    "Whether trades are simulated or real. Start with Paper until you trust the agent.",
  paper:
    "Simulated trading with pretend money and real live prices. Nothing real is bought or sold — the safe way to test a strategy.",
  live:
    "Places REAL orders with REAL money using your linked exchange API keys. Only use once you've tested in paper mode and understand the risk.",
  account: "Which of your linked exchange keys this agent trades with in live mode.",
  orderSize:
    "How much to spend on each BUY, in the quote currency (the part after the slash in the symbol). E.g. 100 on BTC/USD means $100 per buy.",
  interval:
    "How often the agent checks the market and may trade, in seconds. 300 = every 5 minutes. Minimum is 30 seconds.",
  paperBalance:
    "The starting pretend cash for this paper agent, in the quote currency. Its profit/loss is measured against this.",
};

type PresetValues = {
  name: string;
  exchange: string;
  symbol: string;
  timeframe: string;
  strategyType: "rule_based" | "llm";
  useRsi: boolean;
  useMacd: boolean;
  useMaCross: boolean;
  maFast: string;
  maSlow: string;
  guidance: string;
  tradeMode: "paper" | "live";
  orderSize: string;
  interval: string;
  paperBalance: string;
};

type Preset = { key: string; emoji: string; title: string; description: string; values: PresetValues };

const BASE: PresetValues = {
  name: "",
  exchange: "kraken",
  symbol: "BTC/USD",
  timeframe: "1h",
  strategyType: "rule_based",
  useRsi: true,
  useMacd: true,
  useMaCross: true,
  maFast: "20",
  maSlow: "50",
  guidance: "",
  tradeMode: "paper",
  orderSize: "100",
  interval: "300",
  paperBalance: "10000",
};

/** Ready-made starting points a beginner can tweak. All paper by default. */
const PRESETS: Preset[] = [
  {
    key: "btc-starter",
    emoji: "🟠",
    title: "Bitcoin starter",
    description:
      "A balanced first bot. Buys or sells BTC only when RSI, MACD and the trend all agree — fewer, higher-conviction trades.",
    values: { ...BASE, name: "Bitcoin starter", exchange: "kraken", symbol: "BTC/USD", timeframe: "1h" },
  },
  {
    key: "eth-trend",
    emoji: "🔷",
    title: "Ethereum trend-follower",
    description:
      "Rides medium-term Ethereum trends on the 4-hour chart using MACD + moving-average crossover; ignores short-term noise (RSI off).",
    values: {
      ...BASE,
      name: "Ethereum trend-follower",
      exchange: "binance",
      symbol: "ETH/USDT",
      timeframe: "4h",
      useRsi: false,
      useMacd: true,
      useMaCross: true,
    },
  },
  {
    key: "dip-buyer",
    emoji: "🟢",
    title: "Dip buyer",
    description:
      "Waits for oversold dips and buys the bounce, then sells when overbought. Uses RSI only for a simpler, contrarian style.",
    values: {
      ...BASE,
      name: "Dip buyer",
      exchange: "coinbase",
      symbol: "BTC/USD",
      timeframe: "1h",
      useRsi: true,
      useMacd: false,
      useMaCross: false,
    },
  },
  {
    key: "ai-analyst",
    emoji: "🤖",
    title: "AI analyst (Claude)",
    description:
      "Lets Claude weigh the market like a cautious analyst. Needs an AI key configured on the server; without one it just holds.",
    values: {
      ...BASE,
      name: "AI analyst",
      exchange: "kraken",
      symbol: "BTC/USD",
      timeframe: "1h",
      strategyType: "llm",
      guidance:
        "Prioritize capital preservation. Avoid trading in high volatility and only act on strong, confirmed signals.",
    },
  },
];

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
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const params = useLocalSearchParams<{ prefill?: string }>();

  const applyValues = (v: PresetValues) => {
    setName(v.name);
    setExchange(v.exchange);
    setSymbol(v.symbol);
    setTimeframe(v.timeframe);
    setStrategyType(v.strategyType);
    setUseRsi(v.useRsi);
    setUseMacd(v.useMacd);
    setUseMaCross(v.useMaCross);
    setMaFast(v.maFast);
    setMaSlow(v.maSlow);
    setGuidance(v.guidance);
    setTradeMode(v.tradeMode);
    setOrderSize(v.orderSize);
    setIntervalSec(v.interval);
    setPaperBalance(v.paperBalance);
  };

  const applyPreset = (p: Preset) => {
    applyValues(p.values);
    setActivePreset(p.key);
  };

  // "Save As" from an existing agent passes a prefill payload; apply it once.
  useEffect(() => {
    if (!params.prefill) return;
    try {
      const parsed = JSON.parse(params.prefill);
      applyValues({ ...BASE, ...parsed });
    } catch {
      /* ignore malformed prefill */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params.prefill]);

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
      <HelpNote>
        An <Text style={{ fontWeight: "700" }}>agent</Text> is an automated bot that watches one market
        and follows a strategy you choose to decide when to buy and sell. New agents trade in{" "}
        <Text style={{ fontWeight: "700" }}>paper (simulated) mode</Text> by default, so you can try
        ideas with zero risk. Tap the ⓘ next to any option for a plain-language explanation.
      </HelpNote>

      {/* Example presets — a beginner can start here and tweak. */}
      <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: spacing.xs }}>
        Start from an example
      </Text>
      <Text style={{ color: colors.textDim, fontSize: 13, marginBottom: spacing.md }}>
        Tap one to fill in the form, then adjust anything you like.
      </Text>
      {PRESETS.map((p) => {
        const active = activePreset === p.key;
        return (
          <Pressable key={p.key} onPress={() => applyPreset(p)}>
            <View
              style={{
                flexDirection: "row",
                backgroundColor: colors.surface,
                borderRadius: radius.md,
                borderWidth: 1,
                borderColor: active ? colors.primary : colors.border,
                padding: spacing.md,
                marginBottom: spacing.sm,
              }}
            >
              <Text style={{ fontSize: 22, marginRight: spacing.md }}>{p.emoji}</Text>
              <View style={{ flex: 1 }}>
                <View style={{ flexDirection: "row", alignItems: "center", justifyContent: "space-between" }}>
                  <Text style={{ color: colors.text, fontSize: 15, fontWeight: "600" }}>{p.title}</Text>
                  {active ? (
                    <Text style={{ color: colors.primary, fontSize: 12, fontWeight: "700" }}>✓ applied</Text>
                  ) : null}
                </View>
                <Text style={{ color: colors.textDim, fontSize: 12, lineHeight: 17, marginTop: 2 }}>
                  {p.description}
                </Text>
              </View>
            </View>
          </Pressable>
        );
      })}

      <View style={{ height: spacing.md }} />
      <Text style={{ color: colors.textDim, fontSize: 13, marginBottom: spacing.sm }}>
        …or configure everything yourself below.
      </Text>

      <Card>
        <Field label="Name" value={name} onChangeText={setName} help={HELP.name} />
        <Pills
          label="Exchange"
          help={HELP.exchange}
          value={exchange}
          onChange={setExchange}
          options={exchanges.map((e) => ({ value: e.id, label: e.name }))}
        />
        <Field
          label="Symbol"
          value={symbol}
          onChangeText={setSymbol}
          autoCapitalize="characters"
          placeholder="BTC/USD"
          help={HELP.symbol}
        />
        <Pills
          label="Timeframe"
          help={HELP.timeframe}
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
          help={HELP.strategy}
          value={strategyType}
          onChange={setStrategyType}
          options={strategies.map((s) => ({
            value: s.type as any,
            label: s.name,
            help: s.type === "llm" ? HELP.strategyLlm : HELP.strategyRule,
          }))}
        />
        {strategyType === "rule_based" ? (
          <View>
            <HelpNote>
              This strategy runs the indicators you switch on below. Each one casts a buy/sell vote on
              every check, and the majority decides the action — so turning on more indicators means an
              agent that only acts when they agree. All three are on by default.
            </HelpNote>
            <Toggle label="RSI mean-reversion" help={HELP.rsi} value={useRsi} onChange={setUseRsi} />
            <Toggle label="MACD crossover" help={HELP.macd} value={useMacd} onChange={setUseMacd} />
            <Toggle label="MA crossover" help={HELP.maCross} value={useMaCross} onChange={setUseMaCross} />
            {useMaCross && (
              <View style={{ flexDirection: "row", gap: spacing.md, marginTop: spacing.sm }}>
                <View style={{ flex: 1 }}>
                  <Field
                    label="Fast MA"
                    value={maFast}
                    onChangeText={setMaFast}
                    keyboardType="numeric"
                    help={HELP.maFast}
                  />
                </View>
                <View style={{ flex: 1 }}>
                  <Field
                    label="Slow MA"
                    value={maSlow}
                    onChangeText={setMaSlow}
                    keyboardType="numeric"
                    help={HELP.maSlow}
                  />
                </View>
              </View>
            )}
          </View>
        ) : (
          <View>
            <HelpNote>
              Claude reads a snapshot of the market (recent prices and indicators) plus your guidance,
              then returns a buy / sell / hold decision with its reasoning. Needs an AI key configured on
              the server; without one, the agent simply holds.
            </HelpNote>
            <Field
              label="LLM guidance (optional)"
              value={guidance}
              onChangeText={setGuidance}
              placeholder="e.g. Be conservative; avoid trading in high volatility."
              multiline
              help={HELP.guidance}
            />
          </View>
        )}
      </Card>

      <Card>
        <Pills
          label="Trade mode"
          help={HELP.tradeMode}
          value={tradeMode}
          onChange={setTradeMode}
          options={[
            { value: "paper", label: "Paper (simulated)", help: HELP.paper },
            { value: "live", label: "Live (real money)", help: HELP.live },
          ]}
        />
        {tradeMode === "live" && (
          <>
            <Text style={{ color: colors.yellow, marginBottom: spacing.md }}>
              ⚠ Live mode executes real orders. Link a keyed account for {exchange.toUpperCase()}.
            </Text>
            <Pills
              label="Account"
              help={HELP.account}
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
            <Field
              label="Order size (quote)"
              value={orderSize}
              onChangeText={setOrderSize}
              keyboardType="numeric"
              help={HELP.orderSize}
            />
          </View>
          <View style={{ flex: 1 }}>
            <Field
              label="Interval (sec)"
              value={interval}
              onChangeText={setIntervalSec}
              keyboardType="numeric"
              help={HELP.interval}
            />
          </View>
        </View>
        {tradeMode === "paper" && (
          <Field
            label="Paper balance (quote)"
            value={paperBalance}
            onChangeText={setPaperBalance}
            keyboardType="numeric"
            help={HELP.paperBalance}
          />
        )}
      </Card>

      {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}
      <Button title="Create agent" onPress={submit} loading={busy} />
      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}
