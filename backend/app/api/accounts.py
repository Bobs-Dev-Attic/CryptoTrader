"""Exchange-account management (encrypted API-key storage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..enums import ExchangeId
from ..exchanges import get_adapter
from ..exchanges.ccxt_adapter import looks_like_ed25519_key
from ..models import ExchangeAccount, User
from ..schemas import (
    ExchangeAccountCreate,
    ExchangeAccountOut,
    ExchangeAccountValidate,
    ValidationResult,
)
from ..security import encrypt_secret

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.post("/validate", response_model=ValidationResult)
def validate_credentials(
    payload: ExchangeAccountValidate,
    user: User = Depends(get_current_user),
) -> ValidationResult:
    """Test exchange credentials without saving them (used by the setup wizard)."""
    if payload.exchange == ExchangeId.ROBINHOOD:
        return ValidationResult(
            ok=True,
            authenticated=False,
            message="Robinhood runs in paper mode in this build; no live keys needed.",
        )

    if not payload.api_key or not payload.api_secret:
        return ValidationResult(
            ok=True,
            authenticated=False,
            message="No credentials provided — this exchange can still be used for paper trading.",
        )

    # Coinbase Ed25519 keys can't be signed by our ECDSA-only client — catch this
    # before the cryptic "Non-base16 digit found" error and tell the user the fix.
    if payload.exchange == ExchangeId.COINBASE and looks_like_ed25519_key(
        payload.api_secret
    ):
        return ValidationResult(
            ok=False,
            authenticated=False,
            message=(
                "This Coinbase key uses the Ed25519 algorithm, which isn't supported. "
                "Create a new Secret API key in Coinbase and choose the ECDSA "
                "algorithm (Trade + View), then use that key."
            ),
        )

    adapter = get_adapter(
        payload.exchange, payload.api_key, payload.api_secret, payload.api_passphrase
    )
    try:
        balances = adapter.fetch_balance()
    except Exception as exc:
        msg = f"Could not authenticate: {type(exc).__name__}: {exc}"
        if payload.exchange == ExchangeId.COINBASE and "base16" in str(exc).lower():
            msg = (
                "Could not authenticate. If your Coinbase key uses the Ed25519 "
                "algorithm, create a new Secret API key with the ECDSA algorithm "
                "instead. Otherwise, re-paste the full private key including the "
                "BEGIN/END lines."
            )
        return ValidationResult(ok=False, authenticated=False, message=msg)
    return ValidationResult(
        ok=True,
        authenticated=True,
        asset_count=len(balances),
        message=f"Connected. Found {len(balances)} funded asset(s). Ready for live trading.",
    )


def _to_out(acc: ExchangeAccount) -> ExchangeAccountOut:
    out = ExchangeAccountOut.model_validate(acc)
    out.has_credentials = bool(acc.api_key_enc and acc.api_secret_enc)
    return out


@router.get("", response_model=list[ExchangeAccountOut])
def list_accounts(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[ExchangeAccountOut]:
    accounts = (
        db.query(ExchangeAccount).filter(ExchangeAccount.user_id == user.id).all()
    )
    return [_to_out(a) for a in accounts]


@router.post("", response_model=ExchangeAccountOut, status_code=201)
def create_account(
    payload: ExchangeAccountCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExchangeAccountOut:
    acc = ExchangeAccount(
        user_id=user.id,
        exchange=payload.exchange,
        label=payload.label or payload.exchange.value,
        api_key_enc=encrypt_secret(payload.api_key),
        api_secret_enc=encrypt_secret(payload.api_secret),
        api_passphrase_enc=encrypt_secret(payload.api_passphrase),
    )
    db.add(acc)
    db.commit()
    db.refresh(acc)
    return _to_out(acc)


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # No `-> None` return annotation: some FastAPI versions treat it as a
    # NoneType response body and reject it on a 204 (no-body) status.
    acc = db.get(ExchangeAccount, account_id)
    if not acc or acc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
