"""
Expense Tracker - Core Logic
--------------------------------
Date handling, CSV storage, CRUD operations on a list of expense
dicts, and dictionary-based reporting (category/monthly totals).
This module has no console/menu code - it is imported by the Flask
app instead of running as a script.

Author: Nivetha S
"""

import csv
import os
from datetime import datetime
from collections import defaultdict

DATA_FILE = "expenses.csv"
DATE_FORMAT = "%Y-%m-%d"

DEFAULT_CATEGORIES = [
    "Food", "Transport", "Rent", "Utilities", "Entertainment",
    "Shopping", "Health", "Education", "Other"
]


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


def month_key(date_str):
    """Extract 'YYYY-MM' from a 'YYYY-MM-DD' string."""
    return date_str[:7]


def days_between(date_str1, date_str2):
    d1 = datetime.strptime(date_str1, DATE_FORMAT)
    d2 = datetime.strptime(date_str2, DATE_FORMAT)
    return abs((d2 - d1).days)


# --------------------------------------------------------------------
# FILE HANDLING (CSV)
# --------------------------------------------------------------------
def load_expenses(filepath=DATA_FILE):
    """Load all expenses from CSV into a list of dicts."""
    expenses = []
    if not os.path.exists(filepath):
        return expenses
    try:
        with open(filepath, "r", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["amount"] = float(row["amount"])
                expenses.append(row)
    except (IOError, csv.Error, ValueError) as e:
        print(f"Warning: could not read data file ({e}). Starting fresh.")
    return expenses


def save_expenses(expenses, filepath=DATA_FILE):
    """Save the full list of expense dicts back to CSV."""
    try:
        with open(filepath, "w", newline="") as f:
            fieldnames = ["expense_id", "amount", "category", "description", "date"]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for expense in expenses:
                writer.writerow(expense)
    except IOError as e:
        print(f"Error saving data: {e}")


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
    Returns (success: bool, message: str).
    """
    if amount <= 0:
        return False, f"Invalid amount: {amount}. Amount must be greater than 0."

    if date:
        if not is_valid_date(date):
            return False, f"Invalid date: '{date}'. Use format YYYY-MM-DD."
    else:
        date = today_str()

    expense = {
        "expense_id": generate_id(expenses),
        "amount": round(float(amount), 2),
        "category": category.strip().title() if category.strip() else "Other",
        "description": description.strip(),
        "date": date,
    }
    expenses.append(expense)
    save_expenses(expenses)
    return True, f"Expense added with ID {expense['expense_id']}."


def find_expense(expenses, expense_id):
    for expense in expenses:
        if expense["expense_id"] == expense_id:
            return expense
    return None


def update_expense(expenses, expense_id, amount=None, category=None, description=None, date=None):
    expense = find_expense(expenses, expense_id)
    if expense is None:
        return False, f"Expense ID '{expense_id}' not found."

    if amount is not None:
        if amount <= 0:
            return False, f"Invalid amount: {amount}. Amount must be greater than 0."
        expense["amount"] = round(float(amount), 2)

    if category is not None and category.strip():
        expense["category"] = category.strip().title()

    if description is not None and description.strip():
        expense["description"] = description.strip()

    if date is not None and date.strip():
        if not is_valid_date(date):
            return False, f"Invalid date: '{date}'. Use format YYYY-MM-DD."
        expense["date"] = date

    save_expenses(expenses)
    return True, "Expense updated successfully."


def delete_expense(expenses, expense_id):
    expense = find_expense(expenses, expense_id)
    if expense is None:
        return False, f"Expense ID '{expense_id}' not found."
    expenses.remove(expense)
    save_expenses(expenses)
    return True, f"Expense '{expense_id}' deleted."


def list_expenses(expenses):
    return sorted(expenses, key=lambda e: e["date"])


# --------------------------------------------------------------------
# REPORTING FUNCTIONS (dictionary-based aggregation)
# --------------------------------------------------------------------
def category_totals(expenses):
    """Returns {category: total_amount}, sorted highest spend first."""
    totals = defaultdict(float)
    for expense in expenses:
        totals[expense["category"]] += expense["amount"]
    return dict(sorted(totals.items(), key=lambda x: -x[1]))


def monthly_totals(expenses):
    """Returns {'YYYY-MM': total_amount}, sorted chronologically."""
    totals = defaultdict(float)
    for expense in expenses:
        totals[month_key(expense["date"])] += expense["amount"]
    return dict(sorted(totals.items()))


def total_spent(expenses):
    return round(sum(e["amount"] for e in expenses), 2)


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
