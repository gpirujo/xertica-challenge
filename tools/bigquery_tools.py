from datetime import date


def get_latest_transactions(customer_id: str, days: int = 90) -> list[dict]:
    return [
        {
            "transaction_id": "TXN-0001",
            "customer_id": customer_id,
            "date": date(2024, 11, 3).isoformat(),
            "amount_usd": 48500.00,
            "currency": "USD",
            "type": "wire_transfer",
            "counterparty_country": "PA",  # Panama
            "channel": "swift",
            "is_flagged": True,
        },
        {
            "transaction_id": "TXN-0002",
            "customer_id": customer_id,
            "date": date(2024, 11, 7).isoformat(),
            "amount_usd": 9800.00,
            "currency": "COP",
            "type": "cash_deposit",
            "counterparty_country": "CO",  # Colombia
            "channel": "branch",
            "is_flagged": False,
        },
        {
            "transaction_id": "TXN-0003",
            "customer_id": customer_id,
            "date": date(2024, 11, 12).isoformat(),
            "amount_usd": 125000.00,
            "currency": "USD",
            "type": "wire_transfer",
            "counterparty_country": "VG",  # British Virgin Islands (offshore)
            "channel": "swift",
            "is_flagged": True,
        },
        {
            "transaction_id": "TXN-0004",
            "customer_id": customer_id,
            "date": date(2024, 11, 15).isoformat(),
            "amount_usd": 3200.00,
            "currency": "MXN",
            "type": "pos_payment",
            "counterparty_country": "MX",  # Mexico
            "channel": "card",
            "is_flagged": False,
        },
        {
            "transaction_id": "TXN-0005",
            "customer_id": customer_id,
            "date": date(2024, 11, 18).isoformat(),
            "amount_usd": 74900.00,
            "currency": "USD",
            "type": "wire_transfer",
            "counterparty_country": "KY",  # Cayman Islands (offshore)
            "channel": "swift",
            "is_flagged": True,
        },
        {
            "transaction_id": "TXN-0006",
            "customer_id": customer_id,
            "date": date(2024, 11, 21).isoformat(),
            "amount_usd": 1500.00,
            "currency": "PEN",
            "type": "cash_withdrawal",
            "counterparty_country": "PE",  # Peru
            "channel": "atm",
            "is_flagged": False,
        },
        {
            "transaction_id": "TXN-0007",
            "customer_id": customer_id,
            "date": date(2024, 11, 25).isoformat(),
            "amount_usd": 22000.00,
            "currency": "USD",
            "type": "international_transfer",
            "counterparty_country": "CO",  # Colombia
            "channel": "online_banking",
            "is_flagged": False,
        },
        {
            "transaction_id": "TXN-0008",
            "customer_id": customer_id,
            "date": date(2024, 11, 28).isoformat(),
            "amount_usd": 9950.00,
            "currency": "USD",
            "type": "cash_deposit",
            "counterparty_country": "US",
            "channel": "branch",
            "is_flagged": True,  # structuring suspicion (just under $10k)
        },
        {
            "transaction_id": "TXN-0009",
            "customer_id": customer_id,
            "date": date(2024, 12, 2).isoformat(),
            "amount_usd": 310000.00,
            "currency": "USD",
            "type": "wire_transfer",
            "counterparty_country": "PA",  # Panama
            "channel": "swift",
            "is_flagged": True,
        },
        {
            "transaction_id": "TXN-0010",
            "customer_id": customer_id,
            "date": date(2024, 12, 5).isoformat(),
            "amount_usd": 680.00,
            "currency": "COP",
            "type": "mobile_transfer",
            "counterparty_country": "CO",
            "channel": "app",
            "is_flagged": False,
        },
        {
            "transaction_id": "TXN-0011",
            "customer_id": customer_id,
            "date": date(2024, 12, 9).isoformat(),
            "amount_usd": 55000.00,
            "currency": "USD",
            "type": "wire_transfer",
            "counterparty_country": "MX",  # Mexico
            "channel": "swift",
            "is_flagged": False,
        },
        {
            "transaction_id": "TXN-0012",
            "customer_id": customer_id,
            "date": date(2024, 12, 14).isoformat(),
            "amount_usd": 18750.00,
            "currency": "USD",
            "type": "check_deposit",
            "counterparty_country": "PE",  # Peru
            "channel": "branch",
            "is_flagged": False,
        },
    ]
