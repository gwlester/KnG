#!/usr/bin/env python3
"""License management desktop: a local tool for looking at
kng-license-issuance (every purchase and Test Drive record) and for
maintaining kng-beta-testers (the Test Drive approval allowlist)
without going to the AWS console. Runs with your own AWS credentials
(same default credential chain the `aws` CLI uses). The Sales tab is
read-only; the Beta Testers tab can add/remove approved emails.

Usage: python3 app.py [--table NAME] [--beta-testers-table NAME]
                       [--region REGION] [--profile NAME]
"""
from __future__ import annotations

import argparse
import logging
import tkinter as tk
from datetime import datetime, timezone
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from sales_browser import (
    DEFAULT_BETA_TESTERS_TABLE,
    DEFAULT_REGION,
    DEFAULT_TABLE,
    filter_rows,
    normalize_email,
    parse_date_bound,
    product_label,
    simplify_beta_tester_item,
    simplify_item,
)

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR"]
LOG_DIR = Path.home() / ".kng-license-management" / "logs"
LOG_FILE = LOG_DIR / "license_management.log"


def _configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("kng_license_management")
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = _configure_logging()

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

BETA_TESTER_COLUMNS = ("email", "added_at")
BETA_TESTER_COLUMN_LABELS = {"email": "Email", "added_at": "Added"}


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


