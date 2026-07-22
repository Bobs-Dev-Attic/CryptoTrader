"""Exchange-account management (encrypted API-key storage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..enums import ExchangeId
from ..exchanges import get_adapter
from ..models import ExchangeAccount, User
from ..schemas import (
    ExchangeAccountCreate,
    ExchangeAccountOut,
    ExchangeAccountUpdate,
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

    adapter = get_adapter(
        payload.exchange, payload.api_key, payload.api_secret, payload.api_passphrase
    )
    try:
        balances = adapter.fetch_balance()
    except Exception as exc:
        msg = f"Could not authenticate: {type(exc).__name__}: {exc}"
        if payload.exchange == ExchangeId.COINBASE and "base16" in str(exc).lower():
            msg = (
                "Could not authenticate with this Coinbase key. Make sure you pasted "
                "the full private key (including any BEGIN/END lines). Both ECDSA and "
                "Ed25519 Secret API keys are supported."
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


def _owned_account(db: Session, user: User, account_id: int) -> ExchangeAccount:
    acc = db.get(ExchangeAccount, account_id)
    if not acc or acc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    return acc


@router.get("/{account_id}", response_model=ExchangeAccountOut)
def get_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExchangeAccountOut:
    return _to_out(_owned_account(db, user, account_id))


@router.patch("/{account_id}", response_model=ExchangeAccountOut)
def update_account(
    account_id: int,
    payload: ExchangeAccountUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExchangeAccountOut:
    acc = _owned_account(db, user, account_id)
    data = payload.model_dump(exclude_unset=True)
    if "label" in data and data["label"] is not None:
        acc.label = data["label"]
    if "is_active" in data and data["is_active"] is not None:
        acc.is_active = data["is_active"]
    # Only overwrite credentials when a non-empty value is supplied.
    if data.get("api_key"):
        acc.api_key_enc = encrypt_secret(data["api_key"])
    if data.get("api_secret"):
        acc.api_secret_enc = encrypt_secret(data["api_secret"])
    if data.get("api_passphrase") is not None:
        acc.api_passphrase_enc = encrypt_secret(data["api_passphrase"])
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
