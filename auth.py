"""
auth.py - register and "log in" by email.

The spec doesn't require passwords; email identifies a customer.
For a real app you'd add password hashing (bcrypt/argon2) - left as
an extension point.
"""

from db import query_one, execute_returning


def register(name, email, home_iata):
    """Create a new customer. Returns the new cust_id."""
    row = execute_returning(
        """
        INSERT INTO Customer (name, email, home_iata)
        VALUES (%s, %s, %s)
        RETURNING cust_id
        """,
        (name.strip(), email.strip().lower(), home_iata),
    )
    return row["cust_id"]


def login(email):
    """Return the customer row for this email, or None."""
    row = query_one(
        "SELECT cust_id, name, email, home_iata "
        "FROM Customer WHERE email = %s",
        (email.strip().lower(),),
    )
    return dict(row) if row else None


def email_exists(email):
    row = query_one(
        "SELECT 1 FROM Customer WHERE email = %s",
        (email.strip().lower(),),
    )
    return row is not None