def fetch_all_beta_testers(dynamodb_client, table_name: str) -> list[dict]:
    rows = []
    kwargs = {"TableName": table_name}
    while True:
        response = dynamodb_client.scan(**kwargs)
        rows.extend(simplify_beta_tester_item(item) for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return sorted(rows, key=lambda row: row["email"])
        kwargs["ExclusiveStartKey"] = last_key


class SalesBrowserApp:
    def __init__(
        self, root: tk.Tk, table_name: str, beta_testers_table: str, region: str, profile: str | None
    ):
        self.root = root
        self.table_name = table_name
        self.beta_testers_table = beta_testers_table
        self.region = region
        self.profile = profile
        self._client = None
        self._rows: list[dict] = []
        self._beta_testers: list[dict] = []

        root.title(f"KnG License Management -- {region}")
        root.geometry("1100x550")

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        sales_tab = ttk.Frame(self.notebook)
        beta_tab = ttk.Frame(self.notebook)
        self.notebook.add(sales_tab, text="Sales & Test Drives")
        self.notebook.add(beta_tab, text="Beta Testers")

        self._build_sales_tab(sales_tab)
        self._build_beta_testers_tab(beta_tab)
        self._build_menu()
        logger.info("Application started.")

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        self.root.config(menu=menu_bar)

        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Refresh", command=self._refresh_active_tab, accelerator="Ctrl+R")
        file_menu.add_separator()

        log_level_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Set Log Level", menu=log_level_menu)
        self.log_level_var = tk.StringVar(value=logging.getLevelName(logger.level))
        for level in LOG_LEVELS:
            log_level_menu.add_radiobutton(
                label=level, value=level, variable=self.log_level_var,
                command=lambda lvl=level: self._set_log_level(lvl),
            )

        file_menu.add_command(label="View Logs...", command=self._view_logs)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)

        self.root.bind_all("<Control-r>", lambda event: self._refresh_active_tab())

    def _refresh_active_tab(self) -> None:
        if self.notebook.index(self.notebook.select()) == 0:
            self.refresh()
        else:
            self.refresh_beta_testers()

    def _set_log_level(self, level: str) -> None:
        logger.setLevel(getattr(logging, level))
        logger.info("Log level set to %s.", level)

    def _view_logs(self) -> None:
        window = tk.Toplevel(self.root)
        window.title(f"Logs -- {LOG_FILE}")
        window.geometry("700x400")
        text = tk.Text(window, wrap="word")
        scrollbar = ttk.Scrollbar(window, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        try:
            content = LOG_FILE.read_text(encoding="utf-8")
        except FileNotFoundError:
            content = "(no log entries yet)"
        text.insert("1.0", content)
        text.see("end")
        text.configure(state="disabled")

    def _build_sales_tab(self, parent: tk.Widget) -> None:
        filters = ttk.Frame(parent, padding=8)
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

        tree_frame = ttk.Frame(parent)
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
        ttk.Label(parent, textvariable=self.status_var, padding=(8, 4)).pack(side=tk.BOTTOM, fill=tk.X, anchor="w")

    def _build_beta_testers_tab(self, parent: tk.Widget) -> None:
        actions = ttk.Frame(parent, padding=8)
        actions.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(actions, text="Refresh", command=self.refresh_beta_testers).pack(side=tk.LEFT)
        ttk.Button(actions, text="Add...", command=self.add_beta_tester).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(actions, text="Remove selected", command=self.remove_selected_beta_tester).pack(
            side=tk.LEFT, padx=(8, 0)
        )

        tree_frame = ttk.Frame(parent)
        tree_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.beta_tree = ttk.Treeview(tree_frame, columns=BETA_TESTER_COLUMNS, show="headings")
        for col in BETA_TESTER_COLUMNS:
            self.beta_tree.heading(col, text=BETA_TESTER_COLUMN_LABELS[col])
            self.beta_tree.column(col, width=260 if col == "email" else 200, anchor="w")
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.beta_tree.yview)
        self.beta_tree.configure(yscrollcommand=scrollbar.set)
        self.beta_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.beta_status_var = tk.StringVar(value="Click Refresh to load the approved beta tester list.")
        ttk.Label(parent, textvariable=self.beta_status_var, padding=(8, 4)).pack(
            side=tk.BOTTOM, fill=tk.X, anchor="w"
        )

    def _dynamodb_client(self):
        if self._client is None:
            try:
                import boto3  # imported lazily so sales_browser.py's pure logic needs no boto3 to test
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "boto3 is not installed in this Python environment. Run "
                    "'pip install -r requirements.txt' here (inside a virtual environment first "
                    "if your system Python refuses direct installs -- see tools/sales_browser/README.md)."
                ) from exc
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
            logger.exception("Could not load records from %s.", self.table_name)
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
        logger.info("Refreshed sales/Test Drive records: %d of %d shown.", len(rows), len(self._rows))

    def refresh_beta_testers(self):
        self.beta_status_var.set("Loading...")
        self.root.update_idletasks()
        try:
            self._beta_testers = fetch_all_beta_testers(self._dynamodb_client(), self.beta_testers_table)
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not raised
            logger.exception("Could not load the beta tester list from %s.", self.beta_testers_table)
            self.beta_status_var.set(f"Could not load the beta tester list: {exc}")
            messagebox.showerror("Could not load the beta tester list", str(exc))
            return

        self.beta_tree.delete(*self.beta_tree.get_children())
        for row in self._beta_testers:
            self.beta_tree.insert("", tk.END, values=(row["email"], row["added_at"] or ""))
        self.beta_status_var.set(f"{len(self._beta_testers)} approved beta tester(s).")
        logger.info("Refreshed beta tester list: %d approved.", len(self._beta_testers))

    def add_beta_tester(self):
        raw = simpledialog.askstring("Add beta tester", "Email address to approve:", parent=self.root)
        if raw is None:
            return
        email = normalize_email(raw)
        if "@" not in email:
            messagebox.showerror("Invalid email", f"{raw!r} doesn't look like an email address.")
            return
        try:
            self._dynamodb_client().put_item(
                TableName=self.beta_testers_table,
                Item={
                    "email": {"S": email},
                    "added_at": {"S": datetime.now(timezone.utc).isoformat()},
                },
            )
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not raised
            logger.exception("Could not add beta tester %s.", email)
            messagebox.showerror("Could not add beta tester", str(exc))
            return
        logger.info("Added beta tester %s.", email)
        self.refresh_beta_testers()

    def remove_selected_beta_tester(self):
        selected = self.beta_tree.selection()
        if not selected:
            messagebox.showinfo("No selection", "Select a row to remove first.")
            return
        email = self.beta_tree.item(selected[0], "values")[0]
        if not messagebox.askyesno("Remove beta tester", f"Remove {email} from the approved list?"):
            return
        try:
            self._dynamodb_client().delete_item(TableName=self.beta_testers_table, Key={"email": {"S": email}})
        except Exception as exc:  # noqa: BLE001 -- surfaced to the user, not raised
            logger.exception("Could not remove beta tester %s.", email)
            messagebox.showerror("Could not remove beta tester", str(exc))
            return
        logger.info("Removed beta tester %s.", email)
        self.refresh_beta_testers()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--beta-testers-table", default=DEFAULT_BETA_TESTERS_TABLE)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()

    root = tk.Tk()
    SalesBrowserApp(root, args.table, args.beta_testers_table, args.region, args.profile)
    root.mainloop()


if __name__ == "__main__":
    main()
