import { useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Alert, Platform, ScrollView, Switch, Text, View } from "react-native";

import { api, ExchangeAccount, ExchangeMeta } from "@/api";
import { Button, Card, Field } from "@/components";
import { colors, spacing } from "@/theme";

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

export default function EditAccount() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const accountId = Number(id);
  const router = useRouter();
  const navigation = useNavigation();

  const [account, setAccount] = useState<ExchangeAccount | null>(null);
  const [meta, setMeta] = useState<ExchangeMeta | null>(null);
  const [label, setLabel] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [replaceKeys, setReplaceKeys] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");

  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [acc, exchanges] = await Promise.all([api.getAccount(accountId), api.exchanges()]);
        setAccount(acc);
        setLabel(acc.label);
        setIsActive(acc.is_active);
        setMeta(exchanges.find((e) => e.id === acc.exchange) ?? null);
        navigation.setOptions({ title: acc.label });
      } catch {
        setError("Could not load this connection.");
      }
    })();
  }, [accountId, navigation]);

  const save = async () => {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const payload: Record<string, any> = { label, is_active: isActive };
      if (replaceKeys) {
        payload.api_key = apiKey;
        payload.api_secret = apiSecret;
        payload.api_passphrase = passphrase;
      }
      const updated = await api.updateAccount(accountId, payload);
      setAccount(updated);
      setReplaceKeys(false);
      setApiKey("");
      setApiSecret("");
      setPassphrase("");
      setMsg("Saved.");
    } catch (e: any) {
      setError(e?.message ?? "Failed to save");
    } finally {
      setBusy(false);
    }
  };

  const remove = () =>
    confirm("Remove this connection? Agents using it will need a new one for live trading.", async () => {
      await api.deleteAccount(accountId);
      router.back();
    });

  if (!account) {
    return (
      <View style={{ flex: 1, backgroundColor: colors.bg, padding: spacing.lg }}>
        <Text style={{ color: colors.textDim }}>{error || "Loading…"}</Text>
      </View>
    );
  }

  const isCdp = meta?.key_format === "cdp";

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
      <Card>
        <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
          {account.exchange.toUpperCase()} · {account.has_credentials ? "keyed" : "no keys"}
        </Text>
        <Field label="Label" value={label} onChangeText={setLabel} />
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View style={{ flex: 1, paddingRight: spacing.md }}>
            <Text style={{ color: colors.text }}>Active</Text>
            <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2 }}>
              Disabled connections can't be used by live agents.
            </Text>
          </View>
          <Switch value={isActive} onValueChange={setIsActive} trackColor={{ true: colors.primary }} />
        </View>
      </Card>

      <Card>
        <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
          <View style={{ flex: 1, paddingRight: spacing.md }}>
            <Text style={{ color: colors.text }}>Replace API keys</Text>
            <Text style={{ color: colors.textDim, fontSize: 12, marginTop: 2 }}>
              Keys are never shown. Turn on to enter new ones; leave off to keep the current keys.
            </Text>
          </View>
          <Switch value={replaceKeys} onValueChange={setReplaceKeys} trackColor={{ true: colors.primary }} />
        </View>
        {replaceKeys && (
          <View style={{ marginTop: spacing.md }}>
            <Field
              label={isCdp ? "API key (name)" : "API key"}
              value={apiKey}
              onChangeText={setApiKey}
              autoCapitalize="none"
            />
            {isCdp ? (
              <Field
                label="Private key"
                value={apiSecret}
                onChangeText={setApiSecret}
                autoCapitalize="none"
                autoCorrect={false}
                multiline
                numberOfLines={5}
                style={{ minHeight: 110, textAlignVertical: "top", fontFamily: "monospace" } as any}
              />
            ) : (
              <Field
                label="API secret"
                value={apiSecret}
                onChangeText={setApiSecret}
                autoCapitalize="none"
                secureTextEntry
              />
            )}
            {meta?.needs_passphrase && (
              <Field
                label="Passphrase"
                value={passphrase}
                onChangeText={setPassphrase}
                autoCapitalize="none"
                secureTextEntry
              />
            )}
          </View>
        )}
      </Card>

      {msg ? <Text style={{ color: colors.green, marginBottom: spacing.md }}>{msg}</Text> : null}
      {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}

      <Button title="Save changes" onPress={save} loading={busy} />
      <View style={{ height: spacing.md }} />
      <Button title="Remove connection" variant="danger" onPress={remove} />
    </ScrollView>
  );
}
