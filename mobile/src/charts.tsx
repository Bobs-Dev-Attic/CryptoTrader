/** Lightweight SVG charts (equity line + allocation donut) for web and mobile. */
import React, { useEffect, useState } from "react";
import { Text, View } from "react-native";
import Svg, { Circle, G, Polyline } from "react-native-svg";

import { api } from "./api";
import { colors, spacing } from "./theme";

/** Palette for donut slices / categorical series. */
export const CHART_COLORS = [
  "#4f7cff",
  "#2ecc71",
  "#f5b942",
  "#ff5c6c",
  "#9b59f6",
  "#22c1c3",
  "#ff8a4c",
  "#57d9a3",
];

/**
 * A line chart of a numeric series with a soft area fill. Green when the series
 * ends up, red when it ends down.
 */
export function LineChart({
  values,
  width,
  height = 120,
}: {
  values: number[];
  width: number;
  height?: number;
}) {
  if (!values || values.length < 2 || width <= 0) {
    return (
      <View style={{ height, alignItems: "center", justifyContent: "center" }}>
        <Text style={{ color: colors.textDim, fontSize: 12 }}>Not enough data yet.</Text>
      </View>
    );
  }
  const pad = 6;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - 2 * pad);
  const y = (v: number) => pad + (1 - (v - min) / range) * (height - 2 * pad);

  const line = values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? colors.green : colors.red;
  const area = `${x(0)},${height - pad} ${line} ${x(values.length - 1)},${height - pad}`;

  return (
    <Svg width={width} height={height}>
      <Polyline points={area} fill={stroke} fillOpacity={0.12} stroke="none" />
      <Polyline points={line} fill="none" stroke={stroke} strokeWidth={2} strokeLinejoin="round" />
    </Svg>
  );
}

/** A donut chart with a legend. `slices` values need not sum to anything. */
export function Donut({
  slices,
  size = 150,
}: {
  slices: { label: string; value: number }[];
  size?: number;
}) {
  const data = slices.filter((s) => s.value > 0);
  const total = data.reduce((s, d) => s + d.value, 0);
  if (total <= 0) {
    return <Text style={{ color: colors.textDim, fontSize: 12 }}>Nothing deployed yet.</Text>;
  }
  const stroke = 18;
  const r = size / 2 - stroke / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;

  let offset = 0;
  const rings = data.map((d, i) => {
    const frac = d.value / total;
    const dash = frac * circ;
    const el = (
      <Circle
        key={i}
        cx={cx}
        cy={cy}
        r={r}
        stroke={CHART_COLORS[i % CHART_COLORS.length]}
        strokeWidth={stroke}
        fill="none"
        strokeDasharray={`${dash} ${circ - dash}`}
        strokeDashoffset={-offset}
      />
    );
    offset += dash;
    return el;
  });

  return (
    <View style={{ flexDirection: "row", alignItems: "center" }}>
      <Svg width={size} height={size}>
        {/* rotate so slices start at 12 o'clock */}
        <G rotation={-90} origin={`${cx}, ${cy}`}>
          <Circle cx={cx} cy={cy} r={r} stroke={colors.surfaceAlt} strokeWidth={stroke} fill="none" />
          {rings}
        </G>
      </Svg>
      <View style={{ flex: 1, marginLeft: spacing.lg }}>
        {data.map((d, i) => (
          <View key={i} style={{ flexDirection: "row", alignItems: "center", marginBottom: 6 }}>
            <View
              style={{
                width: 10,
                height: 10,
                borderRadius: 2,
                backgroundColor: CHART_COLORS[i % CHART_COLORS.length],
                marginRight: 8,
              }}
            />
            <Text style={{ color: colors.text, fontSize: 12, flex: 1 }} numberOfLines={1}>
              {d.label}
            </Text>
            <Text style={{ color: colors.textDim, fontSize: 12 }}>
              {((d.value / total) * 100).toFixed(0)}%
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

/**
 * A tiny price sparkline that fetches its own recent candles for an
 * (exchange, symbol). Thin line, colored by direction, no axes.
 */
export function Sparkline({
  exchange,
  symbol,
  timeframe = "1h",
  width = 90,
  height = 28,
}: {
  exchange: string;
  symbol: string;
  timeframe?: string;
  width?: number;
  height?: number;
}) {
  const [closes, setCloses] = useState<number[]>([]);

  useEffect(() => {
    let alive = true;
    api
      .candles(exchange, symbol, timeframe, 40)
      .then((cs) => {
        if (alive) setCloses(cs.map((c) => c.close));
      })
      .catch(() => {
        /* leave empty */
      });
    return () => {
      alive = false;
    };
  }, [exchange, symbol, timeframe]);

  if (closes.length < 2) {
    return <View style={{ width, height }} />;
  }
  const pad = 2;
  const min = Math.min(...closes);
  const max = Math.max(...closes);
  const range = max - min || 1;
  const x = (i: number) => pad + (i / (closes.length - 1)) * (width - 2 * pad);
  const y = (v: number) => pad + (1 - (v - min) / range) * (height - 2 * pad);
  const pts = closes.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const up = closes[closes.length - 1] >= closes[0];

  return (
    <Svg width={width} height={height}>
      <Polyline
        points={pts}
        fill="none"
        stroke={up ? colors.green : colors.red}
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    </Svg>
  );
}
