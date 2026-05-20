from datetime import date


def get_alert_data(alert_id: str) -> dict:
    alert_types = ["structuring", "unusual_wire", "pep_transaction", "high_volume", "offshore_transfer"]
    severities = ["low", "medium", "high"]
    customer_ids = ["CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005"]
    created_dates = ["2024-11-01", "2024-11-15", "2024-12-01", "2024-12-10", "2025-01-05"]

    descriptions = {
        "structuring": (
            "Multiple cash deposits just below reporting thresholds detected within 30 days. "
            "Pattern is consistent with structuring to avoid CTR requirements."
        ),
        "unusual_wire": (
            "Wire transfer to a jurisdiction with elevated AML risk flagged outside the customer's normal transaction pattern. "
            "No apparent business justification on file."
        ),
        "pep_transaction": (
            "Transaction involving a counterparty identified as a politically exposed person or a related entity. "
            "Enhanced due diligence is required."
        ),
        "high_volume": (
            "Unusually high cumulative transaction volume detected over the past 90 days, "
            "significantly exceeding the customer's historical average."
        ),
        "offshore_transfer": (
            "Transfer to an offshore jurisdiction with limited transparency. "
            "Recipient entity has no apparent business relationship on file."
        ),
    }

    h = hash(alert_id)
    alert_type = alert_types[h % len(alert_types)]
    return {
        "alert_id": alert_id,
        "customer_id": customer_ids[h % len(customer_ids)],
        "alert_type": alert_type,
        "description": descriptions[alert_type],
        "severity": severities[h % len(severities)],
        "created_at": created_dates[h % len(created_dates)],
    }


def get_customer_data(customer_id: str) -> dict:
    names = [
        "Valentina Ríos Herrera",
        "Andrés Felipe Morales",
        "Lucía Fernanda Castillo",
        "Carlos Eduardo Mendoza",
        "Gabriela Sofía Vargas",
    ]
    country_codes = ["CO", "MX", "PE"]
    risk_profiles = ["low", "medium", "high"]
    account_types = ["personal", "business"]
    since_years = [2010, 2014, 2017, 2019, 2022]

    h = hash(customer_id)
    return {
        "customer_id": customer_id,
        "name": names[h % len(names)],
        "country_code": country_codes[h % len(country_codes)],
        "risk_profile": risk_profiles[h % len(risk_profiles)],
        "is_pep": (h % 7) == 0,
        "account_type": account_types[h % len(account_types)],
        "since_year": since_years[h % len(since_years)],
    }


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
