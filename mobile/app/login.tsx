import React, { useState } from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Text,
  View,
} from "react-native";

import { ApiError } from "@/api";
import { useAuth } from "@/auth";
import { Button, Card, Field } from "@/components";
import { colors, spacing } from "@/theme";

export default function LoginScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), password);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1, backgroundColor: colors.bg }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        contentContainerStyle={{
          padding: spacing.lg,
          justifyContent: "center",
          flexGrow: 1,
          width: "100%",
          maxWidth: 460,
          alignSelf: "center",
        }}
      >
        <Text style={{ color: colors.text, fontSize: 30, fontWeight: "800", marginBottom: spacing.xs }}>
          CryptoTrader
        </Text>
        <Text style={{ color: colors.textDim, marginBottom: spacing.xl }}>
          Configure agents to trade across Kraken, Binance, Coinbase & Robinhood.
        </Text>

        <Card>
          <Field
            label="Email"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            keyboardType="email-address"
            placeholder="you@example.com"
          />
          <Field
            label="Password"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            placeholder="At least 8 characters"
          />
          {error ? (
            <Text style={{ color: colors.red, marginBottom: spacing.md }}>{error}</Text>
          ) : null}
          <Button
            title={mode === "login" ? "Log in" : "Create account"}
            onPress={submit}
            loading={busy}
          />
          <View style={{ height: spacing.md }} />
          <Button
            title={mode === "login" ? "Need an account? Register" : "Have an account? Log in"}
            variant="secondary"
            onPress={() => {
              setError("");
              setMode(mode === "login" ? "register" : "login");
            }}
          />
        </Card>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
