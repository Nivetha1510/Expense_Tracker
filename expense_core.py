"""
Expense Tracker - Core Logic
--------------------------------
Date handling, CSV storage, CRUD operations on a list of expense
dicts, edit history, and dictionary-based reporting (category/monthly
totals). This module has no console/menu code - it is imported by the
Flask app instead of running as a script.

Author: Nivetha S
"""

import csv
import io
import os
import tempfile
from datetime import datetime
from decimal import Decimal, InvalidOperation
from collections import defaultdict

# Anchored to this file so data paths don't depend on the working directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "expenses.csv")
HISTORY_FILE = os.path.join(BASE_DIR, "edit_history.csv")
DATE_FORMAT = "%Y-%m-%d"

EXPENSE_FIELDS = ["expense_id", "amount", "category", "description", "date"]
HISTORY_FIELDS = ["edit_id", "expense_id", "timestamp", "field", "old_value", "new_value"]

DEFAULT_CATEGORIES = [
    "Food", "Transport", "Rent", "Utilities", "Entertainment",
    "Shopping", "Health", "Education", "Other"
]


class DataFileError(Exception):
    """A data file exists but cannot be read safely."""


# --------------------------------------------------------------------
# DATE HANDLING
# --------------------------------------------------------------------
def today_str():
    return datetime.now().strftime(DATE_FORMAT)


def is_valid_date(date_str):
    try:
        datetime.strptime(date_str, DATE_FORMAT)
        return True
    except ValueError:
        return False


def normalize_date(date_str):
    """Return the date as zero-padded YYYY-MM-DD, or raise ValueError."""
    return datetime.strptime(date_str.strip(), DATE_FORMAT).strftime(DATE_FORMAT)


def month_key(date_str):
    """Extract 'YYYY-MM' from a 'YYYY-MM-DD' string."""
    return date_str[:7]


def days_between(date_str1, date_str2):
    d1 = datetime.strptime(date_str1, DATE_FORMAT)
    d2 = datetime.strptime(date_str2, DATE_FORMAT)
    return abs((d2 - d1).days)


# --------------------------------------------------------------------
# MONEY HANDLING
# --------------------------------------------------------------------
CENT = Decimal("0.01")


def parse_amount(value):
    """
    Convert user input (str/int/float/Decimal) to a Decimal with exactly
    two decimal places. Raises ValueError with a user-facing message if
    the value is not a finite, positive amount with at most 2 decimals.
    """
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except InvalidOperation:
        raise ValueError("Amount must be a valid number.") from None

    if not amount.is_finite():
        raise ValueError("Amount must be a valid number.")
    if amount.as_tuple().exponent < -2:
        raise ValueError("Amount can have at most 2 decimal places.")
    if amount <= 0:
        raise ValueError("Amount must be greater than 0.")
    try:
        return amount.quantize(CENT)
    except InvalidOperation:
        raise ValueError("Amount is too large.") from None


def format_value(field, value):
    """Text form of a field value, as written to the edit history."""
    return f"{value:.2f}" if field == "amount" else str(value)


# --------------------------------------------------------------------
# FILE HANDLING (CSV)
# --------------------------------------------------------------------
def _read_csv(filepath, fieldnames):
    """
    Read rows (only the known columns) from a CSV. A missing file is an
    empty table. A file that exists but is unreadable raises
    DataFileError, so the caller never overwrites it with partial data.
    """
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", newline="") as f:
            reader = csv.DictReader(f)
            missing = [name for name in fieldnames if name not in (reader.fieldnames or [])]
            if missing:
                raise DataFileError(f"{filepath} is missing column(s): {', '.join(missing)}")
            return [{name: (row.get(name) or "") for name in fieldnames} for row in reader]
    except (OSError, csv.Error) as e:
        raise DataFileError(f"Could not read {filepath}: {e}") from e


