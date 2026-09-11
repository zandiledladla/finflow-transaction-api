import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.transaction import TransactionStatus, TransactionType


class MoneyOperation(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    reference: str | None = Field(default=None, max_length=140)


class TransferCreate(MoneyOperation):
    source_account_id: uuid.UUID
    destination_account_id: uuid.UUID


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    transaction_type: TransactionType
    source_account_id: uuid.UUID | None
    destination_account_id: uuid.UUID | None
    amount: Decimal
    currency: str
    status: TransactionStatus
    reference: str | None
    created_at: datetime
