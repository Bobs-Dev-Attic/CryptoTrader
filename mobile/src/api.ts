/** Thin typed client for the CryptoTrader backend REST API. */
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

const TOKEN_KEY = "cryptotrader.token";

export function getBaseUrl(): string {
  const fromExtra = (Constants.expoConfig?.extra as any)?.apiBaseUrl;
  // Allow override via env for web builds.
  const fromEnv =
    typeof process !== "undefined" ? process.env?.EXPO_PUBLIC_API_URL : undefined;
  return fromEnv || fromExtra || "http://localhost:8000";
}

export async function getToken(): Promise<string | null> {
  return AsyncStorage.getItem(TOKEN_KEY);
}

export async function setToken(token: string | null): Promise<void> {
  if (token) await AsyncStorage.setItem(TOKEN_KEY, token);
  else await AsyncStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  auth = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (auth) {
    const token = await getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const resp = await fetch(`${getBaseUrl()}${path}`, { ...options, headers });
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = data?.detail || resp.statusText;
    throw new ApiError(resp.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

// --- Types (mirror backend schemas) --------------------------------------- //
export interface User {
  id: number;
  email: string;
  created_at: string;
}
export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}
export interface Position {
  quantity: number;
  avg_entry_price: number;
  cash_quote: number;
  realized_pnl: number;
}
export interface Agent {
  id: number;
  name: string;
  exchange: string;
  symbol: string;
  timeframe: string;
  strategy_type: string;
  strategy_config: Record<string, any>;
  trade_mode: string;
  order_size_quote: number;
  paper_balance_quote: number;
  interval_seconds: number;
  status: string;
  last_error: string;
  last_run_at: string | null;
  account_id: number | null;
  created_at: string;
  position: Position | null;
}
export interface Signal {
  id: number;
  action: string;
  confidence: number;
  price: number;
  rationale: string;
  details: Record<string, any>;
  created_at: string;
}
export interface Trade {
  id: number;
  side: string;
  symbol: string;
  quantity: number;
  price: number;
  cost_quote: number;
  fee_quote: number;
  trade_mode: string;
  status: string;
  note: string;
  created_at: string;
}
export interface AgentDetail extends Agent {
  recent_signals: Signal[];
  recent_trades: Trade[];
  equity: number | null;
  unrealized_pnl: number | null;
}
export interface ExchangeAccount {
  id: number;
  exchange: string;
  label: string;
  is_active: boolean;
  created_at: string;
  has_credentials: boolean;
}
export interface StrategyMeta {
  type: string;
  name: string;
  config_schema: Record<string, { type: string; default: any }>;
}
export interface ExchangeMeta {
  id: string;
  name: string;
  supports_live: boolean;
  needs_passphrase: boolean;
  docs_url: string;
  sample_symbol: string;
  permissions: string[];
  tip: string;
}
export interface ValidationResult {
  ok: boolean;
  message: string;
  authenticated: boolean;
  asset_count: number | null;
}

// --- Endpoints ------------------------------------------------------------ //
export const api = {
  register: (email: string, password: string) =>
    request<TokenResponse>(
      "/api/auth/register",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false
    ),

  login: async (email: string, password: string) => {
    // OAuth2 password flow expects form-encoded body.
    const body = new URLSearchParams({ username: email, password }).toString();
    const resp = await fetch(`${getBaseUrl()}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data?.detail || "Login failed");
    return data as TokenResponse;
  },

  me: () => request<User>("/api/auth/me"),

  listAgents: () => request<Agent[]>("/api/agents"),
  getAgent: (id: number) => request<AgentDetail>(`/api/agents/${id}`),
  createAgent: (payload: Partial<Agent>) =>
    request<Agent>("/api/agents", { method: "POST", body: JSON.stringify(payload) }),
  updateAgent: (id: number, payload: Record<string, any>) =>
    request<Agent>(`/api/agents/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteAgent: (id: number) =>
    request<void>(`/api/agents/${id}`, { method: "DELETE" }),
  startAgent: (id: number) =>
    request<Agent>(`/api/agents/${id}/start`, { method: "POST" }),
  stopAgent: (id: number) =>
    request<Agent>(`/api/agents/${id}/stop`, { method: "POST" }),
  runAgent: (id: number) =>
    request<Signal>(`/api/agents/${id}/run`, { method: "POST" }),
  strategies: () => request<StrategyMeta[]>("/api/agents/strategies", {}, false),

  listAccounts: () => request<ExchangeAccount[]>("/api/accounts"),
  createAccount: (payload: Record<string, any>) =>
    request<ExchangeAccount>("/api/accounts", { method: "POST", body: JSON.stringify(payload) }),
  validateAccount: (payload: Record<string, any>) =>
    request<ValidationResult>("/api/accounts/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteAccount: (id: number) =>
    request<void>(`/api/accounts/${id}`, { method: "DELETE" }),

  exchanges: () => request<ExchangeMeta[]>("/api/market/exchanges", {}, false),
};