def _write_csv(filepath, fieldnames, rows):
    """
    Write rows to a temp file and swap it in, so a failed write never
    truncates the existing data. Raises OSError on failure.
    """
    directory = os.path.dirname(os.path.abspath(filepath))
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        os.replace(tmp_path, filepath)
    except BaseException:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def load_expenses(filepath=None):
    """Load all expenses from CSV into a list of dicts (amount is a Decimal)."""
    filepath = filepath or DATA_FILE
    expenses = _read_csv(filepath, EXPENSE_FIELDS)
    for number, row in enumerate(expenses, start=2):
        try:
            amount = Decimal(row["amount"])
        except InvalidOperation:
            amount = None
        if amount is None or not amount.is_finite():
            raise DataFileError(f"{filepath}, line {number}: invalid amount '{row['amount']}'")
        row["amount"] = amount
    return expenses


def save_expenses(expenses, filepath=None):
    """Save the full list of expense dicts to CSV. Raises OSError on failure."""
    _write_csv(filepath or DATA_FILE, EXPENSE_FIELDS, expenses)


def load_history(filepath=None):
    """Load the edit history: one row per changed field."""
    return _read_csv(filepath or HISTORY_FILE, HISTORY_FIELDS)


def save_history(history, filepath=None):
    """Save the edit history to CSV. Raises OSError on failure."""
    _write_csv(filepath or HISTORY_FILE, HISTORY_FIELDS, history)


# --------------------------------------------------------------------
# CORE FUNCTIONS (CRUD-style operations on the list of dicts)
# --------------------------------------------------------------------
def generate_id(expenses):
    if not expenses:
        return "1"
    existing_ids = [int(e["expense_id"]) for e in expenses if e["expense_id"].isdigit()]
    return str(max(existing_ids, default=0) + 1)


def add_expense(expenses, amount, category, description, date=None):
    """
    Validates and appends a new expense dict to the list.
    Returns (success: bool, message: str) for invalid input.
    Raises OSError if the expense could not be saved (the in-memory
    list is left unchanged in that case).
    """
    try:
        amount = parse_amount(amount)
    except ValueError as e:
        return False, str(e)

    if date:
        try:
            date = normalize_date(date)
        except ValueError:
            return False, f"Invalid date: '{date}'. Use format YYYY-MM-DD."
    else:
        date = today_str()

    expense = {
        "expense_id": generate_id(expenses),
        "amount": amount,
        "category": category.strip().title() if category.strip() else "Other",
        "description": description.strip(),
        "date": date,
    }
    expenses.append(expense)
    try:
        save_expenses(expenses)
    except OSError:
        expenses.remove(expense)
        raise
    return True, f"Expense added with ID {expense['expense_id']}."


def find_expense(expenses, expense_id):
    for expense in expenses:
        if expense["expense_id"] == expense_id:
            return expense
    return None


def update_expense(expenses, history, expense_id,
                   amount=None, category=None, description=None, date=None):
    """
    Edit an expense. A field left as None is not submitted and stays as
    it is; any other value replaces the current one (an empty description
    clears it, an empty category becomes 'Other').

    Every submitted field is validated before anything changes, so a
    rejected edit leaves the expense exactly as it was. For a successful
    edit, one history row per changed field is added to `history` and
    both files are saved. Returns (success, message); raises OSError if
    saving fails, after restoring the previous in-memory state.
    """
    expense = find_expense(expenses, expense_id)
    if expense is None:
        return False, f"Expense ID '{expense_id}' not found."

    submitted = {}
    if amount is not None:
        try:
            submitted["amount"] = parse_amount(amount)
        except ValueError as e:
            return False, str(e)
    if category is not None:
        submitted["category"] = category.strip().title() or "Other"
    if description is not None:
        submitted["description"] = description.strip()
    if date is not None:
        try:
            submitted["date"] = normalize_date(date)
        except ValueError:
            return False, f"Invalid date: '{date}'. Use format YYYY-MM-DD."

    changes = {f: v for f, v in submitted.items() if expense[f] != v}
    if not changes:
        return True, "No changes to save."

    timestamp = datetime.now().isoformat(timespec="seconds")
    edit_id = str(max((int(h["edit_id"]) for h in history if h["edit_id"].isdigit()), default=0) + 1)
    new_rows = [
        {
            "edit_id": edit_id,
            "expense_id": expense_id,
            "timestamp": timestamp,
            "field": field,
            "old_value": format_value(field, expense[field]),
            "new_value": format_value(field, value),
        }
        for field, value in changes.items()
    ]

    original = expense.copy()
    expense.update(changes)
    history.extend(new_rows)

    def revert():
        expense.clear()
        expense.update(original)
        del history[-len(new_rows):]

    try:
        save_expenses(expenses)
    except OSError:
        revert()
        raise
    try:
        save_history(history)
    except OSError:
        revert()
        try:
            save_expenses(expenses)  # put the previous expenses file back
        except OSError:
            pass
        raise
    return True, "Expense updated successfully."


