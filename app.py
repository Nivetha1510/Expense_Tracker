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

from flask import Flask, render_template, request, redirect, url_for, flash
import expense_core as core

app = Flask(__name__)
app.secret_key = "replace-this-with-a-random-secret-key"

# In-memory list of expense dicts, backed by expenses.csv
expenses = core.load_expenses()


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
    )


@app.route("/add", methods=["POST"])
def add():
    amount_raw = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    date = request.form.get("date", "").strip()

    try:
        amount = float(amount_raw)
    except ValueError:
        flash("Amount must be a valid number.", "error")
        return redirect(url_for("index"))

    success, message = core.add_expense(expenses, amount, category, description, date or None)
    flash(message, "success" if success else "error")
    return redirect(url_for("index"))


@app.route("/edit/<expense_id>", methods=["GET", "POST"])
def edit(expense_id):
    existing = core.find_expense(expenses, expense_id)
    if existing is None:
        flash(f"Expense ID '{expense_id}' not found.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        amount_raw = request.form.get("amount", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        date = request.form.get("date", "").strip()

        amount = None
        if amount_raw:
            try:
                amount = float(amount_raw)
            except ValueError:
                flash("Invalid amount entered.", "error")
                return render_template("edit.html", expense=existing, categories=core.DEFAULT_CATEGORIES)

        success, message = core.update_expense(
            expenses, expense_id, amount=amount,
            category=category or None, description=description or None, date=date or None
        )
        flash(message, "success" if success else "error")
        if success:
            return redirect(url_for("index"))

    return render_template("edit.html", expense=existing, categories=core.DEFAULT_CATEGORIES)


@app.route("/delete/<expense_id>", methods=["POST"])
def delete(expense_id):
    success, message = core.delete_expense(expenses, expense_id)
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
