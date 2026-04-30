"""
app.py - terminal UI for the airline booking application.

Run with:

    python app.py

Make sure the schema is loaded first:

    psql -d airline -f schema.sql
"""

from datetime import datetime, date
from decimal import Decimal

import auth
import payments
import search
import bookings


# ----- tiny input helpers -----

def prompt(msg, default=None):
    suffix = f" [{default}]" if default else ""
    val = input(f"{msg}{suffix}: ").strip()
    return val or (default or "")


def prompt_optional(msg):
    val = input(f"{msg} (blank to skip): ").strip()
    return val or None


def prompt_int(msg, default=None):
    while True:
        val = prompt(msg, str(default) if default is not None else None)
        if not val:
            return default
        try:
            return int(val)
        except ValueError:
            print("  Please enter a whole number.")


def prompt_float(msg):
    val = input(f"{msg} (blank to skip): ").strip()
    if not val:
        return None
    try:
        return float(val)
    except ValueError:
        print("  Not a number - skipping.")
        return None


def prompt_date(msg):
    while True:
        val = prompt(f"{msg} (YYYY-MM-DD)")
        try:
            return datetime.strptime(val, "%Y-%m-%d").date()
        except ValueError:
            print("  Bad date format. Try again.")


def fmt_dur(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h}h{m:02d}m"


def fmt_price(p):
    return "-" if p is None else f"${Decimal(p):,.2f}"


# ----- screens -----

def screen_register():
    print("\n--- Register ---")
    name = prompt("Full name")
    email = prompt("Email")
    if auth.email_exists(email):
        print("That email is already registered.")
        return None
    home = prompt_optional("Home airport IATA code")
    cust_id = auth.register(name, email, home.upper() if home else None)
    print(f"Welcome, {name}! (cust_id={cust_id})")
    return auth.login(email)


def screen_login():
    print("\n--- Log in ---")
    email = prompt("Email")
    user = auth.login(email)
    if not user:
        print("No account with that email. Try registering.")
        return None
    print(f"Hello, {user['name']}.")
    return user


def screen_payment(user):
    while True:
        print("\n--- Payment & Address ---")
        print(" 1) List addresses")
        print(" 2) Add address")
        print(" 3) Modify address")
        print(" 4) Delete address")
        print(" 5) List cards")
        print(" 6) Add card")
        print(" 7) Modify card")
        print(" 8) Delete card")
        print(" 0) Back")
        choice = prompt("Choice")

        if choice == "1":
            addrs = payments.list_addresses(user["cust_id"])
            if not addrs:
                print("  (no addresses on file)")
            for a in addrs:
                print(f"  [{a['addr_id']}] {a['name']} - "
                      f"{a['addr_line1']}, {a['city']}, {a['state']} "
                      f"{a['zip']}, {a['country']}")
        elif choice == "2":
            payments.add_address(
                user["cust_id"],
                prompt("Name on address"),
                prompt("Line 1"),
                prompt_optional("Line 2"),
                prompt("City"),
                prompt("State / Province"),
                prompt("Country"),
                prompt("ZIP / Postal code"),
            )
            print("Added.")
        elif choice == "3":
            addr_id = prompt_int("Address ID to modify")
            print("Leave blank to keep existing value.")
            fields = {}
            for field, label in [("name", "Name"), ("addr_line1", "Line 1"),
                                  ("addr_line2", "Line 2"), ("city", "City"),
                                  ("state", "State / Province"),
                                  ("country", "Country"), ("zip", "ZIP / Postal code")]:
                val = prompt_optional(label)
                if val:
                    fields[field] = val
            if payments.update_address(addr_id, user["cust_id"], **fields):
                print("Address updated.")
            else:
                print("Address not found or nothing changed.")
        elif choice == "4":
            addr_id = prompt_int("Address ID to delete")
            ok, msg = payments.delete_address(addr_id, user["cust_id"])
            print(msg)
        elif choice == "5":
            cards = payments.list_cards(user["cust_id"])
            if not cards:
                print("  (no cards on file)")
            for c in cards:
                masked = "*" * (len(c["card_number"]) - 4) + c["card_number"][-4:]
                print(f"  {masked}  exp {c['exp_date']}  "
                      f"name {c['name']}  addr#{c['addr_id']}")
        elif choice == "6":
            ok, msg = payments.add_card(
                user["cust_id"],
                prompt("Card number"),
                prompt_int("Billing address ID"),
                prompt("Name on card"),
                prompt("Security code"),
                prompt("Expiration (YYYY-MM-DD)"),
            )
            print(msg)
        elif choice == "7":
            num = prompt("Card number to modify")
            print("Leave blank to keep existing value.")
            fields = {}
            for field, label in [("name", "Name on card"),
                                  ("security_code", "Security code"),
                                  ("exp_date", "Expiration (YYYY-MM-DD)")]:
                val = prompt_optional(label)
                if val:
                    fields[field] = val
            new_addr = prompt_int("New billing address ID (blank to keep)")
            if new_addr is not None:
                fields["addr_id"] = new_addr
            _, msg = payments.update_card(num, user["cust_id"], **fields)
            print(msg)
        elif choice == "8":
            num = prompt("Card number to delete")
            print("Deleted." if payments.delete_card(num, user["cust_id"])
                  else "Not found.")
        elif choice == "0":
            return


