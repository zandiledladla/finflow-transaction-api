import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.transaction import Transaction
from app.schemas.transaction import MoneyOperation, TransactionRead, TransferCreate
from app.services import transactions as service

router = APIRouter()


def _run(operation):
    try:
        return operation()
    except service.TransactionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/accounts/{account_id}/deposit", response_model=TransactionRead)
def deposit(
    account_id: uuid.UUID,
    payload: MoneyOperation,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", max_length=128
    ),
) -> Transaction:
    return _run(
        lambda: service.deposit(
            db, account_id, payload.amount, payload.reference, idempotency_key
        )
    )


@router.post("/accounts/{account_id}/withdraw", response_model=TransactionRead)
def withdraw(
    account_id: uuid.UUID,
    payload: MoneyOperation,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", max_length=128
    ),
) -> Transaction:
    return _run(
        lambda: service.withdraw(
            db, account_id, payload.amount, payload.reference, idempotency_key
        )
    )


@router.post("/transfer", response_model=TransactionRead)
def transfer(
    payload: TransferCreate,
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(
        default=None, alias="Idempotency-Key", max_length=128
    ),
) -> Transaction:
    return _run(
        lambda: service.transfer(
            db,
            payload.source_account_id,
            payload.destination_account_id,
            payload.amount,
            payload.reference,
            idempotency_key,
        )
    )


@router.get("", response_model=list[TransactionRead])
def list_transactions(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    statement = (
        select(Transaction).order_by(Transaction.created_at.desc()).offset(offset).limit(limit)
    )
    return list(db.scalars(statement))
