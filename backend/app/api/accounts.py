"""Exchange-account management (encrypted API-key storage)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import ExchangeAccount, User
from ..schemas import ExchangeAccountCreate, ExchangeAccountOut
from ..security import encrypt_secret

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


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
) -> None:
    acc = db.get(ExchangeAccount, account_id)
    if not acc or acc.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    db.delete(acc)
    db.commit()
