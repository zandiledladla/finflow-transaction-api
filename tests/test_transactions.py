from decimal import Decimal


def create_customer(client, name: str, email: str) -> dict:
    response = client.post("/api/v1/customers", json={"full_name": name, "email": email})
    assert response.status_code == 201
    return response.json()


def create_account(client, customer_id: str, currency: str = "ZAR") -> dict:
    response = client.post(
        "/api/v1/accounts", json={"customer_id": customer_id, "currency": currency}
    )
    assert response.status_code == 201
    return response.json()


def test_customer_email_must_be_unique(client):
    create_customer(client, "Zandile Dladla", "zandile@example.com")
    duplicate = client.post(
        "/api/v1/customers",
        json={"full_name": "Another Person", "email": "ZANDILE@example.com"},
    )

    assert duplicate.status_code == 409


def test_deposit_and_withdrawal_update_balance(client):
    customer = create_customer(client, "Zandile Dladla", "zandile@example.com")
    account = create_account(client, customer["id"])

    deposit = client.post(
        f"/api/v1/transactions/accounts/{account['id']}/deposit",
        json={"amount": "500.00", "reference": "Initial funding"},
    )
    withdrawal = client.post(
        f"/api/v1/transactions/accounts/{account['id']}/withdraw",
        json={"amount": "125.50", "reference": "Purchase"},
    )
    current = client.get(f"/api/v1/accounts/{account['id']}")

    assert deposit.status_code == 200
    assert withdrawal.status_code == 200
    assert Decimal(current.json()["balance"]) == Decimal("374.50")


def test_transfer_is_atomic_and_updates_both_balances(client):
    sender = create_customer(client, "Sender", "sender@example.com")
    recipient = create_customer(client, "Recipient", "recipient@example.com")
    source = create_account(client, sender["id"])
    destination = create_account(client, recipient["id"])
    client.post(f"/api/v1/transactions/accounts/{source['id']}/deposit", json={"amount": "1000.00"})

    transfer = client.post(
        "/api/v1/transactions/transfer",
        json={
            "source_account_id": source["id"],
            "destination_account_id": destination["id"],
            "amount": "250.00",
            "reference": "Test transfer",
        },
    )

    assert transfer.status_code == 200
    assert Decimal(client.get(f"/api/v1/accounts/{source['id']}").json()["balance"]) == Decimal(
        "750.00"
    )
    assert Decimal(
        client.get(f"/api/v1/accounts/{destination['id']}").json()["balance"]
    ) == Decimal("250.00")


def test_insufficient_funds_does_not_change_balances(client):
    sender = create_customer(client, "Sender", "sender@example.com")
    recipient = create_customer(client, "Recipient", "recipient@example.com")
    source = create_account(client, sender["id"])
    destination = create_account(client, recipient["id"])

    response = client.post(
        "/api/v1/transactions/transfer",
        json={
            "source_account_id": source["id"],
            "destination_account_id": destination["id"],
            "amount": "50.00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient funds"
    assert Decimal(client.get(f"/api/v1/accounts/{source['id']}").json()["balance"]) == 0
    assert Decimal(client.get(f"/api/v1/accounts/{destination['id']}").json()["balance"]) == 0


def test_rejects_transfer_between_different_currencies(client):
    first = create_customer(client, "First", "first@example.com")
    second = create_customer(client, "Second", "second@example.com")
    zar_account = create_account(client, first["id"], "ZAR")
    eur_account = create_account(client, second["id"], "EUR")
    client.post(
        f"/api/v1/transactions/accounts/{zar_account['id']}/deposit",
        json={"amount": "100.00"},
    )

    response = client.post(
        "/api/v1/transactions/transfer",
        json={
            "source_account_id": zar_account["id"],
            "destination_account_id": eur_account["id"],
            "amount": "20.00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Accounts must use the same currency"


def test_account_statement_contains_related_transactions(client):
    customer = create_customer(client, "Statement User", "statement@example.com")
    account = create_account(client, customer["id"])
    client.post(
        f"/api/v1/transactions/accounts/{account['id']}/deposit",
        json={"amount": "300.00", "reference": "Salary"},
    )
    client.post(
        f"/api/v1/transactions/accounts/{account['id']}/withdraw",
        json={"amount": "50.00", "reference": "Groceries"},
    )

    response = client.get(f"/api/v1/accounts/{account['id']}/transactions")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {item["reference"] for item in response.json()} == {"Salary", "Groceries"}
