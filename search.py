"""
search.py - flight connection search.

A "connection" is one or two flights that get a customer from origin
to destination on the requested date. Supports:

  * direct flights (1 leg)
  * one-stop connections (2 legs, second leg leaves >= MIN_LAYOVER_MIN
    after first arrives, both on the requested date)

Extend the algorithm if you want longer connections (recursive CTE
or BFS over the flight graph).

Filters supported (per spec 4.3):
  * max_total_minutes  - total trip length cap
  * max_price          - fare cap (applied to whichever cabin is cheaper)
  * limit              - max number of connections to return
  * order_by           - 'price' or 'duration'
"""

from db import query_all


MIN_LAYOVER_MIN = 45
MAX_LAYOVER_MIN = 600


_CURRENT_PRICE = """
    SELECT DISTINCT ON (airline_code, flight_num, flight_date)
           airline_code, flight_num, flight_date,
           first_price, eco_price
    FROM Price
    ORDER BY airline_code, flight_num, flight_date, effective_from DESC
"""

_SEATS_BOOKED = """
    SELECT airline_code, flight_num, flight_date,
           SUM(CASE WHEN cabin = 'first'   THEN 1 ELSE 0 END) AS booked_first,
           SUM(CASE WHEN cabin = 'economy' THEN 1 ELSE 0 END) AS booked_eco
    FROM Booking_Segment
    GROUP BY airline_code, flight_num, flight_date
"""

_FLIGHTS_ON_DATE = f"""
WITH cur_price AS ({_CURRENT_PRICE}),
     booked    AS ({_SEATS_BOOKED})
SELECT f.airline_code, f.flight_num, f.flight_date,
       f.origin_iata, f.destination_iata,
       f.depart_time, f.arrive_time,
       EXTRACT(EPOCH FROM (f.arrive_time - f.depart_time))/60
           AS duration_min,
       p.first_price, p.eco_price,
       (f.max_first - COALESCE(b.booked_first, 0)) AS first_left,
       (f.max_eco   - COALESCE(b.booked_eco,   0)) AS eco_left
FROM Flight f
JOIN cur_price p USING (airline_code, flight_num, flight_date)
LEFT JOIN booked b USING (airline_code, flight_num, flight_date)
WHERE f.flight_date = %s
"""


def search_connections(origin, destination, flight_date,
                       max_total_minutes=None, max_price=None,
                       limit=None, order_by="price"):
    """
    Return a list of connections. Each connection is a dict with:
        legs                : list of flight dicts
        total_duration_min  : int (incl. layover)
        eco_price           : Decimal | None  (None if any leg is full in eco)
        first_price         : Decimal | None
        depart_time         : datetime
        arrive_time         : datetime
    """
    if order_by not in ("price", "duration"):
        order_by = "price"

    all_flights = [dict(r) for r in query_all(_FLIGHTS_ON_DATE, (flight_date,))]

    by_origin = {}
    for f in all_flights:
        by_origin.setdefault(f["origin_iata"], []).append(f)

    connections = []

    # direct
    for f in by_origin.get(origin, []):
        if f["destination_iata"] == destination:
            connections.append(_build_conn([f]))

    # one-stop
    for f1 in by_origin.get(origin, []):
        if f1["destination_iata"] == destination:
            continue
        for f2 in by_origin.get(f1["destination_iata"], []):
            if f2["destination_iata"] != destination:
                continue
            layover = (f2["depart_time"] - f1["arrive_time"]).total_seconds() / 60
            if MIN_LAYOVER_MIN <= layover <= MAX_LAYOVER_MIN:
                connections.append(_build_conn([f1, f2]))

    def passes(c):
        if max_total_minutes is not None and c["total_duration_min"] > max_total_minutes:
            return False
        if max_price is not None:
            prices = [p for p in (c["eco_price"], c["first_price"]) if p is not None]
            if not prices or min(prices) > max_price:
                return False
        return not (c["eco_price"] is None and c["first_price"] is None)

    connections = [c for c in connections if passes(c)]

    if order_by == "price":
        connections.sort(
            key=lambda c: c["eco_price"] if c["eco_price"] is not None
            else c["first_price"]
        )
    else:
        connections.sort(key=lambda c: c["total_duration_min"])

    if limit is not None:
        connections = connections[:limit]
    return connections


def _build_conn(legs):
    total_min = (legs[-1]["arrive_time"] - legs[0]["depart_time"]).total_seconds() / 60

    eco_price = sum(l["eco_price"] for l in legs) \
        if all(l["eco_left"] > 0 for l in legs) else None
    first_price = sum(l["first_price"] for l in legs) \
        if all(l["first_left"] > 0 for l in legs) else None

    return {
        "legs": legs,
        "total_duration_min": int(total_min),
        "eco_price": eco_price,
        "first_price": first_price,
        "depart_time": legs[0]["depart_time"],
        "arrive_time": legs[-1]["arrive_time"],
    }


def search_round_trip(origin, destination, out_date, return_date, **kwargs):
    """
    Return pairs of (outbound, return) connections. Filters/sort apply
    to the COMBINED itinerary.
    """
    max_total = kwargs.pop("max_total_minutes", None)
    max_price = kwargs.pop("max_price", None)
    order_by  = kwargs.pop("order_by", "price")
    limit     = kwargs.pop("limit", None)

    out  = search_connections(origin, destination, out_date, order_by=order_by)
    back = search_connections(destination, origin, return_date, order_by=order_by)

    pairs = []
    for o in out:
        for b in back:
            total_min = o["total_duration_min"] + b["total_duration_min"]
            eco = (o["eco_price"] + b["eco_price"]
                   if o["eco_price"] is not None and b["eco_price"] is not None
                   else None)
            first = (o["first_price"] + b["first_price"]
                     if o["first_price"] is not None and b["first_price"] is not None
                     else None)
            if eco is None and first is None:
                continue
            if max_total is not None and total_min > max_total:
                continue
            if max_price is not None:
                prices = [p for p in (eco, first) if p is not None]
                if not prices or min(prices) > max_price:
                    continue
            pairs.append({
                "outbound": o,
                "return":   b,
                "total_duration_min": total_min,
                "eco_price":   eco,
                "first_price": first,
            })

    if order_by == "price":
        pairs.sort(key=lambda p: p["eco_price"]
                   if p["eco_price"] is not None else p["first_price"])
    else:
        pairs.sort(key=lambda p: p["total_duration_min"])

    if limit is not None:
        pairs = pairs[:limit]
    return pairs
