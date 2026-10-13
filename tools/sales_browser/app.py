#!/usr/bin/env python3
"""Sales/Test Drive browser: a local desktop tool for looking at
kng-license-issuance (every purchase and Test Drive record) without
going to the AWS console. Runs with your own AWS credentials (same
default credential chain the `aws` CLI uses) -- nothing here is
deployed, and it never writes to the table.

Usage: python3 app.py [--table NAME] [--region REGION] [--profile NAME]
"""
from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import messagebox, ttk

from sales_browser import DEFAULT_REGION, DEFAULT_TABLE, filter_rows, parse_date_bound, product_label, simplify_item

COLUMNS = ("reference", "source", "email", "products", "short_key", "created_at", "valid_to")
COLUMN_LABELS = {
    "reference": "Reference",
    "source": "Source",
    "email": "Email",
    "products": "Products",
    "short_key": "Activation key",
    "created_at": "Created",
    "valid_to": "Valid until",
}


def fetch_all_rows(dynamodb_client, table_name: str) -> list[dict]:
    """Scans the whole table (paginated) and simplifies every item. Small
    scale expected (a new, pre-1.0 product's sales) -- a full scan is
    simpler and cheap enough that a date-range/email-pattern/product
    index isn't worth building yet.
    """
    rows = []
    kwargs = {"TableName": table_name}
    while True:
        response = dynamodb_client.scan(**kwargs)
        rows.extend(simplify_item(item) for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return rows
        kwargs["ExclusiveStartKey"] = last_key


class SalesBrowserApp:
    def __init__(self, root: tk.Tk, table_name: str, region: str, profile: str | None):
        self.root = root
        self.table_name = table_name
        self.region = region
        self.profile = profile
        self._client = None
        self._rows: list[dict] = []

        root.title(f"KnG Sales Browser -- {table_name} ({region})")
        root.geometry("1100x500")

        filters = ttk.Frame(root, padding=8)
        filters.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(filters, text="From (YYYY-MM-DD)").grid(row=0, column=0, sticky="w")
        self.date_from_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.date_from_var, width=12).grid(row=1, column=0, padx=(0, 10))

        ttk.Label(filters, text="To (YYYY-MM-DD)").grid(row=0, column=1, sticky="w")
        self.date_to_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.date_to_var, width=12).grid(row=1, column=1, padx=(0, 10))

        ttk.Label(filters, text="Email contains").grid(row=0, column=2, sticky="w")
        self.email_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.email_var, width=28).grid(row=1, column=2, padx=(0, 10))

        ttk.Label(filters, text="Product").grid(row=0, column=3, sticky="w")
        self.product_var = tk.StringVar(value="All")
        ttk.Combobox(
            filters, textvariable=self.product_var, values=["All", "Server", "MIDI Player"],
            state="readonly", width=12,
        ).grid(row=1, column=3, padx=(0, 10))

        ttk.Button(filters, text="Refresh", command=self.refresh).grid(row=1, column=4, padx=(10, 0))

        tree_frame = ttk.Frame(root)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.tree = ttk.Treeview(tree_frame, columns=COLUMNS, show="headings")
        for col in COLUMNS:
            self.tree.heading(col, text=COLUMN_LABELS[col])
            self.tree.column(col, width=140, anchor="w")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.status_var = tk.StringVar(value="Click Refresh to load records.")
        ttk.Label(root, textvariable=self.status_var, padding=(8, 4)).pack(side=tk.BOTTOM, fill=tk.X, anchor="w")

    def _dynamodb_client(self):
        if self._client is None:
            import boto3  # imported lazily so sales_browser.py's pure logic needs no boto3 to test

            session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
            self._client = session.client("dynamodb", region_name=self.region)
        return self._client

    def refresh(self):
        try:
            date_from = parse_date_bound(self.date_from_var.get())
            date_to = parse_date_bound(self.date_to_var.get())
        except ValueError:
            messagebox.showerror("Invalid date", "Dates must be in YYYY-MM-DD form.")
            return

        self.status_var.set("Loading...")
        self.root.update_idletasks()
        try:
            self._rows = fetch_all_rows(self._dynamodb_client(), self.table_name)
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not raised
            self.status_var.set(f"Could not load records: {exc}")
            messagebox.showerror("Could not load records", str(exc))
            return

        product = {"All": "all", "Server": "server", "MIDI Player": "midi-player"}[self.product_var.get()]
        rows = filter_rows(
            self._rows, date_from=date_from, date_to=date_to, email_pattern=self.email_var.get(), product=product
        )

        self.tree.delete(*self.tree.get_children())
        for row in rows:
            if row["valid_to"]:
                valid_to = row["valid_to"]
            elif row["source"] == "purchase":
                valid_to = "(never expires)"
            else:
                valid_to = ""
            self.tree.insert("", tk.END, values=(
                row["reference"],
                row["source"],
                row["email"],
                ", ".join(product_label(k) for k in row["kinds"]),
                row["short_key"] or "",
                row["created_at"] or "",
                valid_to,
            ))
        self.status_var.set(f"{len(rows)} of {len(self._rows)} total record(s).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    root = tk.Tk()
    SalesBrowserApp(root, args.table, args.region, args.profile)
    root.mainloop()


if __name__ == "__main__":
    main()
