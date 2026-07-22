import { useRouter } from "expo-router";
import * as Linking from "expo-linking";
import React, { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, View } from "react-native";

import { api, ExchangeMeta, ValidationResult } from "@/api";
import { Badge, Button, Card, Field, HelpNote } from "@/components";
import { colors, radius, spacing } from "@/theme";

/** Plain-language help for the connection wizard fields. */
const HELP = {
  label:
    "A name for you to recognize this connection later, e.g. 'My Kraken'. It doesn't affect trading.",
  apiKey:
    "The public identifier of the API key you created on the exchange. Safe to paste — it's like a username for the key.",
  apiSecret:
    "The secret half of the API key — treat it like a password. It's encrypted on the server and never shown again. Never share it with anyone.",
  passphrase:
    "An extra password some exchanges attach to an API key when you create it. Enter the same passphrase you set on the exchange.",
  cdpName:
    "Coinbase key-pair (CDP) keys: paste the 'name' value here — it looks like organizations/xxxx/apiKeys/yyyy.",
  cdpPrivateKey:
    "Paste the whole 'privateKey' value, including the -----BEGIN EC PRIVATE KEY----- and -----END EC PRIVATE KEY----- lines. Line breaks are fine.",
};

const STEPS = ["Exchange", "Get keys", "Credentials", "Connect"];

/** A slim step indicator across the top of the wizard. */
function Stepper({ step }: { step: number }) {
  return (
    <View style={{ flexDirection: "row", gap: spacing.sm, marginBottom: spacing.lg }}>
      {STEPS.map((label, i) => (
        <View key={label} style={{ flex: 1, alignItems: "center" }}>
          <View
            style={{
              width: 26,
              height: 26,
              borderRadius: 13,
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: i <= step ? colors.primary : colors.surfaceAlt,
              borderWidth: 1,
              borderColor: i <= step ? colors.primary : colors.border,
            }}
          >
            <Text style={{ color: i <= step ? "#fff" : colors.textDim, fontSize: 12, fontWeight: "700" }}>
              {i < step ? "✓" : i + 1}
            </Text>
          </View>
          <Text style={{ color: i <= step ? colors.text : colors.textDim, fontSize: 11, marginTop: 4 }}>
            {label}
          </Text>
        </View>
      ))}
    </View>
  );
}