def edits_for(history, expense_id):
    """
    Group history rows into edits for one expense, newest first:
    [{"edit_id", "timestamp", "changes": [{"field", "old", "new"}]}]
    """
    edits = {}
    for row in history:
        if row["expense_id"] != expense_id:
            continue
        edit = edits.setdefault(row["edit_id"], {
            "edit_id": row["edit_id"], "timestamp": row["timestamp"], "changes": [],
        })
        edit["changes"].append({"field": row["field"], "old": row["old_value"], "new": row["new_value"]})
    return sorted(edits.values(), key=lambda e: int(e["edit_id"]) if e["edit_id"].isdigit() else 0, reverse=True)


def history_csv_text(history):
    """
    The whole edit history as CSV text, for download. Text that a
    spreadsheet could run as a formula (starts with = + - @) is prefixed
    with an apostrophe so it opens as plain text.
    """
    def safe(value):
        return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value

    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=HISTORY_FIELDS)
    writer.writeheader()
    for row in history:
        writer.writerow({name: safe(row[name]) for name in HISTORY_FIELDS})
    return out.getvalue()


def edited_ids(history):
    """Set of expense IDs that have at least one recorded edit."""
    return {row["expense_id"] for row in history}


def delete_expense(expenses, expense_id):
    """
    Raises OSError if saving fails (the expense is restored in that case).
    Edit history is kept, so an audit trail survives deletion.
    """
    expense = find_expense(expenses, expense_id)
    if expense is None:
        return False, f"Expense ID '{expense_id}' not found."
    index = expenses.index(expense)
    expenses.remove(expense)
    try:
        save_expenses(expenses)
    except OSError:
        expenses.insert(index, expense)
        raise
    return True, f"Expense '{expense_id}' deleted."


def list_expenses(expenses):
    return sorted(expenses, key=lambda e: e["date"])


# --------------------------------------------------------------------
# REPORTING FUNCTIONS (dictionary-based aggregation)
# --------------------------------------------------------------------
def category_totals(expenses):
    """Returns {category: total_amount}, sorted highest spend first."""
    totals = defaultdict(Decimal)
    for expense in expenses:
        totals[expense["category"]] += expense["amount"]
    return dict(sorted(totals.items(), key=lambda x: -x[1]))


def monthly_totals(expenses):
    """Returns {'YYYY-MM': total_amount}, sorted chronologically."""
    totals = defaultdict(Decimal)
    for expense in expenses:
        totals[month_key(expense["date"])] += expense["amount"]
    return dict(sorted(totals.items()))


def total_spent(expenses):
    return sum((e["amount"] for e in expenses), Decimal("0.00"))


def filter_by_category(expenses, category):
    return [e for e in expenses if e["category"].lower() == category.lower()]


def filter_by_month(expenses, month):
    """month in 'YYYY-MM' format."""
    return [e for e in expenses if e["date"].startswith(month)]


def filter_by_date_range(expenses, start_date, end_date):
    """Both dates in 'YYYY-MM-DD' format, inclusive."""
    if not (is_valid_date(start_date) and is_valid_date(end_date)):
        return []
    return [e for e in expenses if start_date <= e["date"] <= end_date]
