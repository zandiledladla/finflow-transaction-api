import uuid
from decimal import Decimal
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction, TransactionStatus, TransactionType


class TransactionError(ValueError):
    pass


def _fingerprint(*parts: object) -> str:
    canonical_parts = [
        f"{part:.2f}" if isinstance(part, Decimal) else "" if part is None else str(part)
        for part in parts
    ]
    canonical = "|".join(canonical_parts)
    return sha256(canonical.encode()).hexdigest()


def _existing_idempotent_transaction(
    db: Session, idempotency_key: str | None, request_fingerprint: str
) -> Transaction | None:
    if idempotency_key is None:
        return None
    transaction = db.scalar(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    )
    if transaction is not None and transaction.request_fingerprint != request_fingerprint:
        raise TransactionError("Idempotency key was already used for a different request")
    return transaction


def _commit(db: Session, transaction: Transaction) -> Transaction:
    db.add(transaction)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if transaction.idempotency_key is None:
            raise
        existing = db.scalar(
            select(Transaction).where(
                Transaction.idempotency_key == transaction.idempotency_key
            )
        )
        if existing is None or existing.request_fingerprint != transaction.request_fingerprint:
            raise TransactionError(
                "Idempotency key was already used for a different request"
            ) from exc
        return existing
    db.refresh(transaction)
    return transaction


def _locked_account(db: Session, account_id: uuid.UUID) -> Account:
    account = db.scalar(select(Account).where(Account.id == account_id).with_for_update())
    if account is None:
        raise TransactionError("Account not found")
    return account


def deposit(
    db: Session,
    account_id: uuid.UUID,
    amount: Decimal,
    reference: str | None,
    idempotency_key: str | None = None,
) -> Transaction:
    fingerprint = _fingerprint("deposit", account_id, amount, reference)
    existing = _existing_idempotent_transaction(db, idempotency_key, fingerprint)
    if existing is not None:
        return existing
    account = _locked_account(db, account_id)
    account.balance += amount
    transaction = Transaction(
        transaction_type=TransactionType.deposit,
        destination_account_id=account.id,
        amount=amount,
        currency=account.currency,
        status=TransactionStatus.completed,
        reference=reference,
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint if idempotency_key else None,
    )
    return _commit(db, transaction)


def withdraw(
    db: Session,
    account_id: uuid.UUID,
    amount: Decimal,
    reference: str | None,
    idempotency_key: str | None = None,
) -> Transaction:
    fingerprint = _fingerprint("withdrawal", account_id, amount, reference)
    existing = _existing_idempotent_transaction(db, idempotency_key, fingerprint)
    if existing is not None:
        return existing
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
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint if idempotency_key else None,
    )
    return _commit(db, transaction)


def transfer(
    db: Session,
    source_account_id: uuid.UUID,
    destination_account_id: uuid.UUID,
    amount: Decimal,
    reference: str | None,
    idempotency_key: str | None = None,
) -> Transaction:
    if source_account_id == destination_account_id:
        raise TransactionError("Source and destination accounts must be different")

    fingerprint = _fingerprint(
        "transfer", source_account_id, destination_account_id, amount, reference
    )
    existing = _existing_idempotent_transaction(db, idempotency_key, fingerprint)
    if existing is not None:
        return existing

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
        idempotency_key=idempotency_key,
        request_fingerprint=fingerprint if idempotency_key else None,
    )
    return _commit(db, transaction)
