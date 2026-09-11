import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.account import Account
from app.models.customer import Customer
from app.models.transaction import Transaction
from app.schemas.account import AccountCreate, AccountRead
from app.schemas.transaction import TransactionRead

router = APIRouter()


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
def create_account(payload: AccountCreate, db: Session = Depends(get_db)) -> Account:
    if db.get(Customer, payload.customer_id) is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    account = Account(customer_id=payload.customer_id, currency=payload.currency)
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("", response_model=list[AccountRead])
def list_accounts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Account]:
    statement = select(Account).order_by(Account.created_at.desc()).offset(offset).limit(limit)
    return list(db.scalars(statement))


@router.get("/{account_id}", response_model=AccountRead)
def get_account(account_id: uuid.UUID, db: Session = Depends(get_db)) -> Account:
    account = db.get(Account, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/{account_id}/transactions", response_model=list[TransactionRead])
def account_transactions(
    account_id: uuid.UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[Transaction]:
    if db.get(Account, account_id) is None:
        raise HTTPException(status_code=404, detail="Account not found")
    statement = (
        select(Transaction)
        .where(
            or_(
                Transaction.source_account_id == account_id,
                Transaction.destination_account_id == account_id,
            )
        )
        .order_by(Transaction.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(statement))
