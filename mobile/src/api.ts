/** Thin typed client for the CryptoTrader backend REST API. */
import AsyncStorage from "@react-native-async-storage/async-storage";
import Constants from "expo-constants";

const TOKEN_KEY = "cryptotrader.token";

export function getBaseUrl(): string {
  // 1) Explicit override always wins (useful for native builds / custom hosts).
  const fromEnv =
    typeof process !== "undefined" ? process.env?.EXPO_PUBLIC_API_URL : undefined;
  if (fromEnv) return fromEnv;

  // 2) On the deployed web app the API is served from the SAME origin under
  //    /api/* (single-project Vercel deployment), so no configuration is needed.
  if (
    typeof window !== "undefined" &&
    window.location?.origin &&
    !window.location.origin.includes("localhost") &&
    !window.location.origin.includes("127.0.0.1")
  ) {
    return window.location.origin;
  }

  // 3) Local development fallback (Expo web on :8081 -> API on :8000).
  const fromExtra = (Constants.expoConfig?.extra as any)?.apiBaseUrl;
  return fromExtra || "http://localhost:8000";
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
  const base = getBaseUrl();
  let resp: Response;
  try {
    resp = await fetch(`${base}${path}`, { ...options, headers });
  } catch {
    // fetch throws (TypeError) when the server is unreachable / blocked.
    throw new ApiError(0, unreachableMessage(base));
  }
  const text = await resp.text();
  const data = text ? JSON.parse(text) : null;
  if (!resp.ok) {
    const detail = data?.detail || resp.statusText;
    throw new ApiError(resp.status, typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data as T;
}

/** Human-friendly message when the API host can't be reached. */
export function unreachableMessage(base: string): string {
  if (base.includes("localhost") || base.includes("127.0.0.1")) {
    return (
      `Can't reach the API — this build is pointed at ${base}. ` +
      `Set EXPO_PUBLIC_API_URL to your deployed backend URL and redeploy the web app.`
    );
  }
  return `Can't reach the API at ${base}. Is the backend deployed and running?`;
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
  key_format?: string; // "key_secret" (default) or "cdp" (Coinbase key-pair)
}
export interface ValidationResult {
  ok: boolean;
  message: string;
  authenticated: boolean;
  asset_count: number | null;
}
export interface TickerQuote {
  symbol: string;
  last: number;
  change_pct: number | null;
}
export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
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
    const base = getBaseUrl();
    let resp: Response;
    try {
      resp = await fetch(`${base}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
    } catch {
      throw new ApiError(0, unreachableMessage(base));
    }
    const data = await resp.json();
    if (!resp.ok) throw new ApiError(resp.status, data?.detail || "Login failed");
    return data as TokenResponse;
  },

  me: () => request<User>("/api/auth/me"),
  updateEmail: (new_email: string, current_password: string) =>
    request<User>("/api/auth/email", {
      method: "PATCH",
      body: JSON.stringify({ new_email, current_password }),
    }),
  updatePassword: (current_password: string, new_password: string) =>
    request<{ ok: boolean; detail: string }>("/api/auth/password", {
      method: "PATCH",
      body: JSON.stringify({ current_password, new_password }),
    }),

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
  getAccount: (id: number) => request<ExchangeAccount>(`/api/accounts/${id}`),
  createAccount: (payload: Record<string, any>) =>
    request<ExchangeAccount>("/api/accounts", { method: "POST", body: JSON.stringify(payload) }),
  updateAccount: (id: number, payload: Record<string, any>) =>
    request<ExchangeAccount>(`/api/accounts/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  validateAccount: (payload: Record<string, any>) =>
    request<ValidationResult>("/api/accounts/validate", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  testAccount: (id: number) =>
    request<ValidationResult>(`/api/accounts/${id}/test`, { method: "POST" }),
  deleteAccount: (id: number) =>
    request<void>(`/api/accounts/${id}`, { method: "DELETE" }),

  exchanges: () => request<ExchangeMeta[]>("/api/market/exchanges", {}, false),
  portfolioHistory: () => request<{ t: string; equity: number }[]>("/api/portfolio/history"),
  portfolioAllocation: () =>
    request<{ label: string; value: number; symbol: string }[]>("/api/portfolio/allocation"),
  portfolioStats: () => request<Record<string, number>>("/api/portfolio/stats"),
  agentEquity: (id: number) =>
    request<{ t: string; equity: number }[]>(`/api/agents/${id}/equity`),

  candles: (exchange: string, symbol: string, timeframe = "1h", limit = 48) =>
    request<Candle[]>(
      `/api/market/candles?exchange=${encodeURIComponent(exchange)}&symbol=${encodeURIComponent(
        symbol
      )}&timeframe=${encodeURIComponent(timeframe)}&limit=${limit}`,
      {},
      false
    ),
  tickers: (exchange: string, symbols: string[]) =>
    request<TickerQuote[]>(
      `/api/market/tickers?exchange=${encodeURIComponent(exchange)}&symbols=${encodeURIComponent(
        symbols.join(",")
      )}`,
      {},
      false
    ),
};
