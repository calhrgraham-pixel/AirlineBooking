"""
db.py - PostgreSQL connection helper.

Reads connection params from environment variables with sensible defaults.
Uses RealDictCursor so query results are dict-like, which is convenient
in Jinja templates.
"""

import os
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host":     os.environ.get("DB_HOST",   "localhost"),
    "port":     os.environ.get("DB_PORT",   "5432"),
    "dbname":   os.environ.get("DB_NAME",   "Airline Booking"),
    "user":     os.environ.get("DB_USER",   "postgres"),
    "password": os.environ["DB_PASSWORD"],
}


def get_connection():
    """Open a new psycopg2 connection."""
    return psycopg2.connect(**DB_CONFIG)


@contextmanager
def get_cursor(commit=False):
    """Yield (conn, cur). Commits if commit=True; rolls back on exception."""
    conn = get_connection()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield conn, cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()
    finally:
        conn.close()


def query_all(sql, params=None):
    with get_cursor() as (_, cur):
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    with get_cursor() as (_, cur):
        cur.execute(sql, params or ())
        return cur.fetchone()


def execute(sql, params=None):
    with get_cursor(commit=True) as (_, cur):
        cur.execute(sql, params or ())
        return cur.rowcount


def execute_returning(sql, params=None):
    with get_cursor(commit=True) as (_, cur):
        cur.execute(sql, params or ())
        return cur.fetchone()
