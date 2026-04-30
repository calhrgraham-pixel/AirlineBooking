# Airline Booking - CS 425 Spring 2026

Terminal application skeleton for the airline flight booking project.

## Files

- `schema.sql`       - tables, indexes, sample data
- `db.py`            - PostgreSQL connection helper
- `auth.py`          - register / log in by email
- `payments.py`      - addresses & credit cards
- `search.py`        - flight & connection search
- `bookings.py`      - book and cancel
- `app.py`           - terminal menu (entry point)
- `requirements.txt` - Python deps

## Setup

1. Install Python deps:

       pip install -r requirements.txt

2. Create the database and load the schema:

       createdb airline
       psql -d airline -f schema.sql

3. Set environment variables (or accept the defaults in `db.py`):

       export DB_NAME=airline
       export DB_USER=postgres
       export DB_PASSWORD=yourpassword
       export DB_HOST=localhost
       export DB_PORT=5432

4. Run:

       python app.py

   Try logging in as `jausten@example.com` to use the seeded data.

## Schema additions vs. cs425sql.txt

Two changes were needed to satisfy the spec:

- **`Customer.home_iata`** - section 3.1 requires a home airport per
  customer.
- **`Booking_Segment`** - section 3.3 says a booking can consist of
  multiple flights. The original `Booking` table was one-flight-per-row,
  so a header `Booking` row + `Booking_Segment` rows for each leg now
  models that.

A `chk_first_gt_eco` constraint was also added to `Price` since the
spec says first-class fares must exceed economy fares for the same
flight.

## What's complete vs. stubbed

Complete:
- Registration / login by email
- Add/modify/delete addresses & cards (with the rule that an address
  used by a card cannot be deleted)
- Direct + one-stop connection search with filters and sorting
- Round-trip search
- Booking, listing, and cancellation
- Auto seat assignment

Extension points:
- Password auth in `auth.py` - add bcrypt/argon2 hashing
- Multi-stop search beyond 1 stop - extend `search_connections` with a
  recursive CTE or BFS over the flight graph
- Real seat-map UI in `bookings._pick_seat`
- Date-range search rather than exact-date
- Per-leg cabin choice (currently one cabin per booking)
- Soft deletes / audit trail
