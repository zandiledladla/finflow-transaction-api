import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction, TransactionStatus, TransactionType


class TransactionError(ValueError):
    pass


def _locked_account(db: Session, account_id: uuid.UUID) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account is None:
        raise TransactionError("Account not found")
    return account


def deposit(
    db: Session, account_id: uuid.UUID, amount: Decimal, reference: str | None
) -> Transaction:
    account = _locked_account(db, account_id)
    account.balance += amount
    transaction = Transaction(
        transaction_type=TransactionType.deposit,
        destination_account_id=account.id,
        amount=amount,
        currency=account.currency,
        status=TransactionStatus.completed,
        reference=reference,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def withdraw(
    db: Session, account_id: uuid.UUID, amount: Decimal, reference: str | None
) -> Transaction:
    account = _locked_account(db, account_id)
    if account.balance < amount:
        raise TransactionError("Insufficient funds")
    account.balance -= amount
    transaction = Transaction(
        transaction_type=TransactionType.withdrawal,
        source_account_id=account.id,
        amount=amount,
        currency=account.currency,
        status=TransactionStatus.completed,
        reference=reference,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def transfer(
    db: Session,
    source_account_id: uuid.UUID,
    destination_account_id: uuid.UUID,
    amount: Decimal,
    reference: str | None,
) -> Transaction:
    if source_account_id == destination_account_id:
        raise TransactionError("Source and destination accounts must be different")

    # Lock in deterministic order to reduce deadlock risk.
    ids = sorted([source_account_id, destination_account_id], key=str)
    locked = {
        account.id: account for account in (_locked_account(db, account_id) for account_id in ids)
    }
    source = locked[source_account_id]
    destination = locked[destination_account_id]

    if source.currency != destination.currency:
        raise TransactionError("Accounts must use the same currency")
    if source.balance < amount:
        raise TransactionError("Insufficient funds")

    source.balance -= amount
    destination.balance += amount
    transaction = Transaction(
        transaction_type=TransactionType.transfer,
        source_account_id=source.id,
        destination_account_id=destination.id,
        amount=amount,
        currency=source.currency,
        status=TransactionStatus.completed,
        reference=reference,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
