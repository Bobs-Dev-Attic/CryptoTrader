"""ccxt-backed adapter for Kraken, Binance, and Coinbase."""
from __future__ import annotations

import re

from .base import Candle, ExchangeAdapter, OrderResult, Ticker


def looks_like_ed25519_key(secret: str) -> bool:
    """Heuristic: a Coinbase Ed25519 key is a ~88-char base64 string, no PEM.

    ccxt 4.4.x signs Coinbase requests with ES256 (ECDSA) only, so Ed25519 keys
    cannot be used and must be regenerated as ECDSA.
    """
    if not secret or "PRIVATE KEY" in secret:
        return False
    s = secret.strip()
    return bool(re.fullmatch(r"[A-Za-z0-9+/]{80,120}={0,2}", s))


def normalize_secret(secret: str) -> str:
    """Make an exchange API secret usable by ccxt's Coinbase ECDSA signer.

    Users paste Coinbase EC private keys in several shapes ccxt 4.4.x doesn't all
    accept, so we:
      * turn JSON-escaped newlines ("\\n") into real newlines;
      * repair a PEM whose line breaks were stripped (e.g. by a single-line
        input) by re-wrapping the base64 body at 64 columns;
      * convert PKCS#8 ("-----BEGIN PRIVATE KEY-----") to SEC1
        ("-----BEGIN EC PRIVATE KEY-----"), the only header ccxt's ECDSA signer
        recognizes (otherwise it hex-decodes the key -> "Non-base16 digit found").
    Non-PEM secrets (HMAC keys, or unsupported Ed25519 keys) pass through.
    """
    if not secret:
        return secret
    s = secret
    if "PRIVATE KEY" in s and "\\n" in s:
        s = s.replace("\\n", "\n")

    # Rebuild a well-formed PEM from a BEGIN/END block even if newlines were lost.
    m = re.search(r"-----BEGIN ([A-Z0-9 ]+?)-----(.*?)-----END \1-----", s, re.DOTALL)
    if m:
        label = m.group(1)
        body = re.sub(r"\s+", "", m.group(2))
        wrapped = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
        s = f"-----BEGIN {label}-----\n{wrapped}\n-----END {label}-----\n"
        if label == "PRIVATE KEY":  # PKCS#8 -> SEC1
            try:
                from cryptography.hazmat.primitives import serialization

                key = serialization.load_pem_private_key(s.encode(), password=None)
                s = key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                ).decode()
            except Exception:
                pass  # not EC (e.g. Ed25519) — ccxt will surface its own error
    return s

# Map our ExchangeId values to ccxt exchange class names.
CCXT_EXCHANGE_MAP: dict[str, str] = {
    "kraken": "kraken",
    "binance": "binance",
    "coinbase": "coinbase",
}


class CcxtAdapter(ExchangeAdapter):
    """Wraps a ccxt exchange instance.

    ccxt is imported lazily so the rest of the app (and the test suite) does not
    hard-depend on network access or the ccxt package being installed.
    """

    supports_live = True

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        api_passphrase: str = "",
        sandbox: bool = False,
    ) -> None:
        super().__init__(api_key, api_secret, api_passphrase)
        self.exchange_id = exchange_id
        self.sandbox = sandbox
        self._client = None  # lazily constructed

    # ------------------------------------------------------------------ #
    @property
    def client(self):
        if self._client is None:
            import ccxt  # local import: heavy, network-oriented dependency

            if self.exchange_id not in CCXT_EXCHANGE_MAP:
                raise ValueError(f"Unsupported ccxt exchange: {self.exchange_id}")
            klass = getattr(ccxt, CCXT_EXCHANGE_MAP[self.exchange_id])
            params: dict = {"enableRateLimit": True}
            if self.api_key:
                params["apiKey"] = self.api_key
            if self.api_secret:
                params["secret"] = normalize_secret(self.api_secret)
            if self.api_passphrase:
                params["password"] = self.api_passphrase
            client = klass(params)
            if self.sandbox and client.has.get("sandbox"):
                client.set_sandbox_mode(True)
            self._client = client
        return self._client

    # --- Market data --------------------------------------------------- #
    def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> list[Candle]:
        rows = self.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        return [
            Candle(
                timestamp=int(r[0]),
                open=float(r[1]),
                high=float(r[2]),
                low=float(r[3]),
                close=float(r[4]),
                volume=float(r[5]),
            )
            for r in rows
        ]

    def fetch_ticker(self, symbol: str) -> Ticker:
        t = self.client.fetch_ticker(symbol)
        return Ticker(
            symbol=symbol,
            last=float(t.get("last") or t.get("close") or 0.0),
            bid=float(t.get("bid") or 0.0),
            ask=float(t.get("ask") or 0.0),
            timestamp=int(t.get("timestamp") or 0),
        )

    def fetch_price_tickers(self, symbols: list[str]) -> list[dict]:
        try:
            data = self.client.fetch_tickers(symbols)
        except Exception:
            # Some exchanges don't support batch fetch_tickers; fall back.
            return super().fetch_price_tickers(symbols)
        out: list[dict] = []
        for s in symbols:
            t = data.get(s)
            if not t:
                continue
            pct = t.get("percentage")
            out.append(
                {
                    "symbol": s,
                    "last": float(t.get("last") or t.get("close") or 0.0),
                    "change_pct": float(pct) if pct is not None else None,
                }
            )
        return out

    # --- Account (live) ------------------------------------------------ #
    def fetch_balance(self) -> dict[str, float]:
        bal = self.client.fetch_balance()
        free = bal.get("free", {})
        return {k: float(v) for k, v in free.items() if v}

    def create_market_order(
        self, symbol: str, side: str, quantity: float
    ) -> OrderResult:
        order = self.client.create_order(symbol, "market", side, quantity)
        filled = float(order.get("filled") or quantity)
        price = float(order.get("average") or order.get("price") or 0.0)
        cost = float(order.get("cost") or filled * price)
        fee = 0.0
        fee_obj = order.get("fee") or {}
        if isinstance(fee_obj, dict):
            fee = float(fee_obj.get("cost") or 0.0)
        return OrderResult(
            side=side,
            symbol=symbol,
            quantity=filled,
            price=price,
            cost=cost,
            fee=fee,
            status=str(order.get("status") or "filled"),
            external_id=str(order.get("id") or ""),
            raw=order,
        )
