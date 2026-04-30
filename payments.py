"""
payments.py - manage billing addresses and credit cards.

Spec rule (section 4.2): a billing address that is the payment address
for some card cannot be deleted before that card is deleted. The FK
ON DELETE RESTRICT in schema.sql enforces this at the database level;
delete_address() catches the violation and returns a friendly message.
"""

import psycopg2
from db import get_cursor, query_all, query_one, execute, execute_returning


# ----- addresses -----

def list_addresses(cust_id):
    return [dict(r) for r in query_all(
        """
        SELECT addr_id, name, addr_line1, addr_line2,
               city, state, country, zip
        FROM Billing_Address
        WHERE cust_id = %s
        ORDER BY addr_id
        """,
        (cust_id,),
    )]


def add_address(cust_id, name, line1, line2, city, state, country, zip_code):
    row = execute_returning(
        """
        INSERT INTO Billing_Address
            (cust_id, name, addr_line1, addr_line2,
             city, state, country, zip)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING addr_id
        """,
        (cust_id, name, line1, line2, city, state, country, zip_code),
    )
    return row["addr_id"]


def update_address(addr_id, cust_id, **fields):
    """Partial update. Only updates columns explicitly passed in fields."""
    allowed = {"name", "addr_line1", "addr_line2",
               "city", "state", "country", "zip"}
    cols = [c for c in fields if c in allowed]
    if not cols:
        return False
    set_clause = ", ".join(f"{c} = %s" for c in cols)
    values = [fields[c] for c in cols] + [addr_id, cust_id]
    return execute(
        f"UPDATE Billing_Address SET {set_clause} "
        f"WHERE addr_id = %s AND cust_id = %s",
        values,
    ) > 0


def delete_address(addr_id, cust_id):
    """
    Returns (ok, message). Fails with a friendly message if a card still
    points at this address (FK is RESTRICT).
    """
    try:
        n = execute(
            "DELETE FROM Billing_Address "
            "WHERE addr_id = %s AND cust_id = %s",
            (addr_id, cust_id),
        )
        if n == 0:
            return False, "Address not found."
        return True, "Address deleted."
    except psycopg2.errors.ForeignKeyViolation:
        return False, ("Cannot delete: a credit card still uses this "
                       "address. Delete the card first.")


# ----- cards -----

def list_cards(cust_id):
    return [dict(r) for r in query_all(
        """
        SELECT c.card_number, c.name, c.exp_date, c.addr_id,
               a.addr_line1, a.city, a.state, a.country, a.zip
        FROM Card c
        JOIN Billing_Address a ON a.addr_id = c.addr_id
        WHERE c.cust_id = %s
        ORDER BY c.exp_date
        """,
        (cust_id,),
    )]


def add_card(cust_id, card_number, addr_id, name, security_code, exp_date):
    row = query_one(
        "SELECT 1 FROM Billing_Address WHERE addr_id = %s AND cust_id = %s",
        (addr_id, cust_id),
    )
    if not row:
        return False, f"Billing address ID {addr_id} does not exist or does not belong to your account. Add an address first (option 2)."
    try:
        execute(
            """
            INSERT INTO Card (card_number, cust_id, addr_id,
                              name, security_code, exp_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (card_number, cust_id, addr_id, name, security_code, exp_date),
        )
        return True, "Card added."
    except psycopg2.errors.ForeignKeyViolation:
        return False, f"Billing address ID {addr_id} does not exist. Add an address first (option 2)."


def update_card(card_number, cust_id, **fields):
    """Partial update. Allowed fields: name, security_code, exp_date, addr_id."""
    allowed = {"name", "security_code", "exp_date", "addr_id"}
    cols = [c for c in fields if c in allowed]
    if not cols:
        return False, "Nothing to update."
    if "addr_id" in fields:
        row = query_one(
            "SELECT 1 FROM Billing_Address WHERE addr_id = %s AND cust_id = %s",
            (fields["addr_id"], cust_id),
        )
        if not row:
            return False, f"Address ID {fields['addr_id']} does not exist or does not belong to your account."
    set_clause = ", ".join(f"{c} = %s" for c in cols)
    values = [fields[c] for c in cols] + [card_number, cust_id]
    updated = execute(
        f"UPDATE Card SET {set_clause} WHERE card_number = %s AND cust_id = %s",
        values,
    )
    return (True, "Card updated.") if updated else (False, "Card not found.")


def delete_card(card_number, cust_id):
    return execute(
        "DELETE FROM Card WHERE card_number = %s AND cust_id = %s",
        (card_number, cust_id),
    ) > 0