export default function ConnectWizard() {
  const router = useRouter();
  const [exchanges, setExchanges] = useState<ExchangeMeta[]>([]);
  const [step, setStep] = useState(0);
  const [selected, setSelected] = useState<ExchangeMeta | null>(null);

  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [apiSecret, setApiSecret] = useState("");
  const [passphrase, setPassphrase] = useState("");

  const [testing, setTesting] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        setExchanges(await api.exchanges());
      } catch {
        /* ignore */
      }
    })();
  }, []);

  const choose = (ex: ExchangeMeta) => {
    setSelected(ex);
    setLabel(ex.name);
    setResult(null);
    setStep(1);
  };

  const runTest = async () => {
    if (!selected) return;
    setError("");
    setTesting(true);
    setResult(null);
    try {
      const r = await api.validateAccount({
        exchange: selected.id,
        api_key: apiKey,
        api_secret: apiSecret,
        api_passphrase: passphrase,
      });
      setResult(r);
    } catch (e: any) {
      setError(e?.message ?? "Validation failed");
    } finally {
      setTesting(false);
    }
  };

  const save = async () => {
    if (!selected) return;
    setError("");
    setSaving(true);
    try {
      await api.createAccount({
        exchange: selected.id,
        label: label || selected.name,
        api_key: apiKey,
        api_secret: apiSecret,
        api_passphrase: passphrase,
      });
      router.back();
    } catch (e: any) {
      setError(e?.message ?? "Failed to save account");
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={{ padding: spacing.lg }}>
      <Stepper step={step} />

      {/* Step 0 — choose exchange */}
      {step === 0 && (
        <View>
          <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginBottom: spacing.sm }}>
            Which exchange?
          </Text>
          <HelpNote>
            Connecting an exchange lets your <Text style={{ fontWeight: "700" }}>live</Text> agents place
            real orders there. You only need to do this for live trading — {""}
            <Text style={{ fontWeight: "700" }}>paper (simulated) agents work without any keys</Text>. Pick a
            platform below; you can link more than one.
          </HelpNote>
          {exchanges.map((ex) => (
            <Pressable key={ex.id} onPress={() => choose(ex)}>
              <Card>
                <View style={{ flexDirection: "row", justifyContent: "space-between", alignItems: "center" }}>
                  <Text style={{ color: colors.text, fontSize: 16, fontWeight: "600" }}>{ex.name}</Text>
                  <Badge
                    label={ex.supports_live ? "live + paper" : "paper only"}
                    color={ex.supports_live ? colors.green : colors.yellow}
                  />
                </View>
                {ex.tip ? (
                  <Text style={{ color: colors.textDim, marginTop: spacing.sm, fontSize: 13 }}>{ex.tip}</Text>
                ) : null}
              </Card>
            </Pressable>
          ))}
        </View>
      )}

      {/* Step 1 — how to get keys */}
      {step === 1 && selected && (
        <View>
          <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginBottom: spacing.sm }}>
            Create an API key on {selected.name}
          </Text>
          {selected.supports_live ? (
            <Card>
              <Text style={{ color: colors.text, marginBottom: spacing.md }}>
                In your {selected.name} account, create an API key with these permissions:
              </Text>
              {selected.permissions.map((p) => (
                <Text key={p} style={{ color: colors.text, marginBottom: spacing.xs }}>
                  • {p}
                </Text>
              ))}
              {selected.tip ? (
                <Text style={{ color: colors.yellow, marginTop: spacing.md, fontSize: 13 }}>⚠ {selected.tip}</Text>
              ) : null}
              {selected.docs_url ? (
                <View style={{ marginTop: spacing.md }}>
                  <Button
                    title="Open exchange instructions ↗"
                    variant="secondary"
                    onPress={() => Linking.openURL(selected.docs_url)}
                  />
                </View>
              ) : null}
            </Card>
          ) : (
            <Card>
              <Text style={{ color: colors.text }}>
                {selected.name} agents run in paper (simulated) mode in this build — no API keys are
                required. Continue to name and save the connection.
              </Text>
            </Card>
          )}
          <View style={{ flexDirection: "row", gap: spacing.md }}>
            <View style={{ flex: 1 }}>
              <Button title="Back" variant="secondary" onPress={() => setStep(0)} />
            </View>
            <View style={{ flex: 1 }}>
              <Button title="Continue" onPress={() => setStep(selected.supports_live ? 2 : 3)} />
            </View>
          </View>
        </View>
      )}

      {/* Step 2 — enter credentials */}
      {step === 2 && selected && (
        <View>
          <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginBottom: spacing.sm }}>
            Enter your {selected.name} keys
          </Text>
          <Text style={{ color: colors.textDim, marginBottom: spacing.lg }}>
            Keys are encrypted on the server and never shown again. Leave blank to use paper trading only.
          </Text>
          <Card>
            <Field
              label="Label"
              value={label}
              onChangeText={setLabel}
              placeholder={`My ${selected.name}`}
              help={HELP.label}
            />
            <Field
              label={selected.key_format === "cdp" ? "API key (name)" : "API key"}
              value={apiKey}
              onChangeText={setApiKey}
              autoCapitalize="none"
              placeholder={selected.key_format === "cdp" ? "organizations/…/apiKeys/…" : undefined}
              help={selected.key_format === "cdp" ? HELP.cdpName : HELP.apiKey}
            />
            {selected.key_format === "cdp" ? (
              <Field
                label="Private key"
                value={apiSecret}
                onChangeText={setApiSecret}
                autoCapitalize="none"
                autoCorrect={false}
                multiline
                numberOfLines={5}
                placeholder={"-----BEGIN EC PRIVATE KEY-----\n…\n-----END EC PRIVATE KEY-----"}
                style={{ minHeight: 110, textAlignVertical: "top", fontFamily: "monospace" } as any}
                help={HELP.cdpPrivateKey}
              />
            ) : (
              <Field
                label="API secret"
                value={apiSecret}
                onChangeText={setApiSecret}
                autoCapitalize="none"
                secureTextEntry
                help={HELP.apiSecret}
              />
            )}
            {selected.needs_passphrase && (
              <Field
                label="Passphrase"
                value={passphrase}
                onChangeText={setPassphrase}
                autoCapitalize="none"
                secureTextEntry
                help={HELP.passphrase}
              />
            )}
          </Card>
          <View style={{ flexDirection: "row", gap: spacing.md }}>
            <View style={{ flex: 1 }}>
              <Button title="Back" variant="secondary" onPress={() => setStep(1)} />
            </View>
            <View style={{ flex: 1 }}>
              <Button title="Continue" onPress={() => { setResult(null); setStep(3); }} />
            </View>
          </View>
        </View>
      )}

      {/* Step 3 — test + save */}
      {step === 3 && selected && (
        <View>
          <Text style={{ color: colors.text, fontSize: 18, fontWeight: "700", marginBottom: spacing.sm }}>
            Connect {selected.name}
          </Text>

          {selected.supports_live && (apiKey || apiSecret) ? (
            <Card>
              <Text style={{ color: colors.textDim, marginBottom: spacing.md }}>
                Test that your keys authenticate before saving.
              </Text>
              <Button title={testing ? "Testing…" : "Test connection"} onPress={runTest} loading={testing} />
              {testing && <ActivityIndicator style={{ marginTop: spacing.md }} color={colors.primary} />}
              {result && (
                <View
                  style={{
                    marginTop: spacing.md,
                    padding: spacing.md,
                    borderRadius: radius.sm,
                    borderWidth: 1,
                    borderColor: result.ok ? colors.green : colors.red,
                    backgroundColor: colors.surfaceAlt,
                  }}
                >
                  <Text style={{ color: result.ok ? colors.green : colors.red, fontWeight: "600" }}>
                    {result.ok ? (result.authenticated ? "✓ Connected" : "✓ OK") : "✗ Failed"}
                  </Text>
                  <Text style={{ color: colors.text, marginTop: spacing.xs }}>{result.message}</Text>
                </View>
              )}
            </Card>
          ) : (
            <Card>
              <Text style={{ color: colors.text }}>
                This connection will be saved for <Text style={{ fontWeight: "700" }}>paper trading</Text>. You
                can add live keys later by re-linking.
              </Text>
            </Card>
          )}

          {error ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text> : null}

          <View style={{ flexDirection: "row", gap: spacing.md }}>
            <View style={{ flex: 1 }}>
              <Button
                title="Back"
                variant="secondary"
                onPress={() => setStep(selected.supports_live ? 2 : 1)}
              />
            </View>
            <View style={{ flex: 1 }}>
              <Button title="Save connection" onPress={save} loading={saving} />
            </View>
          </View>
        </View>
      )}
    </ScrollView>
  );
}
