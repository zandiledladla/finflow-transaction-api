"""Create a small, repeatable demonstration dataset."""

from decimal import Decimal

from sqlalchemy import select

from app.core.database import Base, SessionLocal, engine
from app.models.account import Account
from app.models.customer import Customer
from app.services.transactions import deposit, transfer


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing = db.scalar(select(Customer).where(Customer.email == "zandile@finflow.demo"))
        if existing:
            print("Demo data already exists; no changes made.")
            return

        zandile = Customer(full_name="Zandile Dladla", email="zandile@finflow.demo")
        amanda = Customer(full_name="Amanda Ndlovu", email="amanda@finflow.demo")
        db.add_all([zandile, amanda])
        db.flush()

        source = Account(customer_id=zandile.id, currency="ZAR")
        destination = Account(customer_id=amanda.id, currency="ZAR")
        db.add_all([source, destination])
        db.commit()

        deposit(db, source.id, Decimal("1000.00"), "Initial demo funding")
        transfer(db, source.id, destination.id, Decimal("250.00"), "Demo transfer")
        print("Demo data created: ZAR 1,000 deposit and ZAR 250 transfer.")


if __name__ == "__main__":
    seed()
