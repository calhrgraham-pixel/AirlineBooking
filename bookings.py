"""
bookings.py - create, list, and cancel bookings.

A booking groups one or more flight legs (Booking_Segment rows) under
a single Booking row. Cancelling a booking deletes its segments via
ON DELETE CASCADE on Booking_Segment, freeing the seats.

Seat assignment is intentionally simple: pick the lowest-numbered seat
not yet taken on that flight, in the requested cabin. Extend
_pick_seat() if you want a real seat map.
"""

from db import get_cursor, query_all


def _pick_seat(cur, airline_code, flight_num, flight_date, cabin):
    """
    Find an unused seat label for this flight + cabin.
    Convention: 'first' = rows 1-3, 'economy' = rows 10-49.
    """
    cur.execute(
        """
        SELECT seat FROM Booking_Segment
        WHERE airline_code = %s AND flight_num = %s AND flight_date = %s
        """,
        (airline_code, flight_num, flight_date),
    )
    taken = {r["seat"] for r in cur.fetchall()}

    rows = range(1, 4) if cabin == "first" else range(10, 50)
    for r in rows:
        for letter in "ABCDEF":
            seat = f"{r}{letter}"
            if seat not in taken:
                return seat
    raise RuntimeError("No seats available")


def book_connection(cust_id, card_number, legs, cabin):
    """
    Create a booking for the given list of flight legs (each a dict with
    keys airline_code, flight_num, flight_date, eco_price, first_price).
    Returns the new book_id. All segments share the same cabin.
    """
    if cabin not in ("first", "economy"):
        raise ValueError("cabin must be 'first' or 'economy'")

    price_key = "first_price" if cabin == "first" else "eco_price"
    total = sum(leg[price_key] for leg in legs)

    with get_cursor(commit=True) as (_, cur):
        cur.execute(
            """
            INSERT INTO Booking (cust_id, card_number, total_paid)
            VALUES (%s, %s, %s)
            RETURNING book_id
            """,
            (cust_id, card_number, total),
        )
        book_id = cur.fetchone()["book_id"]

        for i, leg in enumerate(legs, start=1):
            seat = _pick_seat(cur,
                              leg["airline_code"],
                              leg["flight_num"],
                              leg["flight_date"],
                              cabin)
            cur.execute(
                """
                INSERT INTO Booking_Segment
                    (book_id, seg_num, airline_code, flight_num,
                     flight_date, seat, cabin, fare_paid)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (book_id, i,
                 leg["airline_code"], leg["flight_num"], leg["flight_date"],
                 seat, cabin, leg[price_key]),
            )
        return book_id


def list_bookings(cust_id):
    """Return all bookings for a customer along with their segments."""
    bks = [dict(r) for r in query_all(
        """
        SELECT book_id, booked_at, total_paid, card_number
        FROM Booking
        WHERE cust_id = %s
        ORDER BY booked_at DESC
        """,
        (cust_id,),
    )]
    for bk in bks:
        bk["segments"] = [dict(r) for r in query_all(
            """
            SELECT seg_num, airline_code, flight_num, flight_date,
                   seat, cabin, fare_paid,
                   f.origin_iata, f.destination_iata,
                   f.depart_time, f.arrive_time
            FROM Booking_Segment bs
            JOIN Flight f USING (airline_code, flight_num, flight_date)
            WHERE bs.book_id = %s
            ORDER BY seg_num
            """,
            (bk["book_id"],),
        )]
    return bks


def cancel_booking(book_id, cust_id):
    """Delete a booking. Cascades to segments, releasing the seats."""
    with get_cursor(commit=True) as (_, cur):
        cur.execute(
            "DELETE FROM Booking WHERE book_id = %s AND cust_id = %s",
            (book_id, cust_id),
        )
        return cur.rowcount > 0
