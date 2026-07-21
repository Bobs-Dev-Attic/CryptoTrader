/** A horizontal auto-scrolling price ticker (marquee) for the dashboard. */
import React, { useEffect, useRef, useState } from "react";
import { Animated, Easing, Platform, Text, View } from "react-native";

import { api, TickerQuote } from "./api";
import { colors, pnlColor, radius, spacing } from "./theme";

function fmtPrice(n: number): string {
  if (n >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (n >= 1) return n.toFixed(2);
  return n.toFixed(4);
}

export function PriceTicker({
  exchange = "kraken",
  symbols,
}: {
  exchange?: string;
  symbols: string[];
}) {
  const [quotes, setQuotes] = useState<TickerQuote[]>([]);
  const translateX = useRef(new Animated.Value(0)).current;
  const [rowWidth, setRowWidth] = useState(0);
  const key = symbols.join(",");

  // Fetch + refresh prices every 30s.
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const q = await api.tickers(exchange, symbols);
        if (alive) setQuotes(q.filter((t) => t.last > 0));
      } catch {
        /* leave last-known quotes */
      }
    };
    load();
    const id = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [exchange, key]);

  // Loop the marquee once we know one row's width.
  useEffect(() => {
    if (rowWidth <= 0) return;
    translateX.setValue(0);
    const anim = Animated.loop(
      Animated.timing(translateX, {
        toValue: -rowWidth,
        duration: Math.max(rowWidth * 25, 8000),
        easing: Easing.linear,
        useNativeDriver: Platform.OS !== "web",
      })
    );
    anim.start();
    return () => anim.stop();
  }, [rowWidth, translateX]);

  if (quotes.length === 0) return null;

  const Row = ({ measure }: { measure?: boolean }) => (
    <View
      style={{ flexDirection: "row" }}
      onLayout={measure ? (e) => setRowWidth(e.nativeEvent.layout.width) : undefined}
    >
      {quotes.map((t, i) => (
        <View
          key={(measure ? "a" : "b") + t.symbol + i}
          style={{ flexDirection: "row", alignItems: "center", paddingHorizontal: spacing.md }}
        >
          <Text style={{ color: colors.text, fontWeight: "700", fontSize: 13 }}>{t.symbol}</Text>
          <Text style={{ color: colors.textDim, fontSize: 13, marginLeft: 6 }}>
            ${fmtPrice(t.last)}
          </Text>
          {t.change_pct != null ? (
            <Text style={{ color: pnlColor(t.change_pct), fontSize: 12, marginLeft: 6 }}>
              {t.change_pct >= 0 ? "▲" : "▼"} {Math.abs(t.change_pct).toFixed(2)}%
            </Text>
          ) : null}
        </View>
      ))}
    </View>
  );

  return (
    <View
      style={{
        height: 34,
        overflow: "hidden",
        justifyContent: "center",
        backgroundColor: colors.surface,
        borderRadius: radius.sm,
        borderWidth: 1,
        borderColor: colors.border,
        marginBottom: spacing.md,
      }}
    >
      <Animated.View style={{ flexDirection: "row", transform: [{ translateX }] }}>
        <Row measure />
        <Row />
      </Animated.View>
    </View>
  );
}
