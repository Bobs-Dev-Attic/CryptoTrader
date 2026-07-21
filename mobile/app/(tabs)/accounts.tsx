import { useFocusEffect } from "expo-router";
import React, { useCallback, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";

import { api, ExchangeAccount, ExchangeMeta } from "@/api";
import { Badge, Button, Card, Field } from "@/components";
import { colors, radius, spacing } from "@/theme";

export default function AccountsScreen() {
  const [accounts, setAccounts] = useState<ExchangeAccount[]>([]);
  const [exchanges, setExchanges] = useState<ExchangeMeta[]>([]);
  const [showForm, setShowForm] = useState(false);

  const [exchange, setExchange] = useState("kraken");
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [acc, ex] = await Promise.all([api.listAccounts(), api.exchanges()]);
      setAccounts(acc);
      setExchanges(ex);
    } catch {
      /* ignore */
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      await api.createAccount({
        exchange,
        label,
        api_key: apiKey,
        api_secret: apiSecret,
        api_passphrase: passphrase,
      });
      setApiKey("");
      setApiSecret("");
      setPassphrase("");
      setLabel("");
      setShowForm(false);
      await load();
    } catch (e: any) {
      setError(e?.message ?? "Failed to save account");
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number) => {
    await api.deleteAccount(id);
    await load();
  };

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
      <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
        Link exchange API keys to enable live trading. Keys are encrypted at rest and never
        returned to the app. Paper agents don't need keys.
      </Text>

      {accounts.map((a) => (
        <Card key={a.id}>
          <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
            <View>
              <Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>{a.label}</Text>
              <Text style={{ color: colors.textDim, marginTop: 2 }}>{a.exchange.toUpperCase()}</Text>
            </View>
            <Badge
              label={a.has_credentials ? "keyed" : "no keys"}
              color={a.has_credentials ? colors.green : colors.textDim}
            />
          </View>
          <View style={{ height: spacing.md }} />
          <Button title="Remove" variant="danger" onPress={() => remove(a.id)} />
        </Card>
      ))}

      {!showForm ? (
        <Button title="+ Link an exchange" onPress={() => setShowForm(true)} />
      ) : (
        <Card>
          <Text style={{ color: colors.text, fontWeight: "700", marginBottom: spacing.md }}>
            Link exchange
          </Text>
          <Text style={{ color: colors.textDim, fontSize: 13, marginBottom: spacing.xs }}>Exchange</Text>
          <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md }}>
            {exchanges.map((e) => (
              <Pressable
                key={e.id}
                onPress={() => setExchange(e.id)}
                style={{
                  paddingHorizontal: spacing.md,
                  paddingVertical: spacing.sm,
                  borderRadius: radius.sm,
                  borderWidth: 1,
                  borderColor: exchange === e.id ? colors.primary : colors.border,
                  backgroundColor: exchange === e.id ? colors.primaryDim : colors.surfaceAlt,
                }}
              >
                <Text style={{ color: colors.text }}>
                  {e.name}
                  {!e.supports_live ? " (paper)" : ""}
                </Text>
              </Pressable>
            ))}
          </View>

          <Field label="Label" value={label} onChangeText={setLabel} placeholder="e.g. Main Kraken" />
          <Field label="API key" value={apiKey} onChangeText={setApiKey} autoCapitalize="none" />
          <Field label="API secret" value={apiSecret} onChangeText={setApiSecret} autoCapitalize="none" secureTextEntry />
          <Field
            label="Passphrase (Coinbase only, optional)"
            value={passphrase}
            onChangeText={setPassphrase}
            autoCapitalize="none"
            secureTextEntry
          />
          {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}
          <Button title="Save" onPress={submit} loading={busy} />
          <View style={{ height: spacing.md }} />
          <Button title="Cancel" variant="secondary" onPress={() => setShowForm(false)} />
        </Card>
      )}
    </ScrollView>
  );
}
