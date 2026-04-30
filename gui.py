"""
gui.py - Tkinter desktop UI for the airline booking application.

Run with:
    python gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from decimal import Decimal

import auth
import payments
import search
import bookings


def fmt_dur(minutes):
    h, m = divmod(int(minutes), 60)
    return f"{h}h{m:02d}m"


def fmt_price(p):
    return "-" if p is None else f"${Decimal(p):,.2f}"


# ---- App Shell ----

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Airline Flight Booking - CS 425")
        self.geometry("900x650")
        self.minsize(700, 500)
        self.user = None

        container = tk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames = {}
        for F in (LoginFrame, RegisterFrame, MainFrame, SearchFrame, PaymentFrame, BookingsFrame):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(LoginFrame)

    def show_frame(self, frame_class):
        frame = self.frames[frame_class]
        if hasattr(frame, "on_show"):
            frame.on_show()
        frame.tkraise()

    def login(self, user):
        self.user = user
        self.show_frame(MainFrame)

    def logout(self):
        self.user = None
        self.show_frame(LoginFrame)


# ---- Login ----

class LoginFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padx=40, pady=40)
        self.app = app

        tk.Label(self, text="Airline Flight Booking", font=("Arial", 22, "bold")).pack(pady=(40, 5))
        tk.Label(self, text="CS 425 — Spring 2026", font=("Arial", 11), fg="gray").pack(pady=(0, 30))

        form = tk.Frame(self)
        form.pack()
        tk.Label(form, text="Email:", font=("Arial", 11)).grid(row=0, column=0, sticky="e", padx=8, pady=8)
        self.email_var = tk.StringVar()
        tk.Entry(form, textvariable=self.email_var, width=32, font=("Arial", 11)).grid(row=0, column=1, pady=8)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Log In",   command=self.do_login,                          width=14, font=("Arial", 11)).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Register", command=lambda: app.show_frame(RegisterFrame),  width=14, font=("Arial", 11)).pack(side="left", padx=6)

    def do_login(self):
        email = self.email_var.get().strip()
        if not email:
            messagebox.showerror("Error", "Please enter your email.")
            return
        user = auth.login(email)
        if not user:
            messagebox.showerror("Login Failed", "No account found with that email.")
            return
        self.email_var.set("")
        self.app.login(user)


# ---- Register ----

class RegisterFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padx=40, pady=40)
        self.app = app

        tk.Label(self, text="Create Account", font=("Arial", 18, "bold")).pack(pady=(30, 20))

        form = tk.Frame(self)
        form.pack()
        self.vars = {}
        for i, (label, key) in enumerate([
            ("Full Name", "name"),
            ("Email", "email"),
            ("Home Airport IATA (optional)", "home"),
        ]):
            tk.Label(form, text=f"{label}:", font=("Arial", 11)).grid(row=i, column=0, sticky="e", padx=8, pady=8)
            var = tk.StringVar()
            tk.Entry(form, textvariable=var, width=32, font=("Arial", 11)).grid(row=i, column=1, pady=8)
            self.vars[key] = var

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Register", command=self.do_register,                    width=14, font=("Arial", 11)).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Back",     command=lambda: app.show_frame(LoginFrame),  width=14, font=("Arial", 11)).pack(side="left", padx=6)

    def do_register(self):
        name  = self.vars["name"].get().strip()
        email = self.vars["email"].get().strip()
        home  = self.vars["home"].get().strip().upper() or None
        if not name or not email:
            messagebox.showerror("Error", "Name and email are required.")
            return
        if auth.email_exists(email):
            messagebox.showerror("Error", "That email is already registered.")
            return
        auth.register(name, email, home)
        user = auth.login(email)
        for v in self.vars.values():
            v.set("")
        messagebox.showinfo("Welcome", f"Account created! Welcome, {name}.")
        self.app.login(user)


# ---- Main Menu ----

class MainFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padx=40, pady=40)
        self.app = app

        self.welcome = tk.Label(self, text="", font=("Arial", 14))
        self.welcome.pack(pady=(30, 30))

        for text, frame_class in [
            ("Search & Book Flights", SearchFrame),
            ("Payment & Addresses",   PaymentFrame),
            ("My Bookings",           BookingsFrame),
        ]:
            tk.Button(self, text=text, width=28, font=("Arial", 12),
                      command=lambda fc=frame_class: app.show_frame(fc)).pack(pady=6)

        tk.Button(self, text="Log Out", width=28, font=("Arial", 12),
                  command=app.logout).pack(pady=25)

    def on_show(self):
        if self.app.user:
            self.welcome.config(text=f"Welcome, {self.app.user['name']}  ({self.app.user['email']})")


# ---- Search & Book ----

class SearchFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._results = []

        form_outer = tk.Frame(self, padx=20, pady=10)
        form_outer.pack(fill="x")

        tk.Label(form_outer, text="Search Flights", font=("Arial", 14, "bold")).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        self.vars = {}
        fields = [
            ("Origin IATA",               "origin"),
            ("Destination IATA",          "dest"),
            ("Departure Date (YYYY-MM-DD)", "out_date"),
            ("Return Date (YYYY-MM-DD)",  "ret_date"),
            ("Max Price",                 "max_price"),
            ("Max Trip Minutes",          "max_min"),
            ("Max Results",               "limit"),
        ]
        for i, (label, key) in enumerate(fields):
            row, col = divmod(i, 2)
            tk.Label(form_outer, text=f"{label}:").grid(row=row+1, column=col*2, sticky="e", padx=4, pady=3)
            var = tk.StringVar()
            tk.Entry(form_outer, textvariable=var, width=18).grid(row=row+1, column=col*2+1, sticky="w", padx=4, pady=3)
            self.vars[key] = var

        self.round_trip = tk.BooleanVar()
        tk.Checkbutton(form_outer, text="Round trip", variable=self.round_trip).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=4)

        self.order_var = tk.StringVar(value="price")
        order_frame = tk.Frame(form_outer)
        order_frame.grid(row=5, column=2, columnspan=2, sticky="w")
        tk.Label(order_frame, text="Sort:").pack(side="left")
        tk.Radiobutton(order_frame, text="Price",    variable=self.order_var, value="price").pack(side="left")
        tk.Radiobutton(order_frame, text="Duration", variable=self.order_var, value="duration").pack(side="left")

        btn_row = tk.Frame(form_outer)
        btn_row.grid(row=6, column=0, columnspan=4, pady=6)
        tk.Button(btn_row, text="Search",        command=self.do_search, width=12).pack(side="left", padx=5)
        tk.Button(btn_row, text="Book Selected", command=self.do_book,   width=14).pack(side="left", padx=5)
        tk.Button(btn_row, text="Back", command=lambda: app.show_frame(MainFrame), width=10).pack(side="left", padx=5)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        cols = ("#", "Type", "Depart", "Arrive", "Duration", "Economy", "First", "Route")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree.heading(col, text=col)
            width = 50 if col == "#" else (200 if col == "Route" else 90)
            self.tree.column(col, width=width, anchor="center")
        self.tree.column("Route", anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

    def _parse_date(self, s):
        try:
            return datetime.strptime(s.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None

    def _parse_float(self, s):
        try:
            return float(s.strip())
        except (ValueError, AttributeError):
            return None

    def _parse_int(self, s):
        try:
            return int(s.strip())
        except (ValueError, AttributeError):
            return None

    def do_search(self):
        origin   = self.vars["origin"].get().strip().upper()
        dest     = self.vars["dest"].get().strip().upper()
        out_date = self._parse_date(self.vars["out_date"].get())
        if not origin or not dest or not out_date:
            messagebox.showerror("Error", "Origin, destination, and departure date are required.")
            return

        max_price = self._parse_float(self.vars["max_price"].get())
        max_min   = self._parse_int(self.vars["max_min"].get())
        limit     = self._parse_int(self.vars["limit"].get())
        order_by  = self.order_var.get()

        self.tree.delete(*self.tree.get_children())
        self._results = []

        if self.round_trip.get():
            ret_date = self._parse_date(self.vars["ret_date"].get())
            if not ret_date:
                messagebox.showerror("Error", "Return date is required for round trips.")
                return
            pairs = search.search_round_trip(
                origin, dest, out_date, ret_date,
                max_total_minutes=max_min, max_price=max_price,
                limit=limit, order_by=order_by,
            )
            for i, p in enumerate(pairs, 1):
                route = " / ".join(
                    f"{l['origin_iata']}→{l['destination_iata']}"
                    for l in p["outbound"]["legs"] + p["return"]["legs"]
                )
                self.tree.insert("", "end", values=(
                    i, "Round",
                    p["outbound"]["depart_time"].strftime("%m/%d %H:%M"),
                    p["return"]["arrive_time"].strftime("%m/%d %H:%M"),
                    fmt_dur(p["total_duration_min"]),
                    fmt_price(p["eco_price"]),
                    fmt_price(p["first_price"]),
                    route,
                ))
            self._results = pairs
        else:
            conns = search.search_connections(
                origin, dest, out_date,
                max_total_minutes=max_min, max_price=max_price,
                limit=limit, order_by=order_by,
            )
            for i, c in enumerate(conns, 1):
                label = "Direct" if len(c["legs"]) == 1 else f"{len(c['legs'])-1}-Stop"
                route = " → ".join(f"{l['origin_iata']}→{l['destination_iata']}" for l in c["legs"])
                self.tree.insert("", "end", values=(
                    i, label,
                    c["depart_time"].strftime("%m/%d %H:%M"),
                    c["arrive_time"].strftime("%m/%d %H:%M"),
                    fmt_dur(c["total_duration_min"]),
                    fmt_price(c["eco_price"]),
                    fmt_price(c["first_price"]),
                    route,
                ))
            self._results = conns

        if not self._results:
            messagebox.showinfo("No Results", "No flights found matching your search.")

    def do_book(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select a flight to book.")
            return
        idx = int(self.tree.item(sel[0])["values"][0]) - 1
        result = self._results[idx]
        legs = result["outbound"]["legs"] + result["return"]["legs"] if self.round_trip.get() else result["legs"]
        BookDialog(self, self.app, legs)


class BookDialog(tk.Toplevel):
    def __init__(self, parent, app, legs):
        super().__init__(parent)
        self.app = app
        self.legs = legs
        self.title("Book Flight")
        self.grab_set()
        self.resizable(False, False)

        tk.Label(self, text="Confirm Booking", font=("Arial", 13, "bold")).pack(pady=10, padx=20)

        for leg in legs:
            tk.Label(self, text=f"  {leg['airline_code']}{leg['flight_num']}  "
                                 f"{leg['origin_iata']} → {leg['destination_iata']}  "
                                 f"{leg['depart_time'].strftime('%Y-%m-%d %H:%M')}",
                     anchor="w").pack(fill="x", padx=20)

        tk.Label(self, text="Cabin:").pack(pady=(12, 0))
        self.cabin_var = tk.StringVar(value="economy")
        f = tk.Frame(self)
        f.pack()
        tk.Radiobutton(f, text="Economy", variable=self.cabin_var, value="economy").pack(side="left", padx=10)
        tk.Radiobutton(f, text="First",   variable=self.cabin_var, value="first").pack(side="left", padx=10)

        self._cards = payments.list_cards(app.user["cust_id"])
        if not self._cards:
            tk.Label(self, text="No cards on file. Add one in Payment & Addresses.", fg="red").pack(pady=10)
            tk.Button(self, text="Close", command=self.destroy).pack(pady=5)
            return

        tk.Label(self, text="Payment card:").pack(pady=(12, 0))
        self.card_var = tk.StringVar()
        options = [f"****{c['card_number'][-4:]}  {c['name']}" for c in self._cards]
        self.card_var.set(options[0])
        ttk.Combobox(self, textvariable=self.card_var, values=options, state="readonly", width=32).pack(padx=20)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Confirm", command=self.confirm, width=12).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Cancel",  command=self.destroy, width=12).pack(side="left", padx=6)

    def confirm(self):
        cabin = self.cabin_var.get()
        options = [f"****{c['card_number'][-4:]}  {c['name']}" for c in self._cards]
        card_number = self._cards[options.index(self.card_var.get())]["card_number"]
        try:
            book_id = bookings.book_connection(self.app.user["cust_id"], card_number, self.legs, cabin)
            messagebox.showinfo("Booked!", f"Booking confirmed! Reference #{book_id}")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Booking Failed", str(e))


# ---- Payment & Addresses ----

class PaymentFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        tk.Label(self, text="Payment & Addresses", font=("Arial", 14, "bold")).pack(pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=5)

        self.addr_tab = AddressTab(nb, app)
        self.card_tab = CardTab(nb, app)
        nb.add(self.addr_tab, text="  Addresses  ")
        nb.add(self.card_tab, text="  Cards  ")

        tk.Button(self, text="Back", command=lambda: app.show_frame(MainFrame), width=12).pack(pady=8)

    def on_show(self):
        self.addr_tab.refresh()
        self.card_tab.refresh()


class AddressTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padx=10, pady=10)
        self.app = app
        self._addresses = []

        cols = ("ID", "Name", "Line 1", "City", "State", "Country", "ZIP")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140 if col == "Line 1" else 80, anchor="center")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=6)
        tk.Button(btn_frame, text="Add",     command=self.add,     width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Modify",  command=self.modify,  width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Delete",  command=self.delete,  width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Refresh", command=self.refresh, width=10).pack(side="left", padx=4)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._addresses = payments.list_addresses(self.app.user["cust_id"])
        if not self._addresses:
            self.tree.insert("", "end", values=("—", "(no addresses on file)", "", "", "", "", ""))
            return
        for a in self._addresses:
            self.tree.insert("", "end", values=(
                a["addr_id"], a["name"], a["addr_line1"],
                a["city"], a["state"], a["country"], a["zip"],
            ))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select an address first.")
            return None
        addr_id = self.tree.item(sel[0])["values"][0]
        if addr_id == "—":
            return None
        return next((a for a in self._addresses if a["addr_id"] == addr_id), None)

    def add(self):
        AddressDialog(self, self.app)

    def modify(self):
        addr = self._selected()
        if addr:
            AddressDialog(self, self.app, addr)

    def delete(self):
        addr = self._selected()
        if not addr or not messagebox.askyesno("Confirm", "Delete this address?"):
            return
        ok, msg = payments.delete_address(addr["addr_id"], self.app.user["cust_id"])
        messagebox.showinfo("Result", msg)
        self.refresh()


class AddressDialog(tk.Toplevel):
    def __init__(self, parent, app, addr=None):
        super().__init__(parent)
        self.app = app
        self.addr = addr
        self.parent_tab = parent
        self.title("Edit Address" if addr else "Add Address")
        self.grab_set()
        self.resizable(False, False)

        self.vars = {}
        form = tk.Frame(self, padx=20, pady=10)
        form.pack()
        for i, (label, key) in enumerate([
            ("Name", "name"), ("Line 1", "addr_line1"), ("Line 2", "addr_line2"),
            ("City", "city"), ("State / Province", "state"),
            ("Country", "country"), ("ZIP / Postal Code", "zip"),
        ]):
            tk.Label(form, text=f"{label}:").grid(row=i, column=0, sticky="e", padx=6, pady=4)
            var = tk.StringVar(value=addr.get(key) or "" if addr else "")
            tk.Entry(form, textvariable=var, width=30).grid(row=i, column=1, pady=4)
            self.vars[key] = var

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Save",   command=self.save,    width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=10).pack(side="left", padx=5)

    def save(self):
        vals = {k: (v.get().strip() or None) for k, v in self.vars.items()}
        if any(not vals.get(k) for k in ("name", "addr_line1", "city", "state", "country", "zip")):
            messagebox.showerror("Error", "All fields except Line 2 are required.")
            return
        if self.addr:
            payments.update_address(self.addr["addr_id"], self.app.user["cust_id"], **vals)
            messagebox.showinfo("Saved", "Address updated.")
        else:
            payments.add_address(
                self.app.user["cust_id"],
                vals["name"], vals["addr_line1"], vals["addr_line2"],
                vals["city"], vals["state"], vals["country"], vals["zip"],
            )
            messagebox.showinfo("Saved", "Address added.")
        self.parent_tab.refresh()
        self.destroy()


class CardTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, padx=10, pady=10)
        self.app = app
        self._cards = []

        cols = ("Card Number", "Name", "Expiry", "Addr ID")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=8)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150 if col == "Name" else 100, anchor="center")

        vsb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=1, column=0, columnspan=2, pady=6)
        tk.Button(btn_frame, text="Add",     command=self.add,     width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Modify",  command=self.modify,  width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Delete",  command=self.delete,  width=10).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Refresh", command=self.refresh, width=10).pack(side="left", padx=4)

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._cards = payments.list_cards(self.app.user["cust_id"])
        if not self._cards:
            self.tree.insert("", "end", values=("(no cards on file)", "", "", ""))
            return
        for c in self._cards:
            masked = "*" * (len(c["card_number"]) - 4) + c["card_number"][-4:]
            self.tree.insert("", "end", values=(masked, c["name"], str(c["exp_date"]), c["addr_id"]))

    def _selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select a card first.")
            return None
        idx = self.tree.index(sel[0])
        return self._cards[idx] if idx < len(self._cards) else None

    def add(self):
        CardDialog(self, self.app)

    def modify(self):
        card = self._selected()
        if card:
            CardDialog(self, self.app, card)

    def delete(self):
        card = self._selected()
        if not card or not messagebox.askyesno("Confirm", "Delete this card?"):
            return
        ok = payments.delete_card(card["card_number"], self.app.user["cust_id"])
        messagebox.showinfo("Result", "Card deleted." if ok else "Card not found.")
        self.refresh()


class CardDialog(tk.Toplevel):
    def __init__(self, parent, app, card=None):
        super().__init__(parent)
        self.app = app
        self.card = card
        self.parent_tab = parent
        self.title("Edit Card" if card else "Add Card")
        self.grab_set()
        self.resizable(False, False)

        self.vars = {}
        form = tk.Frame(self, padx=20, pady=10)
        form.pack()
        fields = [
            ("Card Number",            "card_number",   not card),
            ("Name on Card",           "name",          True),
            ("Security Code",          "security_code", True),
            ("Expiration (YYYY-MM-DD)","exp_date",      True),
            ("Billing Address ID",     "addr_id",       True),
        ]
        for i, (label, key, editable) in enumerate(fields):
            tk.Label(form, text=f"{label}:").grid(row=i, column=0, sticky="e", padx=6, pady=4)
            var = tk.StringVar(value=str(card.get(key, "") if card else ""))
            tk.Entry(form, textvariable=var, width=30,
                     state="normal" if editable else "readonly").grid(row=i, column=1, pady=4)
            self.vars[key] = var

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)
        tk.Button(btn_frame, text="Save",   command=self.save,    width=10).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=10).pack(side="left", padx=5)

    def save(self):
        if self.card:
            fields = {k: self.vars[k].get().strip()
                      for k in ("name", "security_code", "exp_date")
                      if self.vars[k].get().strip()}
            addr_str = self.vars["addr_id"].get().strip()
            if addr_str:
                try:
                    fields["addr_id"] = int(addr_str)
                except ValueError:
                    messagebox.showerror("Error", "Address ID must be a number.")
                    return
            ok, msg = payments.update_card(self.card["card_number"], self.app.user["cust_id"], **fields)
            messagebox.showinfo("Result", msg)
        else:
            card_number = self.vars["card_number"].get().strip()
            name        = self.vars["name"].get().strip()
            sec_code    = self.vars["security_code"].get().strip()
            exp_date    = self.vars["exp_date"].get().strip()
            addr_str    = self.vars["addr_id"].get().strip()
            if not all([card_number, name, sec_code, exp_date, addr_str]):
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                addr_id = int(addr_str)
            except ValueError:
                messagebox.showerror("Error", "Address ID must be a number.")
                return
            ok, msg = payments.add_card(self.app.user["cust_id"], card_number, addr_id, name, sec_code, exp_date)
            messagebox.showinfo("Result", msg)
        self.parent_tab.refresh()
        self.destroy()


# ---- My Bookings ----

class BookingsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._bookings = []

        tk.Label(self, text="My Bookings", font=("Arial", 14, "bold")).pack(pady=10)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15)

        cols = ("ID", "Booked At", "Total", "Card", "Segments")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", height=12)
        for col in cols:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=300 if col == "Segments" else 90, anchor="center")
        self.tree.column("Segments", anchor="w")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Refresh",        command=self.refresh,        width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel Booking", command=self.cancel_booking, width=14).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Back",           command=lambda: app.show_frame(MainFrame), width=10).pack(side="left", padx=5)

    def on_show(self):
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        self._bookings = bookings.list_bookings(self.app.user["cust_id"])
        if not self._bookings:
            self.tree.insert("", "end", values=("—", "(no bookings)", "", "", ""))
            return
        for bk in self._bookings:
            segs = "  |  ".join(
                f"{s['airline_code']}{s['flight_num']} {s['origin_iata']}→{s['destination_iata']} {s['seat']} ({s['cabin']})"
                for s in bk["segments"]
            )
            self.tree.insert("", "end", values=(
                bk["book_id"],
                bk["booked_at"].strftime("%Y-%m-%d %H:%M"),
                fmt_price(bk["total_paid"]),
                f"****{bk['card_number'][-4:]}",
                segs,
            ))

    def cancel_booking(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showerror("Error", "Select a booking to cancel.")
            return
        book_id = self.tree.item(sel[0])["values"][0]
        if book_id == "—":
            return
        if not messagebox.askyesno("Confirm", f"Cancel booking #{book_id}? This cannot be undone."):
            return
        ok = bookings.cancel_booking(book_id, self.app.user["cust_id"])
        messagebox.showinfo("Result", "Booking cancelled." if ok else "Booking not found.")
        self.refresh()


if __name__ == "__main__":
    App().mainloop()