def _print_connection(idx, conn):
    legs = conn["legs"]
    label = "DIRECT" if len(legs) == 1 else f"{len(legs) - 1}-STOP"
    print(f"\n  [{idx}] {label}  "
          f"depart {legs[0]['depart_time'].strftime('%H:%M')}  "
          f"arrive {legs[-1]['arrive_time'].strftime('%H:%M')}  "
          f"({fmt_dur(conn['total_duration_min'])})")
    print(f"      eco {fmt_price(conn['eco_price'])}   "
          f"first {fmt_price(conn['first_price'])}")
    for leg in legs:
        print(f"      {leg['airline_code']}{leg['flight_num']}  "
              f"{leg['origin_iata']}->{leg['destination_iata']}  "
              f"{leg['depart_time'].strftime('%H:%M')}-"
              f"{leg['arrive_time'].strftime('%H:%M')}  "
              f"({fmt_dur(leg['duration_min'])})")


def screen_search_and_book(user):
    print("\n--- Search Flights ---")
    origin = prompt("Origin IATA",
                    user.get("home_iata") or "").upper()
    destination = prompt("Destination IATA").upper()
    out_date = prompt_date("Departure date")

    round_trip = prompt("Round trip? (y/N)").lower().startswith("y")
    return_date = prompt_date("Return date") if round_trip else None

    max_minutes = prompt_int("Max trip length in minutes (blank=any)")
    max_price   = prompt_float("Max price")
    limit       = prompt_int("Max results to show")
    order_by    = prompt("Order by (price/duration)", "price")

    if round_trip:
        results = search.search_round_trip(
            origin, destination, out_date, return_date,
            max_total_minutes=max_minutes, max_price=max_price,
            limit=limit, order_by=order_by,
        )
        if not results:
            print("\nNo round-trip itineraries found.")
            return
        for i, pair in enumerate(results, 1):
            print(f"\n=== Itinerary {i} - "
                  f"total {fmt_dur(pair['total_duration_min'])}, "
                  f"eco {fmt_price(pair['eco_price'])}, "
                  f"first {fmt_price(pair['first_price'])} ===")
            print("  OUTBOUND:")
            _print_connection(0, pair["outbound"])
            print("  RETURN:")
            _print_connection(0, pair["return"])
        chosen = prompt_int("Book itinerary number (0 to cancel)", 0)
        if chosen and 1 <= chosen <= len(results):
            pair = results[chosen - 1]
            _book_flow(user, pair["outbound"]["legs"] + pair["return"]["legs"])
    else:
        results = search.search_connections(
            origin, destination, out_date,
            max_total_minutes=max_minutes, max_price=max_price,
            limit=limit, order_by=order_by,
        )
        if not results:
            print("\nNo connections found.")
            return
        for i, conn in enumerate(results, 1):
            _print_connection(i, conn)
        chosen = prompt_int("\nBook connection number (0 to cancel)", 0)
        if chosen and 1 <= chosen <= len(results):
            _book_flow(user, results[chosen - 1]["legs"])


def _book_flow(user, legs):
    cabin = prompt("Cabin (first/economy)", "economy").lower()
    if cabin not in ("first", "economy"):
        print("Cancelled.")
        return

    cards = payments.list_cards(user["cust_id"])
    if not cards:
        print("You have no cards on file. Add one first.")
        return
    print("\nYour cards:")
    for i, c in enumerate(cards, 1):
        masked = "*" * (len(c["card_number"]) - 4) + c["card_number"][-4:]
        print(f"  [{i}] {masked} - {c['name']}")
    pick = prompt_int("Use card #", 1)
    if pick is None or not (1 <= pick <= len(cards)):
        print("Cancelled.")
        return

    confirm = prompt("Confirm booking? (y/N)").lower()
    if not confirm.startswith("y"):
        print("Cancelled.")
        return

    try:
        book_id = bookings.book_connection(
            user["cust_id"], cards[pick - 1]["card_number"], legs, cabin,
        )
        print(f"\nBooked! Confirmation #{book_id}")
    except Exception as e:
        print(f"Booking failed: {e}")


def screen_manage_bookings(user):
    print("\n--- Your Bookings ---")
    bks = bookings.list_bookings(user["cust_id"])
    if not bks:
        print("(none)")
        return
    for bk in bks:
        print(f"\n  Booking #{bk['book_id']} - "
              f"booked {bk['booked_at'].strftime('%Y-%m-%d %H:%M')}, "
              f"total {fmt_price(bk['total_paid'])}")
        for s in bk["segments"]:
            print(f"    leg {s['seg_num']}: "
                  f"{s['airline_code']}{s['flight_num']}  "
                  f"{s['origin_iata']}->{s['destination_iata']}  "
                  f"{s['depart_time'].strftime('%Y-%m-%d %H:%M')}  "
                  f"seat {s['seat']} ({s['cabin']})  "
                  f"{fmt_price(s['fare_paid'])}")
    cancel_id = prompt_int("\nCancel booking # (0 to skip)", 0)
    if cancel_id:
        ok = bookings.cancel_booking(cancel_id, user["cust_id"])
        print("Cancelled." if ok else "Not found.")


# ----- main loop -----

def main():
    print("=" * 50)
    print("  Airline Flight Booking - CS 425 Project")
    print("=" * 50)

    user = None
    while True:
        if not user:
            print("\n 1) Log in")
            print(" 2) Register")
            print(" 0) Quit")
            c = prompt("Choice")
            if c == "1":
                user = screen_login()
            elif c == "2":
                user = screen_register()
            elif c == "0":
                break
        else:
            print(f"\nLogged in as {user['name']} ({user['email']})")
            print(" 1) Search & book flights")
            print(" 2) Manage payment / addresses")
            print(" 3) View / cancel bookings")
            print(" 9) Log out")
            print(" 0) Quit")
            c = prompt("Choice")
            if c == "1":
                screen_search_and_book(user)
            elif c == "2":
                screen_payment(user)
            elif c == "3":
                screen_manage_bookings(user)
            elif c == "9":
                user = None
            elif c == "0":
                break
    print("Goodbye.")


if __name__ == "__main__":
    main()
