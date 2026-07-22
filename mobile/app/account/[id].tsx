import { useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import React, { useEffect, useState } from "react";
import { Alert, Platform, ScrollView, Switch, Text, useWindowDimensions, View } from "react-native";

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
  const { width } = useWindowDimensions();
  // Two columns on wider screens (web / tablets); stack on phones.
  const twoCol = width >= 720;

  const [account, setAccount] = useState<ExchangeAccount | null>(null);
  const [meta, setMeta] = useState<ExchangeMeta | null>(null);
  const [label, setLabel] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [replaceKeys, setReplaceKeys] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");

  const [busy, setBusy] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const runTest = async () => {
    setError("");
    setTestResult(null);
    setTesting(true);
    try {
      // If the user typed new keys, test those; otherwise test the saved ones.
      const result =
        replaceKeys && (apiKey || apiSecret)
          ? await api.validateAccount({
              exchange: account?.exchange,
              api_key: apiKey,
              api_secret: apiSecret,
              api_passphrase: passphrase,
            })
          : await api.testAccount(accountId);
      setTestResult(result);
    } catch (e: any) {
      setTestResult({ ok: false, message: e?.message ?? "Test failed" });
    } finally {
      setTesting(false);
    }
  };

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

  // Left column: Label + Active toggle.
  const labelColumn = (
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
  );

  // Right column: Replace API keys.
  const keysColumn = (
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
      {replaceKeys ? (
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
      ) : (
        <Text style={{ color: colors.textDim, fontSize: 13, marginTop: spacing.md }}>
          Current keys are kept. Turn on “Replace API keys” to enter new ones.
        </Text>
      )}
    </Card>
  );

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
      {/* Top row of actions */}
      <View style={{ flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginBottom: spacing.md }}>
        <View style={{ flex: 1, minWidth: 120 }}>
          <Button
            title={testing ? "Testing…" : "Test connection"}
            onPress={runTest}
            loading={testing}
            variant="secondary"
          />
        </View>
        <View style={{ flex: 1, minWidth: 120 }}>
          <Button title="Save" onPress={save} loading={busy} />
        </View>
        <View style={{ flex: 1, minWidth: 120 }}>
          <Button title="Remove" variant="danger" onPress={remove} />
        </View>
      </View>

      {/* Feedback: test result + save/error messages */}
      {testResult && (
        <View
          style={{
            marginBottom: spacing.md,
            padding: spacing.md,
            borderRadius: 8,
            borderWidth: 1,
            borderColor: testResult.ok ? colors.green : colors.red,
            backgroundColor: colors.surfaceAlt,
          }}
        >
          <Text style={{ color: testResult.ok ? colors.green : colors.red, fontWeight: "600" }}>
            {testResult.ok ? "✓ OK" : "✗ Failed"}
          </Text>
          <Text style={{ color: colors.text, marginTop: spacing.xs }}>{testResult.message}</Text>
        </View>
      )}
      {msg ? <Text style={{ color: colors.green, marginBottom: spacing.md }}>{msg}</Text> : null}
      {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}

      {/* Two-column body: left = Label + Active, right = Replace API keys */}
      <View style={{ flexDirection: twoCol ? "row" : "column", gap: twoCol ? spacing.lg : 0 }}>
        <View style={{ flex: 1 }}>{labelColumn}</View>
        <View style={{ flex: 1 }}>{keysColumn}</View>
      </View>
    </ScrollView>
  );
}
