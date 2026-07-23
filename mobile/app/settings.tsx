import React, { useState } from "react";
import { ScrollView, Text, View } from "react-native";

import { api } from "@/api";
import { useAuth } from "@/auth";
import { Button, Card, Field } from "@/components";
import { colors, spacing, screenContent } from "@/theme";

export default function SettingsScreen() {
  const { user, refresh } = useAuth();

  // Change email
  const [newEmail, setNewEmail] = useState("");
  const [emailPassword, setEmailPassword] = useState("");
  const [emailBusy, setEmailBusy] = useState(false);
  const [emailMsg, setEmailMsg] = useState("");
  const [emailErr, setEmailErr] = useState("");

  // Change password
  const [curPassword, setCurPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [pwBusy, setPwBusy] = useState(false);
  const [pwMsg, setPwMsg] = useState("");
  const [pwErr, setPwErr] = useState("");

  const saveEmail = async () => {
    setEmailErr("");
    setEmailMsg("");
    if (!newEmail.trim()) return setEmailErr("Enter a new email address.");
    if (!emailPassword) return setEmailErr("Enter your current password to confirm.");
    setEmailBusy(true);
    try {
      await api.updateEmail(newEmail.trim(), emailPassword);
      await refresh();
      setNewEmail("");
      setEmailPassword("");
      setEmailMsg("Email updated.");
    } catch (e: any) {
      setEmailErr(e?.message ?? "Failed to update email");
    } finally {
      setEmailBusy(false);
    }
  };

  const savePassword = async () => {
    setPwErr("");
    setPwMsg("");
    if (!curPassword) return setPwErr("Enter your current password.");
    if (newPassword.length < 8) return setPwErr("New password must be at least 8 characters.");
    if (newPassword !== confirmPassword) return setPwErr("New passwords don't match.");
    setPwBusy(true);
    try {
      await api.updatePassword(curPassword, newPassword);
      setCurPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPwMsg("Password updated.");
    } catch (e: any) {
      setPwErr(e?.message ?? "Failed to update password");
    } finally {
      setPwBusy(false);
    }
  };

  return (
    <ScrollView style={{ backgroundColor: colors.bg }} contentContainerStyle={screenContent}>
      <Card>
        <Text style={{ color: colors.text, fontWeight: "700", marginBottom: spacing.xs }}>Signed in as</Text>
        <Text style={{ color: colors.textDim }}>{user?.email ?? "—"}</Text>
      </Card>

      {/* Change email */}
      <Card>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: spacing.md }}>
          Change email
        </Text>
        <Field
          label="New email"
          value={newEmail}
          onChangeText={setNewEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          placeholder="you@example.com"
        />
        <Field
          label="Current password"
          value={emailPassword}
          onChangeText={setEmailPassword}
          autoCapitalize="none"
          secureTextEntry
          help="Confirm it's you by entering your current password."
        />
        {emailMsg ? <Text style={{ color: colors.green, marginBottom: spacing.md }}>{emailMsg}</Text> : null}
        {emailErr ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{emailErr}</Text> : null}
        <Button title="Update email" onPress={saveEmail} loading={emailBusy} />
      </Card>

      {/* Change password */}
      <Card>
        <Text style={{ color: colors.text, fontSize: 16, fontWeight: "700", marginBottom: spacing.md }}>
          Change password
        </Text>
        <Field
          label="Current password"
          value={curPassword}
          onChangeText={setCurPassword}
          autoCapitalize="none"
          secureTextEntry
        />
        <Field
          label="New password"
          value={newPassword}
          onChangeText={setNewPassword}
          autoCapitalize="none"
          secureTextEntry
          help="At least 8 characters."
        />
        <Field
          label="Confirm new password"
          value={confirmPassword}
          onChangeText={setConfirmPassword}
          autoCapitalize="none"
          secureTextEntry
        />
        {pwMsg ? <Text style={{ color: colors.green, marginBottom: spacing.md }}>{pwMsg}</Text> : null}
        {pwErr ? <Text style={{ color: colors.red, marginBottom: spacing.md }}>{pwErr}</Text> : null}
        <Button title="Update password" onPress={savePassword} loading={pwBusy} />
      </Card>

      <View style={{ height: spacing.xl }} />
    </ScrollView>
  );
}
