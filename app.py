"""
Expense Tracker - Flask Web App
------------------------------------
Replaces the console menu with routes: the dashboard supports
filtering by category, month, or date range via query parameters;
add/edit/delete and the category/monthly summary each render an
HTML template instead of printing to a terminal.

Run with:
    python app.py
Then open http://127.0.0.1:5000
"""

import hmac
import os
import secrets

from flask import Flask, Response, render_template, request, redirect, url_for, flash, session, abort
import expense_core as core

app = Flask(__name__)
# Set SECRET_KEY in the environment for sessions that survive restarts.
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)

# In-memory data, backed by expenses.csv and edit_history.csv.
# If either file exists but is unreadable, this raises DataFileError and
# the app refuses to start, so existing data is never overwritten.
expenses = core.load_expenses()
history = core.load_history()


# --------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------
def csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(16)
    return session["_csrf_token"]


app.jinja_env.globals["csrf_token"] = csrf_token
app.jinja_env.filters["money"] = lambda value: f"{value:.2f}"


@app.before_request
def protect_from_csrf():
    if request.method == "POST":
        expected = session.get("_csrf_token", "")
        sent = request.form.get("csrf_token", "")
        if not expected or not hmac.compare_digest(sent, expected):
            abort(400, "Invalid or missing CSRF token. Reload the page and try again.")


def save_failed(error):
    flash(f"Could not save your changes to disk: {error}", "error")


@app.route("/")
def index():
    """Dashboard: full list, or a filtered view based on query params."""
    category = request.args.get("category", "").strip()
    month = request.args.get("month", "").strip()
    start = request.args.get("start", "").strip()
    end = request.args.get("end", "").strip()

    if category:
        results = core.filter_by_category(expenses, category)
    elif month:
        results = core.filter_by_month(expenses, month)
    elif start and end:
        if not (core.is_valid_date(start) and core.is_valid_date(end)):
            flash("Both dates must be valid, in YYYY-MM-DD format.", "error")
            results = core.list_expenses(expenses)
            start = end = ""
        elif start > end:
            flash("The end date must not be before the start date.", "error")
            results = core.list_expenses(expenses)
            start = end = ""
        else:
            results = sorted(core.filter_by_date_range(expenses, start, end), key=lambda e: e["date"])
    else:
        results = core.list_expenses(expenses)

    return render_template(
        "index.html",
        expenses=results,
        category=category, month=month, start=start, end=end,
        categories=core.DEFAULT_CATEGORIES,
        total=core.total_spent(results),
        edited=core.edited_ids(history),
    )


@app.route("/add", methods=["POST"])
def add():
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    date = request.form.get("date", "").strip()

    try:
        success, message = core.add_expense(expenses, amount_raw, category, description, date or None)
    except OSError as e:
        save_failed(e)
    else:
        flash(message, "success" if success else "error")
    return redirect(url_for("index"))


@app.route("/edit/<expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    existing = core.find_expense(expenses, expense_id)
    if existing is None:
        flash(f"Expense ID '{expense_id}' not found.", "error")
        return redirect(url_for("index"))

    values = {}
    if request.method == "POST":
        # Only fields present in the form are submitted; an empty
        # description is a deliberate "clear", not "leave unchanged".
        values = {f: request.form[f] for f in ("amount", "category", "description", "date") if f in request.form}
        try:
            success, message = core.update_expense(expenses, history, expense_id, **values)
        except OSError as e:
            save_failed(e)
        else:
            flash(message, "success" if success else "error")
            if success:
                return redirect(url_for("index"))

    return render_template("edit.html", expense=existing, values=values, categories=core.DEFAULT_CATEGORIES)


@app.route("/download/history")
def download_history():
    """Download the full edit history (all expenses) as a CSV file."""
    return Response(
        core.history_csv_text(history),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=edit_history.csv"},
    )


@app.route("/history/<expense_id>")
def edit_history(expense_id):
    edits = core.edits_for(history, expense_id)
    expense = core.find_expense(expenses, expense_id)
    if expense is None and not edits:
        flash(f"Expense ID '{expense_id}' not found.", "error")
        return redirect(url_for("index"))
    return render_template("history.html", expense_id=expense_id, expense=expense, edits=edits)


@app.route("/delete/<expense_id>", methods=["POST"])
def delete(expense_id):
    try:
        success, message = core.delete_expense(expenses, expense_id)
    except OSError as e:
        save_failed(e)
    else:
        flash(message, "success" if success else "error")
    return redirect(url_for("index"))


@app.route("/summary")
def summary():
    return render_template(
        "summary.html",
        category_totals=core.category_totals(expenses),
        monthly_totals=core.monthly_totals(expenses),
        total=core.total_spent(expenses),
    )


if __name__ == "__main__":
    app.run(debug=True)
