"""Native Coinbase Ed25519 (EdDSA) auth for ccxt.

ccxt 4.4.x signs Coinbase JWTs with ES256 (ECDSA) only. Coinbase now issues
Ed25519 keys by default, whose private key is a base64 string (32-byte seed, or
64 bytes = seed + public key). This module subclasses ccxt's coinbase exchange
and overrides only the JWT builder to sign with EdDSA using the same claim set
ccxt uses for ES256 — so everything else (endpoints, parsing) is unchanged.
"""
from __future__ import annotations

import base64
import json


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def ed25519_jwt(claims: dict, secret_b64: str, kid: str, nonce: str) -> str:
    """Build an EdDSA-signed JWT for Coinbase from a base64 Ed25519 secret."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    header = {"alg": "EdDSA", "typ": "JWT", "kid": kid, "nonce": nonce}
    seg_header = _b64url(json.dumps(header, separators=(",", ":")).encode())
    seg_payload = _b64url(json.dumps(claims, separators=(",", ":")).encode())
    signing_input = f"{seg_header}.{seg_payload}".encode()

    raw = base64.b64decode(secret_b64)
    # Coinbase provides 64 bytes (seed + public key) or 32 bytes (seed only).
    seed = raw[:32]
    key = Ed25519PrivateKey.from_private_bytes(seed)
    signature = key.sign(signing_input)
    return f"{seg_header}.{seg_payload}.{_b64url(signature)}"


def make_coinbase_ed25519(params: dict):
    """Return a ccxt coinbase instance that signs auth JWTs with EdDSA."""
    import ccxt

    class CoinbaseEd25519(ccxt.coinbase):  # type: ignore[misc]
        def create_auth_token(self, seconds, method=None, url=None):
            uri = None
            if url is not None:
                uri = method + " " + url.replace("https://", "")
                ques = uri.find("?")
                if ques > 0:
                    uri = uri[0:ques]
            nonce = self.random_bytes(16)
            request: dict = {
                "aud": ["retail_rest_api_proxy"],
                "iss": "coinbase-cloud",
                "nbf": seconds,
                "exp": seconds + 120,
                "sub": self.apiKey,
                "iat": seconds,
            }
            if uri is not None:
                request["uri"] = uri
            return ed25519_jwt(request, self.secret, self.apiKey, nonce)

    return CoinbaseEd25519(params)
